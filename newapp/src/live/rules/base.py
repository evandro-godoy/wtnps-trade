"""Base contract for plugable monitor decision rules.

Rules evaluate canonical monitor payloads and return a decision tuple:
- True when rule validates the signal.
- False when rule blocks the signal.
- Message with reason for UI-ready decision.validation_reason.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseDecisionRule(ABC):
    """Abstract base class for monitor decision rules."""

    @abstractmethod
    def evaluate(self, payload: dict[str, Any]) -> tuple[bool, str]:
        """Evaluate payload and return (is_valid, reason)."""
