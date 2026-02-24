from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _classify_severity(probability: float) -> str:
    """Classify signal severity using strict legacy thresholds.

    Rules:
    - ALERT when probability > 0.65
    - INFO when probability > 0.55 and not ALERT
    - TICK otherwise
    """
    if probability > 0.65:
        return "ALERT"
    if probability > 0.55:
        return "INFO"
    return "TICK"


def _normalize_signal_direction(signal: str, direction: str) -> str:
    """Normalize ML signal direction to COMPRA/VENDA/HOLD."""
    signal_norm = str(signal or "").upper()
    direction_norm = str(direction or "").upper()

    buy_tokens = {"COMPRA", "CALL", "BUY"}
    sell_tokens = {"VENDA", "PUT", "SELL"}

    if signal_norm in buy_tokens or direction_norm in buy_tokens:
        return "COMPRA"
    if signal_norm in sell_tokens or direction_norm in sell_tokens:
        return "VENDA"
    return "HOLD"


def _build_decision_block(
    ml_signal: str,
    ml_direction: str,
    probability: float,
    analysis_context: dict[str, Any],
    base_signal_valid: bool | None = None,
    base_validation_reason: str = "",
) -> dict[str, Any]:
    """Build decision block with strict technical lock and severity.

    Technical lock rules (legacy-compatible):
    - Block COMPRA/CALL if RSI is SOBRECOMPRADO
    - Block VENDA/PUT if RSI is SOBREVENDIDO
    - Block COMPRA/CALL if pattern is REJEICAO_ALTA
    - Block VENDA/PUT if pattern is REJEICAO_BAIXA
    """
    normalized_side = _normalize_signal_direction(ml_signal, ml_direction)
    rsi_condition = str(analysis_context.get("rsi_condition", "INDEFINIDO")).upper()
    pattern = str(analysis_context.get("pattern", "INDEFINIDO")).upper()

    signal_valid = True
    validation_reason = "Sinal validado pelo contexto técnico"

    if normalized_side == "HOLD":
        signal_valid = False
        validation_reason = "Sem sinal acionável no candle atual"
    elif normalized_side == "COMPRA" and rsi_condition == "SOBRECOMPRADO":
        signal_valid = False
        validation_reason = "Sinal de COMPRA mas RSI está SOBRECOMPRADO"
    elif normalized_side == "VENDA" and rsi_condition == "SOBREVENDIDO":
        signal_valid = False
        validation_reason = "Sinal de VENDA mas RSI está SOBREVENDIDO"
    elif normalized_side == "COMPRA" and pattern == "REJEICAO_ALTA":
        signal_valid = False
        validation_reason = "Sinal de COMPRA mas há REJEIÇÃO da ALTA"
    elif normalized_side == "VENDA" and pattern == "REJEICAO_BAIXA":
        signal_valid = False
        validation_reason = "Sinal de VENDA mas há REJEIÇÃO da BAIXA"
    elif base_signal_valid is False:
        signal_valid = False
        validation_reason = (
            str(base_validation_reason).strip()
            or "Sinal não validado pelo pipeline base"
        )
    elif str(base_validation_reason).strip():
        validation_reason = str(base_validation_reason).strip()

    return {
        "signal_valid": signal_valid,
        "validation_reason": validation_reason,
        "status": "VALIDADO" if signal_valid else "NÃO VALIDADO",
        "severity": _classify_severity(probability),
    }


def build_canonical_monitor_payload(
    *,
    timestamp_value: Any,
    ticker: str,
    timeframe: str,
    ohlcv: dict[str, Any],
    indicators: dict[str, Any],
    analysis: dict[str, Any],
    ml_signal: str,
    ml_direction: str,
    ml_probability: float,
    base_signal_valid: bool | None = None,
    base_validation_reason: str = "",
) -> dict[str, Any]:
    """Build canonical monitor payload shared by realtime WS and API endpoint."""
    decision = _build_decision_block(
        ml_signal=ml_signal,
        ml_direction=ml_direction,
        probability=ml_probability,
        analysis_context=analysis,
        base_signal_valid=base_signal_valid,
        base_validation_reason=base_validation_reason,
    )

    return {
        "timestamp": timestamp_value,
        "ticker": ticker,
        "timeframe": timeframe,
        "ohlcv": ohlcv,
        "indicators": indicators,
        "analysis": analysis,
        "ml": {
            "signal": ml_signal,
            "direction": ml_direction,
            "probability": ml_probability,
        },
        "decision": decision,
    }


def _build_canonical_prediction_item(
    pred_result: dict[str, Any],
    ticker: str,
    timeframe: str,
    fallback_close: float,
) -> dict[str, Any]:
    """Build canonical monitor payload item from legacy monitor prediction result."""
    timestamp_value = pred_result.get("timestamp")
    if hasattr(timestamp_value, "isoformat"):
        timestamp_out = timestamp_value.isoformat()
    else:
        timestamp_out = str(timestamp_value)

    ohlcv = {
        "open": 0.0,
        "high": 0.0,
        "low": 0.0,
        "close": float(pred_result.get("price", fallback_close)),
        "volume": 0,
    }
    indicators = {
        "ema_9": float(pred_result.get("ema_9", 0.0)),
        "ema_20": float(pred_result.get("ema_20", 0.0)),
        "sma_20": float(pred_result.get("sma_20", 0.0)),
        "sma_50": float(pred_result.get("sma_50", 0.0)),
        "rsi_14": float(pred_result.get("rsi", 0.0)),
    }
    analysis = {
        "trend": str(pred_result.get("trend", "INDEFINIDO")),
        "trend_strength": str(pred_result.get("trend_strength", "INDEFINIDO")),
        "support": float(pred_result.get("support", 0.0)),
        "resistance": float(pred_result.get("resistance", 0.0)),
        "pattern": str(pred_result.get("pattern", "INDEFINIDO")),
        "rsi_condition": str(pred_result.get("rsi_condition", "INDEFINIDO")),
    }
    ml_signal = str(pred_result.get("signal", "HOLD"))
    ml_direction = str(pred_result.get("direction", "HOLD"))
    ml_probability = float(pred_result.get("probability", 0.0))

    payload = build_canonical_monitor_payload(
        timestamp_value=timestamp_out,
        ticker=ticker,
        timeframe=timeframe,
        ohlcv=ohlcv,
        indicators=indicators,
        analysis=analysis,
        ml_signal=ml_signal,
        ml_direction=ml_direction,
        ml_probability=ml_probability,
        base_signal_valid=bool(pred_result.get("signal_valid", False)),
        base_validation_reason=str(pred_result.get("validation_reason", "")),
    )
    return payload


def get_monitor_predictions_payload(
    symbol: str,
    timeframe: str,
    count: int,
    provider: Any,
    legacy_monitor_engine: Any,
) -> dict[str, Any]:
    """Generate canonical monitor prediction payload for monitor WS/API contract."""
    try:
        safe_count = min(max(1, count), 10)

        data: pd.DataFrame = provider.get_latest_candles(
            ticker=symbol,
            timeframe=timeframe,
            count=500,
        )

        if data.empty:
            return {
                "predictions": [],
                "latest_candle_time": None,
                "is_market_open": False,
                "error": "No data available",
                "source": "legacy_monitor_engine",
            }

        latest_candle_time = data.index[-1]
        latest_candle_time_str = latest_candle_time.isoformat()

        now_utc = datetime.now(timezone.utc)
        if latest_candle_time.tzinfo is None:
            latest_candle_time = latest_candle_time.replace(tzinfo=timezone.utc)

        time_diff = (now_utc - latest_candle_time).total_seconds()
        is_market_open = time_diff < 600

        predictions: list[dict[str, Any]] = []
        start_idx = max(1, len(data) - safe_count)
        for idx in range(start_idx, len(data)):
            subset = data.iloc[: idx + 1]
            pred_result = legacy_monitor_engine.predict_on_candle(subset, symbol, timeframe)
            if not pred_result:
                continue
            fallback_close = float(subset.iloc[-1]["close"])
            predictions.append(
                _build_canonical_prediction_item(
                    pred_result=pred_result,
                    ticker=symbol,
                    timeframe=timeframe,
                    fallback_close=fallback_close,
                )
            )

        results = predictions[-safe_count:] if predictions else []
        return {
            "predictions": results,
            "latest_candle_time": latest_candle_time_str,
            "is_market_open": is_market_open,
            "source": "legacy_monitor_engine",
            "error": None,
        }
    except Exception as exc:
        logger.error("Error in monitor predictions: %s", exc, exc_info=True)
        return {
            "predictions": [],
            "latest_candle_time": None,
            "is_market_open": False,
            "error": str(exc),
            "source": "legacy_monitor_engine",
        }
