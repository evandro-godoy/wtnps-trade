"""Trend-alignment decision rule for realtime monitor decision block."""

from __future__ import annotations

from typing import Any

from newapp.src.live.rules.base import BaseDecisionRule


class TrendAlignmentRule(BaseDecisionRule):
    """Block operations that go against the main trend context."""

    def evaluate(self, payload: dict[str, Any]) -> tuple[bool, str]:
        """Evaluate trend alignment for actionable signals."""
        ml_block = payload.get("ml", {})
        analysis_block = payload.get("analysis", {})

        side = self._normalize_side(
            signal=ml_block.get("signal", "HOLD"),
            direction=ml_block.get("direction", "HOLD"),
        )
        if side == "HOLD":
            return True, "Sem sinal acionável para validação de tendência"

        trend = str(analysis_block.get("trend", "INDEFINIDO")).upper()
        if trend in {"INDEFINIDO", "NEUTRO", "LATERAL"}:
            return True, "Tendência indefinida/neutra: sem bloqueio"

        if side == "COMPRA" and trend == "BAIXA":
            return False, "Sinal de COMPRA bloqueado: tendência principal em BAIXA"
        if side == "VENDA" and trend == "ALTA":
            return False, "Sinal de VENDA bloqueado: tendência principal em ALTA"

        return True, "Regra de tendência validada"

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
