"""Singleton monitor registry for always-on realtime execution.

This registry centralizes monitor instance lifecycle by logical key
(`ticker+timeframe`) and protects against duplicate initialization.
Integration with FastAPI lifespan and monitor runtime is performed in
subsequent modification tasks.
"""

from __future__ import annotations

import asyncio
from typing import Dict

from newapp.src.live.monitor_engine import RealtimeMarketMonitor


class MonitorRegistry:
    """Registry of singleton monitor instances by logical key."""

    def __init__(self) -> None:
        self._monitors: Dict[str, RealtimeMarketMonitor] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def build_key(ticker: str, timeframe: str) -> str:
        """Build deterministic registry key for monitor instances."""
        ticker_norm = str(ticker or "").upper()
        timeframe_norm = str(timeframe or "").upper()
        return f"{ticker_norm}_{timeframe_norm}"

    async def get_or_create(
        self,
        *,
        ticker: str,
        timeframe: str,
        buffer_size: int = 500,
        enable_db_persistence: bool = False,
    ) -> RealtimeMarketMonitor:
        """Get existing monitor or create a new singleton instance.

        The lock prevents double initialization when concurrent requests
        attempt to create the same monitor key simultaneously.
        """
        key = self.build_key(ticker, timeframe)

        async with self._lock:
            monitor = self._monitors.get(key)
            if monitor is not None:
                return monitor

            monitor = RealtimeMarketMonitor(
                ticker=ticker,
                timeframe_str=timeframe,
                buffer_size=buffer_size,
                enable_db_persistence=enable_db_persistence,
            )
            self._monitors[key] = monitor
            return monitor

    async def remove(self, ticker: str, timeframe: str) -> None:
        """Remove monitor singleton from registry by key."""
        key = self.build_key(ticker, timeframe)
        async with self._lock:
            self._monitors.pop(key, None)

    async def clear(self) -> None:
        """Remove all monitor instances from registry."""
        async with self._lock:
            self._monitors.clear()

    async def count(self) -> int:
        """Return number of registered singleton monitor instances."""
        async with self._lock:
            return len(self._monitors)

    async def list_keys(self) -> list[str]:
        """Return sorted list of monitor keys in registry."""
        async with self._lock:
            return sorted(self._monitors.keys())
