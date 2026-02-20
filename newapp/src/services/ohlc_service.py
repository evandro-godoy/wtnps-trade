from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from newapp.src.data_handler.hybrid_data_loader import get_hybrid_candles

logger = logging.getLogger(__name__)


def get_recent_ohlc(
    symbol: str,
    timeframe: str,
    limit: int,
    provider: Any,
    db: Session | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> pd.DataFrame:
    """Retrieve recent OHLC bars using DB-first hybrid strategy."""
    try:
        if db is not None:
            df = get_hybrid_candles(db, symbol, timeframe, limit, background_tasks)
            if df.empty:
                logger.warning(
                    "Hybrid loader returned empty DataFrame for %s %s", symbol, timeframe
                )
            return df

        df = provider.get_latest_candles(
            ticker=symbol,
            timeframe=timeframe,
            count=limit,
        )
        if df.empty:
            logger.warning("Provider returned empty DataFrame for %s %s", symbol, timeframe)
        return df
    except Exception as exc:
        logger.error("Error fetching OHLC data: %s", exc)
        return pd.DataFrame()


def build_ohlc_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert OHLC dataframe into JSON-serializable records."""
    records: list[dict[str, Any]] = []
    for ts, row in df.iterrows():
        records.append(
            {
                "time": ts.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"])
                if "volume" in row and not pd.isna(row["volume"])
                else 0,
            }
        )
    return records
