from __future__ import annotations

import asyncio
import logging
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


class MonitorRuntime:
    """Manage monitor instances, async tasks and websocket connections."""

    def __init__(self) -> None:
        self._registry = MonitorRegistry()
        self._monitors: dict[str, RealtimeMarketMonitor] = {}
        self._monitor_tasks: dict[str, asyncio.Task[Any]] = {}
        self._ws_connections: list[WebSocket] = []
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

    async def register_websocket(self, websocket: WebSocket) -> None:
        """Register active websocket client."""
        await websocket.accept()
        self._ws_connections.append(websocket)
        logger.info("WebSocket connected. total=%s", len(self._ws_connections))

    def unregister_websocket(self, websocket: WebSocket) -> None:
        """Unregister websocket client."""
        if websocket in self._ws_connections:
            self._ws_connections.remove(websocket)
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

    async def _broadcast_validated_payload(self, payload: MonitorPayload) -> None:
        """Broadcast validated payload to all websocket clients."""
        if not self._ws_connections:
            return

        message = payload.model_dump(mode="json", exclude_none=True)
        dead_connections: list[WebSocket] = []
        for ws in self._ws_connections:
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

        await self._broadcast_validated_payload(payload)
        await self._enqueue_persistence(payload)

    async def broadcast_update(self, data: dict[str, Any]) -> None:
        """Broadcast-only API kept for backward compatibility.

        This method validates and broadcasts payload without persistence.
        """
        payload = self._validate_payload(data)
        if payload is None:
            return
        await self._broadcast_validated_payload(payload)

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
