from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from fastapi import WebSocket

from newapp.src.live.monitor_engine import RealtimeMarketMonitor

logger = logging.getLogger(__name__)


class MonitorRuntime:
    """Manage monitor instances, asyncio tasks and websocket connections."""

    def __init__(self) -> None:
        self._monitors: dict[str, RealtimeMarketMonitor] = {}
        self._monitor_tasks: dict[str, asyncio.Task[Any]] = {}
        self._ws_connections: list[WebSocket] = []
        self._callbacks_registered: set[str] = set()

    @staticmethod
    def build_key(ticker: str, timeframe: str) -> str:
        """Build monitor dictionary key."""
        return f"{ticker}_{timeframe}"

    def get_or_create_monitor(self, ticker: str, timeframe: str) -> RealtimeMarketMonitor:
        """Get existing monitor instance or create one."""
        key = self.build_key(ticker, timeframe)
        if key not in self._monitors:
            self._monitors[key] = RealtimeMarketMonitor(
                ticker=ticker,
                timeframe_str=timeframe,
                buffer_size=500,
                enable_db_persistence=False,
            )
            logger.info("Created monitor %s", key)
        return self._monitors[key]

    async def register_websocket(self, websocket: WebSocket) -> None:
        """Register active websocket client."""
        await websocket.accept()
        self._ws_connections.append(websocket)
        logger.info("WebSocket connected. Total: %s", len(self._ws_connections))

    def unregister_websocket(self, websocket: WebSocket) -> None:
        """Unregister websocket client."""
        if websocket in self._ws_connections:
            self._ws_connections.remove(websocket)
            logger.info("WebSocket removed. Total: %s", len(self._ws_connections))

    async def broadcast_update(self, data: dict[str, Any]) -> None:
        """Broadcast monitor update payload to all websocket clients."""
        if not self._ws_connections:
            return

        message = {
            "timestamp": data["timestamp"].isoformat()
            if isinstance(data["timestamp"], datetime)
            else str(data["timestamp"]),
            "ticker": data.get("ticker"),
            "timeframe": data.get("timeframe"),
            "ohlcv": data.get("ohlcv", {}),
            "indicators": data.get("indicators", {}),
            "analysis": data.get("analysis", {}),
        }

        dead_connections: list[WebSocket] = []
        for ws in self._ws_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            self.unregister_websocket(ws)

    async def start_monitor(self, ticker: str, timeframe: str) -> dict[str, Any]:
        """Start monitor task for ticker/timeframe if not running."""
        key = self.build_key(ticker, timeframe)
        monitor = self.get_or_create_monitor(ticker, timeframe)

        if key in self._monitor_tasks and not self._monitor_tasks[key].done():
            return {
                "status": "already_running",
                "ticker": ticker,
                "timeframe": timeframe,
                "message": f"Monitor already running for {ticker} @ {timeframe}",
            }

        if key not in self._callbacks_registered:
            def callback(data: dict[str, Any]) -> None:
                asyncio.create_task(self.broadcast_update(data))

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

    def stop_monitor(self, ticker: str, timeframe: str) -> dict[str, Any]:
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
            "monitors": monitors_info,
        }

    async def stop_all(self) -> None:
        """Stop all monitor tasks and close all websocket connections."""
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

        self._monitor_tasks.clear()
        self._monitors.clear()
        self._callbacks_registered.clear()

        for ws in list(self._ws_connections):
            try:
                await ws.close()
            except Exception:
                pass

        self._ws_connections.clear()
