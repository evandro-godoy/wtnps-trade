from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from newapp.configs.config import DEFAULT_LIMIT, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, MAX_LIMIT
from newapp.src.api.dependencies import get_state_from_request
from newapp.src.data_handler.hybrid_data_loader import get_hybrid_candles
from newapp.src.database import get_db
from newapp.src.database.repository import MarketAnalysisRepository
from newapp.src.services.ohlc_service import build_ohlc_records

router = APIRouter()


@router.get("/api/ohlc", response_class=JSONResponse)
async def api_ohlc(
    request: Request,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> dict[str, Any]:
    if limit <= 0 or limit > MAX_LIMIT:
        raise HTTPException(status_code=400, detail=f"limit deve estar entre 1 e {MAX_LIMIT}")

    df = get_hybrid_candles(db, symbol, timeframe, limit, background_tasks)
    records = build_ohlc_records(df)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(records),
        "latest": records[-1] if records else None,
        "data": records,
        "source": "Hybrid (DB + Provider)" if not df.empty else "No Data",
    }


@router.get("/api/analysis", response_class=JSONResponse)
async def api_analysis(
    request: Request,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> dict[str, Any]:
    if limit <= 0 or limit > MAX_LIMIT:
        raise HTTPException(status_code=400, detail=f"limit deve estar entre 1 e {MAX_LIMIT}")

    df = get_hybrid_candles(db, symbol, timeframe, limit, background_tasks)
    if df.empty:
        raise HTTPException(status_code=503, detail="Dados de mercado não disponíveis no momento")

    state = get_state_from_request(request)
    context = state.market_analyzer.analyze(df)
    timestamp = df.index[-1]

    try:
        MarketAnalysisRepository.save_analysis(db, symbol, timeframe, timestamp, context, len(df))
    except Exception:
        pass

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles_analyzed": len(df),
        "timestamp": timestamp.isoformat(),
        "analysis": context,
    }


@router.get("/api/combined", response_class=JSONResponse)
@router.get("/api/ohlc-with-analysis", response_class=JSONResponse)
async def api_combined(
    request: Request,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> dict[str, Any]:
    if limit <= 0 or limit > MAX_LIMIT:
        raise HTTPException(status_code=400, detail=f"limit deve estar entre 1 e {MAX_LIMIT}")

    df = get_hybrid_candles(db, symbol, timeframe, limit, background_tasks)
    if df.empty:
        raise HTTPException(status_code=503, detail="Dados de mercado não disponíveis no momento")

    state = get_state_from_request(request)
    records = build_ohlc_records(df)
    context = state.market_analyzer.analyze(df)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(records),
        "timestamp": df.index[-1].isoformat() if not df.empty else None,
        "latest": records[-1] if records else None,
        "ohlc": records,
        "analysis": context,
    }
