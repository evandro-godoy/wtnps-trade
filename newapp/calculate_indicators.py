"""Calculate and update technical indicators in database.

This script uses MarketContextAnalyzer to calculate technical indicators
(EMA, SMA, support/resistance levels) and updates AssetsRates table.

Usage:
    poetry run python newapp/calculate_indicators.py
    poetry run python newapp/calculate_indicators.py --symbol WDO$ --timeframe 5
    poetry run python newapp/calculate_indicators.py --all
"""
from __future__ import annotations

import argparse
import logging
from typing import Optional

from sqlalchemy import text

from newapp.src.database.db import get_engine, get_session
from newapp.src.database.repository import AssetsRatesRepository
from newapp.src.analysis.context_analyzer import MarketContextAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_indicators_for_symbol(
    symbol: str,
    timeframe: int,
    analyzer: Optional[MarketContextAnalyzer] = None
) -> int:
    """Calculate indicators for a specific symbol and timeframe.
    
    Args:
        symbol: Asset symbol (e.g., "WDO$")
        timeframe: Timeframe integer (e.g., 5 for M5)
        analyzer: Optional MarketContextAnalyzer instance
        
    Returns:
        Number of records updated
    """
    logger.info(f"Processing {symbol} timeframe={timeframe}")
    
    with get_session() as db:
        count = AssetsRatesRepository.update_indicators_with_analyzer(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
            analyzer=analyzer
        )
        
        logger.info(f"✅ Updated {count} records for {symbol} TF={timeframe}")
        return count


def calculate_all_indicators(analyzer: Optional[MarketContextAnalyzer] = None) -> dict[str, int]:
    """Calculate indicators for all symbols and timeframes in database.
    
    Args:
        analyzer: Optional MarketContextAnalyzer instance
        
    Returns:
        Dictionary with results: {(symbol, timeframe): count_updated}
    """
    results = {}
    
    # Get all unique symbol/timeframe combinations
    engine = get_engine()
    with engine.connect() as conn:
        query = text("""
            SELECT DISTINCT symbol, timeframe 
            FROM assets_rates 
            ORDER BY symbol, timeframe
        """)
        combinations = conn.execute(query).fetchall()
    
    logger.info(f"Found {len(combinations)} symbol/timeframe combinations")
    
    for symbol, timeframe in combinations:
        try:
            count = calculate_indicators_for_symbol(symbol, timeframe, analyzer)
            results[(symbol, timeframe)] = count
        except Exception as e:
            logger.error(f"Error processing {symbol} TF={timeframe}: {e}", exc_info=True)
            results[(symbol, timeframe)] = 0
    
    return results


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Calculate and update technical indicators in database"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        help="Asset symbol (e.g., WDO$)"
    )
    parser.add_argument(
        "--timeframe",
        type=int,
        help="Timeframe integer (e.g., 5 for M5)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all symbols and timeframes in database"
    )
    parser.add_argument(
        "--ema-fast",
        type=int,
        default=9,
        help="Fast EMA period (default: 9)"
    )
    parser.add_argument(
        "--sma-fast",
        type=int,
        default=20,
        help="Fast SMA period (default: 20)"
    )
    parser.add_argument(
        "--sma-slow",
        type=int,
        default=50,
        help="Slow SMA period (default: 50)"
    )
    parser.add_argument(
        "--lookback-levels",
        type=int,
        default=30,
        help="Lookback period for support/resistance (default: 30)"
    )
    
    args = parser.parse_args()
    
    # Create analyzer with custom parameters
    analyzer = MarketContextAnalyzer(
        ema_fast=args.ema_fast,
        sma_fast=args.sma_fast,
        sma_slow=args.sma_slow,
        lookback_levels=args.lookback_levels
    )
    
    logger.info(f"Using MarketContextAnalyzer: EMA{args.ema_fast}, SMA{args.sma_fast}/{args.sma_slow}")
    
    # Execute based on arguments
    if args.all:
        logger.info("Processing ALL symbols and timeframes...")
        results = calculate_all_indicators(analyzer)
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 SUMMARY")
        print("=" * 70)
        total_updated = 0
        for (symbol, timeframe), count in results.items():
            print(f"  {symbol:<10} TF={timeframe:<5} → {count:>6} records updated")
            total_updated += count
        
        print("=" * 70)
        print(f"✅ Total: {total_updated} records updated across {len(results)} combinations")
        print("=" * 70)
        
    elif args.symbol and args.timeframe:
        logger.info(f"Processing {args.symbol} timeframe={args.timeframe}...")
        count = calculate_indicators_for_symbol(args.symbol, args.timeframe, analyzer)
        
        print("\n" + "=" * 70)
        print(f"✅ Updated {count} records for {args.symbol} TF={args.timeframe}")
        print("=" * 70)
        
    else:
        parser.print_help()
        print("\n⚠️  You must specify either --all or both --symbol and --timeframe")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
