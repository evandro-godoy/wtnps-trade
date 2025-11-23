"""Market Context Analyzer - Classic Technical Analysis.

Provides trend analysis, strength indicators, support/resistance levels,
and price action patterns for enriching ML signals in the web application.

This module is a self-contained version adapted from src/analysis/context_analyzer.py
for use in the newapp web interface.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class MarketContextAnalyzer:
    """Market technical context analyzer.
    
    Combines multiple classic technical indicators to provide complete
    context about trend, strength, and key levels.
    
    Attributes:
        ema_fast: Fast EMA period for trend analysis
        sma_fast: Fast SMA period for trend analysis
        sma_slow: Slow SMA period for trend analysis
        sma_lookback: Periods to calculate slow SMA slope
        rsi_period: RSI calculation period
        lookback_levels: Periods for support/resistance calculation
        strong_candle_threshold: % of range for strong candle classification
    """
    
    def __init__(
        self,
        ema_fast: int = 9,
        sma_fast: int = 20,
        sma_slow: int = 50,
        sma_lookback: int = 25,
        rsi_period: int = 14,
        lookback_levels: int = 30,
        strong_candle_threshold: float = 0.65
    ) -> None:
        """Initialize market context analyzer.
        
        Args:
            ema_fast: Fast EMA period (default: 9)
            sma_fast: Fast SMA period (default: 20)
            sma_slow: Slow SMA period (default: 50)
            sma_lookback: Periods for slow SMA slope (default: 25)
            rsi_period: RSI period (default: 14)
            lookback_levels: Periods for support/resistance (default: 30)
            strong_candle_threshold: Minimum body % for strong candle (default: 0.65)
        """
        self.ema_fast = ema_fast
        self.sma_fast = sma_fast
        self.sma_slow = sma_slow
        self.sma_lookback = sma_lookback
        self.rsi_period = rsi_period
        self.lookback_levels = lookback_levels
        self.strong_candle_threshold = strong_candle_threshold
        
        logger.info(
            f"MarketContextAnalyzer initialized: EMA{ema_fast}, SMA_FAST{sma_fast}, "
            f"SMA_SLOW{sma_slow}, SLOPE_LOOKBACK{sma_lookback}, RSI{rsi_period}, "
            f"LEVELS_LOOKBACK{lookback_levels}, STRONG_CANDLE_THRESH{strong_candle_threshold}"
        )
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """Execute complete technical market analysis.
        
        Args:
            df: DataFrame with OHLCV (index: datetime, cols: open, high, low, close, volume)
        
        Returns:
            Dictionary with complete analysis:
            {
                'trend': str,  # 'ALTA', 'BAIXA', 'LATERAL'
                'trend_strength': str,  # 'FORTE', 'MODERADA', 'FRACA'
                'rsi': float,
                'rsi_condition': str,  # 'SOBRECOMPRADO', 'SOBREVENDIDO', 'NEUTRO'
                'support': float,
                'resistance': float,
                'distance_to_support': float,  # % distance
                'distance_to_resistance': float,  # % distance
                'pattern': str,  # 'BARRA_FORTE_ALTA', 'BARRA_FORTE_BAIXA', etc.
                'ema_fast': float,
                'sma_fast': float,
                'sma_slow': float,
                'current_price': float
            }
        """
        try:
            if df.empty or len(df) < max(self.sma_slow, self.lookback_levels):
                logger.warning(f"Insufficient DataFrame for analysis: {len(df)} rows")
                return self._empty_analysis()
            
            # Copy to avoid modifying original
            data = df.copy()
            
            # Calculate indicators
            data = self._calculate_indicators(data)
            
            # Get last row (most recent candle)
            last = data.iloc[-1]
            current_price = last['close']
            
            # 1. Trend Analysis
            trend, trend_strength = self._analyze_trend(data)
            
            # 2. Strength Analysis (RSI)
            rsi = last['rsi']
            rsi_condition = self._get_rsi_condition(rsi)
            
            # 3. Support and Resistance Levels
            support, resistance = self._find_support_resistance(data)
            
            # Calculate distances
            distance_to_support = ((current_price - support) / support * 100) if support > 0 else 0
            distance_to_resistance = ((resistance - current_price) / current_price * 100) if resistance > 0 else 0
            
            # 4. Price Action Analysis (last candle)
            pattern = self._analyze_price_action(last)
            
            # Build result
            context = {
                'trend': trend,
                'trend_strength': trend_strength,
                'rsi': round(rsi, 2),
                'rsi_condition': rsi_condition,
                'support': round(support, 2),
                'resistance': round(resistance, 2),
                'distance_to_support': round(distance_to_support, 2),
                'distance_to_resistance': round(distance_to_resistance, 2),
                'pattern': pattern,
                'ema_fast': round(last['ema_fast'], 2),
                'sma_fast': round(last.get('sma_fast', np.nan), 2),
                'sma_slow': round(last['sma_slow'], 2),
                'current_price': round(current_price, 2)
            }
            
            logger.debug(f"Complete analysis: {context}")
            return context
        
        except Exception as e:
            logger.error(f"Error in context analysis: {e}", exc_info=True)
            return self._empty_analysis()
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required technical indicators.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with added indicator columns
        """
        # Fast EMA
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        
        # Fast SMA
        df['sma_fast'] = df['close'].rolling(window=self.sma_fast).mean()
        
        # Slow SMA
        df['sma_slow'] = df['close'].rolling(window=self.sma_slow).mean()
        
        # RSI
        df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)
        
        return df
    
    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        """Calculate Relative Strength Index (RSI).
        
        Args:
            series: Price close series
            period: RSI period
        
        Returns:
            Series with RSI values
        """
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _analyze_trend(self, df: pd.DataFrame) -> Tuple[str, str]:
        """Analyze trend using moving average crossover and slope.
        
        Args:
            df: DataFrame with calculated indicators
        
        Returns:
            Tuple (trend, strength):
            - trend: 'ALTA', 'BAIXA', 'LATERAL'
            - strength: 'FORTE', 'MODERADA', 'FRACA'
        """
        last = df.iloc[-1]
        
        ema_fast = last['ema_fast']
        sma_fast = last['sma_fast']
        sma_slow = last['sma_slow']
        close = last['close']
        
        # Check moving average crossover
        ema_above_smas = ema_fast > sma_fast and ema_fast > sma_slow
        ema_bellow_smas = ema_fast < sma_fast and ema_fast < sma_slow
        price_above_ema = close > ema_fast
        
        # Calculate slow SMA slope using configurable window
        valid_sma = df['sma_slow'].dropna()
        if len(valid_sma) >= self.sma_lookback:
            start_val = valid_sma.iloc[-self.sma_lookback]
            end_val = valid_sma.iloc[-1]
            sma_slope = (end_val - start_val) / start_val * 100 if start_val else 0
        elif len(valid_sma) >= 5:
            start_val = valid_sma.iloc[-5]
            end_val = valid_sma.iloc[-1]
            sma_slope = (end_val - start_val) / start_val * 100 if start_val else 0
        else:
            sma_slope = 0
        
        # Determine trend
        if ema_above_smas and price_above_ema:
            trend = 'ALTA'
        elif ema_bellow_smas and not price_above_ema:
            trend = 'BAIXA'
        else:
            trend = 'LATERAL'
        
        # Determine trend strength
        slope_abs = abs(sma_slope)
        
        if slope_abs > 1.0:
            strength = 'FORTE'
        elif slope_abs > 0.3:
            strength = 'MODERADA'
        else:
            strength = 'FRACA'
        
        # If sideways, strength always weak
        if trend == 'LATERAL':
            strength = 'FRACA'
        
        return trend, strength
    
    def _get_rsi_condition(self, rsi: float) -> str:
        """Classify RSI condition.
        
        Args:
            rsi: RSI value
        
        Returns:
            'SOBRECOMPRADO', 'SOBREVENDIDO' or 'NEUTRO'
        """
        if rsi > 70:
            return 'SOBRECOMPRADO'
        elif rsi < 30:
            return 'SOBREVENDIDO'
        else:
            return 'NEUTRO'
    
    def _find_support_resistance(self, df: pd.DataFrame) -> Tuple[float, float]:
        """Identify support and resistance levels.
        
        Uses high/low of last N periods.
        
        Args:
            df: DataFrame with OHLCV
        
        Returns:
            Tuple (support, resistance)
        """
        # Get last N periods
        lookback_data = df.tail(self.lookback_levels)
        
        # Support = low of last N periods
        support = lookback_data['low'].min()
        
        # Resistance = high of last N periods
        resistance = lookback_data['high'].max()
        
        return support, resistance
    
    def _analyze_price_action(self, candle: pd.Series) -> str:
        """Analyze price action pattern of candle.
        
        Identifies:
        - Strong Bar (large body, small shadow)
        - Rejection (large shadow in one direction)
        
        Args:
            candle: Series with OHLC of single candle
        
        Returns:
            String describing the pattern
        """
        open_price = candle['open']
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        # Calculate candle components
        total_range = high - low
        body = abs(close - open_price)
        
        # Avoid division by zero
        if total_range == 0:
            return 'NEUTRO'
        
        body_percent = body / total_range
        
        # Candle direction
        is_bullish = close > open_price
        
        # Shadows
        if is_bullish:
            upper_shadow = high - close
            lower_shadow = open_price - low
        else:
            upper_shadow = high - open_price
            lower_shadow = close - low
        
        upper_shadow_percent = upper_shadow / total_range
        lower_shadow_percent = lower_shadow / total_range
        
        # Detect patterns
        
        # STRONG BAR: body > threshold% of range
        if body_percent > self.strong_candle_threshold:
            if is_bullish:
                return 'BARRA_FORTE_ALTA'
            else:
                return 'BARRA_FORTE_BAIXA'
        
        # REJECTION: large shadow (> 60%) in one direction
        if upper_shadow_percent > 0.6:
            return 'REJEICAO_ALTA'  # Rejection of highs (bearish)
        
        if lower_shadow_percent > 0.6:
            return 'REJEICAO_BAIXA'  # Rejection of lows (bullish)
        
        return 'NEUTRO'
    
    def _empty_analysis(self) -> Dict:
        """Return empty analysis when error or insufficient data.
        
        Returns:
            Dictionary with INDEFINIDO values
        """
        return {
            'trend': 'INDEFINIDO',
            'trend_strength': 'INDEFINIDO',
            'rsi': 0.0,
            'rsi_condition': 'INDEFINIDO',
            'support': 0.0,
            'resistance': 0.0,
            'distance_to_support': 0.0,
            'distance_to_resistance': 0.0,
            'pattern': 'INDEFINIDO',
            'ema_fast': 0.0,
            'sma_fast': 0.0,
            'sma_slow': 0.0,
            'current_price': 0.0
        }
    
    def validate_signal(
        self,
        ml_direction: str,
        context: Dict,
        require_trend_alignment: bool = True
    ) -> Tuple[bool, str]:
        """Validate ML signal against technical context.
        
        Args:
            ml_direction: ML signal direction ('COMPRA', 'VENDA', 'CALL' or 'PUT')
            context: Dictionary returned by analyze()
            require_trend_alignment: If True, requires trend alignment
        
        Returns:
            Tuple (valid: bool, reason: str)
        """
        # Normalize direction to COMPRA/VENDA
        if ml_direction.upper() in ['CALL', 'BUY']:
            ml_direction = 'COMPRA'
        elif ml_direction.upper() in ['PUT', 'SELL']:
            ml_direction = 'VENDA'
        
        # Extract context data
        trend = context.get('trend', 'INDEFINIDO')
        rsi_condition = context.get('rsi_condition', 'INDEFINIDO')
        pattern = context.get('pattern', 'INDEFINIDO')
        
        # Validation list
        validations = []
        
        # 1. Trend Alignment (if required)
        if require_trend_alignment:
            if ml_direction == 'COMPRA' and trend != 'ALTA':
                return False, f"Sinal de COMPRA mas tendência é {trend}"
            if ml_direction == 'VENDA' and trend != 'BAIXA':
                return False, f"Sinal de VENDA mas tendência é {trend}"
            validations.append("Tendência alinhada")
        
        # 2. RSI - Avoid extreme zones in signal direction
        if ml_direction == 'COMPRA' and rsi_condition == 'SOBRECOMPRADO':
            return False, "Sinal de COMPRA mas RSI está SOBRECOMPRADO"
        if ml_direction == 'VENDA' and rsi_condition == 'SOBREVENDIDO':
            return False, "Sinal de VENDA mas RSI está SOBREVENDIDO"
        validations.append(f"RSI {rsi_condition}")
        
        # 3. Price Action - Rejection pattern contrary to signal
        if ml_direction == 'COMPRA' and pattern == 'REJEICAO_ALTA':
            return False, "Sinal de COMPRA mas há REJEIÇÃO da ALTA"
        if ml_direction == 'VENDA' and pattern == 'REJEICAO_BAIXA':
            return False, "Sinal de VENDA mas há REJEIÇÃO da BAIXA"
        
        if pattern not in ['NEUTRO', 'INDEFINIDO']:
            validations.append(f"Padrão: {pattern}")
        
        # Signal validated
        reason = " | ".join(validations)
        return True, reason


def analyze_market_context(
    df: pd.DataFrame,
    **kwargs
) -> Dict:
    """Convenience function for quick market analysis.
    
    Args:
        df: DataFrame with OHLCV data
        **kwargs: Optional parameters for MarketContextAnalyzer
        
    Returns:
        Analysis dictionary from MarketContextAnalyzer.analyze()
        
    Example:
        >>> from newapp.data.provider import get_default_provider
        >>> from newapp.analysis.context_analyzer import analyze_market_context
        >>> 
        >>> provider = get_default_provider()
        >>> df = provider.get_latest_candles('WDO$', 'M5', 500)
        >>> context = analyze_market_context(df)
        >>> print(f"Trend: {context['trend']}, RSI: {context['rsi']}")
    """
    analyzer = MarketContextAnalyzer(**kwargs)
    return analyzer.analyze(df)
