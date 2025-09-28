# src/strategies/sentiment_lstm.py
import pandas as pd
import numpy as np
from sklearn.base import BaseEstimator

from src.strategies.base import BaseStrategy
from src.strategies.lstm import KerasLSTMWrapper # Reutilizamos o Wrapper que já criamos

class SentimentLSTMStrategy(BaseStrategy):
    """
    Estratégia híbrida que combina indicadores técnicos com um indicador de sentimento
    de mercado (VIX) para alimentar um modelo LSTM.
    """
    def __init__(self, lookback=60, lstm_units=50):
        self.lookback = lookback
        self.lstm_units = lstm_units
        # Adicionamos 'Sentiment' à lista de features
        self.feature_names = [
            'SMA_9', 'EMA_21', 'EMA_50', 'EMA_200',
            'Volume', 'Volatility', 'Sentiment'
        ]

    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Adiciona os indicadores técnicos e garante que o indicador de sentimento esteja presente.
        """
        df = data.copy()
        
        # 1. Indicadores Técnicos
        df['SMA_9'] = df['Close'].rolling(window=9).mean()
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()

        # 2. Volatilidade e Retornos
        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(window=21).std() * np.sqrt(252)
        
        # 3. Sentimento (já deve ter sido carregado pelo provider)
        if 'Sentiment' not in df.columns:
            raise ValueError("A coluna 'Sentiment' não foi encontrada nos dados. Verifique o data_provider.")
        
        return df

    def define_model(self) -> BaseEstimator:
        """
        Retorna uma instância do nosso wrapper do modelo LSTM, agora ciente do
        número correto de features.
        """
        return KerasLSTMWrapper(
            lookback=self.lookback,
            lstm_units=self.lstm_units,
            n_features=len(self.feature_names)
        )
    
    def get_feature_names(self) -> list[str]:
        """
        Retorna a lista de colunas a serem usadas como features.
        """
        return self.feature_names