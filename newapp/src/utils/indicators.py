"""Centralized technical indicators calculation module.

Provides reusable functions for calculating common technical indicators
to avoid code duplication across ingestion, enrichment, and analysis modules.

All functions work with pandas Series/DataFrame and use vectorized operations
for performance.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, Optional, List


def calculate_ema(series: pd.Series, span: int, adjust: bool = False) -> pd.Series:
    """Calculate Exponential Moving Average.
    
    Args:
        series: Price series (typically close prices)
        span: EMA span/period
        adjust: If True, use adjusted EMA calculation
        
    Returns:
        Series with EMA values
        
    Example:
        >>> close_prices = pd.Series([100, 102, 101, 103, 105])
        >>> ema9 = calculate_ema(close_prices, span=9)
    """
    return series.ewm(span=span, adjust=adjust).mean()


def calculate_sma(series: pd.Series, window: int, min_periods: int = 1) -> pd.Series:
    """Calculate Simple Moving Average.
    
    Args:
        series: Price series (typically close prices)
        window: SMA window/period
        min_periods: Minimum observations needed for calculation
        
    Returns:
        Series with SMA values
        
    Example:
        >>> close_prices = pd.Series([100, 102, 101, 103, 105])
        >>> sma20 = calculate_sma(close_prices, window=20, min_periods=1)
    """
    return series.rolling(window=window, min_periods=min_periods).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI).
    
    RSI measures the magnitude of recent price changes to evaluate
    overbought or oversold conditions (0-100 scale).
    
    Args:
        series: Price close series
        period: RSI period (default: 14)
    
    Returns:
        Series with RSI values (0-100)
        
    Example:
        >>> close_prices = pd.Series([100, 102, 101, 103, 105, 104, 106])
        >>> rsi = calculate_rsi(close_prices, period=14)
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def add_basic_indicators(
    df: pd.DataFrame,
    ema_periods: Optional[List[int]] = None,
    sma_periods: Optional[List[int]] = None,
    rsi_period: Optional[int] = None,
    overwrite: bool = False
) -> pd.DataFrame:
    """Add basic technical indicators to DataFrame.
    
    Default configuration matches legacy pattern:
    - EMA: 9
    - SMA: 20, 50, 200
    - RSI: 14 (optional)
    
    Args:
        df: DataFrame with at least 'close' column
        ema_periods: List of EMA periods to calculate (default: [9])
        sma_periods: List of SMA periods to calculate (default: [20, 50, 200])
        rsi_period: RSI period (None to skip RSI calculation)
        overwrite: If True, recalculate even if columns exist
        
    Returns:
        DataFrame with added indicator columns
        
    Raises:
        ValueError: If 'close' column is missing
        
    Example:
        >>> df = pd.DataFrame({'close': [100, 102, 101, 103, 105]})
        >>> df = add_basic_indicators(df)
        >>> print(df.columns)  # ['close', 'ema_9', 'sma_20', 'sma_50', 'sma_200']
    """
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column")
    
    # Defaults match existing implementation
    if ema_periods is None:
        ema_periods = [9]
    if sma_periods is None:
        sma_periods = [20, 50, 200]
    
    # Sort by index for accurate rolling calculations
    df = df.sort_index()
    
    # Calculate EMAs
    for period in ema_periods:
        col_name = f'ema_{period}'
        if overwrite or col_name not in df.columns:
            df[col_name] = calculate_ema(df['close'], span=period, adjust=False)
    
    # Calculate SMAs
    for period in sma_periods:
        col_name = f'sma_{period}'
        if overwrite or col_name not in df.columns:
            df[col_name] = calculate_sma(df['close'], window=period, min_periods=1)
    
    # Calculate RSI if requested
    if rsi_period is not None:
        col_name = 'rsi' if rsi_period == 14 else f'rsi_{rsi_period}'
        if overwrite or col_name not in df.columns:
            df[col_name] = calculate_rsi(df['close'], period=rsi_period)
    
    return df


def enrich_indicators_from_close(
    df: pd.DataFrame,
    overwrite: bool = False
) -> pd.DataFrame:
    """Legacy-compatible indicator enrichment (EMA9, SMA20, SMA50, SMA200).
    
    Convenience wrapper for add_basic_indicators with default periods.
    Skips calculation if columns already exist unless overwrite=True.
    
    Args:
        df: DataFrame with 'close' column
        overwrite: If True, recalculate existing indicators
        
    Returns:
        DataFrame with enriched indicators
        
    Example:
        >>> df = pd.DataFrame({'close': [100, 102, 101, 103, 105]})
        >>> df = enrich_indicators_from_close(df)
        >>> 'ema_9' in df.columns
        True
    """
    return add_basic_indicators(
        df,
        ema_periods=[9],
        sma_periods=[20, 50, 200],
        rsi_period=None,
        overwrite=overwrite
    )


def compute_indicator_dict(close_series: pd.Series) -> Dict[str, pd.Series]:
    """Compute all standard indicators and return as dictionary.
    
    Useful for batch operations where individual Series are needed
    (e.g., repository bulk updates).
    
    Args:
        close_series: Pandas Series of close prices (sorted index)
        
    Returns:
        Dictionary with keys: 'ema_9', 'sma_20', 'sma_50', 'sma_200'
        
    Example:
        >>> close_prices = pd.Series([100, 102, 101, 103, 105])
        >>> indicators = compute_indicator_dict(close_prices)
        >>> indicators['ema_9']
        0    100.000000
        1    101.000000
        ...
    """
    return {
        'ema_9': calculate_ema(close_series, span=9, adjust=False),
        'sma_20': calculate_sma(close_series, window=20, min_periods=1),
        'sma_50': calculate_sma(close_series, window=50, min_periods=1),
        'sma_200': calculate_sma(close_series, window=200, min_periods=1),
    }


__all__ = [
    'calculate_ema',
    'calculate_sma',
    'calculate_rsi',
    'add_basic_indicators',
    'enrich_indicators_from_close',
    'compute_indicator_dict',
]
