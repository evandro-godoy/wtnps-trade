# src/strategies/sentiment_lstm.py
import pandas as pd
from sklearn.base import BaseEstimator

from src.strategies.base import BaseStrategy
from src.strategies.lstm import KerasLSTMWrapper

class SentimentLSTMStrategy(BaseStrategy):
    def __init__(self, lookback=60, lstm_units=50):
        self.lookback = lookback
        self.lstm_units = lstm_units
        # Usando nomes em minúsculas
        self.feature_names = [
            'sma_9', 'ema_21', 'ema_50', 'ema_200', 'rsi',
            'volume', 'volatility', 'sentiment'
        ]

    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        # Usando 'close' em minúsculo
        df['sma_9'] = df['close'].rolling(window=9).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(window=21).std() * 252**0.5
        
        if 'sentiment' not in df.columns:
            raise ValueError("A coluna 'sentiment' não foi encontrada. Verifique o data_provider.")
        
        return df

    def define_model(self) -> BaseEstimator:
        return KerasLSTMWrapper(
            lookback=self.lookback,
            lstm_units=self.lstm_units,
            n_features=len(self.feature_names)
        )
    
    def get_feature_names(self) -> list[str]:
        return self.feature_names