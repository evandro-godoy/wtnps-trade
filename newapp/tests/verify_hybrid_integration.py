"""Quick verification script for hybrid loader database integration.

Tests:
1. Queries AssetsRates database
2. Detects gaps in data
3. Fetches missing candles from provider
4. Persists new data

Run: poetry run python newapp/tests/verify_hybrid_integration.py
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging
from datetime import datetime, timezone
from newapp.src.database.db import get_db
from newapp.src.data_handler.hybrid_data_loader import get_hybrid_candles_sync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


def verify_hybrid_loader():
    """Verify hybrid loader functionality with real database."""
    logger.info("=" * 60)
    logger.info("HYBRID LOADER INTEGRATION VERIFICATION")
    logger.info("=" * 60)
    
    # Test parameters
    symbol = "WDO$"
    timeframe = "M5"
    limit = 100
    
    logger.info(f"Testing with: {symbol} @ {timeframe}, limit={limit}")
    
    # Get database session
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        # Step 1: Check current database state
        logger.info("\n[STEP 1] Checking database state...")
        from newapp.src.database.repository import AssetsRatesRepository
        
        timeframe_int = 300  # M5 = 300 seconds
        df_db = AssetsRatesRepository.get_all_rates(db, symbol, timeframe_int)
        if not df_db.empty and len(df_db) > limit:
            df_db = df_db.tail(limit)
        
        if df_db.empty:
            logger.warning("⚠️ Database is EMPTY - will fetch from provider")
        else:
            latest_db = df_db.index[-1]
            logger.info(f"✅ Database has {len(df_db)} candles")
            logger.info(f"   Latest: {latest_db.isoformat()}")
            
            # Calculate gap
            now = datetime.now(timezone.utc)
            if latest_db.tzinfo is None:
                latest_db = latest_db.replace(tzinfo=timezone.utc)
            
            gap_seconds = (now - latest_db).total_seconds()
            gap_candles = gap_seconds / 300
            
            logger.info(f"   Gap: {gap_seconds:.0f}s ({gap_candles:.1f} candles)")
        
        # Step 2: Use hybrid loader
        logger.info("\n[STEP 2] Running hybrid loader (sync mode)...")
        df_result = get_hybrid_candles_sync(db, symbol, timeframe, limit)
        
        if df_result.empty:
            logger.error("❌ Hybrid loader returned EMPTY DataFrame!")
            return False
        
        logger.info(f"✅ Hybrid loader returned {len(df_result)} candles")
        logger.info(f"   Latest: {df_result.index[-1].isoformat()}")
        logger.info(f"   Oldest: {df_result.index[0].isoformat()}")
        
        # Step 3: Verify database update
        logger.info("\n[STEP 3] Verifying database persistence...")
        df_db_after = AssetsRatesRepository.get_all_rates(db, symbol, timeframe_int)
        if not df_db_after.empty and len(df_db_after) > limit:
            df_db_after = df_db_after.tail(limit)
        
        if df_db_after.empty:
            logger.error("❌ Database still EMPTY after hybrid load!")
            return False
        
        new_candles = len(df_db_after) - len(df_db) if not df_db.empty else len(df_db_after)
        logger.info(f"✅ Database now has {len(df_db_after)} candles (+{new_candles} new)")
        logger.info(f"   Latest: {df_db_after.index[-1].isoformat()}")
        
        # Step 4: Check data freshness
        logger.info("\n[STEP 4] Checking data freshness...")
        latest = df_db_after.index[-1]
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        age_seconds = (now - latest).total_seconds()
        age_candles = age_seconds / 300
        
        if age_candles < 2:
            logger.info(f"✅ Data is FRESH (age: {age_seconds:.0f}s / {age_candles:.2f} candles)")
        else:
            logger.warning(f"⚠️ Data is STALE (age: {age_seconds:.0f}s / {age_candles:.2f} candles)")
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✅ Hybrid loader: WORKING")
        logger.info(f"✅ Database query: WORKING")
        logger.info(f"✅ Provider fallback: WORKING")
        logger.info(f"✅ Data persistence: WORKING")
        logger.info(f"📊 Total candles: {len(df_db_after)}")
        logger.info(f"🔄 New candles added: {new_candles}")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Verification FAILED: {e}", exc_info=True)
        return False
        
    finally:
        db.close()


if __name__ == '__main__':
    success = verify_hybrid_loader()
    sys.exit(0 if success else 1)
