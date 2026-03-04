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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Callable

import pandas as pd
import yaml

from newapp.src.data_handler.provider import get_default_provider
from newapp.src.analysis.context_analyzer import MarketContextAnalyzer
from newapp.src.live.rules import BaseDecisionRule, RULE_REGISTRY
from newapp.src.ml.legacy_monitor_engine import get_legacy_monitor_engine
from newapp.src.services.prediction_service import build_canonical_monitor_payload
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
        enable_db_persistence: bool = False,
        config_path: str = "configs/main.yaml",
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
        self.config_path = config_path
        
        # Initialize components
        logger.info("Initializing data provider...")
        self.provider = get_default_provider()
        
        logger.info("Initializing market context analyzer...")
        self.analyzer = MarketContextAnalyzer()
        self.legacy_monitor_engine = get_legacy_monitor_engine()
        
        self.repository = None
        
        # State
        self.buffer_df: Optional[pd.DataFrame] = None
        self.callbacks: list[Callable] = []
        self.running = False
        self.last_processed_time: Optional[datetime] = None
        self.decision_rules: list[BaseDecisionRule] = self._load_active_rules()
        
        logger.info(f"✅ Monitor initialized: {ticker} @ {timeframe_str}")
        logger.info(
            "✅ Decision rules loaded: %s",
            [rule.__class__.__name__ for rule in self.decision_rules],
        )
        logger.info("=" * 80)

    def _load_active_rules(self) -> list[BaseDecisionRule]:
        """Load and instantiate active decision rules from YAML config."""
        active_rule_names = self._read_active_rules_from_config()
        if not active_rule_names:
            logger.warning(
                "No active_rules configured for %s @ %s; decision block keeps base strategy result",
                self.ticker,
                self.timeframe_str,
            )
            return []

        instances: list[BaseDecisionRule] = []
        for rule_name in active_rule_names:
            rule_class = RULE_REGISTRY.get(rule_name)
            if rule_class is None:
                logger.warning(
                    "Skipping unknown decision rule '%s' for %s @ %s",
                    rule_name,
                    self.ticker,
                    self.timeframe_str,
                )
                continue
            instances.append(rule_class())

        return instances

    def _read_active_rules_from_config(self) -> list[str]:
        """Read active_rules from configs/main.yaml with graceful fallback."""
        config = self._load_yaml_config()
        if not config:
            return []

        assets = config.get("assets", []) if isinstance(config, dict) else []
        ticker_norm = str(self.ticker or "").upper()
        timeframe_norm = str(self.timeframe_str or "").upper()

        for asset in assets:
            if not isinstance(asset, dict):
                continue
            if str(asset.get("ticker", "")).upper() != ticker_norm:
                continue

            live_trading = asset.get("live_trading", {})
            if isinstance(live_trading, dict):
                asset_timeframe = str(
                    live_trading.get("timeframe_str", "")
                ).upper()
                if asset_timeframe in {"", timeframe_norm}:
                    rules = live_trading.get("active_rules")
                    if isinstance(rules, list):
                        return [str(item) for item in rules if str(item).strip()]

            asset_rules = asset.get("active_rules")
            if isinstance(asset_rules, list):
                return [str(item) for item in asset_rules if str(item).strip()]

        monitor_rules = config.get("monitor_rules", {})
        if isinstance(monitor_rules, dict):
            rules = monitor_rules.get("active_rules")
            if isinstance(rules, list):
                return [str(item) for item in rules if str(item).strip()]

        return []

    def _load_yaml_config(self) -> dict[str, Any]:
        """Load monitor YAML config from project-level path."""
        possible_paths = [
            Path(self.config_path),
            Path(__file__).resolve().parents[3] / "configs" / "main.yaml",
        ]

        for config_candidate in possible_paths:
            try:
                if not config_candidate.exists():
                    continue
                with config_candidate.open("r", encoding="utf-8") as config_file:
                    parsed = yaml.safe_load(config_file) or {}
                    if isinstance(parsed, dict):
                        return parsed
            except Exception as exc:
                logger.warning(
                    "Failed to read monitor config path=%s error=%s",
                    config_candidate,
                    exc,
                )

        logger.warning("Unable to load monitor rules config from known paths")
        return {}

    def _apply_decision_rules(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply active decision rules in order and update decision block."""
        if not self.decision_rules:
            return payload

        decision = dict(payload.get("decision", {}))
        base_valid = bool(decision.get("signal_valid", False))
        default_reason = str(
            decision.get("validation_reason", "Sinal validado pelas regras ativas")
        )
        if not base_valid:
            decision["status"] = "NÃO VALIDADO"
            decision["validation_reason"] = default_reason
            payload["decision"] = decision
            return payload

        decision["signal_valid"] = True
        decision["status"] = "VALIDADO"
        decision["validation_reason"] = default_reason

        final_reason = default_reason
        for rule in self.decision_rules:
            rule_valid, reason = rule.evaluate(payload)
            if str(reason).strip():
                final_reason = str(reason).strip()
            if not rule_valid:
                decision["signal_valid"] = False
                decision["status"] = "NÃO VALIDADO"
                decision["validation_reason"] = str(reason).strip() or (
                    f"Sinal bloqueado pela regra {rule.__class__.__name__}"
                )
                payload["decision"] = decision
                return payload

        decision["validation_reason"] = final_reason
        payload["decision"] = decision
        return payload
    
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
        """Process latest candle and generate canonical combined payload."""
        try:
            if self.buffer_df is None or self.buffer_df.empty:
                raise ValueError("Buffer not initialized")
            
            # Get latest candle
            latest_candle = self.buffer_df.iloc[-1]
            candle_time = self.buffer_df.index[-1]

            analysis_context = self.analyzer.analyze(self.buffer_df.copy())
            ml_result = self.legacy_monitor_engine.predict_on_candle(
                data=self.buffer_df.copy(),
                symbol=self.ticker,
                timeframe=self.timeframe_str,
            )
            result = self._build_canonical_payload(
                candle_time=candle_time,
                latest_candle=latest_candle,
                analysis_context=analysis_context,
                ml_result=ml_result,
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing candle: {e}", exc_info=True)
            raise

    def _build_canonical_payload(
        self,
        candle_time: datetime,
        latest_candle: pd.Series,
        analysis_context: Dict[str, Any],
        ml_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build canonical payload used by realtime monitor and APIs.

        Mandatory contract fields:
        timestamp, ticker, timeframe, ohlcv, indicators, analysis, ml, decision.
        """
        close_series = self.buffer_df["close"] if self.buffer_df is not None else pd.Series(dtype=float)
        ema_20_value = float(close_series.ewm(span=20, adjust=False).mean().iloc[-1]) if not close_series.empty else 0.0

        ohlcv = {
            "open": float(latest_candle.get("open", 0.0)),
            "high": float(latest_candle.get("high", 0.0)),
            "low": float(latest_candle.get("low", 0.0)),
            "close": float(latest_candle.get("close", 0.0)),
            "volume": int(latest_candle.get("volume", 0)) if not pd.isna(latest_candle.get("volume", 0)) else 0,
        }

        indicators = {
            "ema_9": float(ml_result.get("ema_9", analysis_context.get("ema_fast", 0.0))) if ml_result else float(analysis_context.get("ema_fast", 0.0)),
            "ema_20": float(ml_result.get("ema_20", ema_20_value)) if ml_result else ema_20_value,
            "sma_20": float(ml_result.get("sma_20", analysis_context.get("sma_fast", 0.0))) if ml_result else float(analysis_context.get("sma_fast", 0.0)),
            "sma_50": float(ml_result.get("sma_50", analysis_context.get("sma_slow", 0.0))) if ml_result else float(analysis_context.get("sma_slow", 0.0)),
            "rsi_14": float(ml_result.get("rsi", analysis_context.get("rsi", 0.0))) if ml_result else float(analysis_context.get("rsi", 0.0)),
        }

        analysis = {
            "trend": str(analysis_context.get("trend", "INDEFINIDO")),
            "trend_strength": str(analysis_context.get("trend_strength", "INDEFINIDO")),
            "support": float(analysis_context.get("support", 0.0)),
            "resistance": float(analysis_context.get("resistance", 0.0)),
            "pattern": str(analysis_context.get("pattern", "INDEFINIDO")),
            "rsi_condition": str(analysis_context.get("rsi_condition", "INDEFINIDO")),
        }

        ml_signal = str(ml_result.get("signal", "HOLD")) if ml_result else "HOLD"
        ml_direction = str(ml_result.get("direction", "HOLD")) if ml_result else "HOLD"
        ml_probability = float(ml_result.get("probability", 0.0)) if ml_result else 0.0

        if ml_result:
            base_signal_valid = bool(ml_result.get("signal_valid", False))
            base_validation_reason = str(ml_result.get("validation_reason", ""))
        else:
            base_signal_valid = False
            base_validation_reason = "Sem resultado ML para o candle atual"

        payload = build_canonical_monitor_payload(
            timestamp_value=candle_time,
            ticker=self.ticker,
            timeframe=self.timeframe_str,
            ohlcv=ohlcv,
            indicators=indicators,
            analysis=analysis,
            ml_signal=ml_signal,
            ml_direction=ml_direction,
            ml_probability=ml_probability,
            base_signal_valid=base_signal_valid,
            base_validation_reason=base_validation_reason,
        )

        return self._apply_decision_rules(payload)
    
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

        # First tick immediately after warm-up
        try:
            first_tick = self._process_new_candle()
            self.last_processed_time = first_tick["timestamp"]
            self._notify_callbacks(first_tick)
            logger.info("✅ First tick emitted immediately: %s", first_tick["timestamp"])
        except Exception as exc:
            logger.error("Failed to emit first tick after warm-up: %s", exc, exc_info=True)
        
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
                        ticker=self.ticker,
                        timeframe=self.timeframe_str,
                        count=1
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
                    self.buffer_df = self.buffer_df[~self.buffer_df.index.duplicated(keep='last')]
                    self.buffer_df = self.buffer_df.sort_index()
                    
                    # Maintain buffer size
                    if len(self.buffer_df) > self.buffer_size:
                        self.buffer_df = self.buffer_df.iloc[-self.buffer_size:]
                    
                    # Process candle
                    result = self._process_new_candle()

                    if self.last_processed_time is not None and result['timestamp'] <= self.last_processed_time:
                        logger.debug("Skipping duplicated candle timestamp: %s", result['timestamp'])
                        continue

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

        # First tick immediately after warm-up
        try:
            first_tick = await asyncio.to_thread(self._process_new_candle)
            self.last_processed_time = first_tick["timestamp"]
            self._notify_callbacks(first_tick)
            logger.info("✅ Async first tick emitted immediately: %s", first_tick["timestamp"])
        except Exception as exc:
            logger.error("Failed to emit async first tick after warm-up: %s", exc, exc_info=True)
        
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
                        ticker=self.ticker,
                        timeframe=self.timeframe_str,
                        count=1
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
                    self.buffer_df = self.buffer_df[~self.buffer_df.index.duplicated(keep='last')]
                    self.buffer_df = self.buffer_df.sort_index()
                    
                    if len(self.buffer_df) > self.buffer_size:
                        self.buffer_df = self.buffer_df.iloc[-self.buffer_size:]
                    
                    # Process in thread pool
                    result = await asyncio.to_thread(self._process_new_candle)

                    if self.last_processed_time is not None and result['timestamp'] <= self.last_processed_time:
                        logger.debug("Skipping duplicated async candle timestamp: %s", result['timestamp'])
                        continue

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
