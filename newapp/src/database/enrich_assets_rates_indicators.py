"""Batch enrichment of missing indicators in AssetsRates.

Updates only indicator columns (ema_9, sma_20, sma_50, sma_200) without modifying
OHLCV values. Supports overwrite mode to recalculate all indicators or default
mode that fills only null/zero values.

Usage:
    poetry run python newapp\src\database\enrich_assets_rates_indicators.py --symbol WDO$ --timeframe M5
    poetry run python newapp\src\database\enrich_assets_rates_indicators.py --symbol WDO$ --timeframe M5 --overwrite

Optional date filters (reduce processing window):
    --start 2024-01-01 --end 2024-06-01
If provided, only indicators for candles in range are recalculated/filled.
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from newapp.src.database.db import get_db, init_database
from newapp.src.database.repository import AssetsRatesRepository
from newapp.src.database.ingest_historical import map_timeframe_str_to_seconds
from newapp.src.database.models import AssetsRates
from sqlalchemy import and_

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich missing indicators in AssetsRates table.")
    parser.add_argument("--symbol", required=True, help="Asset symbol (e.g., WDO$)")
    parser.add_argument("--timeframe", required=True, help="Timeframe string (e.g., M5, H1)")
    parser.add_argument("--start", required=False, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=False, help="End date YYYY-MM-DD")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing indicator values")
    return parser.parse_args()


def _filter_by_range(db: Session, symbol: str, timeframe: int, start: Optional[str], end: Optional[str]):
    """Return count of rows within optional range for logging."""
    query = db.query(AssetsRates).filter(and_(AssetsRates.symbol == symbol, AssetsRates.timeframe == timeframe))
    if start:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        query = query.filter(AssetsRates.timestamp >= start_dt)
    if end:
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        query = query.filter(AssetsRates.timestamp <= end_dt)
    return query.count()


def enrich(symbol: str, timeframe_str: str, start: Optional[str], end: Optional[str], overwrite: bool) -> int:
    init_database()
    timeframe_seconds = map_timeframe_str_to_seconds(timeframe_str)
    with next(get_db()) as db:  # type: ignore
        if start or end:
            total = _filter_by_range(db, symbol, timeframe_seconds, start, end)
            logger.info(f"Rows in selected range: {total}")
            # For range-limited enrichment, we temporarily select subset and build dataframe manually
            # Fetch subset records
            query = db.query(AssetsRates).filter(and_(AssetsRates.symbol == symbol, AssetsRates.timeframe == timeframe_seconds))
            if start:
                start_dt = datetime.strptime(start, "%Y-%m-%d")
                query = query.filter(AssetsRates.timestamp >= start_dt)
            if end:
                end_dt = datetime.strptime(end, "%Y-%m-%d")
                query = query.filter(AssetsRates.timestamp <= end_dt)
            # Build DataFrame for indicator computation
            records = query.order_by(AssetsRates.timestamp).all()
            if not records:
                logger.info("No records found in specified range.")
                return 0
            import pandas as pd
            from newapp.src.utils.indicators import compute_indicator_dict
            
            df = pd.DataFrame([
                {'time': r.timestamp, 'close': r.close} for r in records
            ])
            df.set_index('time', inplace=True)
            df = df.sort_index()
            
            # Compute indicators using centralized function
            indicators = compute_indicator_dict(df['close'])
            ema9 = indicators['ema_9']
            sma20 = indicators['sma_20']
            sma50 = indicators['sma_50']
            sma200 = indicators['sma_200']
            updated_fields = 0
            for r in records:
                ts = r.timestamp
                def should_update(current, new):
                    return overwrite or current is None or current == 0
                if should_update(r.ema_9, ema9.loc[ts]):
                    r.ema_9 = float(ema9.loc[ts]); updated_fields += 1
                if should_update(r.sma_20, sma20.loc[ts]):
                    r.sma_20 = float(sma20.loc[ts]); updated_fields += 1
                if should_update(r.sma_50, sma50.loc[ts]):
                    r.sma_50 = float(sma50.loc[ts]); updated_fields += 1
                if should_update(r.sma_200, sma200.loc[ts]):
                    r.sma_200 = float(sma200.loc[ts]); updated_fields += 1
            db.commit()
            logger.info(f"Range enrichment completed. Field updates: {updated_fields}")
            return updated_fields
        else:
            # Full enrichment using repository helper
            updated = AssetsRatesRepository.enrich_missing_indicators(db, symbol, timeframe_seconds, overwrite=overwrite)
            return updated


def main():
    args = _parse_args()
    updated = enrich(args.symbol, args.timeframe, args.start, args.end, args.overwrite)
    logger.info(f"Enrichment finished. Total field updates: {updated}")


if __name__ == "__main__":
    main()
