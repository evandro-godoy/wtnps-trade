from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from newapp.configs.config import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
from newapp.src.api.dependencies import get_state_from_request
from newapp.src.services.prediction_service import get_monitor_predictions_payload

router = APIRouter()


class MonitorActionBody(BaseModel):
    ticker: str | None = None
    timeframe: str | None = None


@router.post("/api/monitor/start")
async def start_monitor(
    request: Request,
    body: MonitorActionBody | None = Body(default=None),
    ticker: str = Query(default=DEFAULT_SYMBOL),
    timeframe: str = Query(default=DEFAULT_TIMEFRAME),
) -> JSONResponse:
    state = get_state_from_request(request)
    selected_ticker = body.ticker if body and body.ticker else ticker
    selected_timeframe = body.timeframe if body and body.timeframe else timeframe

    try:
        result = await state.monitor_runtime.start_monitor(selected_ticker, selected_timeframe)
        return JSONResponse(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/monitor/stop")
async def stop_monitor(
    request: Request,
    body: MonitorActionBody | None = Body(default=None),
    ticker: str = Query(default=DEFAULT_SYMBOL),
    timeframe: str = Query(default=DEFAULT_TIMEFRAME),
) -> JSONResponse:
    state = get_state_from_request(request)
    selected_ticker = body.ticker if body and body.ticker else ticker
    selected_timeframe = body.timeframe if body and body.timeframe else timeframe

    result = await state.monitor_runtime.stop_monitor(selected_ticker, selected_timeframe)
    return JSONResponse(result)


@router.get("/api/monitor/status")
async def monitor_status(request: Request) -> JSONResponse:
    state = get_state_from_request(request)
    return JSONResponse(state.monitor_runtime.status())


@router.get("/api/monitor-predictions")
async def api_monitor_predictions(
    request: Request,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    count: int = 10,
) -> JSONResponse:
    state = get_state_from_request(request)
    payload: dict[str, Any] = get_monitor_predictions_payload(
        symbol=symbol,
        timeframe=timeframe,
        count=count,
        provider=state.data_provider,
        legacy_monitor_engine=state.legacy_monitor_engine,
    )
    return JSONResponse(payload)
