from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from newapp.configs.config import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
from newapp.src.backtest.engine import BacktestConfig, BacktestEngine
from newapp.src.database import get_db
from newapp.src.database.models import BacktestRun, BacktestTrade

router = APIRouter()


def map_timeframe_to_int(tf: str) -> int:
    """Map timeframe string to timeframe in seconds."""
    mapping_seconds = {
        "M1": 60,
        "M5": 5 * 60,
        "M15": 15 * 60,
        "M30": 30 * 60,
        "H1": 60 * 60,
        "H4": 4 * 60 * 60,
        "D1": 24 * 60 * 60,
        "W1": 7 * 24 * 60 * 60,
        "MN1": 30 * 24 * 60 * 60,
    }
    return mapping_seconds.get(tf.upper(), 5 * 60)


@router.post("/api/backtest/run")
async def api_backtest_run(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    start: str | None = None,
    end: str | None = None,
    initial_capital: float = 100_000.0,
    position_size: float = 1.0,
    db: Session = Depends(get_db),
) -> JSONResponse:
    try:
        now = datetime.now(timezone.utc)
        end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) if end else now
        start_dt = (
            datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
            if start
            else end_dt - pd.Timedelta(days=90)
        )

        if start_dt >= end_dt:
            raise HTTPException(status_code=400, detail="start must be before end")

        cfg = BacktestConfig(
            symbol=symbol,
            timeframe_int=map_timeframe_to_int(timeframe),
            timeframe_str=timeframe,
            start_date=start_dt,
            end_date=end_dt,
            initial_capital=initial_capital,
            position_size=position_size,
        )
        summary = BacktestEngine(db, cfg).run_backtest()
        return JSONResponse(summary)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/backtest/run/{run_id}")
async def api_backtest_run_get(run_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    trades = (
        db.query(BacktestTrade)
        .filter(BacktestTrade.run_id == run_id)
        .order_by(BacktestTrade.entry_time)
        .all()
    )
    trades_payload = []
    for trade in trades:
        trades_payload.append(
            {
                "id": trade.id,
                "entry_time": trade.entry_time.isoformat(),
                "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
                "direction": trade.direction,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "pnl": trade.pnl,
                "return_pct": trade.return_pct,
                "reason_exit": trade.reason_exit,
            }
        )

    return JSONResponse(
        {
            "run_id": run.id,
            "symbol": run.symbol,
            "timeframe": run.timeframe,
            "start_date": run.start_date.isoformat(),
            "end_date": run.end_date.isoformat(),
            "strategy": run.strategy,
            "initial_capital": run.initial_capital,
            "final_capital": run.final_capital,
            "net_profit": run.net_profit,
            "total_trades": run.total_trades,
            "wins": run.wins,
            "losses": run.losses,
            "win_rate": run.win_rate,
            "profit_factor": run.profit_factor,
            "max_drawdown": run.max_drawdown,
            "avg_trade_return": run.avg_trade_return,
            "trades": trades_payload,
        }
    )
