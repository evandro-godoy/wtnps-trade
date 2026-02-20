"""Canonical FastAPI entrypoint for newapp monolith."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from newapp.configs.config import APP_NAME, APP_VERSION, HOST, LOG_FORMAT, LOG_LEVEL, PORT, RELOAD, STATIC_DIR
from newapp.src.api.lifespan import app_lifespan
from newapp.src.api.routers.backtest import map_timeframe_to_int
from newapp.src.api.routers.backtest import router as backtest_router
from newapp.src.api.routers.market_data import router as market_data_router
from newapp.src.api.routers.monitor import router as monitor_router
from newapp.src.api.routers.pages import router as pages_router
from newapp.src.api.websockets.backtest_ws import router as backtest_ws_router
from newapp.src.api.websockets.monitor_ws import router as monitor_ws_router

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Disable static file cache for UI iteration."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=app_lifespan)
app.add_middleware(NoCacheMiddleware)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(pages_router)
app.include_router(market_data_router)
app.include_router(monitor_router)
app.include_router(backtest_router)
app.include_router(monitor_ws_router)
app.include_router(backtest_ws_router)

# Backward compatible symbol export
_map_timeframe_to_int = map_timeframe_to_int


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "newapp.src.api.main:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
    )
