# src/strategies/random_forest.py
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.base import BaseEstimator

from src.strategies.base import BaseStrategy

class SentimentRandomForestFeatureStrategy(BaseStrategy):
    """
    Implementação da estratégia baseada em features de indicadores técnicos
    e um modelo RandomForestClassifier.
    """
    def __init__(self, short_window=5, long_window=20, rsi_window=14):
        self.short_window = short_window
        self.long_window = long_window
        self.rsi_window = rsi_window
        self.feature_names = ['ma_diff', 'rsi', 'returns', 'sentiment']

    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        # 1. Médias Móveis
        df['ma_short'] = df['close'].rolling(window=self.short_window).mean()
        df['ma_long'] = df['close'].rolling(window=self.long_window).mean()
        df['ma_diff'] = df['ma_short'] - df['ma_long']

        # 2. Índice de Força Relativa (RSI)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_window).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 3. Retornos Diários
        df['returns'] = df['close'].pct_change()
        
        if 'sentiment' not in df.columns:
            raise ValueError("A coluna 'sentiment' não foi encontrada. Verifique o data_provider.")
        
        return df

    def define_model(self) -> BaseEstimator:
        return RandomForestClassifier(n_estimators=100, min_samples_split=50, random_state=42)
    
    def get_feature_names(self) -> list[str]:
        return self.feature_names