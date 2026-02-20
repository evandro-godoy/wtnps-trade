from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _format_prediction_message(pred_result: dict[str, Any], prob_pct: float) -> str:
    """Format prediction message for charts_clean grid."""
    if prob_pct >= 65:
        target = (
            pred_result["resistance"]
            if pred_result["direction"] == "CALL"
            else pred_result["support"]
        )
        validation_icon = "✅" if pred_result["signal_valid"] else "⚠️"
        return (
            f"{validation_icon} SINAL {pred_result['direction']} ({prob_pct:.1f}%) | "
            f"Tendência: {pred_result['trend']} ({pred_result['trend_strength']}) | "
            f"Padrão: {pred_result['pattern']} | "
            f"Alvo: {target:.2f}"
        )

    if prob_pct >= 55:
        return (
            f"📊 Prob. Moderada ({prob_pct:.1f}%) | "
            f"Tendência: {pred_result['trend']} | "
            f"RSI: {pred_result['rsi']:.0f} ({pred_result['rsi_condition']})"
        )

    return f"Candle processado | Tendência: {pred_result['trend']}"


def get_monitor_predictions_payload(
    symbol: str,
    timeframe: str,
    count: int,
    provider: Any,
    legacy_monitor_engine: Any,
) -> dict[str, Any]:
    """Generate monitor prediction payload compatible with charts_clean frontend."""
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
            }

        latest_candle_time = data.index[-1]
        latest_candle_time_str = latest_candle_time.strftime("%Y-%m-%d %H:%M:%S")

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

            timestamp_str = (
                pred_result["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(pred_result["timestamp"], "strftime")
                else str(pred_result["timestamp"])
            )

            prob_pct = round(pred_result["probability"] * 100, 2)
            message = _format_prediction_message(pred_result, prob_pct)

            predictions.append(
                {
                    "timestamp": timestamp_str,
                    "tipo": pred_result["signal"],
                    "direction": pred_result["direction"],
                    "preco": int(pred_result["price"]),
                    "prob_ml": prob_pct,
                    "mensagem": message,
                    "indicators": {
                        "close": pred_result["price"],
                        "ema_9": pred_result["ema_9"],
                        "ema_20": pred_result["ema_20"],
                        "sma_20": pred_result["sma_20"],
                        "sma_50": pred_result["sma_50"],
                        "rsi_14": pred_result["rsi"],
                    },
                    "analysis": {
                        "trend": pred_result["trend"],
                        "trend_strength": pred_result["trend_strength"],
                        "rsi": pred_result["rsi"],
                        "rsi_condition": pred_result["rsi_condition"],
                        "support": pred_result["support"],
                        "resistance": pred_result["resistance"],
                        "pattern": pred_result["pattern"],
                        "signal_valid": pred_result["signal_valid"],
                    },
                }
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
