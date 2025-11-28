# newapp/src/strategies/lstm_volatility.py
"""LSTM Volatility Strategy for predicting volatility explosions.

This module is identical to legacy src/strategies/lstm_volatility.py,
maintaining the same business logic and model architecture.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
import logging
from sklearn.preprocessing import MinMaxScaler
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.utils.class_weight import compute_class_weight
from tensorflow import keras
from tensorflow.keras.models import Sequential # type: ignore
from tensorflow.keras.layers import LSTM, Dense, Dropout # type: ignore
from tensorflow.keras.callbacks import EarlyStopping # type: ignore

from newapp.src.strategies.base import BaseStrategy

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Funções Auxiliares ---

def calculate_true_range(df: pd.DataFrame) -> pd.Series:
    """
    Calcula o True Range (TR).
    TR = max(high-low, high-prev_close, low-prev_close)
    """
    df_temp = df.copy()
    df_temp['high-low'] = df_temp['high'] - df_temp['low']
    df_temp['high-prev_close'] = np.abs(df_temp['high'] - df_temp['close'].shift(1))
    df_temp['low-prev_close'] = np.abs(df_temp['low'] - df_temp['close'].shift(1))
    true_range = df_temp[['high-low', 'high-prev_close', 'low-prev_close']].max(axis=1)
    return true_range


def create_sequences(X_data, y_data, lookback):
    """
    Transforma um array de features e um array de targets em sequências
    para alimentar a LSTM.
    """
    X, y = [], []
    # Garante que X_data e y_data não estão vazios e têm comprimento suficiente
    if X_data is None or y_data is None or len(X_data) <= lookback or len(y_data) <= lookback:
        return np.array(X), np.array(y)
        
    for i in range(len(X_data) - lookback):
        X.append(X_data[i:(i + lookback), :])
        y.append(y_data[i + lookback])
    return np.array(X), np.array(y)


# --- Wrapper para compatibilidade com Scikit-Learn ---

class LSTMVolatilityWrapper(BaseEstimator, ClassifierMixin):
    """
    Wrapper para o modelo LSTM de volatilidade.
    Predição binária: 1 = explosão de volatilidade, 0 = mercado normal.
    """
    def __init__(self, lookback=96, lstm_units=64, dropout_rate=0.2, epochs=50, batch_size=128, n_features=1):
        self.lookback = lookback
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.n_features = n_features
        self.model = self._build_model()
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        # Armazena histórico do último treino (dicionário de listas)
        self.last_history = None

    def _build_model(self):
        """Define a arquitetura da rede LSTM para detecção de volatilidade."""
        model = Sequential()
        # Uma camada LSTM principal
        model.add(LSTM(
            units=self.lstm_units, 
            return_sequences=False, 
            input_shape=(self.lookback, self.n_features)
        ))
        model.add(Dropout(self.dropout_rate))
        # Saída binária
        model.add(Dense(units=1, activation='sigmoid'))
        
        model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        return model

    def fit(self, X, y):
        """
        Treina o modelo com class weighting balanceado.
        """
        # Garante que X e y sejam arrays numpy ou dataframes/series pandas
        if isinstance(X, pd.DataFrame):
            X_values = X.values
        elif isinstance(X, np.ndarray):
            X_values = X
        else:
            raise ValueError(f"X deve ser DataFrame ou ndarray, recebido: {type(X)}")

        if isinstance(y, (pd.Series, pd.DataFrame)):
            y_values = y.values.ravel()
        elif isinstance(y, np.ndarray):
            y_values = y.ravel()
        else:
            raise ValueError(f"y deve ser Series, DataFrame ou ndarray, recebido: {type(y)}")
            
        # Garante que n_features está correto
        if X_values.shape[1] != self.n_features:
            self.n_features = X_values.shape[1]

        X_scaled = self.scaler.fit_transform(X_values)
        X_seq, y_seq = create_sequences(X_scaled, y_values, self.lookback)
        
        y_seq = y_seq.ravel()
        
        if len(X_seq) == 0:
            logging.warning("Nenhuma sequência criada. Verifique lookback e tamanho do dataset.")
            return self

        # Calcula class weights para balanceamento
        class_weights_array = compute_class_weight(
            'balanced',
            classes=np.unique(y_seq),
            y=y_seq
        )
        class_weights = dict(enumerate(class_weights_array))
        logging.info(f"Class weights calculados: {class_weights}")

        early_stopping = EarlyStopping(
            monitor='val_loss', 
            patience=15, 
            restore_best_weights=True
        )

        n_samples = len(X_seq)
        val_size = max(1, int(n_samples * 0.1)) if n_samples > 1 else 0
        validation_split = 0.1 if val_size > 0 and n_samples >= 10 else 0.0

        history_obj = None
        if validation_split > 0:
            history_obj = self.model.fit(
                X_seq, y_seq,
                epochs=self.epochs,
                batch_size=self.batch_size,
                class_weight=class_weights,
                validation_split=validation_split,
                callbacks=[early_stopping],
                verbose=1
            )
        elif n_samples > 0:
            history_obj = self.model.fit(
                X_seq, y_seq,
                epochs=self.epochs,
                batch_size=self.batch_size,
                class_weight=class_weights,
                verbose=1
            )
        else:
            logging.warning("Dataset muito pequeno para treino.")

        if history_obj is not None:
            self.last_history = history_obj.history
        
        return self

    def predict(self, X):
        """
        Faz previsões binárias (0 ou 1).
        """
        if isinstance(X, pd.DataFrame):
            X_values = X.values
        elif isinstance(X, np.ndarray):
            X_values = X
        else:
            raise ValueError(f"X deve ser DataFrame ou ndarray, recebido: {type(X)}")
            
        if X_values.shape[1] != self.scaler.n_features_in_:
            raise ValueError(f"Número de features incompatível: esperado {self.scaler.n_features_in_}, recebido {X_values.shape[1]}")

        X_scaled = self.scaler.transform(X_values)
        y_dummy = np.zeros(len(X_scaled))
        X_seq, _ = create_sequences(X_scaled, y_dummy, self.lookback)
        
        if len(X_seq) == 0:
            logging.warning("Nenhuma sequência para predição. Retornando array vazio.")
            return np.array([])
            
        predictions_proba = self.model.predict(X_seq)
        predictions = (predictions_proba > 0.5).astype(int)
        return predictions.flatten()

    def predict_proba(self, X):
        """Retorna probabilidades da classe positiva (explosão de volatilidade).
        Compatível com interface scikit-learn (n_samples, 2) onde a segunda coluna é a classe 1.
        """
        if isinstance(X, pd.DataFrame):
            X_values = X.values
        elif isinstance(X, np.ndarray):
            X_values = X
        else:
            raise ValueError(f"X deve ser DataFrame ou ndarray, recebido: {type(X)}")

        if X_values.shape[1] != self.scaler.n_features_in_:
            raise ValueError(f"Número de features incompatível: esperado {self.scaler.n_features_in_}, recebido {X_values.shape[1]}")

        X_scaled = self.scaler.transform(X_values)
        y_dummy = np.zeros(len(X_scaled))
        X_seq, _ = create_sequences(X_scaled, y_dummy, self.lookback)

        if len(X_seq) == 0:
            logging.warning("Nenhuma sequência para predição. Retornando array vazio.")
            return np.empty((0, 2))

        proba_pos = self.model.predict(X_seq).flatten()
        proba_neg = 1.0 - proba_pos
        return np.vstack([proba_neg, proba_pos]).T

    def get_params(self, deep=True):
        """Retorna os parâmetros do wrapper."""
        return {
            'lookback': self.lookback,
            'lstm_units': self.lstm_units,
            'dropout_rate': self.dropout_rate,
            'epochs': self.epochs,
            'batch_size': self.batch_size,
            'n_features': self.n_features
        }

    def set_params(self, **params):
        """Define os parâmetros e reconstrói o modelo se necessário."""
        rebuild = False
        for param, value in params.items():
            setattr(self, param, value)
            if param in ['lookback', 'lstm_units', 'dropout_rate', 'n_features']:
                rebuild = True
        
        if rebuild:
            self.model = self._build_model()
            
        return self
    
    def save(self, model_path_prefix: str):
        """Salva o modelo Keras, scaler e parâmetros."""
        Path(model_path_prefix).parent.mkdir(parents=True, exist_ok=True)
        
        model_path = f"{model_path_prefix}_lstm.keras"
        scaler_path = f"{model_path_prefix}_scaler.joblib"
        params_path = f"{model_path_prefix}_params.joblib"
        
        self.model.save(model_path)
        joblib.dump(self.scaler, scaler_path)
        params_to_save = {'lookback': self.lookback, 'n_features': self.n_features}
        joblib.dump(params_to_save, params_path)
        
        logging.info(f"Modelo salvo em {model_path}, scaler em {scaler_path}, params em {params_path}")

    @classmethod
    def load(cls, model_path_prefix: str):
        """Carrega o modelo Keras, scaler e parâmetros."""
        model_path = f"{model_path_prefix}_lstm.keras"
        scaler_path = f"{model_path_prefix}_scaler.joblib"
        params_path = f"{model_path_prefix}_params.joblib"
        
        model = keras.models.load_model(model_path)
        scaler = joblib.load(scaler_path)
        params = joblib.load(params_path)
        
        wrapper = cls(lookback=params['lookback'], n_features=params['n_features'])
        wrapper.model = model
        wrapper.scaler = scaler
        
        logging.info(f"Modelo carregado de {model_path}")
        return wrapper


# --- Implementação da Estratégia LSTM Volatility ---

class LSTMVolatilityStrategy(BaseStrategy):
    """
    Estratégia de trading que utiliza LSTM para prever explosões de volatilidade.
    Usa features avançadas de dinâmica de preço, morfologia de candles e time embeddings.
    """
    def __init__(self, lookback=96, lstm_units=64, dropout_rate=0.2, epochs=30, batch_size=128, target_period=5, volatility_multiplier=3.0):
        self.lookback = lookback
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.target_period = target_period
        self.volatility_multiplier = volatility_multiplier
        
        # Lista completa de features (25 features)
        self.feature_names = [
            # Dinâmica de preço (5)
            'retorno', 'gap', 'roc_3', 'roc_8', 'retorno_relativo',
            # Médias móveis e distâncias (6)
            'ema_9', 'sma_20', 'sma_200', 'dist_ema_9', 'dist_sma_20', 'dist_sma_200',
            # Indicadores técnicos (3)
            'rsi', 'band_width', 'atr_norm',
            # Morfologia de candle (3)
            'body_rel', 'upper_shad_rel', 'lower_shad_rel',
            # Time embeddings (4)
            'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
            # Volume (1)
            'volume'
        ]

    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Adiciona features avançadas baseadas no notebook:
        - Dinâmica de preço (retorno, gap, ROC, retorno relativo)
        - Indicadores técnicos (EMAs, SMAs, RSI, Bollinger Bands, ATR)
        - Morfologia de candles
        - Time embeddings
        """
        df = data.copy()
        
        # --- 1. DINÂMICA DE PREÇO ---
        
        # Retorno simples (% variação do fechamento)
        df['retorno'] = df['close'].pct_change()
        
        # Gap de abertura
        df['gap'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        
        # Rate of Change (ROC) - Momentum
        for window in [3, 8]:
            df[f'roc_{window}'] = df['close'].pct_change(periods=window)
        
        # Calcula True Range e ATR
        df['true_range'] = calculate_true_range(df)
        df['atr'] = df['true_range'].rolling(window=14).mean()
        
        # Retorno relativo (normalizado pela volatilidade)
        df['retorno_relativo'] = df['retorno'] / (df['atr'] / df['close'])
        
        # --- 2. INDICADORES TÉCNICOS CLÁSSICOS ---
        
        # Médias Móveis
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_200'] = df['close'].rolling(window=200).mean()
        
        # Distâncias (Normalizadas)
        df['dist_ema_9'] = (df['close'] - df['ema_9']) / df['close']
        df['dist_sma_20'] = (df['close'] - df['sma_20']) / df['close']
        df['dist_sma_200'] = (df['close'] - df['sma_200']) / df['close']
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50) / 100.0  # Normalizado para [0, 1]
        
        # Bollinger Bands Width
        df['std_20'] = df['close'].rolling(window=20).std()
        df['band_width'] = (df['std_20'] * 4) / df['sma_20']
        
        # ATR Normalizado
        df['atr_norm'] = df['atr'] / df['close']
        
        # --- 3. MORFOLOGIA DE CANDLE ---
        
        df['body_size'] = np.abs(df['close'] - df['open'])
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
        
        # Normalizar pela volatilidade (ATR)
        df['body_rel'] = df['body_size'] / (df['atr'] + 1e-6)
        df['upper_shad_rel'] = df['upper_shadow'] / (df['atr'] + 1e-6)
        df['lower_shad_rel'] = df['lower_shadow'] / (df['atr'] + 1e-6)
        
        # --- 4. TIME EMBEDDINGS ---
        
        hour = df.index.hour
        day_of_week = df.index.dayofweek
        
        df['hour_sin'] = np.sin(2 * np.pi * hour / 24)
        df['hour_cos'] = np.cos(2 * np.pi * hour / 24)
        df['day_sin'] = np.sin(2 * np.pi * day_of_week / 5)
        df['day_cos'] = np.cos(2 * np.pi * day_of_week / 5)
        
        # --- LIMPEZA FINAL ---
        
        # Preenche NaNs (gerados por rolling windows no início)
        df.ffill(inplace=True)
        df.bfill(inplace=True)
        
        return df

    def define_target(self, data: pd.DataFrame) -> pd.Series:
        """
        Define o target como explosão de volatilidade com filtro Day Trade.
        1 = Amplitude futura > threshold (ATR * multiplier)
        0 = Mercado normal/travado
        
        Filtro Day Trade: Zera o target para candles após as 17:00 (horário limite)
        para evitar sinais próximos ao fechamento do pregão.
        """
        df = data.copy()
        
        # Calcular amplitude futura (Max High - Min Low nos próximos períodos)
        indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=self.target_period)
        future_high = df['high'].rolling(window=indexer).max()
        future_low = df['low'].rolling(window=indexer).min()
        future_amplitude = future_high - future_low
        
        # Threshold de volatilidade
        df['atr'] = df['true_range'].rolling(window=14).mean() if 'atr' not in df.columns else df['atr']
        threshold = df['atr'] * self.volatility_multiplier
        
        # Target: 1 se amplitude futura > threshold, 0 caso contrário
        target = (future_amplitude > threshold).astype(int)
        
        # Filtro Day Trade: Zera target após 17:00
        if hasattr(df.index, 'hour'):
            hour = df.index.hour
            target = target.where(hour < 17, 0)
        
        return target

    def define_model(self) -> BaseEstimator:
        """
        Retorna uma instância não treinada do LSTMVolatilityWrapper.
        """
        return LSTMVolatilityWrapper(
            lookback=self.lookback,
            lstm_units=self.lstm_units,
            dropout_rate=self.dropout_rate,
            epochs=self.epochs,
            batch_size=self.batch_size,
            n_features=len(self.feature_names)
        )
    
    def get_feature_names(self) -> list[str]:
        """Retorna os nomes das features."""
        return self.feature_names

    def save(self, model: BaseEstimator, model_path_prefix: str):
        """
        Delega ao método save do wrapper.
        """
        if not isinstance(model, LSTMVolatilityWrapper):
            raise TypeError(f"Modelo deve ser LSTMVolatilityWrapper, recebido: {type(model)}")
        model.save(model_path_prefix)

    @classmethod
    def load(cls, model_path_prefix: str) -> BaseEstimator:
        """
        Carrega o modelo LSTMVolatilityWrapper.
        """
        return LSTMVolatilityWrapper.load(model_path_prefix)
