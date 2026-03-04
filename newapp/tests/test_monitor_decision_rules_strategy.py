"""Tests for Slice 2 decision rules strategy integration in monitor engine."""

from __future__ import annotations

from typing import Any

from newapp.src.live import monitor_engine as monitor_engine_module
from newapp.src.live.monitor_engine import RealtimeMarketMonitor


class _DummyProvider:
    """Minimal provider stub for monitor initialization."""


class _DummyLegacyEngine:
    """Minimal legacy engine stub for monitor initialization."""


def _build_monitor_with_config(
    monkeypatch: Any,
    config: dict[str, Any],
) -> RealtimeMarketMonitor:
    """Build monitor with deterministic dependencies and inline YAML config."""
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
    monkeypatch.setattr(
        RealtimeMarketMonitor,
        "_load_yaml_config",
        lambda self: config,
    )

    return RealtimeMarketMonitor(ticker="WDO$", timeframe_str="M5", buffer_size=10)


def test_loads_only_active_known_rules(monkeypatch: Any) -> None:
    """Monitor must instantiate only known active rules in configured order."""
    config = {
        "assets": [
            {
                "ticker": "WDO$",
                "live_trading": {
                    "timeframe_str": "M5",
                    "active_rules": [
                        "TrendAlignmentRule",
                        "InvalidRule",
                        "RsiOverboughtOversoldRule",
                    ],
                },
            }
        ]
    }

    monitor = _build_monitor_with_config(monkeypatch, config)

    loaded_names = [rule.__class__.__name__ for rule in monitor.decision_rules]
    assert loaded_names == ["TrendAlignmentRule", "RsiOverboughtOversoldRule"]


def test_rule_chain_blocks_first_failure_in_order(monkeypatch: Any) -> None:
    """Decision must fail fast and keep reason from first failing configured rule."""
    config = {
        "assets": [
            {
                "ticker": "WDO$",
                "live_trading": {
                    "timeframe_str": "M5",
                    "active_rules": [
                        "TrendAlignmentRule",
                        "RsiOverboughtOversoldRule",
                    ],
                },
            }
        ]
    }

    monitor = _build_monitor_with_config(monkeypatch, config)

    payload = {
        "ml": {"signal": "COMPRA", "direction": "CALL", "probability": 0.80},
        "analysis": {"trend": "BAIXA", "rsi_condition": "SOBRECOMPRADO"},
        "indicators": {"rsi_14": 75.0},
        "decision": {
            "signal_valid": True,
            "validation_reason": "Sinal validado pelo contexto técnico",
            "status": "VALIDADO",
            "severity": "ALERT",
        },
    }

    result = monitor._apply_decision_rules(payload)

    assert result["decision"]["signal_valid"] is False
    assert result["decision"]["status"] == "NÃO VALIDADO"
    assert "tendência principal em BAIXA" in result["decision"]["validation_reason"]


def test_rule_chain_skips_when_base_decision_is_invalid(monkeypatch: Any) -> None:
    """Rules must not override an already invalid base decision from base strategy."""
    config = {
        "assets": [
            {
                "ticker": "WDO$",
                "live_trading": {
                    "timeframe_str": "M5",
                    "active_rules": ["TrendAlignmentRule"],
                },
            }
        ]
    }

    monitor = _build_monitor_with_config(monkeypatch, config)

    payload = {
        "ml": {"signal": "COMPRA", "direction": "CALL", "probability": 0.80},
        "analysis": {"trend": "ALTA"},
        "indicators": {"rsi_14": 50.0},
        "decision": {
            "signal_valid": False,
            "validation_reason": "Sinal não validado pelo pipeline base",
            "status": "NÃO VALIDADO",
            "severity": "ALERT",
        },
    }

    result = monitor._apply_decision_rules(payload)

    assert result["decision"]["signal_valid"] is False
    assert result["decision"]["validation_reason"] == (
        "Sinal não validado pelo pipeline base"
    )
