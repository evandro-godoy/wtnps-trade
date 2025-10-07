# src/strategies/lstm.py
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.base import BaseEstimator, ClassifierMixin
from tensorflow import keras
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
import joblib
import logging

from src.strategies.base import BaseStrategy

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Funções Auxiliares para Preparação de Dados ---

def create_sequences(X_data, y_data, lookback):
    """
    Transforma um array de features e um array de targets em sequências
    para alimentar a LSTM.
    """
    X, y = [], []
    for i in range(len(X_data) - lookback):
        X.append(X_data[i:(i + lookback), :])
        y.append(y_data[i + lookback])
    return np.array(X), np.array(y)

# --- Wrapper para compatibilidade com Scikit-Learn ---

class KerasLSTMWrapper(BaseEstimator, ClassifierMixin):
    """
    Um wrapper para o modelo Keras (TensorFlow) para torná-lo compatível
    com a API do Scikit-Learn, esperada pelo nosso motor de backtest.
    """
    def __init__(self, lookback=60, lstm_units=50, epochs=50, batch_size=32, n_features=1):
        self.lookback = lookback
        self.lstm_units = lstm_units
        self.epochs = epochs
        self.batch_size = batch_size
        self.n_features = n_features
        self.model = self._build_model()
        self.scaler = MinMaxScaler(feature_range=(0, 1))

    def _build_model(self):
        """Define a arquitetura da rede LSTM."""
        model = Sequential()
        model.add(LSTM(units=self.lstm_units, return_sequences=True, input_shape=(self.lookback, self.n_features)))
        model.add(Dropout(0.2))
        model.add(LSTM(units=self.lstm_units, return_sequences=False))
        model.add(Dropout(0.2))
        model.add(Dense(units=25))
        model.add(Dense(units=1, activation='sigmoid'))
        
        model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        return model

    def fit(self, X, y):
        """
        Treina o modelo. Esta função irá escalar os dados, criar as sequências
        e então treinar o modelo Keras.
        """
        X_scaled = self.scaler.fit_transform(X)
        X_seq, y_seq = create_sequences(X_scaled, y.values, self.lookback)
        
        if len(X_seq) == 0:
            print("Não há dados suficientes para criar sequências com o lookback fornecido.")
            return self

        early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
        self.model.fit(
            X_seq, y_seq,
            epochs=self.epochs,
            batch_size=self.batch_size,
            validation_split=0.1,
            callbacks=[early_stopping],
            verbose=0
        )
        return self

    def predict(self, X):
        """
        Faz previsões. Os dados de teste são escalados usando o mesmo scaler
        do treino e transformados em sequências.
        """
        X_scaled = self.scaler.transform(X)
        X_seq, _ = create_sequences(X_scaled, np.zeros(len(X_scaled)), self.lookback)
        
        if len(X_seq) == 0:
            return np.array([])
            
        predictions_proba = self.model.predict(X_seq)
        predictions = (predictions_proba > 0.5).astype(int)
        
        return predictions.flatten()

    def get_params(self, deep=True):
        return {
            'lookback': self.lookback,
            'lstm_units': self.lstm_units,
            'epochs': self.epochs,
            'batch_size': self.batch_size,
            'n_features': self.n_features
        }

    def set_params(self, **params):
        for param, value in params.items():
            setattr(self, param, value)
        return self
    
    def save_model(self, model_path: str, scaler_path: str):
        """Salva o modelo Keras e o scaler em arquivos separados."""
        self.model.save(model_path)
        joblib.dump(self.scaler, scaler_path)
        logging.info(f"Modelo salvo em {model_path} e scaler em {scaler_path}")

    @classmethod
    def load_model(cls, model_path: str, scaler_path: str):
        """Carrega um modelo Keras e um scaler de arquivos e retorna uma nova instância do wrapper."""
        logging.info(f"Carregando modelo de {model_path} e scaler de {scaler_path}")
        
        # Carrega o modelo e o scaler
        loaded_keras_model = keras.models.load_model(model_path)
        loaded_scaler = joblib.load(scaler_path)

        # Cria uma nova instância do wrapper com os componentes carregados
        # É preciso saber os parâmetros originais para recriar o wrapper
        # Aqui, usamos os padrões, mas em um sistema complexo, salvaríamos os metadados
        instance = cls() 
        instance.model = loaded_keras_model
        instance.scaler = loaded_scaler
        
        # Extrai parâmetros do modelo carregado
        try:
            instance.lookback = instance.model.input_shape[1]
            instance.n_features = instance.model.input_shape[2]
        except Exception as e:
            logging.warning(f"Não foi possível extrair lookback/n_features do modelo carregado: {e}")

        return instance

# --- Implementação da Estratégia LSTM Aprimorada ---

class LSTMStrategy(BaseStrategy):
    """
    Estratégia de trading que utiliza uma rede neural LSTM com um conjunto
    expandido de indicadores técnicos.
    """
    def __init__(self, lookback=60, lstm_units=50):
        self.lookback = lookback
        self.lstm_units = lstm_units
        self.feature_names = [
            'sma_9', 'ema_21', 'ema_50', 'ema_200',
            'volume', 'volatility'
        ]

    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Adiciona os indicadores técnicos que servirão de features para o modelo.
        """
        df = data.copy()
        
        # 1. Médias Móveis
        df['sma_9'] = df['close'].rolling(window=9).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        # 2. Volume (já presente nos dados)
        # Apenas garantimos que a coluna 'Volume' está sendo usada.

        # 3. Volatilidade (desvio padrão dos retornos em uma janela)
        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(window=21).std() * np.sqrt(252) # Volatilidade anualizada

        return df

    def define_model(self) -> BaseEstimator:
        """
        Retorna uma instância do nosso wrapper do modelo LSTM.
        """
        return KerasLSTMWrapper(
            lookback=self.lookback,
            lstm_units=self.lstm_units,
            n_features=len(self.feature_names) # Informa ao modelo quantas features estamos usando
        )
    
    def get_feature_names(self) -> list[str]:
        """
        Retorna a lista de colunas a serem usadas como features.
        """
        return self.feature_names