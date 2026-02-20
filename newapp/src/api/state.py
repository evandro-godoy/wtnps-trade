from __future__ import annotations

from dataclasses import dataclass

from fastapi.templating import Jinja2Templates

from newapp.src.analysis.context_analyzer import MarketContextAnalyzer
from newapp.src.data_handler.provider import BaseDataProvider
from newapp.src.ml.prediction_engine import MLPredictionEngine
from newapp.src.ml.legacy_monitor_engine import LegacyMonitorEngine
from newapp.src.services.monitor_runtime import MonitorRuntime


@dataclass
class AppStateContainer:
    """Application shared state container."""

    templates: Jinja2Templates
    data_provider: BaseDataProvider
    market_analyzer: MarketContextAnalyzer
    ml_prediction_engine: MLPredictionEngine
    legacy_monitor_engine: LegacyMonitorEngine
    monitor_runtime: MonitorRuntime
