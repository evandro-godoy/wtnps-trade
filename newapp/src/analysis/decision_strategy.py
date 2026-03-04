"""Decision validation strategies for realtime monitor payload.

This module decouples decision validation from ML inference by using
the Strategy pattern. The default implementation preserves current
legacy lock rules for RSI and candlestick patterns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class DecisionResult:
    """Decision validation output consumed by payload serializers."""

    signal_valid: bool
    validation_reason: str
    status: str
    severity: str

    def to_dict(self) -> dict[str, Any]:
        """Convert dataclass result to serializable dictionary."""
        return {
            "signal_valid": self.signal_valid,
            "validation_reason": self.validation_reason,
            "status": self.status,
            "severity": self.severity,
        }


class DecisionValidationStrategy(Protocol):
    """Strategy interface for decision validation."""

    def validate(
        self,
        *,
        ml_signal: str,
        ml_direction: str,
        probability: float,
        analysis_context: dict[str, Any],
        base_signal_valid: bool | None = None,
        base_validation_reason: str = "",
    ) -> DecisionResult:
        """Validate decision block based on ML and technical context."""


class DefaultDecisionValidationStrategy:
    """Default strategy preserving strict legacy validation rules."""

    def validate(
        self,
        *,
        ml_signal: str,
        ml_direction: str,
        probability: float,
        analysis_context: dict[str, Any],
        base_signal_valid: bool | None = None,
        base_validation_reason: str = "",
    ) -> DecisionResult:
        """Apply technical locks and return canonical decision result."""
        normalized_side = self._normalize_signal_direction(ml_signal, ml_direction)
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

        severity = self._classify_severity(float(probability))
        status = "VALIDADO" if signal_valid else "NÃO VALIDADO"

        return DecisionResult(
            signal_valid=signal_valid,
            validation_reason=validation_reason,
            status=status,
            severity=severity,
        )

    def _classify_severity(self, probability: float) -> str:
        """Classify severity using strict threshold comparators."""
        if probability > 0.65:
            return "ALERT"
        if probability > 0.55:
            return "INFO"
        return "TICK"

    def _normalize_signal_direction(self, signal: str, direction: str) -> str:
        """Normalize side values to COMPRA, VENDA or HOLD."""
        signal_norm = str(signal or "").upper()
        direction_norm = str(direction or "").upper()

        buy_tokens = {"COMPRA", "CALL", "BUY"}
        sell_tokens = {"VENDA", "PUT", "SELL"}

        if signal_norm in buy_tokens or direction_norm in buy_tokens:
            return "COMPRA"
        if signal_norm in sell_tokens or direction_norm in sell_tokens:
            return "VENDA"
        return "HOLD"
