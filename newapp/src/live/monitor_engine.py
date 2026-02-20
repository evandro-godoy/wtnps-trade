"""Real-time Market Monitor for newapp.

Modern implementation using existing newapp infrastructure:
- HybridProvider for data fetching (MT5 → Cache → Synthetic)
- MarketContextAnalyzer for technical analysis
- Database repository for persistence
- WebSocket-ready for real-time streaming to web UI

This version is optimized for web-based monitoring vs legacy desktop UI.
"""
from __future__ import annotations

import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from pathlib import Path

import pandas as pd
import numpy as np

from newapp.src.data_handler.provider import get_default_provider
from newapp.src.analysis.context_analyzer import MarketContextAnalyzer
from newapp.src.database.repository import AssetsRatesRepository
from newapp.configs.config import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME

logger = logging.getLogger(__name__)


class RealtimeMarketMonitor:
    """Real-time market monitoring engine for newapp.
    
    Monitors market candles and generates trading signals using ML/technical analysis.
    Designed for async/WebSocket streaming to web clients.
    
    Key differences from legacy monitor:
    - Uses HybridProvider (MT5 → Cache → Synthetic fallback)
    - Async-first design for FastAPI/WebSocket integration
    - Database persistence via AssetsRatesRepository
    - No model loading (uses context analyzer only for now - models can be added later)
    - Callback-based architecture for UI updates
    
    Attributes:
        ticker (str): Asset symbol to monitor
        timeframe_str (str): Timeframe string (M1, M5, etc.)
        buffer_size (int): Number of historical candles to maintain
        provider: Data provider instance
        analyzer: Technical analysis engine
        repository: Database repository for persistence
        buffer_df (pd.DataFrame): Historical candle buffer
        callbacks (list): List of callback functions for updates
        running (bool): Monitor execution state
    """
    
    def __init__(
        self,
        ticker: str = DEFAULT_SYMBOL,
        timeframe_str: str = DEFAULT_TIMEFRAME,
        buffer_size: int = 500,
        enable_db_persistence: bool = False
    ):
        """Initialize real-time monitor.
        
        Args:
            ticker: Asset symbol (e.g., "WDO$", "WIN$")
            timeframe_str: Timeframe string (M1, M5, M15, M30, H1, H4, D1)
            buffer_size: Number of candles to keep in memory buffer
            enable_db_persistence: Save processed candles to database
        """
        logger.info("=" * 80)
        logger.info("INITIALIZING REALTIME MARKET MONITOR (newapp)")
        logger.info("=" * 80)
        
        self.ticker = ticker
        self.timeframe_str = timeframe_str
        self.buffer_size = buffer_size
        self.enable_db_persistence = enable_db_persistence
        
        # Initialize components
        logger.info("Initializing data provider...")
        self.provider = get_default_provider()
        
        logger.info("Initializing market context analyzer...")
        self.analyzer = MarketContextAnalyzer()
        
        if enable_db_persistence:
            logger.info("Initializing database repository...")
            self.repository = AssetsRatesRepository()
        else:
            self.repository = None
        
        # State
        self.buffer_df: Optional[pd.DataFrame] = None
        self.callbacks: list[Callable] = []
        self.running = False
        self.last_processed_time: Optional[datetime] = None
        
        logger.info(f"✅ Monitor initialized: {ticker} @ {timeframe_str}")
        logger.info("=" * 80)
    
    def register_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register callback function for market updates.
        
        Callback will be called with dict containing:
        - timestamp: Candle timestamp
        - ticker: Asset symbol
        - timeframe: Timeframe string
        - ohlcv: {open, high, low, close, volume}
        - analysis: Technical analysis results
        - signal: Trading signal (if any)
        
        Args:
            callback: Function to call on each update
        """
        self.callbacks.append(callback)
        logger.info(f"Registered callback: {callback.__name__}")
    
    def _notify_callbacks(self, data: Dict[str, Any]) -> None:
        """Notify all registered callbacks with update data.
        
        Args:
            data: Market update data dictionary
        """
        for callback in self.callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in callback {callback.__name__}: {e}")
    
    def _warm_up(self) -> None:
        """Warm up buffer with historical candles.
        
        Fetches buffer_size candles from provider to initialize the system.
        Uses HybridProvider's fallback chain (MT5 → Cache → Synthetic).
        """
        logger.info(f"WARM-UP: Fetching {self.buffer_size} historical candles...")
        
        try:
            data = self.provider.get_latest_candles(
                ticker=self.ticker,
                timeframe=self.timeframe_str,
                count=self.buffer_size
            )
            
            if data.empty:
                logger.warning("No data returned from provider, using synthetic fallback")
                # Provider should auto-fallback, but double-check
                return
            
            # Validate required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing = [col for col in required_cols if col not in data.columns]
            if missing:
                raise ValueError(f"Missing required columns: {missing}")
            
            self.buffer_df = data[required_cols].copy()
            
            logger.info(f"✅ Buffer initialized with {len(self.buffer_df)} candles")
            logger.info(f"   Period: {self.buffer_df.index[0]} → {self.buffer_df.index[-1]}")
            
        except Exception as e:
            logger.error(f"Warm-up failed: {e}", exc_info=True)
            raise
    
    def _process_new_candle(self) -> Dict[str, Any]:
        """Process latest candle and generate analysis.
        
        Returns:
            Dictionary with processing results:
            - timestamp: Candle timestamp
            - ticker: Asset symbol
            - timeframe: Timeframe string
            - ohlcv: OHLCV data
            - analysis: Technical analysis from MarketContextAnalyzer
            - indicators: Calculated indicators
        """
        try:
            if self.buffer_df is None or self.buffer_df.empty:
                raise ValueError("Buffer not initialized")
            
            # Get latest candle
            latest_candle = self.buffer_df.iloc[-1]
            candle_time = self.buffer_df.index[-1]
            
            # Run technical analysis
            analysis_result = self.analyzer.analyze(self.buffer_df.copy())
            
            # Extract indicators from last row
            indicators = {}
            if 'ema_9' in analysis_result.columns:
                indicators['ema_9'] = float(analysis_result['ema_9'].iloc[-1])
            if 'sma_20' in analysis_result.columns:
                indicators['sma_20'] = float(analysis_result['sma_20'].iloc[-1])
            if 'sma_50' in analysis_result.columns:
                indicators['sma_50'] = float(analysis_result['sma_50'].iloc[-1])
            if 'sma_200' in analysis_result.columns:
                indicators['sma_200'] = float(analysis_result['sma_200'].iloc[-1])
            if 'rsi_14' in analysis_result.columns:
                indicators['rsi_14'] = float(analysis_result['rsi_14'].iloc[-1])
            
            # Build result
            result = {
                'timestamp': candle_time,
                'ticker': self.ticker,
                'timeframe': self.timeframe_str,
                'ohlcv': {
                    'open': float(latest_candle['open']),
                    'high': float(latest_candle['high']),
                    'low': float(latest_candle['low']),
                    'close': float(latest_candle['close']),
                    'volume': int(latest_candle['volume']) if not pd.isna(latest_candle['volume']) else 0
                },
                'indicators': indicators,
                'analysis': {
                    'trend': 'neutral',  # TODO: Extract from analyzer
                    'strength': 'medium',
                    'rsi_condition': self._get_rsi_condition(indicators.get('rsi_14'))
                }
            }
            
            # Persist to DB if enabled
            if self.enable_db_persistence and self.repository:
                try:
                    # Convert to DataFrame row for repository
                    df_row = pd.DataFrame([{
                        'open': result['ohlcv']['open'],
                        'high': result['ohlcv']['high'],
                        'low': result['ohlcv']['low'],
                        'close': result['ohlcv']['close'],
                        'volume': result['ohlcv']['volume'],
                        **indicators
                    }], index=[candle_time])
                    
                    # Map timeframe to seconds
                    timeframe_seconds = self._timeframe_to_seconds(self.timeframe_str)
                    
                    self.repository.save_rates_dataframe(
                        df=df_row,
                        ticker=self.ticker,
                        timeframe_seconds=timeframe_seconds
                    )
                    logger.debug(f"Persisted candle to DB: {candle_time}")
                except Exception as e:
                    logger.error(f"DB persistence failed: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing candle: {e}", exc_info=True)
            raise
    
    def _get_rsi_condition(self, rsi: Optional[float]) -> str:
        """Get RSI condition label.
        
        Args:
            rsi: RSI value
            
        Returns:
            Condition label: oversold, overbought, or neutral
        """
        if rsi is None:
            return 'unknown'
        if rsi < 30:
            return 'oversold'
        elif rsi > 70:
            return 'overbought'
        else:
            return 'neutral'
    
    def _timeframe_to_seconds(self, timeframe_str: str) -> int:
        """Convert timeframe string to seconds.
        
        Args:
            timeframe_str: Timeframe (M1, M5, H1, etc.)
            
        Returns:
            Timeframe in seconds
        """
        mapping = {
            'M1': 60,
            'M5': 300,
            'M15': 900,
            'M30': 1800,
            'H1': 3600,
            'H4': 14400,
            'D1': 86400,
            'W1': 604800,
            'MN1': 2592000
        }
        return mapping.get(timeframe_str.upper(), 300)
    
    def _calculate_sleep_until_next_candle(self) -> float:
        """Calculate seconds to sleep until next candle closes.
        
        Returns:
            Seconds to sleep
        """
        now = datetime.now()
        timeframe_seconds = self._timeframe_to_seconds(self.timeframe_str)
        
        # Calculate seconds since epoch
        epoch_seconds = int(now.timestamp())
        
        # Calculate next candle close time
        next_close = ((epoch_seconds // timeframe_seconds) + 1) * timeframe_seconds
        
        # Sleep time (add 5 seconds buffer to ensure candle is fully closed)
        sleep_seconds = (next_close - epoch_seconds) + 5
        
        return max(sleep_seconds, 5)  # Minimum 5 seconds
    
    def start(self) -> None:
        """Start monitoring loop (blocking).
        
        This is a synchronous blocking loop for CLI/script usage.
        For async/WebSocket usage, use start_async() instead.
        """
        logger.info("=" * 80)
        logger.info("STARTING REALTIME MONITORING (BLOCKING MODE)")
        logger.info("=" * 80)
        
        self.running = True
        
        # Warm up
        self._warm_up()
        
        logger.info(f"""
Monitor configured and ready!
Ticker: {self.ticker}
Timeframe: {self.timeframe_str}
Buffer size: {self.buffer_size}
DB persistence: {self.enable_db_persistence}

Press Ctrl+C to stop.
        """)
        logger.info("=" * 80)
        
        consecutive_errors = 0
        max_errors = 5
        
        try:
            while self.running:
                try:
                    # Sleep until next candle
                    sleep_time = self._calculate_sleep_until_next_candle()
                    logger.info(f"Waiting {sleep_time:.0f}s for next candle...")
                    time.sleep(sleep_time)
                    
                    # Fetch new candle
                    new_data = self.provider.get_latest_candles(
                        symbol=self.ticker,
                        timeframe=self.timeframe_str,
                        limit=1
                    )
                    
                    if new_data.empty:
                        logger.warning("No data returned from provider")
                        consecutive_errors += 1
                        if consecutive_errors >= max_errors:
                            logger.critical(f"Max consecutive errors ({max_errors}) reached")
                            break
                        continue
                    
                    # Update buffer
                    new_candle = new_data.iloc[-1:]
                    self.buffer_df = pd.concat([self.buffer_df, new_candle])
                    
                    # Maintain buffer size
                    if len(self.buffer_df) > self.buffer_size:
                        self.buffer_df = self.buffer_df.iloc[-self.buffer_size:]
                    
                    # Process candle
                    result = self._process_new_candle()
                    self.last_processed_time = result['timestamp']
                    
                    # Notify callbacks
                    self._notify_callbacks(result)
                    
                    logger.info(
                        f"✅ Processed: {result['timestamp']} | "
                        f"Close: {result['ohlcv']['close']:.2f} | "
                        f"RSI: {result['indicators'].get('rsi_14', 0):.1f}"
                    )
                    
                    # Reset error counter
                    consecutive_errors = 0
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        logger.critical(f"Max consecutive errors ({max_errors}) reached")
                        break
                    time.sleep(30)
        
        except KeyboardInterrupt:
            logger.info("\nKeyboard interrupt detected (Ctrl+C)")
        finally:
            self.running = False
            logger.info("=" * 80)
            logger.info("MONITOR STOPPED")
            logger.info("=" * 80)
    
    def stop(self) -> None:
        """Stop monitoring loop gracefully."""
        logger.info("Stop requested...")
        self.running = False
    
    async def start_async(self, callback: Optional[Callable] = None) -> None:
        """Start monitoring loop (async, non-blocking).
        
        Async version for FastAPI/WebSocket integration.
        Runs monitoring in background task.
        
        Args:
            callback: Optional callback for each update
        """
        if callback:
            self.register_callback(callback)
        
        logger.info("Starting async monitoring loop...")
        self.running = True
        
        # Warm up in thread pool to avoid blocking
        await asyncio.to_thread(self._warm_up)
        
        consecutive_errors = 0
        max_errors = 5
        
        try:
            while self.running:
                try:
                    # Calculate sleep time
                    sleep_time = self._calculate_sleep_until_next_candle()
                    await asyncio.sleep(sleep_time)
                    
                    # Fetch new candle (blocking I/O in thread)
                    new_data = await asyncio.to_thread(
                        self.provider.get_latest_candles,
                        symbol=self.ticker,
                        timeframe=self.timeframe_str,
                        limit=1
                    )
                    
                    if new_data.empty:
                        logger.warning("No data from provider")
                        consecutive_errors += 1
                        if consecutive_errors >= max_errors:
                            break
                        continue
                    
                    # Update buffer
                    new_candle = new_data.iloc[-1:]
                    self.buffer_df = pd.concat([self.buffer_df, new_candle])
                    
                    if len(self.buffer_df) > self.buffer_size:
                        self.buffer_df = self.buffer_df.iloc[-self.buffer_size:]
                    
                    # Process in thread pool
                    result = await asyncio.to_thread(self._process_new_candle)
                    self.last_processed_time = result['timestamp']
                    
                    # Notify callbacks
                    self._notify_callbacks(result)
                    
                    logger.info(f"✅ Async processed: {result['timestamp']}")
                    
                    consecutive_errors = 0
                    
                except asyncio.CancelledError:
                    logger.info("Async monitoring cancelled")
                    break
                except Exception as e:
                    logger.error(f"Async monitoring error: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        break
                    await asyncio.sleep(30)
        finally:
            self.running = False
            logger.info("Async monitoring stopped")
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current monitor state for status checks.
        
        Returns:
            Dictionary with current state info
        """
        return {
            'running': self.running,
            'ticker': self.ticker,
            'timeframe': self.timeframe_str,
            'buffer_size': len(self.buffer_df) if self.buffer_df is not None else 0,
            'last_processed': self.last_processed_time.isoformat() if self.last_processed_time else None,
            'callbacks_registered': len(self.callbacks)
        }
