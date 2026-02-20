from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from newapp.configs.config import APP_VERSION, DEFAULT_LIMIT, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, MAX_LIMIT
from newapp.src.api.dependencies import get_state_from_request
from newapp.src.database import get_db
from newapp.src.services.chart_service import build_chart_components
from newapp.src.services.ohlc_service import get_recent_ohlc

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def root_page() -> RedirectResponse:
    return RedirectResponse(url="/home")


@router.get("/home", response_class=HTMLResponse)
async def home_page(request: Request) -> HTMLResponse:
    state = get_state_from_request(request)
    return state.templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "app_version": APP_VERSION,
            "version": int(time.time()),
        },
    )


@router.get("/charts", response_class=HTMLResponse)
async def charts_page(
    request: Request,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> HTMLResponse:
    state = get_state_from_request(request)
    safe_limit = min(limit, MAX_LIMIT)
    df = get_recent_ohlc(
        symbol=symbol,
        timeframe=timeframe,
        limit=safe_limit,
        provider=state.data_provider,
        db=db,
        background_tasks=background_tasks,
    )
    script, div = build_chart_components(df)
    return state.templates.TemplateResponse(
        "charts.html",
        {
            "request": request,
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": safe_limit,
            "app_version": APP_VERSION,
            "version": int(time.time()),
            "bokeh_script": script,
            "bokeh_div": div,
        },
    )


@router.get("/charts-clean", response_class=HTMLResponse)
async def charts_clean_page(
    request: Request,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> HTMLResponse:
    state = get_state_from_request(request)
    safe_limit = min(limit, MAX_LIMIT)
    df = get_recent_ohlc(
        symbol=symbol,
        timeframe=timeframe,
        limit=safe_limit,
        provider=state.data_provider,
        db=db,
        background_tasks=background_tasks,
    )
    script, div = build_chart_components(df)
    return state.templates.TemplateResponse(
        "charts_clean.html",
        {
            "request": request,
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": safe_limit,
            "app_version": APP_VERSION,
            "version": int(time.time()),
            "bokeh_script": script,
            "bokeh_div": div,
        },
    )


@router.get("/home-clean", response_class=HTMLResponse)
async def home_clean_page() -> RedirectResponse:
    return RedirectResponse(url="/charts-clean")


@router.get("/monitor", response_class=HTMLResponse)
async def monitor_page(request: Request) -> HTMLResponse:
    state = get_state_from_request(request)
    return state.templates.TemplateResponse(
        "monitor.html",
        {
            "request": request,
            "app_version": APP_VERSION,
            "version": int(time.time()),
        },
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> HTMLResponse:
    state = get_state_from_request(request)
    df = get_recent_ohlc(
        symbol=DEFAULT_SYMBOL,
        timeframe=DEFAULT_TIMEFRAME,
        limit=DEFAULT_LIMIT,
        provider=state.data_provider,
        db=db,
        background_tasks=background_tasks,
    )
    script, div = build_chart_components(df)
    return state.templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "symbol": DEFAULT_SYMBOL,
            "timeframe": DEFAULT_TIMEFRAME,
            "limit": DEFAULT_LIMIT,
            "version": int(time.time()),
            "bokeh_script": script,
            "bokeh_div": div,
        },
    )


@router.get("/analysis", response_class=HTMLResponse)
async def analysis_page(request: Request) -> HTMLResponse:
    state = get_state_from_request(request)
    return state.templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "app_version": APP_VERSION,
            "version": int(time.time()),
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    state = get_state_from_request(request)
    return state.templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "app_version": APP_VERSION,
            "version": int(time.time()),
        },
    )


@router.get("/backtest", response_class=HTMLResponse)
async def backtest_page(request: Request) -> HTMLResponse:
    state = get_state_from_request(request)
    end_dt = datetime.now(timezone.utc).replace(microsecond=0, second=0)
    start_dt = end_dt - timedelta(days=30)
    return state.templates.TemplateResponse(
        "backtest.html",
        {
            "request": request,
            "app_version": APP_VERSION,
            "version": int(time.time()),
            "default_start": start_dt.isoformat(),
            "default_end": end_dt.isoformat(),
        },
    )
