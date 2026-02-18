"""Historical data ingestion script for AssetsRates table.

Fetches OHLCV data from configured provider (MetaTrader5 or fallback synthetic) and
persists into SQLite/SQL Server through AssetsRatesRepository with partial immutability.

Usage (PowerShell):
    poetry run python newapp/src/database/ingest_historical.py --symbol WDO$ --timeframe M5 --start 2024-01-01 --end 2024-01-10

Environment variables:
    WTNPS_DB_BACKEND      -> 'sqlite' (default) or 'sqlserver'
    WTNPS_SQLITE_PATH     -> Absolute path to database file (recommended)

The script calculates minimal indicators (EMA9, SMA20, SMA50, SMA200) before persistence.
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

# Ensure project root is on sys.path when executed as a script
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from newapp.src.database.db import get_db, init_database
from newapp.src.database.repository import AssetsRatesRepository
from newapp.src.data_handler.provider import MetaTraderProvider

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')

# ---------------------------------------------------------------------------
# Timeframe mapping utilities (store as SECONDS for compatibility with existing data)
# ---------------------------------------------------------------------------
_TIMEFRAME_SECONDS_MAP = {
    'M1': 60,
    'M5': 5 * 60,
    'M15': 15 * 60,
    'M30': 30 * 60,
    'H1': 60 * 60,
    'H4': 4 * 60 * 60,
    'D1': 24 * 60 * 60,
    'W1': 7 * 24 * 60 * 60,
    'MN1': 30 * 24 * 60 * 60,  # Approx month
}

def map_timeframe_str_to_seconds(tf: str) -> int:
    """Map timeframe string to seconds integer (persisted representation).

    Args:
        tf: Timeframe string like 'M5', 'H1'.
    Returns:
        Seconds representation (int).
    Raises:
        ValueError: if timeframe unsupported.
    """
    normalized = tf.upper()
    if normalized not in _TIMEFRAME_SECONDS_MAP:
        raise ValueError(f"Unsupported timeframe '{tf}'. Valid: {list(_TIMEFRAME_SECONDS_MAP)}")
    return _TIMEFRAME_SECONDS_MAP[normalized]

# ---------------------------------------------------------------------------
# Indicator calculations (delegated to centralized utils)
# ---------------------------------------------------------------------------

def enrich_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate basic indicators for ingestion if absent.

    Adds columns: ema_9, sma_20, sma_50, sma_200.
    Skips recalculation if column already exists.
    """
    from newapp.src.utils.indicators import enrich_indicators_from_close
    return enrich_indicators_from_close(df, overwrite=False)

# ---------------------------------------------------------------------------
# Data acquisition
# ---------------------------------------------------------------------------

def fetch_provider_data(symbol: str, timeframe_str: str, start: str, end: str) -> pd.DataFrame:
    """Fetch data from MetaTrader provider (currently only MT5 supported).

    Args:
        symbol: Asset symbol (e.g., 'WDO$').
        timeframe_str: String timeframe (e.g., 'M5').
        start: Start date (YYYY-MM-DD).
        end: End date (YYYY-MM-DD).
    Returns:
        DataFrame indexed by UTC timestamps.
    """
    provider = MetaTraderProvider()
    if not provider.is_connected():
        logger.error("MetaTrader provider not connected. Aborting fetch.")
        return pd.DataFrame()

    # Convert timeframe to MT5 constant via provider private map (reuse logic)
    mt5_tf = provider._get_mt5_timeframe(timeframe_str)  # type: ignore (access by design here)
    if mt5_tf is None:
        logger.error(f"Cannot map timeframe {timeframe_str} to MT5 constant.")
        return pd.DataFrame()

    df = provider.get_data(symbol, start, end, mt5_tf)
    if df.empty:
        logger.warning("Provider returned empty DataFrame.")
        return df

    # Normalize index timezone: ensure naive UTC for DB
    if isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is not None:
            df.index = df.index.tz_convert('UTC').tz_localize(None)
    return df

# ---------------------------------------------------------------------------
# Ingestion core
# ---------------------------------------------------------------------------

def ingest_range(symbol: str, timeframe_str: str, start: str, end: str, allow_enrich: bool = True) -> int:
    """Ingest historical data range into AssetsRates.

    Args:
        symbol: Asset symbol.
        timeframe_str: Timeframe string (e.g., 'M5').
        start: Start date (YYYY-MM-DD).
        end: End date (YYYY-MM-DD).
        allow_enrich: Whether to enrich indicators for existing records.
    Returns:
        Number of records inserted/updated.
    """
    timeframe_seconds = map_timeframe_str_to_seconds(timeframe_str)
    df = fetch_provider_data(symbol, timeframe_str, start, end)
    if df.empty:
        logger.info("No data fetched; nothing to ingest.")
        return 0

    # Basic columns normalization
    for col in ['open', 'high', 'low', 'close', 'tick_volume','volume']:
        if col not in df.columns:
            raise ValueError(f"Column '{col}' missing from provider data")

    # Add tick_volume/spread placeholder if absent
    if 'tick_volume' not in df.columns:
        df['tick_volume'] = 0
    if 'spread' not in df.columns:
        df['spread'] = 0

    df = enrich_indicators(df)

    # Persist
    with next(get_db()) as db_session:  # type: ignore
        count = AssetsRatesRepository.save_rates_dataframe(
            db_session,
            df,
            symbol,
            timeframe_seconds,
            timeframe_str=timeframe_str,
            allow_enrich=allow_enrich
        )
    logger.info(f"Ingest completed: {count} records for {symbol} {timeframe_str} ({start} -> {end})")
    return count

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest historical OHLCV data into database.")
    parser.add_argument("--symbol", required=True, help="Asset symbol (e.g., WDO$)")
    parser.add_argument("--timeframe", required=True, help="Timeframe string (e.g., M5, H1)")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--no-enrich", action="store_true", help="Disable enrichment for existing records")
    return parser.parse_args()


def main():
    args = _parse_args()

    # Validate dates
    try:
        datetime.strptime(args.start, "%Y-%m-%d")
        datetime.strptime(args.end, "%Y-%m-%d")
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        raise SystemExit(1)

    init_database()  # Ensure schema exists
    ingest_range(
        symbol=args.symbol,
        timeframe_str=args.timeframe,
        start=args.start,
        end=args.end,
        allow_enrich=not args.no_enrich
    )


if __name__ == "__main__":
    main()
