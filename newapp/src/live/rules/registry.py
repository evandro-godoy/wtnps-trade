"""Registry for monitor decision rules loaded from YAML config."""

from __future__ import annotations

from typing import Type

from newapp.src.live.rules.base import BaseDecisionRule
from newapp.src.live.rules.rsi_rule import RsiOverboughtOversoldRule
from newapp.src.live.rules.trend_rule import TrendAlignmentRule


RULE_REGISTRY: dict[str, Type[BaseDecisionRule]] = {
    "RsiOverboughtOversoldRule": RsiOverboughtOversoldRule,
    "TrendAlignmentRule": TrendAlignmentRule,
}
