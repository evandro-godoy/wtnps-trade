from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

import pandas as pd
from fastapi import WebSocket
from pydantic import ValidationError

from newapp.src.database.db import get_session_factory
from newapp.src.database.repository import AssetsRatesRepository
from newapp.src.live.monitor_engine import RealtimeMarketMonitor
from newapp.src.schemas.monitor_payload import MonitorPayload
from newapp.src.services.monitor_registry import MonitorRegistry

logger = logging.getLogger(__name__)


FREQUENCY_TICK = "tick"
FREQUENCY_CLOSE = "close"
FREQUENCY_HYBRID = "hybrid"
VALID_FREQUENCY_MODES = {
    FREQUENCY_TICK,
    FREQUENCY_CLOSE,
    FREQUENCY_HYBRID,
}


@dataclass(slots=True)
class WebSocketClientState:
    """Store per-client websocket delivery preferences and counters."""

    mode: str = FREQUENCY_TICK
    last_sent_monotonic: float = 0.0
    sent_count_window: int = 0
    dropped_count_window: int = 0
    window_started_monotonic: float = field(default_factory=time.monotonic)


class MonitorRuntime:
    """Manage monitor instances, async tasks and websocket connections."""

    hybrid_heartbeat_seconds: float = 2.0
    frequency_log_window_seconds: float = 30.0

    def __init__(self) -> None:
        self._registry = MonitorRegistry()
        self._monitors: dict[str, RealtimeMarketMonitor] = {}
        self._monitor_tasks: dict[str, asyncio.Task[Any]] = {}
        self._ws_connections: list[WebSocket] = []
        self._ws_client_state: dict[WebSocket, WebSocketClientState] = {}
        self._callbacks_registered: set[str] = set()

        self._persist_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._persist_worker_task: asyncio.Task[Any] | None = None
        self._persist_worker_running = False

    @staticmethod
    def build_key(ticker: str, timeframe: str) -> str:
        """Build monitor dictionary key."""
        return f"{ticker.upper()}_{timeframe.upper()}"

    async def start_default_monitors(self) -> list[dict[str, Any]]:
        """Start canonical always-on monitors during FastAPI lifespan."""
        defaults: Iterable[tuple[str, str]] = (("WDO$", "M5"), ("WIN$", "M5"))
        results: list[dict[str, Any]] = []

        await self._ensure_persist_worker()

        for ticker, timeframe in defaults:
            result = await self.start_monitor(ticker=ticker, timeframe=timeframe)
            results.append(result)

        return results

    async def _get_or_create_monitor(
        self,
        ticker: str,
        timeframe: str,
    ) -> RealtimeMarketMonitor:
        """Get monitor singleton from registry and keep runtime references."""
        monitor = await self._registry.get_or_create(
            ticker=ticker,
            timeframe=timeframe,
            buffer_size=500,
            enable_db_persistence=False,
        )
        key = self.build_key(ticker, timeframe)
        self._monitors[key] = monitor
        return monitor

    async def register_websocket(
        self,
        websocket: WebSocket,
        mode: str = FREQUENCY_TICK,
    ) -> str:
        """Register active websocket client and return normalized mode."""
        await websocket.accept()
        self._ws_connections.append(websocket)
        normalized_mode = self._normalize_frequency_mode(mode)
        self._ws_client_state[websocket] = WebSocketClientState(mode=normalized_mode)
        logger.info("WebSocket connected. total=%s", len(self._ws_connections))
        return normalized_mode

    @staticmethod
    def _normalize_frequency_mode(mode: str | None) -> str:
        """Normalize client frequency mode to supported values."""
        candidate = str(mode or FREQUENCY_TICK).strip().lower()
        if candidate in VALID_FREQUENCY_MODES:
            return candidate
        logger.warning("Invalid frequency mode '%s'. Falling back to tick.", mode)
        return FREQUENCY_TICK

    def set_websocket_frequency(self, websocket: WebSocket, mode: str | None) -> str:
        """Set frequency mode for one websocket client and return active mode."""
        if websocket not in self._ws_connections:
            raise ValueError("WebSocket not registered")

        normalized_mode = self._normalize_frequency_mode(mode)
        state = self._ws_client_state.setdefault(websocket, WebSocketClientState())
        state.mode = normalized_mode
        logger.info(
            "WebSocket frequency updated. mode=%s total=%s",
            normalized_mode,
            len(self._ws_connections),
        )
        return normalized_mode

    def get_websocket_frequency(self, websocket: WebSocket) -> str:
        """Get configured frequency mode for one websocket client."""
        state = self._ws_client_state.get(websocket)
        return state.mode if state else FREQUENCY_TICK

    def unregister_websocket(self, websocket: WebSocket) -> None:
        """Unregister websocket client."""
        if websocket in self._ws_connections:
            self._ws_connections.remove(websocket)
            self._ws_client_state.pop(websocket, None)
            logger.info("WebSocket removed. total=%s", len(self._ws_connections))

    def _validate_payload(self, data: dict[str, Any]) -> MonitorPayload | None:
        """Validate strict websocket payload contract."""
        clean_payload = {
            "schema_version": data.get("schema_version"),
            "timestamp": data.get("timestamp"),
            "ticker": data.get("ticker"),
            "timeframe": data.get("timeframe"),
            "ohlcv": data.get("ohlcv", {}),
            "indicators": data.get("indicators", {}),
            "analysis": data.get("analysis", {}),
            "ml": data.get("ml", {}),
            "decision": data.get("decision", {}),
        }
        try:
            return MonitorPayload.from_runtime_payload(clean_payload)
        except ValidationError as exc:
            logger.error(
                "monitor_payload_validation_failed source=monitor_runtime "
                "ticker=%s timeframe=%s error=%s",
                clean_payload.get("ticker"),
                clean_payload.get("timeframe"),
                exc,
            )
            return None

    def _should_send_for_mode(
        self,
        state: WebSocketClientState,
        is_closed: bool,
        now_monotonic: float,
    ) -> bool:
        """Decide if payload should be delivered to a websocket client."""
        if state.mode == FREQUENCY_TICK:
            return True
        if state.mode == FREQUENCY_CLOSE:
            return is_closed
        if is_closed:
            return True
        return (
            now_monotonic - state.last_sent_monotonic
            >= self.hybrid_heartbeat_seconds
        )

    def _track_delivery_stats(
        self,
        state: WebSocketClientState,
        sent: bool,
        now_monotonic: float,
    ) -> None:
        """Track sent/dropped counters and emit periodic frequency logs."""
        if sent:
            state.sent_count_window += 1
            state.last_sent_monotonic = now_monotonic
        else:
            state.dropped_count_window += 1

        if (
            now_monotonic - state.window_started_monotonic
            >= self.frequency_log_window_seconds
        ):
            logger.info(
                "ws_frequency_window mode=%s sent=%s dropped=%s window_seconds=%s",
                state.mode,
                state.sent_count_window,
                state.dropped_count_window,
                self.frequency_log_window_seconds,
            )
            state.window_started_monotonic = now_monotonic
            state.sent_count_window = 0
            state.dropped_count_window = 0

    async def _broadcast_validated_payload(
        self,
        payload: MonitorPayload,
        *,
        is_closed: bool,
    ) -> None:
        """Broadcast validated payload to all websocket clients."""
        if not self._ws_connections:
            return

        message = payload.model_dump(mode="json", exclude_none=True)
        dead_connections: list[WebSocket] = []
        now_monotonic = time.monotonic()
        for ws in self._ws_connections:
            state = self._ws_client_state.setdefault(ws, WebSocketClientState())
            should_send = self._should_send_for_mode(
                state=state,
                is_closed=is_closed,
                now_monotonic=now_monotonic,
            )
            self._track_delivery_stats(
                state=state,
                sent=should_send,
                now_monotonic=now_monotonic,
            )
            if not should_send:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            self.unregister_websocket(ws)

    async def _enqueue_persistence(self, payload: MonitorPayload) -> None:
        """Enqueue validated payload for background persistence."""
        event = {
            "payload": payload.model_dump(mode="python", exclude_none=True),
            "attempt": 0,
        }
        await self._persist_queue.put(event)
        logger.debug(
            "persist_enqueue ticker=%s timeframe=%s queue_size=%s",
            payload.ticker,
            payload.timeframe,
            self._persist_queue.qsize(),
        )

    async def _handle_monitor_update(self, data: dict[str, Any]) -> None:
        """Process monitor update with WS priority and async persistence."""
        payload = self._validate_payload(data)
        if payload is None:
            return

        is_closed = bool(data.get("is_closed", True))
        await self._broadcast_validated_payload(payload, is_closed=is_closed)
        await self._enqueue_persistence(payload)

    async def broadcast_update(self, data: dict[str, Any]) -> None:
        """Broadcast-only API kept for backward compatibility.

        This method validates and broadcasts payload without persistence.
        """
        payload = self._validate_payload(data)
        if payload is None:
            return
        is_closed = bool(data.get("is_closed", True))
        await self._broadcast_validated_payload(payload, is_closed=is_closed)

    async def _ensure_persist_worker(self) -> None:
        """Ensure persistence worker task is running."""
        if self._persist_worker_task and not self._persist_worker_task.done():
            return

        self._persist_worker_running = True
        self._persist_worker_task = asyncio.create_task(self._persist_worker_loop())

    async def _persist_worker_loop(self) -> None:
        """Background worker for eventual-consistency persistence."""
        while self._persist_worker_running or not self._persist_queue.empty():
            try:
                event = await asyncio.wait_for(self._persist_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            payload = event["payload"]
            attempt = int(event.get("attempt", 0))

            try:
                await asyncio.to_thread(self._persist_payload_sync, payload)
                logger.debug(
                    "persist_success ticker=%s timeframe=%s",
                    payload.get("ticker"),
                    payload.get("timeframe"),
                )
            except Exception as exc:
                if attempt < 1:
                    retry_event = {"payload": payload, "attempt": attempt + 1}
                    await self._persist_queue.put(retry_event)
                    logger.warning(
                        "persist_retry ticker=%s timeframe=%s attempt=%s error=%s",
                        payload.get("ticker"),
                        payload.get("timeframe"),
                        attempt + 1,
                        exc,
                    )
                else:
                    logger.error(
                        "persist_failure ticker=%s timeframe=%s error=%s",
                        payload.get("ticker"),
                        payload.get("timeframe"),
                        exc,
                    )
            finally:
                self._persist_queue.task_done()

    def _persist_payload_sync(self, payload: dict[str, Any]) -> None:
        """Persist monitor payload using repository methods only."""
        ticker = str(payload["ticker"])
        timeframe_str = str(payload["timeframe"])

        candle_time = payload.get("timestamp")
        if isinstance(candle_time, str):
            candle_time = datetime.fromisoformat(candle_time)
        if not isinstance(candle_time, datetime):
            raise ValueError("Invalid payload timestamp for persistence")

        ohlcv = payload.get("ohlcv", {})
        indicators = payload.get("indicators", {})

        row = {
            "open": float(ohlcv.get("open", 0.0)),
            "high": float(ohlcv.get("high", 0.0)),
            "low": float(ohlcv.get("low", 0.0)),
            "close": float(ohlcv.get("close", 0.0)),
            "volume": int(ohlcv.get("volume", 0)),
            "tick_volume": int(ohlcv.get("volume", 0)),
            "spread": 0,
            "ema_9": float(indicators.get("ema_9", 0.0)),
            "sma_20": float(indicators.get("sma_20", 0.0)),
            "sma_50": float(indicators.get("sma_50", 0.0)),
        }
        df = pd.DataFrame([row], index=[candle_time])

        session_factory = get_session_factory()
        db = session_factory()
        try:
            AssetsRatesRepository.save_rates_dataframe(
                db=db,
                df=df,
                symbol=ticker,
                timeframe=self._timeframe_to_minutes(timeframe_str),
                timeframe_str=timeframe_str,
            )
        finally:
            db.close()

    @staticmethod
    def _timeframe_to_minutes(timeframe: str) -> int:
        """Map timeframe string to minute-based integer representation."""
        mapping = {
            "M1": 1,
            "M5": 5,
            "M15": 15,
            "M30": 30,
            "H1": 60,
            "H4": 240,
            "D1": 1440,
            "W1": 10080,
            "MN1": 43200,
        }
        return mapping.get(timeframe.upper(), 5)

    async def start_monitor(self, ticker: str, timeframe: str) -> dict[str, Any]:
        """Start monitor task for ticker/timeframe if not running."""
        await self._ensure_persist_worker()

        key = self.build_key(ticker, timeframe)
        monitor = await self._get_or_create_monitor(ticker, timeframe)

        existing_task = self._monitor_tasks.get(key)
        if existing_task is not None and not existing_task.done():
            return {
                "status": "already_running",
                "ticker": ticker,
                "timeframe": timeframe,
                "message": f"Monitor already running for {ticker} @ {timeframe}",
            }

        if key not in self._callbacks_registered:

            def callback(data: dict[str, Any]) -> None:
                asyncio.create_task(self._handle_monitor_update(data))

            monitor.register_callback(callback)
            self._callbacks_registered.add(key)

        task = asyncio.create_task(monitor.start_async())
        self._monitor_tasks[key] = task

        return {
            "status": "started",
            "ticker": ticker,
            "timeframe": timeframe,
            "message": f"Monitor started for {ticker} @ {timeframe}",
        }

    async def stop_monitor(self, ticker: str, timeframe: str) -> dict[str, Any]:
        """Stop monitor task for ticker/timeframe."""
        key = self.build_key(ticker, timeframe)
        monitor = self._monitors.get(key)
        task = self._monitor_tasks.get(key)

        if monitor is None:
            return {
                "status": "not_found",
                "ticker": ticker,
                "timeframe": timeframe,
                "message": f"No monitor found for {ticker} @ {timeframe}",
            }

        monitor.stop()
        if task and not task.done():
            task.cancel()

        self._monitor_tasks.pop(key, None)
        self._monitors.pop(key, None)
        self._callbacks_registered.discard(key)
        await self._registry.remove(ticker, timeframe)

        return {
            "status": "stopped",
            "ticker": ticker,
            "timeframe": timeframe,
        }

    def status(self) -> dict[str, Any]:
        """Get status of active monitors and websocket clients."""
        monitors_info = []
        for monitor in self._monitors.values():
            monitors_info.append(monitor.get_current_state())

        return {
            "active_monitors": len(self._monitors),
            "websocket_connections": len(self._ws_connections),
            "persistence_queue_size": self._persist_queue.qsize(),
            "persistence_worker_running": (
                self._persist_worker_task is not None
                and not self._persist_worker_task.done()
            ),
            "monitors": monitors_info,
        }

    async def stop_all(self) -> None:
        """Stop all monitor tasks, flush persistence and close websockets."""
        for key, monitor in list(self._monitors.items()):
            monitor.stop()
            task = self._monitor_tasks.get(key)
            if task and not task.done():
                task.cancel()

        for task in list(self._monitor_tasks.values()):
            if not task.done():
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.error("Error stopping monitor task: %s", exc)

        self._persist_worker_running = False
        try:
            await asyncio.wait_for(self._persist_queue.join(), timeout=8.0)
        except asyncio.TimeoutError:
            logger.warning(
                "Persist queue drain timeout. pending=%s",
                self._persist_queue.qsize(),
            )

        if self._persist_worker_task and not self._persist_worker_task.done():
            self._persist_worker_task.cancel()
            try:
                await self._persist_worker_task
            except asyncio.CancelledError:
                pass

        self._persist_worker_task = None
        self._monitor_tasks.clear()
        self._monitors.clear()
        self._callbacks_registered.clear()
        await self._registry.clear()

        for ws in list(self._ws_connections):
            try:
                await ws.close()
            except Exception:
                pass

        self._ws_connections.clear()
