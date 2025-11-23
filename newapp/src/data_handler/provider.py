"""Data provider module for newapp web application.

Provides abstraction layer for market data access with support for:
- MetaTrader5 (live trading data, Windows-only)
- Cache-based fallback (Parquet files)
- Synthetic data generation (development/testing)

Thread-safe singleton pattern ensures efficient resource usage across
concurrent web requests.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
from abc import ABC, abstractmethod
import threading
import random
import logging
import os

import pandas as pd
import pytz

# Conditional MT5 import for cloud compatibility
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None  # type: ignore
    MT5_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Cache directory configuration
CACHE_DIR = Path(__file__).parent.parent.parent / '.cache_data'
os.makedirs(CACHE_DIR, exist_ok=True)
logger.info(f"Cache directory initialized: {CACHE_DIR.resolve()}")

# Timezone configuration (UTC for consistency)
DESIRED_TIMEZONE = pytz.UTC


class BaseDataProvider(ABC):
    """Abstract base class for data providers."""

    @abstractmethod
    def get_data(self, ticker: str, start_date: str, end_date: str, timeframe) -> pd.DataFrame:
        """Fetch historical market data.
        Args:
            ticker: Asset symbol
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            timeframe: Timeframe specification (provider-specific)

        Returns:
            DataFrame with OHLCV data, timezone-aware index
        """
        pass

    @abstractmethod
    def get_latest_candles(
        self,
        ticker: str,
        timeframe: Any,
        count: int
    ) -> pd.DataFrame:
        """Fetch most recent candles.

        Args:
            ticker: Asset symbol
            timeframe: Timeframe specification
            count: Number of candles to retrieve

        Returns:
            DataFrame with OHLCV data, timezone-aware index
        """
        pass

    def close_connection(self) -> None:
        """Close provider connections (if applicable)."""
        pass

    def is_connected(self) -> bool:
        """Check connection status.

        Returns:
            True if provider is operational
        """
        return True

class DataBaseProvider(BaseDataProvider):
    """Base data provider with common utilities."""

    def __init__(self) -> None:
        """Initialize base provider."""
        pass

class MetaTraderProvider(BaseDataProvider):
    """MetaTrader 5 data provider with connection pooling.

    Singleton pattern ensures single MT5 connection across all requests.
    Thread-safe for concurrent web application usage.
    """

    _instance: Optional[MetaTraderProvider] = None
    _lock = threading.Lock()

    def __new__(cls) -> MetaTraderProvider:
        """Implement singleton pattern with thread safety."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        """Initialize MT5 connection (once per singleton lifecycle)."""
        if self._initialized:
            return
        
        if not MT5_AVAILABLE:
            logger.critical("MetaTrader5 module not available (cloud environment?)")
            self.connection_active = False
        else:
            self.connection_active = self._initialize_mt5()
            if not self.connection_active:
                logger.critical("Failed to initialize MetaTrader 5 connection")
        
        self._initialized = True

    def _initialize_mt5(self) -> bool:
        """Initialize MT5 terminal connection.

        Returns:
            True if connection successful
        """
        if not MT5_AVAILABLE or mt5 is None:
            return False

        # Check if already connected
        if mt5.terminal_info() is not None:
            logger.info("MT5 connection already active")
            return True

        # Initialize new connection
        if not mt5.initialize():
            logger.error(f"MT5 initialization failed, error code: {mt5.last_error()}")
            return False

        terminal_info = mt5.terminal_info()
        if terminal_info:
            logger.info(f"MetaTrader 5 Connected: {terminal_info.name}")
            return True
        else:
            logger.error("mt5.initialize() succeeded but terminal_info() is None")
            return False

    def is_connected(self) -> bool:
        """Verify MT5 connection status.

        Returns:
            True if MT5 terminal is connected
        """
        if not MT5_AVAILABLE or mt5 is None:
            return False
        return self.connection_active and mt5.terminal_info() is not None

    def _get_mt5_timeframe(self, tf_str: str) -> Optional[int]:
        """Convert timeframe string to MT5 constant.

        Args:
            tf_str: Timeframe string (M1, M5, H1, etc.)

        Returns:
            MT5 timeframe constant or None if invalid
        """
        if not MT5_AVAILABLE or mt5 is None:
            return None

        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1
        }
        tf_constant = tf_map.get(tf_str.upper())
        if tf_constant is None:
            logger.warning(f"Timeframe '{tf_str}' not mapped to MT5 constant")
        return tf_constant

    def _download_rates_in_chunks(
        self,
        ticker: str,
        timeframe: int,
        start_dt: datetime,
        end_dt: datetime,
        chunk_size_days: int = 183
    ) -> pd.DataFrame:
        """Download MT5 data in chunks to avoid API limits.

        Args:
            ticker: Asset symbol
            timeframe: MT5 timeframe constant
            start_dt: Start datetime (UTC timezone)
            end_dt: End datetime (UTC timezone)
            chunk_size_days: Chunk size in days (default: 183)

        Returns:
            Consolidated DataFrame with all chunks
        """
        if not MT5_AVAILABLE or mt5 is None:
            return pd.DataFrame()

        rates_list = []
        current_start = start_dt.astimezone(pytz.UTC) if start_dt.tzinfo else pytz.UTC.localize(start_dt)
        final_end = end_dt.astimezone(pytz.UTC) if end_dt.tzinfo else pytz.UTC.localize(end_dt)
        final_end = final_end + timedelta(hours=23, minutes=59)

        logger.info(f"Starting chunked download ({chunk_size_days} days) for {ticker}...")

        chunk_count = 0
        while current_start < final_end:
            current_end = min(current_start + timedelta(days=chunk_size_days), final_end)

            logger.debug(f"  Chunk {chunk_count + 1}: {current_start.date()} to {current_end.date()}")

            try:
                rates = mt5.copy_rates_range(ticker, timeframe, current_start, current_end)
                if rates is not None and len(rates) > 0:
                    df_chunk = pd.DataFrame(rates)
                    rates_list.append(df_chunk)
                    logger.debug(f"    → {len(df_chunk)} candles retrieved")
                else:
                    logger.warning(f"    → No data for chunk {chunk_count + 1}")
            except Exception as e:
                logger.error(f"Error downloading chunk {chunk_count + 1}: {e}")

            current_start = current_end
            chunk_count += 1

        if not rates_list:
            logger.warning(f"No data retrieved for {ticker} in any chunk")
            return pd.DataFrame()

        # Consolidate and remove duplicates
        df_final = pd.concat(rates_list, ignore_index=True)

        if 'time' in df_final.columns:
            df_final.drop_duplicates(subset=['time'], keep='first', inplace=True)

        logger.info(f"Chunked download complete: {len(df_final)} candles from {chunk_count} chunks")
        return df_final

    def get_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        timeframe: int
    ) -> pd.DataFrame:
        """Fetch historical data from MT5 with caching.

        Args:
            ticker: Asset symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            timeframe: MT5 timeframe constant

        Returns:
            DataFrame with OHLCV data, timezone-aware index
        """
        if not self.is_connected():
            logger.error("MT5 not connected, cannot fetch data")
            return pd.DataFrame()

        try:
            start_dt_utc = pytz.UTC.localize(datetime.strptime(start_date, "%Y-%m-%d"))
            end_dt_utc = pytz.UTC.localize(datetime.strptime(end_date, "%Y-%m-%d"))
        except ValueError:
            logger.error(f"Invalid date format: {start_date} or {end_date}")
            return pd.DataFrame()

        # Generate cache filename
        tf_map_rev = {v: k for k, v in mt5.__dict__.items() if k.startswith('TIMEFRAME_')}
        timeframe_str = tf_map_rev.get(timeframe, f'UNKNOWN_{timeframe}').replace('TIMEFRAME_', '')

        cache_filename = f"MT5_{ticker.replace('$', '')}_{timeframe_str}_{start_dt_utc.strftime('%Y%m%d')}_{end_dt_utc.strftime('%Y%m%d')}.parquet"
        cache_filepath = CACHE_DIR / cache_filename

        # Check cache
        if cache_filepath.exists():
            try:
                logger.info(f"Loading cached data: {cache_filename}")
                data = pd.read_parquet(cache_filepath)
                if not data.empty:
                    logger.info(f"Cache hit: {len(data)} candles loaded")
                    return data
            except Exception as e:
                logger.warning(f"Cache read failed: {e}, fetching fresh data")

        logger.info(f"Fetching {ticker} from MT5 ({start_date} to {end_date} @ {timeframe_str})...")

        # Download data in chunks
        data = self._download_rates_in_chunks(ticker, timeframe, start_dt_utc, end_dt_utc)

        if data.empty:
            logger.warning(f"No data retrieved for {ticker}")
            return pd.DataFrame()

        # Remove invalid rows (all OHLC = 0 or null)
        data = data[(data[['open', 'high', 'low', 'close']] != 0).any(axis=1)]
        data = data.dropna(subset=['open', 'high', 'low', 'close'], how='all')

        if data.empty:
            logger.warning("All data rows invalid (zero/null OHLC)")
            return pd.DataFrame()

        # Format DataFrame
        data['time'] = pd.to_datetime(data['time'], unit='s', utc=True)
        data.set_index('time', inplace=True)
        data.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'tick_volume': 'volume'
        }, inplace=True)

        # Ensure required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in data.columns:
                data[col] = 0.0

        data = data[required_cols]

        # Save to cache
        try:
            data.to_parquet(cache_filepath)
            logger.info(f"Data cached: {cache_filename}")
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

        logger.info(f"MT5 data fetched and converted to {DESIRED_TIMEZONE}")
        return data

    def get_latest_candles(
        self,
        ticker: str,
        timeframe: int,
        count: int
    ) -> pd.DataFrame:
        """Fetch most recent candles from MT5.

        Args:
            ticker: Asset symbol
            timeframe: MT5 timeframe constant
            count: Number of candles to retrieve

        Returns:
            DataFrame with OHLCV data, timezone-aware index
        """
        if not self.is_connected():
            logger.error("MT5 not connected, cannot fetch latest candles")
            return pd.DataFrame()

        try:
            rates = mt5.copy_rates_from_pos(ticker, timeframe, 0, count)
        except Exception as e:
            logger.error(f"Error fetching latest candles: {e}")
            return pd.DataFrame()

        if rates is None or len(rates) == 0:
            logger.warning(f"No recent data for {ticker}")
            return pd.DataFrame()

        data = pd.DataFrame(rates)
        data['time'] = pd.to_datetime(data['time'], unit='s', utc=True)
        data.set_index('time', inplace=True)
        data.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'tick_volume': 'volume'
        }, inplace=True)

        # Handle volume columns
        if 'real_volume' in data.columns and 'volume' not in data.columns:
            data['volume'] = data['real_volume']
        elif 'real_volume' in data.columns and 'volume' in data.columns:
            data.drop(columns=['real_volume'], inplace=True)

        required_cols = ['open', 'high', 'low', 'close', 'volume']
        data = data[[col for col in required_cols if col in data.columns]]
        if 'volume' not in data.columns:
            data['volume'] = 0

        return data

    def close_connection(self) -> None:
        """Close MT5 connection."""
        if self.connection_active and MT5_AVAILABLE and mt5 is not None:
            if mt5.terminal_info() is not None:
                mt5.shutdown()
                logger.info("MT5 connection closed")
                self.connection_active = False


class CacheProvider(BaseDataProvider):
    """Cache-based data provider (reads from Parquet files).

    Fallback provider when MT5 is unavailable. Searches for cached
    parquet files matching the requested symbol/timeframe.
    """

    def __init__(self) -> None:
        """Initialize cache provider."""
        if not CACHE_DIR.exists():
            logger.warning(f"Cache directory does not exist: {CACHE_DIR}")

    def get_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        timeframe: Any
    ) -> pd.DataFrame:
        """Load historical data from cache.

        Args:
            ticker: Asset symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            timeframe: Timeframe string (M5, H1, etc.)

        Returns:
            DataFrame with OHLCV data, timezone-aware index
        """
        if not CACHE_DIR.exists():
            return pd.DataFrame()

        # Pattern: MT5_<TICKER>_<TF>_*.parquet
        ticker_clean = ticker.replace('$', '')
        tf_str = timeframe if isinstance(timeframe, str) else 'M5'
        pattern = f"MT5_{ticker_clean}_{tf_str}_*.parquet"

        candidates = sorted(CACHE_DIR.glob(pattern))
        if not candidates:
            logger.warning(f"No cache files found matching: {pattern}")
            return pd.DataFrame()

        # Use most recent cache file
        latest = candidates[-1]
        try:
            logger.info(f"Loading cache file: {latest.name}")
            df = pd.read_parquet(latest)

            if not isinstance(df.index, pd.DatetimeIndex):
                logger.error("Cache file index is not DatetimeIndex")
                return pd.DataFrame()

            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC')

            # Filter by date range
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                df = df[(df.index >= start_dt) & (df.index <= end_dt)]
            except ValueError:
                logger.warning("Invalid date format, returning all cached data")

            logger.info(f"Loaded {len(df)} candles from cache")
            return df
        except Exception as exc:
            logger.error(f"Failed to load cache file {latest}: {exc}")
            return pd.DataFrame()

    def get_latest_candles(
        self,
        ticker: str,
        timeframe: Any,
        count: int
    ) -> pd.DataFrame:
        """Load most recent candles from cache.

        Args:
            ticker: Asset symbol
            timeframe: Timeframe string (M5, H1, etc.)
            count: Number of candles to retrieve

        Returns:
            DataFrame with OHLCV data, timezone-aware index
        """
        if not CACHE_DIR.exists():
            return pd.DataFrame()

        ticker_clean = ticker.replace('$', '')
        tf_str = timeframe if isinstance(timeframe, str) else 'M5'
        pattern = f"MT5_{ticker_clean}_{tf_str}_*.parquet"

        candidates = sorted(CACHE_DIR.glob(pattern))
        if not candidates:
            logger.warning(f"No cache files found matching: {pattern}")
            return pd.DataFrame()

        latest = candidates[-1]
        try:
            logger.info(f"Loading latest candles from cache: {latest.name}")
            df = pd.read_parquet(latest)

            if not isinstance(df.index, pd.DatetimeIndex):
                return pd.DataFrame()

            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC')

            df = df.tail(count)
            logger.info(f"Loaded {len(df)} recent candles from cache")
            return df
        except Exception as exc:
            logger.error(f"Failed to load cache file {latest}: {exc}")
            return pd.DataFrame()


class SyntheticProvider(BaseDataProvider):
    """Synthetic data provider for development/testing.

    Generates random walk OHLCV data. Useful for:
    - Development without MT5 connection
    - Testing chart rendering
    - Demo deployments (cloud environments)
    """

    def __init__(self, base_price: float = 100000.0, seed: Optional[int] = None) -> None:
        """Initialize synthetic provider.

        Args:
            base_price: Starting price for random walk
            seed: Random seed for reproducibility (optional)
        """
        self.base_price = base_price
        if seed is not None:
            random.seed(seed)

    def _generate_candles(self, count: int, interval_minutes: int = 5) -> pd.DataFrame:
        """Generate synthetic OHLCV candles.

        Args:
            count: Number of candles to generate
            interval_minutes: Time interval per candle

        Returns:
            DataFrame with synthetic OHLCV data
        """
        rows = []
        current_price = self.base_price
        now = datetime.utcnow()

        for i in range(count):
            ts = now - timedelta(minutes=interval_minutes * (count - i))
            change = random.uniform(-50, 50)
            open_price = current_price
            close_price = max(10.0, open_price + change)
            high_price = max(open_price, close_price) + random.uniform(0, 30)
            low_price = min(open_price, close_price) - random.uniform(0, 30)
            volume = random.randint(500, 5000)

            rows.append({
                'time': ts,
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume
            })
            current_price = close_price

        df = pd.DataFrame(rows).set_index('time')
        df.index = pd.to_datetime(df.index, utc=True)
        return df

    def get_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        timeframe: Any
    ) -> pd.DataFrame:
        """Generate synthetic historical data.

        Args:
            ticker: Asset symbol (ignored, for API compatibility)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            timeframe: Timeframe string (M5, H1, etc.)

        Returns:
            DataFrame with synthetic OHLCV data
        """
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            days_diff = (end_dt - start_dt).days

            # Estimate candle count based on timeframe
            interval_map = {'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240, 'D1': 1440}
            interval_minutes = interval_map.get(timeframe, 5)
            count = int((days_diff * 1440) / interval_minutes)  # 1440 min/day
            count = min(count, 10000)  # Limit for performance

        except ValueError:
            logger.warning("Invalid date format, generating 500 candles")
            count = 500
            interval_minutes = 5

        logger.info(f"Generating {count} synthetic candles for {ticker}")
        return self._generate_candles(count, interval_minutes)

    def get_latest_candles(
        self,
        ticker: str,
        timeframe: Any,
        count: int
    ) -> pd.DataFrame:
        """Generate synthetic recent candles.

        Args:
            ticker: Asset symbol (ignored)
            timeframe: Timeframe string
            count: Number of candles to generate

        Returns:
            DataFrame with synthetic OHLCV data
        """
        interval_map = {'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240, 'D1': 1440}
        interval_minutes = interval_map.get(timeframe, 5)

        logger.info(f"Generating {count} synthetic recent candles for {ticker}")
        return self._generate_candles(count, interval_minutes)


class HybridProvider(BaseDataProvider):
    """Hybrid data provider with intelligent fallback cascade.

    Attempts data retrieval in order:
    1. MetaTrader5 (if available and connected)
    2. Cache (Parquet files)
    3. Synthetic (always succeeds)

    Thread-safe for concurrent web requests.
    """

    _instance: Optional[HybridProvider] = None
    _lock = threading.Lock()

    def __new__(cls) -> HybridProvider:
        """Implement singleton pattern."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        """Initialize hybrid provider with fallback chain."""
        if self._initialized:
            return

        self.mt5_provider = MetaTraderProvider() if MT5_AVAILABLE else None
        self.cache_provider = CacheProvider()
        self.synthetic_provider = SyntheticProvider()
        self.database_provider = DataBaseProvider()

        self._initialized = True
        logger.info("HybridProvider initialized with fallback chain: MT5 → Cache → Synthetic")

    def get_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        timeframe: Any
    ) -> pd.DataFrame:
        """Fetch historical data with intelligent fallback.

        Args:
            ticker: Asset symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            timeframe: Timeframe specification

        Returns:
            DataFrame with OHLCV data from first successful provider
        """
        # Try MT5
        if self.mt5_provider and self.mt5_provider.is_connected():
            # Convert timeframe string to MT5 constant if needed
            if isinstance(timeframe, str):
                tf_const = self.mt5_provider._get_mt5_timeframe(timeframe)
                if tf_const:
                    df = self.mt5_provider.get_data(ticker, start_date, end_date, tf_const)
                    if not df.empty:
                        logger.info(f"Data source: MetaTrader5 ({len(df)} candles)")
                        return df

        # Try Cache
        df = self.cache_provider.get_data(ticker, start_date, end_date, timeframe)
        if not df.empty:
            logger.info(f"Data source: Cache ({len(df)} candles)")
            return df

        # Fallback to Synthetic
        logger.warning("Falling back to synthetic data generation")
        df = self.synthetic_provider.get_data(ticker, start_date, end_date, timeframe)
        logger.info(f"Data source: Synthetic ({len(df)} candles)")
        return df

    def get_latest_candles(
        self,
        ticker: str,
        timeframe: Any,
        count: int
    ) -> pd.DataFrame:
        """Fetch recent candles with intelligent fallback.

        Args:
            ticker: Asset symbol
            timeframe: Timeframe specification
            count: Number of candles to retrieve

        Returns:
            DataFrame with OHLCV data from first successful provider
        """
        # Try MT5
        if self.mt5_provider and self.mt5_provider.is_connected():
            if isinstance(timeframe, str):
                tf_const = self.mt5_provider._get_mt5_timeframe(timeframe)
                if tf_const:
                    df = self.mt5_provider.get_latest_candles(ticker, tf_const, count)
                    if not df.empty:
                        logger.info(f"Latest candles source: MetaTrader5 ({len(df)} candles)")
                        return df

        # Try Cache
        df = self.cache_provider.get_latest_candles(ticker, timeframe, count)
        if not df.empty:
            logger.info(f"Latest candles source: Cache ({len(df)} candles)")
            return df

        # Fallback to Synthetic
        logger.warning("Falling back to synthetic data for latest candles")
        df = self.synthetic_provider.get_latest_candles(ticker, timeframe, count)
        logger.info(f"Latest candles source: Synthetic ({len(df)} candles)")
        return df

    def is_connected(self) -> bool:
        """Check if any provider is operational.

        Returns:
            True if at least one provider can serve data
        """
        return (
            (self.mt5_provider and self.mt5_provider.is_connected()) or
            True  # Cache and Synthetic always available
        )

    def close_connection(self) -> None:
        """Close all provider connections."""
        if self.mt5_provider:
            self.mt5_provider.close_connection()


def get_provider(provider_type: str = 'hybrid') -> BaseDataProvider:
    """Factory function to instantiate data providers.

    Args:
        provider_type: Provider type ('mt5', 'cache', 'synthetic', 'hybrid')

    Returns:
        Configured data provider instance

    Raises:
        ValueError: If provider_type is unknown
    """
    provider_type = provider_type.lower()

    if provider_type == 'mt5':
        return MetaTraderProvider()
    elif provider_type == 'cache':
        return CacheProvider()
    elif provider_type == 'synthetic':
        return SyntheticProvider()
    elif provider_type == 'hybrid':
        return HybridProvider()
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")


# Singleton instance for convenience
_default_provider: Optional[HybridProvider] = None


def get_default_provider() -> HybridProvider:
    """Get default hybrid provider singleton.

    Returns:
        Shared HybridProvider instance
    """
    global _default_provider
    if _default_provider is None:
        _default_provider = HybridProvider()
    return _default_provider
