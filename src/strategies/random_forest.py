# src/strategies/random_forest.py
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.base import BaseEstimator

from src.strategies.base import BaseStrategy

class RandomForestFeatureStrategy(BaseStrategy):
    """
    Implementação da estratégia baseada em features de indicadores técnicos
    e um modelo RandomForestClassifier.
    """
    def __init__(self, short_window=5, long_window=20, rsi_window=14):
        self.short_window = short_window
        self.long_window = long_window
        self.rsi_window = rsi_window
        self.feature_names = ['MA_Diff', 'RSI', 'Returns']

    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        # 1. Médias Móveis
        df['MA_Short'] = df['Close'].rolling(window=self.short_window).mean()
        df['MA_Long'] = df['Close'].rolling(window=self.long_window).mean()
        df['MA_Diff'] = df['MA_Short'] - df['MA_Long']

        # 2. Índice de Força Relativa (RSI)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_window).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # 3. Retornos Diários
        df['Returns'] = df['Close'].pct_change()
        
        return df

    def define_model(self) -> BaseEstimator:
        return RandomForestClassifier(n_estimators=100, min_samples_split=50, random_state=42)
    
    def get_feature_names(self) -> list[str]:
        return self.feature_names