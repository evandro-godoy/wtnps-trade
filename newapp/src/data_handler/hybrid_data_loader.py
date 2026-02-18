"""Hybrid data loader with database-first strategy and async persistence.

Provides intelligent data loading:
1. Query AssetsRates database first
2. Detect gaps (missing recent candles)
3. Fetch missing data via HybridProvider (MT5 → Cache → Synthetic)
4. Return data immediately for rendering
5. Persist new candles asynchronously to avoid blocking

Thread-safe and designed for low-latency web requests.
"""
from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timezone, timedelta, time
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from newapp.src.database.repository import AssetsRatesRepository
from newapp.src.data_handler.provider import get_default_provider

logger = logging.getLogger(__name__)

# Timeframe mapping: string -> integer (seconds)
TIMEFRAME_TO_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
    "W1": 604800,
    "MN1": 2592000,
}

# Horário de funcionamento B3: 09:00-18:00 
MARKET_OPEN_UTC = time(9, 0)   # 09:00 BRT
MARKET_CLOSE_UTC = time(18, 25)  # 18:25 BRT


def _get_timeframe_int(timeframe_str: str) -> int:
    """Convert timeframe string to integer (seconds).
    
    Args:
        timeframe_str: Timeframe string (M5, H1, etc.)
        
    Returns:
        Timeframe in seconds
    """
    return TIMEFRAME_TO_SECONDS.get(timeframe_str.upper(), 300)


def _is_market_open(dt: datetime) -> bool:
    """Check if market is open at given UTC time.
    
    B3 operates: 09:00-18:00 BRT (UTC-3) = 12:00-21:00 UTC, Mon-Fri.
    
    Args:
        dt: Datetime to check (UTC, tz-aware)
        
    Returns:
        True if market is open
    """
    # Check weekday (0=Monday, 6=Sunday)
    if dt.weekday() >= 5:  # Saturday or Sunday
        return False
    
    current_time = dt.time()
    return MARKET_OPEN_UTC <= current_time <= MARKET_CLOSE_UTC


def _get_expected_latest_time(timeframe_str: str) -> datetime:
    """Calculate expected latest candle time based on current UTC time.
    
    Rounds down to nearest timeframe boundary.
    If market is closed, returns last market close time.
    
    Args:
        timeframe_str: Timeframe string
        
    Returns:
        Expected latest candle timestamp (UTC, tz-aware)
    """
    now = datetime.now()
    now = now.replace(tzinfo=timezone.utc)
    tf_seconds = _get_timeframe_int(timeframe_str)
    
    # If market is closed, use last close time (18:25 BRT)
    if not _is_market_open(now):
        # Get today's close or most recent close
        close_today = datetime.combine(now.date(), MARKET_CLOSE_UTC, tzinfo=timezone.utc)
        
        if now < close_today:
            # Before today's open, use yesterday's close
            close_today -= timedelta(days=1)
            
        # Align to timeframe boundary
        timestamp_seconds = int(close_today.timestamp())
        aligned_seconds = (timestamp_seconds // tf_seconds) * tf_seconds
        return datetime.fromtimestamp(aligned_seconds, tz=timezone.utc)
    
    # Market is open: use current time aligned to timeframe
    timestamp_seconds = int(now.timestamp())
    aligned_seconds = (timestamp_seconds // tf_seconds) * tf_seconds
    
    return datetime.fromtimestamp(aligned_seconds, tz=timezone.utc)


async def _persist_candles_async(
    db_session: Session,
    df: pd.DataFrame,
    symbol: str,
    timeframe_int: int,
    timeframe_str: str
) -> None:
    """Persist candles to database asynchronously (background task).
    
    Args:
        db_session: SQLAlchemy session (must be created in this thread)
        df: DataFrame with OHLCV data
        symbol: Asset symbol
        timeframe_int: Timeframe in seconds
        timeframe_str: Timeframe string
    """
    try:
        # Run in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            AssetsRatesRepository.save_rates_dataframe,
            db_session,
            df,
            symbol,
            timeframe_int,
            timeframe_str,
            False  # allow_enrich=False for new data
        )
        logger.info(f"✅ Persisted {len(df)} candles to database (async)")
    except Exception as e:
        logger.error(f"❌ Failed to persist candles asynchronously: {e}")


def get_hybrid_candles(
    db: Session,
    symbol: str,
    timeframe_str: str,
    limit: int,
    background_tasks: Optional[any] = None
) -> pd.DataFrame:
    """Get candles with hybrid strategy: DB-first, provider fallback, async persist.
    
    Workflow:
    1. Query AssetsRates for last `limit` candles
    2. Check if latest DB candle is recent enough (< 1 timeframe old)
    3. If gap detected: fetch from provider (MT5 → Cache → Synthetic)
    4. Return combined data immediately (DB + fresh)
    5. Persist new candles in background (non-blocking)
    
    Args:
        db: SQLAlchemy session
        symbol: Asset symbol (e.g., "WDO$")
        timeframe_str: Timeframe string (e.g., "M5")
        limit: Number of candles requested
        background_tasks: FastAPI BackgroundTasks instance (optional)
        
    Returns:
        DataFrame with OHLCV data, timezone-aware index
    """
    timeframe_int = _get_timeframe_int(timeframe_str)
    
    logger.info(f"📊 Hybrid load for {symbol} {timeframe_str} | {timeframe_int} (limit={limit})")

    # Step 1: Query database
    df_db = AssetsRatesRepository.get_all_rates(db, symbol, timeframe_int)
    if not df_db.empty and len(df_db) > limit:
        df_db = df_db.tail(limit)  # Keep only last N candles
    
    # Step 2: Check for gaps
    expected_latest = _get_expected_latest_time(timeframe_str)
    gap_detected = False
    
    if df_db.empty:
        logger.info(f"📊 No data in database for {symbol} {timeframe_str}, fetching from provider...")
        gap_detected = True
    else:
        latest_db_time = df_db.index[-1]
        
        # Ensure timezone-aware comparison
        if latest_db_time.tzinfo is None:
            latest_db_time = latest_db_time.replace(tzinfo=timezone.utc)
        
        time_diff = (expected_latest - latest_db_time).total_seconds()
        gap_threshold = timeframe_int * 2  # Allow 2 candles tolerance
        
        # Normalize timestamp format for logging (remove tz suffix)
        latest_str = latest_db_time.strftime('%Y-%m-%dT%H:%M:%S')
        expected_str = expected_latest.strftime('%Y-%m-%dT%H:%M:%S')
        
        if time_diff > gap_threshold:
            # Check if market is currently open before flagging as gap
            logger.info(
                    f"📊 Gap detected :  DB latest={latest_str}, " 
                    f"expected={expected_str} (diff={time_diff}s)"
                )
            gap_detected = True
            
        else:
            logger.info(f"✅ Database data is fresh ({len(df_db)} candles, latest={latest_str})")
    
    # Step 3: Fetch missing data if gap detected
    df_new = pd.DataFrame()
    
    if gap_detected:
        provider = get_default_provider()
        
        try:
            # Fetch full limit from provider (ensures we have enough data)
            # df_provider = provider.get_latest_candles(
            #    ticker=symbol,
            #    timeframe=timeframe_str,
            #    count=limit
            #)

            # ajusta formato para mt5
            start_date = latest_db_time.strftime('%Y-%m-%d') 
            end_date = expected_latest.strftime('%Y-%m-%d')
            df_provider = provider.get_data(symbol, start_date, end_date, timeframe_str)
            
            if not df_provider.empty:
                # Identify truly new candles (not in DB)
                if df_db.empty:
                    df_new = df_provider
                else:
                    # Filter to only candles newer than latest DB entry
                    latest_db_time = df_db.index[-1]
                    if latest_db_time.tzinfo is None:
                        latest_db_time = latest_db_time.replace(tzinfo=timezone.utc)
                    
                    df_new = df_provider[df_provider.index > latest_db_time]
                
                if not df_new.empty:
                    logger.info(f"📥 Fetched {len(df_new)} new candles from provider")
                    
                    # Step 5: Persist asynchronously (non-blocking)
                    if background_tasks:
                        # FastAPI BackgroundTasks (preferred)
                        background_tasks.add_task(
                            AssetsRatesRepository.save_rates_dataframe,
                            db,
                            df_new,
                            symbol,
                            timeframe_int,
                            timeframe_str,
                            False
                        )
                        logger.info(f"📤 Queued {len(df_new)} candles for background persistence (FastAPI)")
                    else:
                        # Fallback: asyncio task (for non-FastAPI contexts)
                        try:
                            asyncio.create_task(
                                _persist_candles_async(db, df_new, symbol, timeframe_int, timeframe_str)
                            )
                            logger.info(f"📤 Created async task to persist {len(df_new)} candles")
                        except RuntimeError:
                            # No event loop, persist synchronously (blocking)
                            logger.warning("⚠️ No event loop, persisting synchronously")
                            AssetsRatesRepository.save_rates_dataframe(
                                db, df_new, symbol, timeframe_int, timeframe_str, False
                            )
                else:
                    logger.info("✅ Provider data already in database (no new candles)")
            else:
                logger.warning("⚠️ Provider returned empty DataFrame")
                
        except Exception as e:
            logger.error(f"❌ Error fetching from provider: {e}")
    
    # Step 4: Determine display data
    # To avoid visible gaps on the chart when a freshness gap is detected,
    # prefer provider-only tail(limit) for rendering. Still persist only truly new candles.
    df_result: pd.DataFrame
    if df_db.empty and df_new.empty:
        logger.warning(f"⚠️ No data available for {symbol} {timeframe_str}")
        return pd.DataFrame()
    
    if gap_detected:
        # When a gap is detected, display continuous provider data to avoid holes
        try:
            provider = get_default_provider()
            df_provider_display = provider.get_latest_candles(
                ticker=symbol,
                timeframe=timeframe_str,
                count=limit
            )
            if not df_provider_display.empty:
                # Normalize tz
                if df_provider_display.index.tz is None:
                    df_provider_display.index = df_provider_display.index.tz_localize('UTC')
                df_result = df_provider_display.tail(limit)
                result_latest = df_result.index[-1].strftime('%Y-%m-%dT%H:%M:%S') if not df_result.empty else 'N/A'
                logger.info(f"📊 Displaying provider-only data to avoid gaps: {len(df_result)} candles (latest={result_latest})")
            else:
                # Fallback to combined logic if provider failed
                logger.warning("⚠️ Provider display data empty; falling back to combined DB + new")
                if df_db.empty:
                    df_result = df_new.tail(limit)
                elif df_new.empty:
                    df_result = df_db.tail(limit)
                else:
                    if df_db.index.tz is None and df_new.index.tz is not None:
                        df_db.index = df_db.index.tz_localize('UTC')
                    elif df_db.index.tz is not None and df_new.index.tz is None:
                        df_new.index = df_new.index.tz_localize('UTC')
                    df_combined = pd.concat([df_db, df_new])
                    df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
                    df_result = df_combined.sort_index().tail(limit)
        except Exception as e:
            logger.error(f"❌ Error preparing provider-only display data: {e}")
            # Fallback to previous combined behavior
            if df_db.empty:
                df_result = df_new.tail(limit)
            elif df_new.empty:
                df_result = df_db.tail(limit)
            else:
                if df_db.index.tz is None and df_new.index.tz is not None:
                    df_db.index = df_db.index.tz_localize('UTC')
                elif df_db.index.tz is not None and df_new.index.tz is None:
                    df_new.index = df_new.index.tz_localize('UTC')
                df_combined = pd.concat([df_db, df_new])
                df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
                df_result = df_combined.sort_index().tail(limit)
    else:
        # No gap: use DB-only (fresh) or combined if any new was added
        if df_db.empty:
            df_result = df_new.tail(limit)
        elif df_new.empty:
            df_result = df_db.tail(limit)
        else:
            if df_db.index.tz is None and df_new.index.tz is not None:
                df_db.index = df_db.index.tz_localize('UTC')
            elif df_db.index.tz is not None and df_new.index.tz is None:
                df_new.index = df_new.index.tz_localize('UTC')
            df_combined = pd.concat([df_db, df_new])
            df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
            df_result = df_combined.sort_index().tail(limit)
    
    logger.info(f"📊 Returning {len(df_result)} candles (DB: {len(df_db)}, New: {len(df_new)})")
    return df_result


def get_hybrid_candles_sync(
    db: Session,
    symbol: str,
    timeframe_str: str,
    limit: int
) -> pd.DataFrame:
    """Synchronous version of get_hybrid_candles (for non-async contexts).
    
    Persists new data synchronously (may block briefly).
    Use only when FastAPI BackgroundTasks is unavailable.
    
    Args:
        db: SQLAlchemy session
        symbol: Asset symbol
        timeframe_str: Timeframe string
        limit: Number of candles
        
    Returns:
        DataFrame with OHLCV data
    """
    timeframe_int = _get_timeframe_int(timeframe_str)
    
    df_db = AssetsRatesRepository.get_all_rates(db, symbol, timeframe_int)
    if not df_db.empty and len(df_db) > limit:
        df_db = df_db.tail(limit)
    expected_latest = _get_expected_latest_time(timeframe_str)
    gap_detected = False
    
    if df_db.empty:
        gap_detected = True
    else:
        latest_db_time = df_db.index[-1]
        if latest_db_time.tzinfo is None:
            latest_db_time = latest_db_time.replace(tzinfo=timezone.utc)
        
        time_diff = (expected_latest - latest_db_time).total_seconds()
        if time_diff > timeframe_int * 2:
            gap_detected = True
    
    df_new = pd.DataFrame()
    
    if gap_detected:
        provider = get_default_provider()
        
        try:
            # ajusta formato para mt5
            start_date = latest_db_time.strftime('%Y-%m-%d') 
            end_date = expected_latest.strftime('%Y-%m-%d')
            
            df_provider = provider.get_data(symbol, start_date, end_date, timeframe_str)
            
            if not df_provider.empty:
                if df_db.empty:
                    df_new = df_provider
                else:
                    latest_db_time = df_db.index[-1]
                    if latest_db_time.tzinfo is None:
                        latest_db_time = latest_db_time.replace(tzinfo=timezone.utc)
                    df_new = df_provider[df_provider.index > latest_db_time]
                
                if not df_new.empty:
                    # Persist synchronously (blocking)
                    AssetsRatesRepository.save_rates_dataframe(
                        db, df_new, symbol, timeframe_int, timeframe_str, False
                    )
                    logger.info(f"✅ Persisted {len(df_new)} candles (sync)")
        except Exception as e:
            logger.error(f"❌ Error in sync fetch: {e}")
    
    # Combine results
    if df_db.empty and df_new.empty:
        return pd.DataFrame()
    elif df_db.empty:
        return df_new.tail(limit)
    elif df_new.empty:
        return df_db.tail(limit)
    else:
        # Ensure consistent timezone before concatenating
        if df_db.index.tz is None and df_new.index.tz is not None:
            df_db.index = df_db.index.tz_localize('UTC')
        elif df_db.index.tz is not None and df_new.index.tz is None:
            df_new.index = df_new.index.tz_localize('UTC')
        
        df_combined = pd.concat([df_db, df_new])
        df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
        return df_combined.sort_index().tail(limit)
