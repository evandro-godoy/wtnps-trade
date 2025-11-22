# src/analysis/context_analyzer.py

"""
Analisador de Contexto de Mercado - Análise Técnica Clássica.

Fornece análise de tendência, força, níveis de suporte/resistência e
padrões de price action para enriquecer sinais de ML.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class MarketContextAnalyzer:
    """
    Analisador de contexto técnico do mercado.
    
    Combina múltiplos indicadores técnicos clássicos para fornecer
    contexto completo sobre tendência, força e níveis chave.
    
    Attributes:
        ema_fast (int): Período da EMA rápida para tendência
        sma_fast (int): Período da SMA rápida para tendência
        sma_slow (int): Período da SMA lenta para tendência 
        sma_lookback (int): Períodos para calcular inclinação da SMA lenta       
        rsi_period (int): Período do RSI
        lookback_levels (int): Períodos para calcular suporte/resistência
        strong_candle_threshold (float): % do range para candle forte
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
    ):
        """
        Inicializa o analisador de contexto.
        
        Args:
            ema_fast: Período da EMA rápida (padrão: 9)
            sma_fast: Período da SMA rápida (padrão: 20)    
            sma_slow: Período da SMA lenta (padrão: 50)
            sma_lookback: Períodos para inclinação da SMA lenta (padrão: 25)
            rsi_period: Período do RSI (padrão: 14)
            lookback_levels: Períodos para níveis de suporte/resistência (padrão: 20)
            strong_candle_threshold: % mínimo do corpo para candle forte (padrão: 0.7)
        """
        self.ema_fast = ema_fast
        self.sma_fast = sma_fast
        self.sma_slow = sma_slow
        self.sma_lookback = sma_lookback
        self.rsi_period = rsi_period
        self.lookback_levels = lookback_levels
        self.strong_candle_threshold = strong_candle_threshold
        
        logger.info(
            f"MarketContextAnalyzer inicializado: EMA{ema_fast}, SMA_FAST{sma_fast}, "
            f"SMA_SLOW{sma_slow}, SLOPE_LOOKBACK{sma_lookback}, RSI{rsi_period}, LEVELS={lookback_levels}"
        )
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Executa análise técnica completa do mercado.
        
        Args:
            df: DataFrame com OHLCV (index: datetime, cols: open, high, low, close, volume)
        
        Returns:
            Dicionário com análise completa:
            {
                'trend': str,  # 'ALTA', 'BAIXA', 'LATERAL'
                'trend_strength': str,  # 'FORTE', 'MODERADA', 'FRACA'
                'rsi': float,
                'rsi_condition': str,  # 'SOBRECOMPRADO', 'SOBREVENDIDO', 'NEUTRO'
                'support': float,
                'resistance': float,
                'distance_to_support': float,  # % de distância
                'distance_to_resistance': float,  # % de distância
                'pattern': str,  # 'BARRA_FORTE_ALTA', 'BARRA_FORTE_BAIXA', 'REJEICAO_ALTA', 'REJEICAO_BAIXA', 'NEUTRO'
                'ema_fast': float,
                ,'sma_fast': float,
                'sma_slow': float,
                'current_price': float
            }
        """
        try:
            if df.empty or len(df) < max(self.sma_slow, self.lookback_levels):
                logger.warning(f"DataFrame insuficiente para análise: {len(df)} linhas")
                return self._empty_analysis()
            
            # Copia para não modificar original
            data = df.copy()
            
            # Calcula indicadores
            data = self._calculate_indicators(data)
            
            # Obtém última linha (candle mais recente)
            last = data.iloc[-1]
            current_price = last['close']
            
            # 1. Análise de Tendência
            trend, trend_strength = self._analyze_trend(data)
            
            # 2. Análise de Força (RSI)
            rsi = last['rsi']
            rsi_condition = self._get_rsi_condition(rsi)
            
            # 3. Níveis de Suporte e Resistência
            support, resistance = self._find_support_resistance(data)
            
            # Calcula distâncias
            distance_to_support = ((current_price - support) / support * 100) if support > 0 else 0
            distance_to_resistance = ((resistance - current_price) / current_price * 100) if resistance > 0 else 0
            
            # 4. Análise de Price Action (último candle)
            pattern = self._analyze_price_action(last)
            
            # Monta resultado
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
            
            logger.debug(f"Análise completa: {context}")
            return context
        
        except Exception as e:
            logger.error(f"Erro na análise de contexto: {e}", exc_info=True)
            return self._empty_analysis()
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula todos os indicadores técnicos necessários."""
        # EMA rápida
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        
        # SMA rápida adicional
        df['sma_fast'] = df['close'].rolling(window=self.sma_fast).mean()
        
        # SMA lenta
        df['sma_slow'] = df['close'].rolling(window=self.sma_slow).mean()
        
        # RSI
        df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)
        
        return df
    
    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        """
        Calcula o Relative Strength Index (RSI).
        
        Args:
            series: Série de preços de fechamento
            period: Período do RSI
        
        Returns:
            Série com valores do RSI
        """
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _analyze_trend(self, df: pd.DataFrame) -> Tuple[str, str]:
        """
        Analisa tendência usando cruzamento de médias e inclinação.
        
        Args:
            df: DataFrame com indicadores calculados
        
        Returns:
            Tupla (tendência, força):
            - tendência: 'ALTA', 'BAIXA', 'LATERAL'
            - força: 'FORTE', 'MODERADA', 'FRACA'
        """
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        
        ema_fast = last['ema_fast']
        sma_fast = last['sma_fast']
        sma_slow = last['sma_slow']
        close = last['close']
        
        # Verifica cruzamento de médias
        ema_above_sma = ema_fast > sma_fast
        price_above_ema = close > ema_fast
        
        # Calcula inclinação da SMA lenta usando janela configurável
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
        
        # Determina tendência
        if ema_above_sma and price_above_ema:
            trend = 'ALTA'
        elif not ema_above_sma and not price_above_ema:
            trend = 'BAIXA'
        else:
            trend = 'LATERAL'
        
        # Determina força da tendência
        slope_abs = abs(sma_slope)
        
        if slope_abs > 1.0:
            strength = 'FORTE'
        elif slope_abs > 0.3:
            strength = 'MODERADA'
        else:
            strength = 'FRACA'
        
        # Se lateral, força sempre fraca
        if trend == 'LATERAL':
            strength = 'FRACA'
        
        return trend, strength
    
    def _get_rsi_condition(self, rsi: float) -> str:
        """
        Classifica condição do RSI.
        
        Args:
            rsi: Valor do RSI
        
        Returns:
            'SOBRECOMPRADO', 'SOBREVENDIDO' ou 'NEUTRO'
        """
        if rsi > 70:
            return 'SOBRECOMPRADO'
        elif rsi < 30:
            return 'SOBREVENDIDO'
        else:
            return 'NEUTRO'
    
    def _find_support_resistance(self, df: pd.DataFrame) -> Tuple[float, float]:
        """
        Identifica níveis de suporte e resistência.
        
        Usa máxima e mínima dos últimos N períodos.
        
        Args:
            df: DataFrame com OHLCV
        
        Returns:
            Tupla (suporte, resistência)
        """
        # Pega últimos N períodos
        lookback_data = df.tail(self.lookback_levels)
        
        # Suporte = mínima dos últimos N períodos
        support = lookback_data['low'].min()
        
        # Resistência = máxima dos últimos N períodos
        resistance = lookback_data['high'].max()
        
        return support, resistance
    
    def _analyze_price_action(self, candle: pd.Series) -> str:
        """
        Analisa padrão de price action do candle.
        
        Identifica:
        - Barra de Força (corpo grande, pouca sombra)
        - Rejeição (sombra grande em uma direção)
        
        Args:
            candle: Série com OHLC de um único candle
        
        Returns:
            String descrevendo o padrão
        """
        open_price = candle['open']
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        # Calcula componentes do candle
        total_range = high - low
        body = abs(close - open_price)
        
        # Evita divisão por zero
        if total_range == 0:
            return 'NEUTRO'
        
        body_percent = body / total_range
        
        # Direção do candle
        is_bullish = close > open_price
        
        # Sombras
        if is_bullish:
            upper_shadow = high - close
            lower_shadow = open_price - low
        else:
            upper_shadow = high - open_price
            lower_shadow = close - low
        
        upper_shadow_percent = upper_shadow / total_range
        lower_shadow_percent = lower_shadow / total_range
        
        # Detecta padrões
        
        # BARRA DE FORÇA: corpo > 70% do range
        if body_percent > self.strong_candle_threshold:
            if is_bullish:
                return 'BARRA_FORTE_ALTA'
            else:
                return 'BARRA_FORTE_BAIXA'
        
        # REJEIÇÃO: sombra grande (> 60%) em uma direção
        if upper_shadow_percent > 0.6:
            return 'REJEICAO_ALTA'  # Rejeição da alta (bearish)
        
        if lower_shadow_percent > 0.6:
            return 'REJEICAO_BAIXA'  # Rejeição da baixa (bullish)
        
        return 'NEUTRO'
    
    def _empty_analysis(self) -> Dict:
        """Retorna análise vazia quando há erro ou dados insuficientes."""
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
        """
        Valida sinal de ML contra contexto técnico.
        
        Args:
            ml_direction: Direção do sinal ML ('CALL' ou 'PUT')
            context: Dicionário retornado por analyze()
            require_trend_alignment: Se True, exige alinhamento de tendência
        
        Returns:
            Tupla (válido: bool, motivo: str)
        """
        # Extrai dados do contexto
        trend = context.get('trend', 'INDEFINIDO')
        rsi_condition = context.get('rsi_condition', 'INDEFINIDO')
        pattern = context.get('pattern', 'INDEFINIDO')
        
        # Lista de validações
        validations = []
        
        # 1. Alinhamento de Tendência (se requerido)
        if require_trend_alignment:
            if ml_direction == 'CALL' and trend != 'ALTA':
                return False, f"Sinal de CALL mas tendência é {trend}"
            if ml_direction == 'PUT' and trend != 'BAIXA':
                return False, f"Sinal de PUT mas tendência é {trend}"
            validations.append("Tendência alinhada")
        
        # 2. RSI - Evita zonas extremas na direção do sinal
        if ml_direction == 'CALL' and rsi_condition == 'SOBRECOMPRADO':
            return False, "Sinal de CALL mas RSI está SOBRECOMPRADO"
        if ml_direction == 'PUT' and rsi_condition == 'SOBREVENDIDO':
            return False, "Sinal de PUT mas RSI está SOBREVENDIDO"
        validations.append(f"RSI {rsi_condition}")
        
        # 3. Price Action - Padrão de rejeição contrário ao sinal
        if ml_direction == 'CALL' and pattern == 'REJEICAO_ALTA':
            return False, "Sinal de CALL mas há REJEIÇÃO da ALTA"
        if ml_direction == 'PUT' and pattern == 'REJEICAO_BAIXA':
            return False, "Sinal de PUT mas há REJEIÇÃO da BAIXA"
        
        if pattern != 'NEUTRO' and pattern != 'INDEFINIDO':
            validations.append(f"Padrão: {pattern}")
        
        # Sinal validado
        reason = " | ".join(validations)
        return True, reason
