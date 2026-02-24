"""Guardian tests for first tick and canonical payload contract.

This suite validates two critical guarantees:
1) First tick is emitted immediately after warm-up (no blocking on sleep).
2) Canonical payload contract uses strict top-level keys.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from newapp.src.live import monitor_engine as monitor_engine_module
from newapp.src.live.monitor_engine import RealtimeMarketMonitor
from newapp.src.services.monitor_runtime import MonitorRuntime
from newapp.src.services.prediction_service import (
    _build_canonical_prediction_item,
    build_canonical_monitor_payload,
)


EXPECTED_CANONICAL_KEYS = {
    "timestamp",
    "ticker",
    "timeframe",
    "ohlcv",
    "indicators",
    "analysis",
    "ml",
    "decision",
}


class _DummyProvider:
    """Minimal provider stub for monitor initialization."""


class _DummyLegacyEngine:
    """Minimal legacy engine stub for monitor initialization."""


def _build_monitor(monkeypatch: Any) -> RealtimeMarketMonitor:
    """Build a monitor instance with deterministic lightweight dependencies."""
    monkeypatch.setattr(
        monitor_engine_module,
        "get_default_provider",
        lambda: _DummyProvider(),
    )
    monkeypatch.setattr(
        monitor_engine_module,
        "get_legacy_monitor_engine",
        lambda: _DummyLegacyEngine(),
    )
    return RealtimeMarketMonitor(ticker="WDO$", timeframe_str="M5", buffer_size=10)


def test_start_emits_first_tick_before_sleep(monkeypatch: Any) -> None:
    """Monitor must emit first tick before entering the sleep wait cycle."""
    monitor = _build_monitor(monkeypatch)

    event_log: list[str] = []
    received_payloads: list[dict[str, Any]] = []
    tick_time = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)

    def callback(payload: dict[str, Any]) -> None:
        """Collect callback payload for assertions."""
        event_log.append("callback")
        received_payloads.append(payload)

    def fake_warm_up() -> None:
        """Warm-up stub that avoids external integrations."""
        event_log.append("warm_up")

    def fake_process_new_candle() -> dict[str, Any]:
        """Return deterministic canonical payload for first tick."""
        event_log.append("process")
        return {
            "timestamp": tick_time,
            "ticker": "WDO$",
            "timeframe": "M5",
            "ohlcv": {
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10,
            },
            "indicators": {},
            "analysis": {},
            "ml": {},
            "decision": {},
        }

    def fake_calculate_sleep() -> float:
        """Return any value; sequence is what matters for this test."""
        event_log.append("calculate_sleep")
        return 999.0

    def fake_sleep(seconds: float) -> None:
        """Stop loop on first sleep call to keep test deterministic."""
        event_log.append("sleep")
        monitor.running = False

    monitor.register_callback(callback)
    monkeypatch.setattr(monitor, "_warm_up", fake_warm_up)
    monkeypatch.setattr(monitor, "_process_new_candle", fake_process_new_candle)
    monkeypatch.setattr(monitor, "_calculate_sleep_until_next_candle", fake_calculate_sleep)
    monkeypatch.setattr(monitor_engine_module.time, "sleep", fake_sleep)

    monitor.start()

    assert len(received_payloads) == 1
    assert received_payloads[0]["timestamp"] == tick_time
    assert event_log.index("callback") < event_log.index("sleep")
    assert event_log[:3] == ["warm_up", "process", "callback"]


def test_build_canonical_payload_has_strict_root_keys(monkeypatch: Any) -> None:
    """Canonical monitor payload must expose only the strict root contract keys."""
    monitor = _build_monitor(monkeypatch)

    monitor.buffer_df = pd.DataFrame(
        {"close": [100.0, 101.0, 102.0]},
        index=pd.DatetimeIndex(
            [
                datetime(2026, 2, 20, 11, 50, tzinfo=timezone.utc),
                datetime(2026, 2, 20, 11, 55, tzinfo=timezone.utc),
                datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc),
            ]
        ),
    )

    latest_candle = pd.Series(
        {
            "open": 100.0,
            "high": 103.0,
            "low": 99.5,
            "close": 102.0,
            "volume": 1200,
        }
    )

    payload = monitor._build_canonical_payload(
        candle_time=datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc),
        latest_candle=latest_candle,
        analysis_context={
            "trend": "ALTA",
            "trend_strength": "FORTE",
            "support": 99.0,
            "resistance": 104.0,
            "pattern": "INDEFINIDO",
            "rsi_condition": "NEUTRO",
            "ema_fast": 101.0,
            "sma_fast": 100.5,
            "sma_slow": 98.5,
            "rsi": 54.0,
        },
        ml_result={
            "signal": "COMPRA",
            "direction": "UP",
            "probability": 0.76,
            "signal_valid": True,
            "validation_reason": "setup_ok",
            "ema_9": 101.0,
            "ema_20": 99.8,
            "sma_20": 100.5,
            "sma_50": 98.5,
            "rsi": 54.0,
        },
    )

    assert set(payload.keys()) == EXPECTED_CANONICAL_KEYS


def test_prediction_item_has_strict_root_keys() -> None:
    """Prediction service canonical item must expose strict root contract keys."""
    payload = _build_canonical_prediction_item(
        pred_result={
            "timestamp": datetime(2026, 2, 20, 12, 5, tzinfo=timezone.utc),
            "price": 5231.5,
            "signal": "VENDA",
            "direction": "DOWN",
            "probability": 0.66,
            "signal_valid": True,
            "validation_reason": "setup_ok",
        },
        ticker="WDO$",
        timeframe="M5",
        fallback_close=5230.0,
    )

    assert set(payload.keys()) == EXPECTED_CANONICAL_KEYS


def test_monitor_runtime_broadcast_keeps_canonical_root_keys() -> None:
    """WebSocket broadcast must preserve strict canonical root contract keys."""

    class _DummyWebSocket:
        """Capture outgoing websocket payloads."""

        def __init__(self) -> None:
            self.messages: list[dict[str, Any]] = []

        async def send_json(self, message: dict[str, Any]) -> None:
            """Store message for assertions."""
            self.messages.append(message)

    runtime = MonitorRuntime()
    ws = _DummyWebSocket()
    runtime._ws_connections.append(ws)  # controlled test double registration

    source_payload = {
        "timestamp": datetime(2026, 2, 20, 12, 10, tzinfo=timezone.utc),
        "ticker": "WDO$",
        "timeframe": "M5",
        "ohlcv": {"open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
        "indicators": {"ema_9": 1.1},
        "analysis": {"trend": "ALTA"},
        "ml": {"signal": "COMPRA"},
        "decision": {"signal_valid": True},
        "unexpected": "must_not_leak",
    }

    asyncio.run(runtime.broadcast_update(source_payload))

    assert len(ws.messages) == 1
    outbound = ws.messages[0]
    assert set(outbound.keys()) == EXPECTED_CANONICAL_KEYS
    assert isinstance(outbound["timestamp"], str)


def test_decision_severity_uses_strict_threshold_edges() -> None:
    """Severity must follow strict '>' comparisons on probability thresholds."""
    base_args = {
        "timestamp_value": "2026-02-20T12:00:00+00:00",
        "ticker": "WDO$",
        "timeframe": "M5",
        "ohlcv": {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1},
        "indicators": {"ema_9": 1.2, "ema_20": 1.1, "sma_20": 1.0, "sma_50": 0.9, "rsi_14": 50.0},
        "analysis": {"trend": "ALTA", "trend_strength": "FORTE", "support": 1.0, "resistance": 2.0, "pattern": "NEUTRO", "rsi_condition": "NEUTRO"},
        "ml_signal": "COMPRA",
        "ml_direction": "CALL",
        "base_signal_valid": True,
        "base_validation_reason": "ok",
    }

    payload_065 = build_canonical_monitor_payload(**base_args, ml_probability=0.65)
    payload_055 = build_canonical_monitor_payload(**base_args, ml_probability=0.55)
    payload_alert = build_canonical_monitor_payload(**base_args, ml_probability=0.65001)
    payload_info = build_canonical_monitor_payload(**base_args, ml_probability=0.55001)

    assert payload_065["decision"]["severity"] == "INFO"
    assert payload_055["decision"]["severity"] == "TICK"
    assert payload_alert["decision"]["severity"] == "ALERT"
    assert payload_info["decision"]["severity"] == "INFO"


def test_decision_blocks_buy_and_sell_by_technical_context() -> None:
    """Decision must block conflicting COMPRA/VENDA signals by RSI/pattern."""
    common_args = {
        "timestamp_value": "2026-02-20T12:00:00+00:00",
        "ticker": "WDO$",
        "timeframe": "M5",
        "ohlcv": {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1},
        "indicators": {"ema_9": 1.2, "ema_20": 1.1, "sma_20": 1.0, "sma_50": 0.9, "rsi_14": 75.0},
        "ml_probability": 0.7,
        "base_signal_valid": True,
        "base_validation_reason": "ok",
    }

    buy_blocked_by_rsi = build_canonical_monitor_payload(
        **common_args,
        analysis={"trend": "ALTA", "trend_strength": "FORTE", "support": 1.0, "resistance": 2.0, "pattern": "NEUTRO", "rsi_condition": "SOBRECOMPRADO"},
        ml_signal="COMPRA",
        ml_direction="CALL",
    )
    buy_blocked_by_pattern = build_canonical_monitor_payload(
        **common_args,
        analysis={"trend": "ALTA", "trend_strength": "FORTE", "support": 1.0, "resistance": 2.0, "pattern": "REJEICAO_ALTA", "rsi_condition": "NEUTRO"},
        ml_signal="COMPRA",
        ml_direction="CALL",
    )
    sell_blocked_by_rsi = build_canonical_monitor_payload(
        **common_args,
        analysis={"trend": "BAIXA", "trend_strength": "FORTE", "support": 1.0, "resistance": 2.0, "pattern": "NEUTRO", "rsi_condition": "SOBREVENDIDO"},
        ml_signal="VENDA",
        ml_direction="PUT",
    )
    sell_blocked_by_pattern = build_canonical_monitor_payload(
        **common_args,
        analysis={"trend": "BAIXA", "trend_strength": "FORTE", "support": 1.0, "resistance": 2.0, "pattern": "REJEICAO_BAIXA", "rsi_condition": "NEUTRO"},
        ml_signal="VENDA",
        ml_direction="PUT",
    )

    for blocked in [
        buy_blocked_by_rsi,
        buy_blocked_by_pattern,
        sell_blocked_by_rsi,
        sell_blocked_by_pattern,
    ]:
        assert blocked["decision"]["signal_valid"] is False
        assert blocked["decision"]["status"] == "NÃO VALIDADO"
