# src/strategies/lstm.py
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.base import BaseEstimator, ClassifierMixin
from tensorflow import keras
from tensorflow.keras.models import Sequential # type: ignore
from tensorflow.keras.layers import LSTM, Dense, Dropout # type: ignore
from tensorflow.keras.callbacks import EarlyStopping # type: ignore
import joblib
import logging

from src.strategies.base import BaseStrategy, calculate_target

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Funções Auxiliares para Preparação de Dados ---

def create_sequences_dpc(X_data, y_data, lookback):
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

class LSTMWrapper(BaseEstimator, ClassifierMixin): # RENOMEADO
    """
    Um wrapper para o modelo Keras (TensorFlow) para torná-lo compatível
    com a API do Scikit-Learn e adicionar métodos de persistência.
    """
    def __init__(self, lookback=60, lstm_units=50, epochs=50, batch_size=128, n_features=1):
        self.lookback = lookback
        self.lstm_units = lstm_units
        self.epochs = epochs
        self.batch_size = batch_size
        self.n_features = n_features # Guardar n_features
        self.model = self._build_model()
        self.scaler = MinMaxScaler(feature_range=(0, 1))

    def _build_model(self):
        """Define a arquitetura da rede LSTM."""
        model = Sequential()
        # Usa n_features na input_shape
        model.add(LSTM(units=self.lstm_units, return_sequences=True, input_shape=(self.lookback, self.n_features)))
        model.add(Dropout(0.2))
        model.add(LSTM(units=self.lstm_units, return_sequences=False))
        model.add(Dropout(0.2))
        model.add(Dense(units=25))
        model.add(Dense(units=1, activation='sigmoid')) # Saída única para classificação binária
        
        model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        return model

    def fit(self, X, y):
        """
        Treina o modelo. Esta função irá escalar os dados, criar as sequências
        e então treinar o modelo Keras.
        """
        # Garante que X e y sejam arrays numpy ou dataframes/series pandas
        if isinstance(X, pd.DataFrame):
            X_values = X.values
        elif isinstance(X, np.ndarray):
            X_values = X
        else:
            raise ValueError("X deve ser um DataFrame Pandas ou array NumPy")

        if isinstance(y, (pd.Series, pd.DataFrame)):
            y_values = y.values.ravel() # Usa ravel() para garantir que y seja 1D
        elif isinstance(y, np.ndarray):
             y_values = y.ravel() # Usa ravel() para garantir que y seja 1D
        else:
            raise ValueError("y deve ser uma Series/DataFrame Pandas ou array NumPy")
            
        # Garante que n_features está correto
        if X_values.shape[1] != self.n_features:
            logging.warning(f"Número de features em X ({X_values.shape[1]}) difere do n_features esperado ({self.n_features}). Reconstruindo o modelo.")
            self.n_features = X_values.shape[1]
            self.model = self._build_model() # Reconstrói o modelo com o n_features correto

        X_scaled = self.scaler.fit_transform(X_values)
        X_seq, y_seq = create_sequences(X_scaled, y_values, self.lookback)
        
        # y_seq pode ser (n_samples,) ou (n_samples, 1). Garante que seja (n_samples,)
        y_seq = y_seq.ravel()
        
        if len(X_seq) == 0:
            logging.warning("Não há dados suficientes para criar sequências com o lookback fornecido.")
            return self

        early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)

        # Determina o tamanho da validação (mínimo 1, máximo 20% ou o que for possível)
        n_samples = len(X_seq)
        val_size = max(1, int(n_samples * 0.1)) if n_samples > 1 else 0
        
        # Evita erro se n_samples for muito pequeno
        validation_split = 0.1 if val_size > 0 and n_samples >= 10 else 0.0 # Só usa split se tiver dados suficientes

        # Verifica se y_seq tem a forma correta para binary_crossentropy
        if y_seq.ndim > 1 and y_seq.shape[1] > 1:
             logging.error(f"Target y_seq tem shape inesperado {y_seq.shape} para loss binary_crossentropy. Target deve ser 1D.")
             # Tenta ajustar, se possível (isso pode não ser o ideal dependendo da lógica)
             if y_seq.shape[1] == 1:
                 y_seq = y_seq.ravel()
             else:
                 # Aqui pode ser necessário repensar o target ou a loss function
                 raise ValueError("Shape do target incompatível com binary_crossentropy.")


        if validation_split > 0:
            self.history = self.model.fit(
                X_seq, y_seq,
                epochs=self.epochs,
                batch_size=self.batch_size,
                validation_split=validation_split,
                callbacks=[early_stopping],
                verbose=0 # Reduz verbosidade no treino
            )
        elif n_samples > 0: # Treina sem validação se não houver split
             self.history = self.model.fit(
                X_seq, y_seq,
                epochs=self.epochs,
                batch_size=self.batch_size,
                verbose=0
            )
        else:
            logging.warning("Nenhuma sequência gerada, impossível treinar.")
        

        return self

    def predict(self, X):
        """
        Faz previsões. Os dados de teste são escalados usando o mesmo scaler
        do treino e transformados em sequências.
        """
        # Garante que X seja array numpy ou dataframe pandas
        if isinstance(X, pd.DataFrame):
            X_values = X.values
        elif isinstance(X, np.ndarray):
            X_values = X
        else:
            raise ValueError("X deve ser um DataFrame Pandas ou array NumPy")
            
        # Garante que X_values tem o número correto de features esperado pelo scaler
        if X_values.shape[1] != self.scaler.n_features_in_:
            raise ValueError(f"Número de features em X ({X_values.shape[1]}) é diferente do esperado pelo scaler ({self.scaler.n_features_in_})")


        X_scaled = self.scaler.transform(X_values)
        
        # Para predição, não precisamos de y, então passamos um array de zeros
        y_dummy = np.zeros(len(X_scaled))
        X_seq, _ = create_sequences(X_scaled, y_dummy, self.lookback)
        
        if len(X_seq) == 0:
            # Se não há sequências (dados insuficientes), retorna array vazio compatível
            # O número de predições deveria ser len(X) - lookback
            # Retorna um array de -1 (ou outro indicador) para sinalizar falha? Ou vazio?
            # Por consistência, retornar array vazio pode ser melhor.
            return np.array([], dtype=int)
            
        predictions_proba = self.model.predict(X_seq)
        # Aplica threshold e converte para int
        predictions = (predictions_proba > 0.5).astype(int)
        
        # O número de predições será len(X) - lookback.
        # Retorna as predições achatadas.
        return predictions.flatten()

    def get_params(self, deep=True):
        """Retorna os parâmetros do wrapper."""
        return {
            'lookback': self.lookback,
            'lstm_units': self.lstm_units,
            'epochs': self.epochs,
            'batch_size': self.batch_size,
            'n_features': self.n_features
        }

    def set_params(self, **params):
        """Define os parâmetros e reconstrói o modelo se necessário."""
        rebuild = False
        for param, value in params.items():
            setattr(self, param, value)
            # Verifica se parâmetros que afetam a arquitetura foram alterados
            if param in ['lookback', 'lstm_units', 'n_features']:
                rebuild = True
        
        if rebuild:
            self.model = self._build_model() # Reconstrói se necessário
            
        return self
    
    # --- MÉTODOS DE PERSISTÊNCIA ATUALIZADOS ---
    
    def save(self, model_path_prefix: str): # MÉTODO ATUALIZADO
        """Salva o modelo Keras e o scaler usando um prefixo de caminho."""
        # Garante que o diretório pai exista
        Path(model_path_prefix).parent.mkdir(parents=True, exist_ok=True)
        
        model_path = f"{model_path_prefix}_lstm.keras"
        scaler_path = f"{model_path_prefix}_scaler.joblib"
        params_path = f"{model_path_prefix}_params.joblib" # Salva parâmetros também
        
        self.model.save(model_path)
        joblib.dump(self.scaler, scaler_path)
        # Salva parâmetros essenciais (lookback, n_features) para recarregar corretamente
        params_to_save = {'lookback': self.lookback, 'n_features': self.n_features}
        joblib.dump(params_to_save, params_path)
        
        logging.info(f"Modelo salvo em {model_path}, scaler em {scaler_path}, params em {params_path}")

    @classmethod
    def load(cls, model_path_prefix: str): # MÉTODO ATUALIZADO
        """Carrega um modelo Keras, scaler e parâmetros a partir de um prefixo."""
        model_path = f"{model_path_prefix}_lstm.keras"
        scaler_path = f"{model_path_prefix}_scaler.joblib"
        params_path = f"{model_path_prefix}_params.joblib"
        
        logging.info(f"Carregando modelo de {model_path}, scaler de {scaler_path}, params de {params_path}")
        
        # Carrega os componentes
        try:
            loaded_keras_model = keras.models.load_model(model_path)
            loaded_scaler = joblib.load(scaler_path)
            loaded_params = joblib.load(params_path)
        except FileNotFoundError as e:
            logging.error(f"Erro ao carregar arquivos do modelo: {e}")
            raise
        except Exception as e:
            logging.error(f"Erro inesperado ao carregar modelo/scaler/params: {e}", exc_info=True)
            raise

        # Cria uma nova instância do wrapper usando os parâmetros carregados
        instance = cls(
            lookback=loaded_params.get('lookback', 60), # Usa valor padrão se não encontrar
            n_features=loaded_params.get('n_features', 1) # Usa valor padrão se não encontrar
        )
        instance.model = loaded_keras_model
        instance.scaler = loaded_scaler
        
        # Atribui outros parâmetros se existirem (opcional, mas pode ser útil)
        instance.lstm_units = getattr(instance.model.layers[0], 'units', 50) # Tenta pegar do modelo

        logging.info(f"LSTMWrapper carregado com lookback={instance.lookback}, n_features={instance.n_features}")
        return instance

# --- Implementação da Estratégia LSTM ---

class LSTMStrategy(BaseStrategy):
    """
    Estratégia de trading que utiliza uma rede neural LSTM.
    """
    # Define parâmetros padrão ou recebe via __init__ se quiser configurá-los externamente
    def __init__(self, lookback=60, lstm_units=50, target_period=1):
        self.lookback = lookback
        self.lstm_units = lstm_units
        self.target_period = target_period
        # Nomes das features que serão usadas (importante!)
        self.feature_names = [
            'ema_9', 'sma_20', 'sma_200', 'dist_sma_20', 'dist_sma_200',
            'volume', 'volatility'
        ]

    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Adiciona os indicadores técnicos que servirão de features para o modelo.
        """
        df = data.copy()
        
        # Médias Móveis
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['sma_20'] = df['close'].rolling(window=20).mean()
        # df['sma_50'] = df['close'].rolling(window=50).mean()
        df['sma_200'] = df['close'].rolling(window=200).mean()

        df['dist_sma_20'] = (df['close'] - df['sma_20']) / df['close']
        df['dist_sma_200'] = (df['close'] - df['sma_200']) / df['close']
        
        df['dist_sma_20'] = df['dist_sma_20'].fillna(0)  # Preenche NaNs iniciais
        df['dist_sma_200'] = df['dist_sma_200'].fillna(0)  # Preenche NaNs iniciais

        # Volume (assume que 'volume' já existe nos dados do provider)
        if 'volume' not in df.columns:
            logging.warning("Coluna 'volume' não encontrada nos dados. Será preenchida com 0.")
            df['volume'] = 0

        # Volatilidade (desvio padrão dos retornos)
        df['returns'] = df['close'].pct_change()
        # Ajusta a janela de volatilidade se necessário
        volatility_window = min(21, len(df) - 1) if len(df) > 1 else 1
        # df['volatility'] = df['returns'].rolling(window=21).std() * np.sqrt(252) # Volatilidade anualizada
        if volatility_window > 0:
             # Calcula std apenas se a janela for válida
             df['volatility'] = df['returns'].rolling(window=volatility_window).std()
             # Multiplica por sqrt(252) para anualizar se for D1, ajuste para outros timeframes
             # Para simplificar, podemos não anualizar ou ajustar o fator (ex: sqrt(num_periods_in_year))
             # df['volatility'] = df['volatility'] * np.sqrt(252) # Exemplo anualizado
        else:
             df['volatility'] = 0.0 # Define como 0 se não houver dados suficientes

        # RSI (Índice de Força Relativa)
        """
        rsi_period = 14
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        
        # Evita divisão por zero no RSI
        rs = gain / loss.replace(0, 1e-6) # Substitui 0 por um valor pequeno para evitar NaN/inf
        
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50) # Preenche NaNs iniciais (comum no RSI) com 50 (neutro)
        """

        # Remove colunas auxiliares se existirem
        df = df.drop(columns=['returns', 'future_close'], errors='ignore')

        # Preenche NaNs restantes (gerados por rolling windows no início)
        # Pode usar ffill (propagação para frente) ou bfill (para trás) ou média/mediana
        df.ffill(inplace=True) # Propaga o último valor válido para frente
        df.bfill(inplace=True) # Preenche os NaNs restantes no início propagando para trás

        return df

    def define_target(self, data: pd.DataFrame) -> pd.Series:
        """Define o target como a previsão de alta no próximo período."""
        return calculate_target(data, target_period=self.target_period)

    def define_model(self) -> BaseEstimator:
        """Retorna uma instância do wrapper do modelo LSTM."""
        return LSTMWrapper( # NOME ATUALIZADO
            lookback=self.lookback,
            lstm_units=self.lstm_units,
            n_features=len(self.feature_names) # Passa o número correto de features
        )
    
    def get_feature_names(self) -> list[str]:
        """Retorna a lista de colunas a serem usadas como features."""
        return self.feature_names

    # --- Implementação dos Métodos de Persistência ---

    def save(self, model: BaseEstimator, model_path_prefix: str): # NOVO MÉTODO
        """Salva o modelo LSTMWrapper (modelo keras + scaler + params)."""
        logging.info(f"LSTMStrategy: Iniciando save para prefixo {model_path_prefix}")
        if isinstance(model, LSTMWrapper):
            try:
                model.save(model_path_prefix)
                logging.info(f"LSTMStrategy: Modelo salvo com sucesso usando prefixo {model_path_prefix}")
            except Exception as e:
                 logging.error(f"LSTMStrategy: Falha ao salvar o modelo LSTMWrapper: {e}", exc_info=True)
                 raise
        else:
            logging.error(f"LSTMStrategy: Esperado um modelo LSTMWrapper para salvar, mas recebeu {type(model)}")
            raise TypeError("Modelo incompatível para salvar com LSTMStrategy.")

    @classmethod
    def load(cls, model_path_prefix: str) -> BaseEstimator: # NOVO MÉTODO
        """Carrega o modelo LSTMWrapper (modelo keras + scaler + params)."""
        logging.info(f"LSTMStrategy: Iniciando load do prefixo {model_path_prefix}")
        try:
            model_instance = LSTMWrapper.load(model_path_prefix)
            logging.info(f"LSTMStrategy: Modelo carregado com sucesso do prefixo {model_path_prefix}")
            return model_instance
        except Exception as e:
            logging.error(f"LSTMStrategy: Falha ao carregar modelo LSTMWrapper: {e}", exc_info=True)
            raise