"""Test script for newapp market context analyzer.

Validates technical analysis functionality with real/simulated data.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging
from datetime import datetime

from newapp.src.data_handler.provider import get_default_provider
from newapp.src.analysis.context_analyzer import (
    MarketContextAnalyzer,
    analyze_market_context,
)
from newapp.configs.config import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


def test_market_analyzer():
    """Test MarketContextAnalyzer with real data."""
    logger.info("=" * 60)
    logger.info("Testing MarketContextAnalyzer...")
    logger.info("=" * 60)
    
    # Get data provider
    provider = get_default_provider()
    
    # Fetch market data
    logger.info(f"Fetching {DEFAULT_SYMBOL} data ({DEFAULT_TIMEFRAME})...")
    df = provider.get_latest_candles(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, 500)
    
    if df.empty:
        logger.error("✗ No data available for analysis")
        return False
    
    logger.info(f"✓ Loaded {len(df)} candles")
    logger.info(f"  Date range: {df.index[0]} to {df.index[-1]}")
    logger.info(f"  Latest price: {df.iloc[-1]['close']:.2f}")
    
    # Initialize analyzer
    analyzer = MarketContextAnalyzer(
        ema_fast=9,
        sma_fast=20,
        sma_slow=50,
        sma_lookback=25,
        rsi_period=14,
        lookback_levels=30,
        strong_candle_threshold=0.65
    )
    
    # Perform analysis
    logger.info("\nExecuting technical analysis...")
    context = analyzer.analyze(df)
    
    # Display results
    logger.info("\n" + "=" * 60)
    logger.info("TECHNICAL ANALYSIS RESULTS")
    logger.info("=" * 60)
    
    logger.info(f"\n📊 TREND ANALYSIS:")
    logger.info(f"  Trend:          {context['trend']}")
    logger.info(f"  Strength:       {context['trend_strength']}")
    logger.info(f"  EMA(9):         {context['ema_fast']:.2f}")
    logger.info(f"  SMA(20):        {context['sma_fast']:.2f}")
    logger.info(f"  SMA(50):        {context['sma_slow']:.2f}")
    
    logger.info(f"\n💪 MOMENTUM ANALYSIS:")
    logger.info(f"  RSI(14):        {context['rsi']:.2f}")
    logger.info(f"  RSI Condition:  {context['rsi_condition']}")
    
    logger.info(f"\n📈 SUPPORT/RESISTANCE:")
    logger.info(f"  Support:        {context['support']:.2f}")
    logger.info(f"  Resistance:     {context['resistance']:.2f}")
    logger.info(f"  Distance to S:  {context['distance_to_support']:.2f}%")
    logger.info(f"  Distance to R:  {context['distance_to_resistance']:.2f}%")
    
    logger.info(f"\n🕯️ PRICE ACTION:")
    logger.info(f"  Pattern:        {context['pattern']}")
    logger.info(f"  Current Price:  {context['current_price']:.2f}")
    
    # Validate fields
    required_fields = [
        'trend', 'trend_strength', 'rsi', 'rsi_condition',
        'support', 'resistance', 'pattern', 'current_price'
    ]
    
    for field in required_fields:
        assert field in context, f"Missing field: {field}"
        assert context[field] != 'INDEFINIDO', f"Field {field} is INDEFINIDO"
    
    logger.info("\n✓ All required fields present and valid")
    return True


def test_signal_validation():
    """Test signal validation against technical context."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Signal Validation...")
    logger.info("=" * 60)
    
    # Get data
    provider = get_default_provider()
    df = provider.get_latest_candles(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, 500)
    
    if df.empty:
        logger.error("✗ No data available for validation test")
        return False
    
    # Analyze context
    analyzer = MarketContextAnalyzer()
    context = analyzer.analyze(df)
    
    logger.info(f"\nCurrent context: Trend={context['trend']}, RSI={context['rsi']:.2f}")
    
    # Test validation scenarios
    test_cases = [
        ('COMPRA', True, 'Compra com alinhamento de tendência'),
        ('VENDA', True, 'Venda com alinhamento de tendência'),
        ('COMPRA', False, 'Compra sem exigir alinhamento'),
        ('VENDA', False, 'Venda sem exigir alinhamento'),
    ]
    
    for direction, require_alignment, description in test_cases:
        valid, reason = analyzer.validate_signal(direction, context, require_alignment)
        status = "✓ VÁLIDO" if valid else "✗ INVÁLIDO"
        logger.info(f"\n{description}:")
        logger.info(f"  Status: {status}")
        logger.info(f"  Razão:  {reason}")
    
    logger.info("\n✓ Signal validation tests completed")
    return True


def test_convenience_function():
    """Test convenience function for quick analysis."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Convenience Function...")
    logger.info("=" * 60)
    
    # Get data
    provider = get_default_provider()
    df = provider.get_latest_candles(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, 200)
    
    if df.empty:
        logger.error("✗ No data available")
        return False
    
    # Use convenience function
    context = analyze_market_context(df)
    
    logger.info(f"\n✓ Quick analysis completed:")
    logger.info(f"  Trend: {context['trend']} ({context['trend_strength']})")
    logger.info(f"  RSI:   {context['rsi']:.2f} ({context['rsi_condition']})")
    logger.info(f"  Price: {context['current_price']:.2f}")
    
    assert 'trend' in context, "Missing trend in analysis"
    assert 'rsi' in context, "Missing RSI in analysis"
    
    logger.info("✓ Convenience function working correctly")
    return True


def test_edge_cases():
    """Test analyzer with edge cases."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Edge Cases...")
    logger.info("=" * 60)
    
    import pandas as pd
    
    analyzer = MarketContextAnalyzer()
    
    # Test 1: Empty DataFrame
    logger.info("\n1. Empty DataFrame:")
    empty_df = pd.DataFrame()
    context = analyzer.analyze(empty_df)
    assert context['trend'] == 'INDEFINIDO', "Empty DataFrame should return INDEFINIDO"
    logger.info("  ✓ Handles empty DataFrame correctly")
    
    # Test 2: Insufficient data
    logger.info("\n2. Insufficient data (10 rows, needs 50):")
    provider = get_default_provider()
    small_df = provider.get_latest_candles(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, 10)
    context = analyzer.analyze(small_df)
    # Should either return INDEFINIDO or handle gracefully
    logger.info(f"  ✓ Result: {context['trend']}")
    
    # Test 3: Custom parameters
    logger.info("\n3. Custom analyzer parameters:")
    custom_analyzer = MarketContextAnalyzer(
        ema_fast=5,
        sma_fast=10,
        sma_slow=20,
        rsi_period=7
    )
    df = provider.get_latest_candles(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, 100)
    if not df.empty:
        context = custom_analyzer.analyze(df)
        logger.info(f"  ✓ Custom analysis: Trend={context['trend']}, RSI={context['rsi']:.2f}")
    
    logger.info("\n✓ Edge case tests completed")
    return True


def main():
    """Run all analyzer tests."""
    logger.info("\n" + "=" * 60)
    logger.info("NEWAPP MARKET CONTEXT ANALYZER TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    tests = [
        ("Market Analyzer", test_market_analyzer),
        ("Signal Validation", test_signal_validation),
        ("Convenience Function", test_convenience_function),
        ("Edge Cases", test_edge_cases),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"\n✗ Test '{test_name}' failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        logger.info("\n" + "=" * 60)
        logger.info("ALL TESTS PASSED ✓")
        logger.info("=" * 60)
        return 0
    else:
        logger.error("\n" + "=" * 60)
        logger.error("SOME TESTS FAILED ✗")
        logger.error("=" * 60)
        return 1


if __name__ == '__main__':
    exit(main())
