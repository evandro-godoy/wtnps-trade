from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from newapp.configs.config import TEMPLATES_DIR
from newapp.src.analysis.context_analyzer import MarketContextAnalyzer
from newapp.src.api.state import AppStateContainer
from newapp.src.data_handler.provider import get_default_provider
from newapp.src.database import close_database, init_database
from newapp.src.ml.legacy_monitor_engine import get_legacy_monitor_engine
from newapp.src.ml.prediction_engine import get_prediction_engine
from newapp.src.services.monitor_runtime import MonitorRuntime

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Canonical FastAPI lifespan handler for startup/shutdown."""
    init_database()

    app.state.container = AppStateContainer(
        templates=Jinja2Templates(directory=str(TEMPLATES_DIR)),
        data_provider=get_default_provider(),
        market_analyzer=MarketContextAnalyzer(),
        ml_prediction_engine=get_prediction_engine(),
        legacy_monitor_engine=get_legacy_monitor_engine(),
        monitor_runtime=MonitorRuntime(),
    )

    try:
        await app.state.container.monitor_runtime.start_default_monitors()
    except Exception as exc:
        logger.error("always_on_monitor_bootstrap_failed error=%s", exc, exc_info=True)

    try:
        yield
    finally:
        await app.state.container.monitor_runtime.stop_all()
        close_database()
