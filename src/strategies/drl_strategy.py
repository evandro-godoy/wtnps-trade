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
        Calcula as features de mercado (exatamente as mesmas do TradingEnv).
        
        CRÍTICO: As features devem ser IDÊNTICAS às usadas no ambiente de treino.
        
        Args:
            data: DataFrame com dados OHLCV
        
        Returns:
            DataFrame com features calculadas
        """
        df = data.copy()
        
        # 1. Log Returns
        df['log_return'] = np.log(df['close'] / df['close'].shift(1))
        
        # 2. Log Returns de diferentes períodos
        df['log_return_5'] = np.log(df['close'] / df['close'].shift(5))
        df['log_return_10'] = np.log(df['close'] / df['close'].shift(10))
        df['log_return_20'] = np.log(df['close'] / df['close'].shift(20))
        
        # 3. Volume log change
        df['log_volume'] = np.log(df['tick_volume'] + 1)  # +1 para evitar log(0)
        df['log_volume_change'] = df['log_volume'] - df['log_volume'].shift(1)
        
        # 4. Volatilidade (desvio padrão rolling dos log returns)
        df['volatility_10'] = df['log_return'].rolling(window=10).std()
        df['volatility_20'] = df['log_return'].rolling(window=20).std()
        
        # 5. Percentile rank do preço (posição relativa)
        df['price_percentile_20'] = df['close'].rolling(window=20).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )
        
        # 6. RSI (Relative Strength Index)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-10)  # Evita divisão por zero
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def get_feature_names(self) -> list:
        """
        Retorna a lista de nomes das features de mercado.
        
        Estas são as features que a Q-Network espera receber
        (antes de concatenar com a position feature).
        """
        return [
            'log_return', 'log_return_5', 'log_return_10', 'log_return_20',
            'log_volume_change', 'volatility_10', 'volatility_20',
            'price_percentile_20', 'rsi'
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
