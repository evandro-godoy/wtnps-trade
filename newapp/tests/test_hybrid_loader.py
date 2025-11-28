"""Tests for hybrid_data_loader module.

Verifies DB-first strategy, gap detection, provider fallback, and async persistence.
"""
import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

from newapp.src.data_handler.hybrid_data_loader import (
    get_hybrid_candles,
    get_hybrid_candles_sync,
    _get_timeframe_int,
    _get_expected_latest_time,
    TIMEFRAME_TO_SECONDS
)


def test_get_timeframe_int():
    """Test timeframe string to integer conversion."""
    assert _get_timeframe_int("M5") == 300
    assert _get_timeframe_int("H1") == 3600
    assert _get_timeframe_int("D1") == 86400
    assert _get_timeframe_int("INVALID") == 300  # Default fallback


def test_get_expected_latest_time():
    """Test expected latest candle time calculation."""
    # Mock current time for deterministic test
    with patch('newapp.src.data_handler.hybrid_data_loader.datetime') as mock_dt:
        mock_now = datetime(2025, 11, 27, 14, 23, 45, tzinfo=timezone.utc)
        mock_dt.now.return_value = mock_now
        mock_dt.fromtimestamp = datetime.fromtimestamp
        
        # M5: should round down to 14:20:00
        expected = _get_expected_latest_time("M5")
        assert expected.hour == 14
        assert expected.minute == 20
        assert expected.second == 0


def test_hybrid_candles_empty_db_fetches_provider(tmp_path):
    """Test that empty DB triggers provider fetch."""
    # Mock database session
    mock_db = Mock()
    
    # Mock empty DB response
    with patch('newapp.src.data_handler.hybrid_data_loader.AssetsRatesRepository') as mock_repo:
        mock_repo.get_rates.return_value = pd.DataFrame()  # Empty DB
        
        # Mock provider returning data
        mock_provider = Mock()
        mock_df = pd.DataFrame({
            'open': [100.0, 101.0],
            'high': [102.0, 103.0],
            'low': [99.0, 100.0],
            'close': [101.0, 102.0],
            'volume': [1000, 1100]
        }, index=pd.DatetimeIndex([
            datetime(2025, 11, 27, 14, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 11, 27, 14, 5, 0, tzinfo=timezone.utc)
        ]))
        mock_provider.get_latest_candles.return_value = mock_df
        
        with patch('newapp.src.data_handler.hybrid_data_loader.get_default_provider', return_value=mock_provider):
            # Mock BackgroundTasks
            mock_tasks = Mock()
            
            df = get_hybrid_candles(mock_db, "WDO$", "M5", 100, mock_tasks)
            
            # Verify provider was called
            mock_provider.get_latest_candles.assert_called_once_with(
                ticker="WDO$",
                timeframe="M5",
                count=100
            )
            
            # Verify data returned
            assert not df.empty
            assert len(df) == 2
            
            # Verify persistence was queued (BackgroundTasks.add_task called)
            assert mock_tasks.add_task.called


def test_hybrid_candles_fresh_db_no_provider_call():
    """Test that fresh DB data skips provider call."""
    mock_db = Mock()
    
    # Mock fresh DB data (within 2 candles of expected time)
    now = datetime.now(timezone.utc)
    latest_time = now - timedelta(minutes=3)  # 3 minutes ago (< 2*M5)
    
    mock_df = pd.DataFrame({
        'open': [100.0],
        'high': [102.0],
        'low': [99.0],
        'close': [101.0],
        'volume': [1000]
    }, index=pd.DatetimeIndex([latest_time]))
    
    with patch('newapp.src.data_handler.hybrid_data_loader.AssetsRatesRepository') as mock_repo:
        mock_repo.get_rates.return_value = mock_df
        
        mock_provider = Mock()
        
        with patch('newapp.src.data_handler.hybrid_data_loader.get_default_provider', return_value=mock_provider):
            df = get_hybrid_candles(mock_db, "WDO$", "M5", 100, None)
            
            # Verify provider was NOT called (DB data is fresh)
            mock_provider.get_latest_candles.assert_not_called()
            
            # Verify DB data returned
            assert not df.empty
            assert len(df) == 1


def test_hybrid_candles_gap_detected_fetches_new_data():
    """Test that old DB data triggers provider fetch for gap filling."""
    mock_db = Mock()
    
    # Mock old DB data (gap > 2 candles)
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    
    mock_db_df = pd.DataFrame({
        'open': [100.0],
        'high': [102.0],
        'low': [99.0],
        'close': [101.0],
        'volume': [1000]
    }, index=pd.DatetimeIndex([old_time]))
    
    # Mock provider returning recent data
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=3)
    mock_provider_df = pd.DataFrame({
        'open': [105.0],
        'high': [107.0],
        'low': [104.0],
        'close': [106.0],
        'volume': [1200]
    }, index=pd.DatetimeIndex([recent_time]))
    
    with patch('newapp.src.data_handler.hybrid_data_loader.AssetsRatesRepository') as mock_repo:
        mock_repo.get_rates.return_value = mock_db_df
        
        mock_provider = Mock()
        mock_provider.get_latest_candles.return_value = mock_provider_df
        
        with patch('newapp.src.data_handler.hybrid_data_loader.get_default_provider', return_value=mock_provider):
            mock_tasks = Mock()
            
            df = get_hybrid_candles(mock_db, "WDO$", "M5", 100, mock_tasks)
            
            # Verify provider was called
            mock_provider.get_latest_candles.assert_called_once()
            
            # Verify combined data (DB + new)
            assert not df.empty
            assert len(df) == 2  # Old + new
            
            # Verify only NEW data queued for persistence
            assert mock_tasks.add_task.called
            # First arg should be repository method, second arg is db, third is df
            call_args = mock_tasks.add_task.call_args
            persisted_df = call_args[0][2]  # Third positional arg is the DataFrame
            assert len(persisted_df) == 1  # Only new candle


def test_sync_version_blocks_on_persist():
    """Test synchronous version persists data immediately (blocking)."""
    mock_db = Mock()
    
    with patch('newapp.src.data_handler.hybrid_data_loader.AssetsRatesRepository') as mock_repo:
        mock_repo.get_rates.return_value = pd.DataFrame()  # Empty DB
        
        mock_df = pd.DataFrame({
            'open': [100.0],
            'high': [102.0],
            'low': [99.0],
            'close': [101.0],
            'volume': [1000]
        }, index=pd.DatetimeIndex([datetime.now(timezone.utc)]))
        
        mock_provider = Mock()
        mock_provider.get_latest_candles.return_value = mock_df
        
        with patch('newapp.src.data_handler.hybrid_data_loader.get_default_provider', return_value=mock_provider):
            df = get_hybrid_candles_sync(mock_db, "WDO$", "M5", 100)
            
            # Verify provider was called
            mock_provider.get_latest_candles.assert_called_once()
            
            # Verify save_rates_dataframe was called synchronously
            mock_repo.save_rates_dataframe.assert_called_once()
            
            # Verify data returned
            assert not df.empty


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
