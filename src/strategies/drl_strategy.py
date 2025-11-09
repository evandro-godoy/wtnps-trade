# src/strategies/drl_strategy.py
"""
Estratégia de Deep Reinforcement Learning (DRL) para inferência.
Esta classe herda de BaseStrategy e implementa a interface necessária
para ser carregada e usada pelo SimulationEngine e live_trader.
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Any

from src.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class DRLStrategy(BaseStrategy):
    """
    Estratégia DRL (Deep Q-Network / DDQN) para inferência.
    
    Usa uma Q-Network treinada para escolher ações (Venda, Hold, Compra)
    baseado no estado de mercado + posição atual.
    
    Estado (State):
        - Market features: log returns, volatilidade, RSI, etc. (mesmas que TradingEnv)
        - Position feature: one-hot encoding da posição atual
    
    Predição:
        - Q-values para cada ação [Q(Venda), Q(Hold), Q(Compra)]
        - Ação escolhida: argmax(Q-values)
    """
    
    def __init__(self):
        """Inicializa a estratégia DRL."""
        super().__init__()
        logger.info("DRLStrategy inicializada")
    
    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula as features de mercado usando indicadores técnicos (pandas_ta).
        
        CRÍTICO: As features devem ser IDÊNTICAS às usadas no ambiente de treino.
        
        Args:
            data: DataFrame com dados OHLCV
        
        Returns:
            DataFrame com features calculadas
        """
        import pandas_ta as ta
        
        df = data.copy()
        
        # --- Novas Features usando pandas_ta ---
        
        # 1. EMA 9
        df['ema_9'] = ta.ema(df['close'], length=9)
        
        # 2. SMA 20
        df['sma_20'] = ta.sma(df['close'], length=20)
        
        # 3. SMA 200
        df['sma_200'] = ta.sma(df['close'], length=200)
        
        # 4. Distância (normalizada) para a SMA 20
        df['dist_sma_20'] = (df['close'] - df['sma_20']) / df['close']
        
        # 5. Distância (normalizada) para a SMA 200
        df['dist_sma_200'] = (df['close'] - df['sma_200']) / df['close']
        
        # 6. ATR (Volatilidade Normalizada)
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['atr'] = atr / df['close']  # Normaliza o ATR pelo preço
        
        # Normaliza as features baseadas em preço (exceto distâncias e ATR que já são relativos)
        price_features = ['ema_9', 'sma_20', 'sma_200']
        for col in price_features:
            df[col] = (df[col] / df['close']) - 1  # Normaliza pelo preço de fechamento
        
        return df
    
    def get_feature_names(self) -> list:
        """
        Retorna a lista de nomes das features de mercado.
        
        Estas são as features que a Q-Network espera receber
        (antes de concatenar com a position feature).
        """
        return [
            'ema_9', 'sma_20', 'sma_200', 
            'dist_sma_20', 'dist_sma_200', 'atr'
        ]
    
    @classmethod
    def load(cls, model_path_prefix: str) -> Any:
        """
        Carrega a Q-Network treinada.
        
        Args:
            model_path_prefix: Prefixo do caminho (ex: 'models/WDO$_DRL_prod')
        
        Returns:
            Modelo Keras carregado (Q-Network)
        """
        import tensorflow as tf
        
        model_path = f"{model_path_prefix}_drl.keras"
        
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Modelo DRL não encontrado: {model_path}. "
                f"Execute 'poetry run python train_drl_model.py' primeiro."
            )
        
        logger.info(f"Carregando modelo DRL de {model_path}")
        model = tf.keras.models.load_model(model_path)
        
        # IMPORTANTE: SimulationEngine espera que o modelo tenha atributo 'lookback'
        # Para DRL, o lookback é 1 (usa apenas o estado atual)
        # Se você implementar DRQN (recorrente) com múltiplos steps, ajuste aqui
        model.lookback = 1
        
        logger.info(f"Modelo DRL carregado com sucesso. Lookback={model.lookback}")
        
        return model
    
    def save(self, model: Any, model_path_prefix: str):
        """
        Salva a Q-Network treinada.
        
        Args:
            model: Modelo Keras (Q-Network)
            model_path_prefix: Prefixo do caminho (ex: 'models/WDO$_DRL_prod')
        """
        model_path = f"{model_path_prefix}_drl.keras"
        
        logger.info(f"Salvando modelo DRL em {model_path}")
        model.save(model_path)
        logger.info(f"Modelo DRL salvo com sucesso")
    
    # --- Métodos não usados por DRL (sobrescrevem BaseStrategy) ---
    
    def define_target(self, data: pd.DataFrame) -> pd.Series:
        """
        DRL não usa targets supervisionados.
        Este método não é chamado durante inferência.
        """
        raise NotImplementedError("DRLStrategy não usa define_target (aprendizado por reforço)")
    
    def define_model(self) -> Any:
        """
        DRL não usa define_model (a Q-Network é criada pelo DDQNAgent).
        Este método não é chamado durante inferência.
        """
        raise NotImplementedError("DRLStrategy não usa define_model (use DDQNAgent para treino)")
