from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from newapp.configs.config import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
from newapp.src.api.routers.backtest import map_timeframe_to_int
from newapp.src.backtest.engine import BacktestConfig, BacktestEngine
from newapp.src.database import get_session_factory

router = APIRouter()


@router.websocket("/ws/backtest")
async def websocket_backtest(websocket: WebSocket):
    await websocket.accept()
    db = None
    try:
        msg = await websocket.receive_text()
        params = json.loads(msg)

        if params.get("action") != "start":
            await websocket.send_json({"type": "error", "message": "Expected action=start"})
            return

        symbol = params.get("symbol", DEFAULT_SYMBOL)
        timeframe = params.get("timeframe", DEFAULT_TIMEFRAME)
        start = params.get("start")
        end = params.get("end")
        initial_capital = float(params.get("initial_capital", 100000.0))
        position_size = float(params.get("position_size", 1.0))
        update_interval = int(params.get("update_interval", 5))

        now = datetime.now(timezone.utc)
        end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) if end else now
        start_dt = (
            datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
            if start
            else end_dt - pd.Timedelta(days=30)
        )

        if start_dt >= end_dt:
            await websocket.send_json({"type": "error", "message": "start must be before end"})
            return

        session_factory = get_session_factory()
        db = session_factory()

        engine = BacktestEngine(
            db,
            BacktestConfig(
                symbol=symbol,
                timeframe_int=map_timeframe_to_int(timeframe),
                timeframe_str=timeframe,
                start_date=start_dt,
                end_date=end_dt,
                initial_capital=initial_capital,
                position_size=position_size,
            ),
        )

        engine._load_prices()
        if engine.df is None or engine.df.empty:
            await websocket.send_json({"type": "error", "message": "No data for range"})
            return

        candles = []
        for ts, row in engine.df.iterrows():
            candles.append(
                {
                    "time": ts.isoformat(),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                }
            )

        await websocket.send_json(
            {
                "type": "init",
                "symbol": symbol,
                "timeframe": timeframe,
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "candles": candles,
                "total": len(candles),
            }
        )

        async def send_snapshot(snapshot: dict):
            await websocket.send_json(snapshot)

        await engine.run_backtest_stream(send_snapshot, update_interval=update_interval)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        if db is not None:
            db.close()
        try:
            await websocket.close()
        except Exception:
            pass
