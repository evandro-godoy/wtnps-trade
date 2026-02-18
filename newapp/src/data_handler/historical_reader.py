"""Historical data reader with database-first strategy.

Provides `load_range` which attempts to read candles + indicators from the
AssetsRates table; if coverage is insufficient it fetches missing data via
MetaTrader provider and ingests them before returning a complete DataFrame.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from newapp.src.database.db import get_db, init_database
from newapp.src.database.repository import AssetsRatesRepository
from newapp.src.database.ingest_historical import map_timeframe_str_to_seconds, ingest_range
from newapp.src.data_handler.provider import MetaTraderProvider

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')

# ---------------------------------------------------------------------------
# Coverage utilities
# ---------------------------------------------------------------------------

def _expected_candle_count(start_dt: datetime, end_dt: datetime, timeframe_minutes: int) -> int:
    """Estimate expected number of candles given timeframe.

    Inclusive start/end day boundaries.
    """
    total_minutes = int((end_dt - start_dt).total_seconds() // 60)
    if timeframe_minutes <= 0:
        return 0
    return total_minutes // timeframe_minutes + 1


def _compute_coverage(df: pd.DataFrame, start_dt: datetime, end_dt: datetime, timeframe_minutes: int) -> float:
    """Compute coverage ratio (present / expected)."""
    if df.empty:
        return 0.0
    expected = _expected_candle_count(start_dt, end_dt, timeframe_minutes)
    if expected == 0:
        return 0.0
    return min(1.0, len(df) / expected)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_range(
    symbol: str,
    timeframe_str: str,
    start: str,
    end: str,
    min_coverage: float = 0.95,
    auto_fill: bool = True,
    allow_enrich: bool = True
) -> pd.DataFrame:
    """Load historical candles + indicators for a given range.

    Strategy:
        1. Attempt to read from database (AssetsRates)
        2. Evaluate coverage
        3. If insufficient and auto_fill=True: ingest missing range
        4. Re-read and return consolidated DataFrame

    Args:
        symbol: Asset symbol
        timeframe_str: Timeframe string (M5, H1)
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        min_coverage: Desired minimum coverage ratio before triggering ingest
        auto_fill: If True, perform ingest when coverage < min_coverage
        allow_enrich: Pass-through to ingestion (enrich indicadores)

    Returns:
        DataFrame indexed by time with OHLCV + indicators columns
    """
    init_database()

    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        return pd.DataFrame()

    if end_dt < start_dt:
        logger.error("End date precedes start date")
        return pd.DataFrame()

    timeframe_seconds = map_timeframe_str_to_seconds(timeframe_str)

    with next(get_db()) as db_session:  # type: ignore
        db_df = AssetsRatesRepository.get_rates_range(
            db_session,
            symbol,
            timeframe_seconds,
            start_dt,
            end_dt + timedelta(hours=23, minutes=59)  # include end day fully
        )

    coverage = _compute_coverage(db_df, start_dt, end_dt, timeframe_seconds)
    logger.info(f"Coverage {coverage:.2%} for {symbol} {timeframe_str} {start}->{end}")

    if coverage < min_coverage and auto_fill:
        logger.info("Coverage below threshold; triggering ingestion.")
        ingest_range(symbol, timeframe_str, start, end, allow_enrich=allow_enrich)
        with next(get_db()) as db_session:  # type: ignore
            db_df = AssetsRatesRepository.get_rates_range(
                db_session,
                symbol,
                timeframe_seconds,
                start_dt,
                end_dt + timedelta(hours=23, minutes=59)
            )
        coverage = _compute_coverage(db_df, start_dt, end_dt, timeframe_seconds)
        logger.info(f"Post-ingest coverage {coverage:.2%}")

    # Attempt indicator fetch if indicators absent
    missing_indicators = [c for c in ['ema_9', 'sma_20', 'sma_50', 'sma_200'] if c not in db_df.columns]
    if missing_indicators:
        logger.info("Indicators missing; performing selective enrich in-memory.")
        from newapp.src.database.ingest_historical import enrich_indicators
        try:
            db_df = enrich_indicators(db_df)
        except Exception as e:
            logger.warning(f"Indicator enrichment failed: {e}")

    return db_df.sort_index()

__all__ = ["load_range"]
