"""Test database connection and schema creation.

Run this script to verify SQL Server connection and initialize database schema.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


def test_connection():
    """Test basic database connection."""
    logger.info("=" * 60)
    logger.info("Testing Database Connection...")
    logger.info("=" * 60)
    
    try:
        from newapp.src.database.db import get_engine, get_connection_string, DB_BACKEND
        
        # Show connection string (without password)
        conn_str = get_connection_string()
        logger.info(f"Backend: {DB_BACKEND}")
        logger.info(f"Connection string: {conn_str[:100]}...")
        
        # Get engine
        engine = get_engine()
        
        # Test connection with backend-specific query
        with engine.connect() as conn:
            from sqlalchemy import text
            
            if DB_BACKEND.lower() == 'sqlite':
                result = conn.execute(text("SELECT sqlite_version() AS version"))
                version = result.fetchone()[0]
                logger.info(f"✅ Connected to SQLite")
                logger.info(f"Version: {version}")
            else:
                result = conn.execute(text("SELECT @@VERSION AS version"))
                version = result.fetchone()[0]
                logger.info(f"✅ Connected to SQL Server")
                logger.info(f"Version: {version[:80]}...")
            
        logger.info("✅ Connection test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"❌ Connection test FAILED: {e}")
        logger.error(f"Check environment variables:")
        logger.error(f"  - WTNPS_DB_BACKEND (current: {DB_BACKEND})")
        if DB_BACKEND.lower() == 'sqlserver':
            logger.error(f"  - WTNPS_DB_SERVER")
            logger.error(f"  - WTNPS_DB_NAME")
            logger.error(f"  - WTNPS_DB_TRUSTED_CONNECTION")
        import traceback
        traceback.print_exc()
        return False


def test_schema_creation():
    """Test database schema creation."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Schema Creation...")
    logger.info("=" * 60)
    
    try:
        from newapp.src.database.db import init_database, get_engine, DB_BACKEND
        from sqlalchemy import inspect, text
        
        # Initialize schema
        init_database()
        logger.info("✅ Schema initialized")
        
        # Verify tables using SQLAlchemy inspector (backend-agnostic)
        engine = get_engine()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f"Found {len(tables)} tables:")
        for table in sorted(tables):
            logger.info(f"  - {table}")
        
        # Verify expected tables exist
        expected_tables = {'ohlcv_data', 'technical_indicators', 'market_analysis', 'data_provider_log'}
        missing = expected_tables - set(tables)
        
        if missing:
            logger.error(f"Missing tables: {missing}")
            return False
        
        logger.info("✅ Schema creation test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"❌ Schema creation test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crud_operations():
    """Test CRUD operations with sample data."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing CRUD Operations...")
    logger.info("=" * 60)
    
    try:
        import pandas as pd
        from newapp.src.database import get_session_factory
        from newapp.src.database.repository import (
            OHLCVRepository,
            MarketAnalysisRepository,
            DataProviderLogRepository,
        )
        
        SessionLocal = get_session_factory()
        db = SessionLocal()
        
        # Create sample DataFrame
        sample_data = pd.DataFrame({
            'open': [100.0, 101.0, 102.0],
            'high': [101.5, 102.5, 103.5],
            'low': [99.5, 100.5, 101.5],
            'close': [101.0, 102.0, 103.0],
            'volume': [1000, 1500, 2000],
        }, index=pd.date_range(start='2025-11-22 10:00', periods=3, freq='5min'))
        
        # Test OHLCV insert
        logger.info("Testing OHLCV insert...")
        count = OHLCVRepository.save_dataframe(db, sample_data, "TEST$", "M5")
        logger.info(f"✅ Inserted {count} OHLCV records")
        
        # Test OHLCV query
        logger.info("Testing OHLCV query...")
        df = OHLCVRepository.get_latest_candles(db, "TEST$", "M5", limit=10)
        logger.info(f"✅ Retrieved {len(df)} OHLCV records")
        
        # Test Market Analysis insert
        logger.info("Testing Market Analysis insert...")
        sample_analysis = {
            'trend': {'direction': 'ALTA', 'strength': 0.75},
            'levels': {'supports': [99.0, 98.5], 'resistances': [104.0, 105.0]},
            'price_action': {'patterns': ['BULLISH_ENGULFING']},
            'rsi': 65.5,
            'moving_averages': {'ema9': 101.0, 'sma20': 100.0, 'sma50': 99.0}
        }
        analysis = MarketAnalysisRepository.save_analysis(
            db, "TEST$", "M5", datetime.now(), sample_analysis, 100
        )
        logger.info(f"✅ Saved market analysis (ID: {analysis.id})")
        
        # Test Data Provider Log
        logger.info("Testing Data Provider Log...")
        log = DataProviderLogRepository.log_operation(
            db, "TEST$", "M5", "MT5", 500, success=True
        )
        logger.info(f"✅ Logged provider operation (ID: {log.id})")
        
        db.close()
        logger.info("✅ CRUD operations test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"❌ CRUD operations test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_data():
    """Remove test data."""
    logger.info("\n" + "=" * 60)
    logger.info("Cleaning up test data...")
    logger.info("=" * 60)
    
    try:
        from newapp.src.database import get_engine
        from sqlalchemy import text
        
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM ohlcv_data WHERE symbol = 'TEST$'"))
            conn.execute(text("DELETE FROM market_analysis WHERE symbol = 'TEST$'"))
            conn.execute(text("DELETE FROM data_provider_log WHERE symbol = 'TEST$'"))
            conn.commit()
        
        logger.info("✅ Test data cleaned up")
        return True
        
    except Exception as e:
        logger.error(f"❌ Cleanup FAILED: {e}")
        return False


if __name__ == '__main__':
    results = []
    
    # Run tests
    results.append(("Connection", test_connection()))
    
    if results[-1][1]:  # Only proceed if connection succeeded
        results.append(("Schema Creation", test_schema_creation()))
        results.append(("CRUD Operations", test_crud_operations()))
        results.append(("Cleanup", cleanup_test_data()))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        logger.info("\n🎉 All tests PASSED! Database is ready.")
        sys.exit(0)
    else:
        logger.error("\n❌ Some tests FAILED. Check logs above.")
        sys.exit(1)
