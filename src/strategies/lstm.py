# src/strategies/lstm.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.base import BaseEstimator, ClassifierMixin
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping

from src.strategies.base import BaseStrategy

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
        model.add(Dense(units=1, activation='sigmoid')) # Sigmoid para classificação binária (alta/baixa)
        
        model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        return model

    def fit(self, X, y):
        """
        Treina o modelo. Esta função irá escalar os dados, criar as sequências
        e então treinar o modelo Keras.
        """
        # 1. Escalar os dados de treino
        X_scaled = self.scaler.fit_transform(X)

        # 2. Criar sequências
        X_seq, y_seq = create_sequences(X_scaled, y.values, self.lookback)
        
        if len(X_seq) == 0:
            print("Não há dados suficientes para criar sequências com o lookback fornecido.")
            return self

        # 3. Treinar o modelo
        early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
        self.model.fit(
            X_seq, y_seq,
            epochs=self.epochs,
            batch_size=self.batch_size,
            validation_split=0.1, # Usa 10% dos dados para validação
            callbacks=[early_stopping],
            verbose=0 # Desliga o log de treino para não poluir a saída do backtest
        )
        return self

    def predict(self, X):
        """
        Faz previsões. Os dados de teste são escalados usando o mesmo scaler
        do treino e transformados em sequências.
        """
        # 1. Escalar os dados de teste
        X_scaled = self.scaler.transform(X)
        
        # 2. Criar sequências
        X_seq, _ = create_sequences(X_scaled, np.zeros(len(X_scaled)), self.lookback)
        
        if len(X_seq) == 0:
            # Se não for possível criar sequências, retorna um array vazio com o formato correto.
            return np.array([])
            
        # 3. Fazer a predição
        predictions_proba = self.model.predict(X_seq)
        
        # 4. Converter probabilidades em classes (0 ou 1)
        predictions = (predictions_proba > 0.5).astype(int)
        
        return predictions.flatten()

    def get_params(self, deep=True):
        """Método necessário para compatibilidade com Scikit-Learn."""
        return {
            'lookback': self.lookback,
            'lstm_units': self.lstm_units,
            'epochs': self.epochs,
            'batch_size': self.batch_size,
            'n_features': self.n_features
        }

    def set_params(self, **params):
        """Método necessário para compatibilidade com Scikit-Learn."""
        for param, value in params.items():
            setattr(self, param, value)
        return self

# --- Implementação da Estratégia LSTM ---

class LSTMStrategy(BaseStrategy):
    """
    Estratégia de trading que utiliza uma rede neural LSTM.
    O foco desta estratégia está no preço de fechamento.
    """
    def __init__(self, lookback=60, lstm_units=50):
        self.lookback = lookback
        self.lstm_units = lstm_units
        self.feature_names = ['Close'] # Para este exemplo simples, usamos apenas o preço de fechamento

    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula os retornos diários, que são necessários para a avaliação da performance
        pelo motor de backtest. A criação de sequências e a normalização das features
        para o modelo serão feitas dentro do wrapper.
        """
        df = data.copy()
        df['Returns'] = df['Close'].pct_change()
        return df

    def define_model(self) -> BaseEstimator:
        """
        Retorna uma instância do nosso wrapper do modelo LSTM, que se comporta
        como um classificador Scikit-Learn.
        """
        return KerasLSTMWrapper(
            lookback=self.lookback,
            lstm_units=self.lstm_units,
            n_features=len(self.feature_names)
        )
    
    def get_feature_names(self) -> list[str]:
        """
        Retorna a lista de colunas a serem usadas. Neste caso, apenas 'Close'.
        """
        return self.feature_names