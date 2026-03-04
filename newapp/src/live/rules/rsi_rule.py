"""RSI-based decision rule for realtime monitor decision block."""

from __future__ import annotations

from typing import Any

from newapp.src.live.rules.base import BaseDecisionRule


class RsiOverboughtOversoldRule(BaseDecisionRule):
    """Block COMPRA/VENDA when RSI context indicates opposite extremes."""

    def evaluate(self, payload: dict[str, Any]) -> tuple[bool, str]:
        """Evaluate RSI lock conditions and return decision tuple."""
        ml_block = payload.get("ml", {})
        analysis_block = payload.get("analysis", {})
        indicators_block = payload.get("indicators", {})

        side = self._normalize_side(
            signal=ml_block.get("signal", "HOLD"),
            direction=ml_block.get("direction", "HOLD"),
        )
        if side == "HOLD":
            return True, "Sem sinal acionável para validação por RSI"

        rsi_condition = str(
            analysis_block.get("rsi_condition", "INDEFINIDO")
        ).upper()
        rsi_value = self._safe_float(indicators_block.get("rsi_14"))

        if side == "COMPRA":
            if rsi_condition == "SOBRECOMPRADO":
                return False, "Sinal de COMPRA bloqueado: RSI em SOBRECOMPRADO"
            if rsi_value is not None and rsi_value > 70.0:
                return False, "Sinal de COMPRA bloqueado: RSI > 70"

        if side == "VENDA":
            if rsi_condition == "SOBREVENDIDO":
                return False, "Sinal de VENDA bloqueado: RSI em SOBREVENDIDO"
            if rsi_value is not None and rsi_value < 30.0:
                return False, "Sinal de VENDA bloqueado: RSI < 30"

        return True, "Regra RSI validada"

    @staticmethod
    def _normalize_side(signal: Any, direction: Any) -> str:
        """Normalize side values to COMPRA, VENDA or HOLD."""
        signal_norm = str(signal or "").upper()
        direction_norm = str(direction or "").upper()

        buy_tokens = {"COMPRA", "CALL", "BUY", "UP"}
        sell_tokens = {"VENDA", "PUT", "SELL", "DOWN"}

        if signal_norm in buy_tokens or direction_norm in buy_tokens:
            return "COMPRA"
        if signal_norm in sell_tokens or direction_norm in sell_tokens:
            return "VENDA"
        return "HOLD"

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        """Convert value to float when possible."""
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
