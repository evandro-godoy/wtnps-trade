"""Test script for newapp data provider.

Validates provider functionality and fallback chain.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging
from datetime import datetime, timedelta

from newapp.src.data_handler.provider import (
    get_default_provider,
    MetaTraderProvider,
    CacheProvider,
    SyntheticProvider,
    HybridProvider,
)
from newapp.configs.config import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, DEFAULT_LIMIT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


def test_synthetic_provider():
    """Test synthetic data generation."""
    logger.info("=" * 60)
    logger.info("Testing SyntheticProvider...")
    logger.info("=" * 60)
    
    provider = SyntheticProvider(seed=42)
    
    # Test get_latest_candles
    df = provider.get_latest_candles('WDO$', 'M5', 100)
    logger.info(f"✓ Generated {len(df)} candles")
    logger.info(f"  First timestamp: {df.index[0]}")
    logger.info(f"  Last timestamp: {df.index[-1]}")
    logger.info(f"  Columns: {list(df.columns)}")
    logger.info(f"  Price range: {df['close'].min():.2f} - {df['close'].max():.2f}")
    
    # Test get_data
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    df_hist = provider.get_data('WDO$', start_date, end_date, 'H1')
    logger.info(f"✓ Generated {len(df_hist)} historical candles (30 days, H1)")
    
    assert not df.empty, "DataFrame should not be empty"
    assert len(df) == 100, "Should have 100 candles"
    assert all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume']), "Missing columns"
    
    logger.info("✓ SyntheticProvider tests passed\n")


def test_cache_provider():
    """Test cache-based data loading."""
    logger.info("=" * 60)
    logger.info("Testing CacheProvider...")
    logger.info("=" * 60)
    
    provider = CacheProvider()
    
    # Try to load cached data
    df = provider.get_latest_candles('WDO', 'M5', 500)
    
    if df.empty:
        logger.warning("⚠ No cache files found (expected if fresh install)")
        logger.info("  Run 'poetry run python train_model.py' to populate cache")
    else:
        logger.info(f"✓ Loaded {len(df)} candles from cache")
        logger.info(f"  First timestamp: {df.index[0]}")
        logger.info(f"  Last timestamp: {df.index[-1]}")
        logger.info(f"  Price range: {df['close'].min():.2f} - {df['close'].max():.2f}")
    
    logger.info("✓ CacheProvider tests completed\n")


def test_mt5_provider():
    """Test MetaTrader5 connection."""
    logger.info("=" * 60)
    logger.info("Testing MetaTraderProvider...")
    logger.info("=" * 60)
    
    try:
        provider = MetaTraderProvider()
        
        if not provider.is_connected():
            logger.warning("⚠ MT5 not connected (expected in cloud/Linux)")
            logger.info("  Ensure MetaTrader 5 terminal is running on Windows")
        else:
            logger.info("✓ MT5 connected successfully")
            
            # Test data fetch
            df = provider.get_latest_candles('WDO', provider._get_mt5_timeframe('M5'), 10)
            
            if not df.empty:
                logger.info(f"✓ Fetched {len(df)} candles from MT5")
                logger.info(f"  Latest price: {df.iloc[-1]['close']:.2f}")
            else:
                logger.warning("⚠ No data returned from MT5")
    except Exception as e:
        logger.error(f"✗ MT5Provider error: {e}")
    
    logger.info("✓ MetaTraderProvider tests completed\n")


def test_hybrid_provider():
    """Test hybrid provider with fallback chain."""
    logger.info("=" * 60)
    logger.info("Testing HybridProvider (Fallback Chain)...")
    logger.info("=" * 60)
    
    provider = HybridProvider()
    
    # Test get_latest_candles
    df = provider.get_latest_candles(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, DEFAULT_LIMIT)
    
    logger.info(f"✓ Retrieved {len(df)} candles via fallback chain")
    logger.info(f"  First timestamp: {df.index[0]}")
    logger.info(f"  Last timestamp: {df.index[-1]}")
    logger.info(f"  Latest close: {df.iloc[-1]['close']:.2f}")
    
    # Test get_data
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    df_hist = provider.get_data(DEFAULT_SYMBOL, start_date, end_date, DEFAULT_TIMEFRAME)
    
    logger.info(f"✓ Retrieved {len(df_hist)} historical candles")
    
    assert not df.empty, "HybridProvider should always return data (synthetic fallback)"
    assert provider.is_connected(), "HybridProvider should always be connected"
    
    logger.info("✓ HybridProvider tests passed\n")


def test_default_provider():
    """Test default provider singleton."""
    logger.info("=" * 60)
    logger.info("Testing get_default_provider()...")
    logger.info("=" * 60)
    
    provider1 = get_default_provider()
    provider2 = get_default_provider()
    
    assert provider1 is provider2, "Should return same singleton instance"
    logger.info("✓ Singleton pattern working correctly")
    
    # Test data fetch
    df = provider1.get_latest_candles('WDO$', 'M5', 50)
    logger.info(f"✓ Fetched {len(df)} candles via default provider")
    
    logger.info("✓ Default provider tests passed\n")


def main():
    """Run all provider tests."""
    logger.info("\n" + "=" * 60)
    logger.info("NEWAPP DATA PROVIDER TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    try:
        # Run tests in order
        test_synthetic_provider()
        test_cache_provider()
        test_mt5_provider()
        test_hybrid_provider()
        test_default_provider()
        
        logger.info("=" * 60)
        logger.info("ALL TESTS COMPLETED SUCCESSFULLY ✓")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
