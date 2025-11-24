"""Unit tests for centralized indicators module.

Tests basic technical indicator calculations and DataFrame enrichment functions.
"""
import pytest
import pandas as pd
import numpy as np

from newapp.src.utils.indicators import (
    calculate_ema,
    calculate_sma,
    calculate_rsi,
    add_basic_indicators,
    enrich_indicators_from_close,
    compute_indicator_dict,
)


@pytest.fixture
def sample_close_series():
    """Sample close price series for testing."""
    return pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111])


@pytest.fixture
def sample_ohlcv_dataframe():
    """Sample OHLCV DataFrame for testing."""
    dates = pd.date_range('2024-01-01', periods=50, freq='5min')
    np.random.seed(42)
    return pd.DataFrame({
        'open': np.random.randn(50).cumsum() + 100,
        'high': np.random.randn(50).cumsum() + 102,
        'low': np.random.randn(50).cumsum() + 98,
        'close': np.random.randn(50).cumsum() + 100,
        'volume': np.random.randint(1000, 10000, 50)
    }, index=dates)


class TestBasicIndicators:
    """Test individual indicator calculation functions."""
    
    def test_calculate_ema(self, sample_close_series):
        """Test EMA calculation."""
        ema9 = calculate_ema(sample_close_series, span=9, adjust=False)
        
        assert isinstance(ema9, pd.Series)
        assert len(ema9) == len(sample_close_series)
        assert not ema9.isna().all()
        assert ema9.iloc[-1] > 0
    
    def test_calculate_sma(self, sample_close_series):
        """Test SMA calculation."""
        sma20 = calculate_sma(sample_close_series, window=20, min_periods=1)
        
        assert isinstance(sma20, pd.Series)
        assert len(sma20) == len(sample_close_series)
        # With min_periods=1, first value should not be NaN
        assert not pd.isna(sma20.iloc[0])
    
    def test_calculate_rsi(self, sample_close_series):
        """Test RSI calculation."""
        rsi = calculate_rsi(sample_close_series, period=14)
        
        assert isinstance(rsi, pd.Series)
        assert len(rsi) == len(sample_close_series)
        # RSI should be between 0-100 for valid values
        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()


class TestDataFrameEnrichment:
    """Test DataFrame enrichment functions."""
    
    def test_add_basic_indicators_default(self, sample_ohlcv_dataframe):
        """Test add_basic_indicators with default parameters."""
        df = sample_ohlcv_dataframe.copy()
        df_enriched = add_basic_indicators(df)
        
        assert 'ema_9' in df_enriched.columns
        assert 'sma_20' in df_enriched.columns
        assert 'sma_50' in df_enriched.columns
        assert 'sma_200' in df_enriched.columns
        assert 'rsi' not in df_enriched.columns  # RSI not added by default
    
    def test_add_basic_indicators_with_rsi(self, sample_ohlcv_dataframe):
        """Test add_basic_indicators with RSI enabled."""
        df = sample_ohlcv_dataframe.copy()
        df_enriched = add_basic_indicators(df, rsi_period=14)
        
        assert 'rsi' in df_enriched.columns
    
    def test_add_basic_indicators_custom_periods(self, sample_ohlcv_dataframe):
        """Test add_basic_indicators with custom periods."""
        df = sample_ohlcv_dataframe.copy()
        df_enriched = add_basic_indicators(
            df,
            ema_periods=[5, 10],
            sma_periods=[10, 30],
            rsi_period=21
        )
        
        assert 'ema_5' in df_enriched.columns
        assert 'ema_10' in df_enriched.columns
        assert 'sma_10' in df_enriched.columns
        assert 'sma_30' in df_enriched.columns
        assert 'rsi_21' in df_enriched.columns
    
    def test_add_basic_indicators_no_overwrite(self, sample_ohlcv_dataframe):
        """Test that existing columns are not overwritten by default."""
        df = sample_ohlcv_dataframe.copy()
        df['ema_9'] = 999.0  # Pre-existing value
        
        df_enriched = add_basic_indicators(df, overwrite=False)
        
        # Should preserve existing value
        assert (df_enriched['ema_9'] == 999.0).all()
    
    def test_add_basic_indicators_with_overwrite(self, sample_ohlcv_dataframe):
        """Test overwrite flag."""
        df = sample_ohlcv_dataframe.copy()
        df['ema_9'] = 999.0
        
        df_enriched = add_basic_indicators(df, overwrite=True)
        
        # Should recalculate and replace
        assert not (df_enriched['ema_9'] == 999.0).all()
    
    def test_add_basic_indicators_missing_close(self):
        """Test error handling when 'close' column is missing."""
        df = pd.DataFrame({'open': [100, 102, 101]})
        
        with pytest.raises(ValueError, match="must contain 'close' column"):
            add_basic_indicators(df)
    
    def test_enrich_indicators_from_close(self, sample_ohlcv_dataframe):
        """Test legacy wrapper function."""
        df = sample_ohlcv_dataframe.copy()
        df_enriched = enrich_indicators_from_close(df)
        
        # Should add standard indicators
        assert 'ema_9' in df_enriched.columns
        assert 'sma_20' in df_enriched.columns
        assert 'sma_50' in df_enriched.columns
        assert 'sma_200' in df_enriched.columns


class TestComputeIndicatorDict:
    """Test compute_indicator_dict function."""
    
    def test_compute_indicator_dict(self, sample_close_series):
        """Test indicator dictionary computation."""
        indicators = compute_indicator_dict(sample_close_series)
        
        assert isinstance(indicators, dict)
        assert 'ema_9' in indicators
        assert 'sma_20' in indicators
        assert 'sma_50' in indicators
        assert 'sma_200' in indicators
        
        # All values should be Series
        for key, value in indicators.items():
            assert isinstance(value, pd.Series)
            assert len(value) == len(sample_close_series)
    
    def test_compute_indicator_dict_values(self, sample_close_series):
        """Test that computed values are reasonable."""
        indicators = compute_indicator_dict(sample_close_series)
        
        # All indicators should have non-NaN values at the end
        for key in ['ema_9', 'sma_20']:
            assert not pd.isna(indicators[key].iloc[-1])
            assert indicators[key].iloc[-1] > 0
