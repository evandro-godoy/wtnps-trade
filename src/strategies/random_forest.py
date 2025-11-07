# src/strategies/random_forest.py
from pathlib import Path
import pandas as pd
import numpy as np
import joblib # Para salvar/carregar modelos sklearn
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler # Para escalar features
from sklearn.pipeline import Pipeline # Para combinar scaler e modelo
from sklearn.base import BaseEstimator, ClassifierMixin # Para o Wrapper

from src.strategies.base import BaseStrategy, calculate_target # Importa a base e helper

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- Wrapper de Pipeline para RandomForest ---

class RFPipelineWrapper(BaseEstimator, ClassifierMixin):
    """
    Um wrapper para o pipeline do Scikit-Learn (Scaler + Modelo RandomForest)
    para fornecer métodos 'save' e 'load' padronizados, compatíveis com BaseStrategy.
    """
    # Adiciona parâmetros do RandomForest ao __init__ para configuração
    def __init__(self, n_estimators=100, random_state=42, n_jobs=-1, **rf_params):
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.n_jobs = n_jobs
        # Guarda quaisquer outros parâmetros para o RandomForest
        self.rf_params = rf_params 
        # Constrói o pipeline internamente
        self.pipeline = self._build_pipeline()

    def _build_pipeline(self):
        """Define o pipeline (scaler + modelo RandomForest)."""
        # Combina os parâmetros definidos com os extras
        all_rf_params = {
            'n_estimators': self.n_estimators,
            'random_state': self.random_state,
            'n_jobs': self.n_jobs,
            **self.rf_params # Adiciona outros parâmetros passados via **rf_params
        }
        return Pipeline([
            ('scaler', StandardScaler()), # Etapa 1: Escalar dados
            ('model', RandomForestClassifier(**all_rf_params)) # Etapa 2: Modelo RF
        ])

    def fit(self, X, y):
        """Treina o pipeline (scaler + modelo)."""
        # Garante que y seja 1D
        y_ravel = np.ravel(y)
        return self.pipeline.fit(X, y_ravel)

    def predict(self, X):
        """Faz previsões com o pipeline."""
        return self.pipeline.predict(X)
        
    def predict_proba(self, X):
        """Faz previsões de probabilidade com o pipeline."""
        # Verifica se o modelo dentro do pipeline tem predict_proba
        if hasattr(self.pipeline.named_steps['model'], 'predict_proba'):
            return self.pipeline.predict_proba(X)
        else:
            # Se não tiver, retorna probabilidades baseadas no predict (0 ou 1)
            preds = self.predict(X)
            proba = np.zeros((len(preds), 2))
            proba[np.arange(len(preds)), preds] = 1 # Coloca 1 na classe predita
            return proba

    def get_params(self, deep=True):
        """Retorna os parâmetros do wrapper e do pipeline."""
        # Delega ao pipeline, mas também inclui os parâmetros do wrapper
        params = self.pipeline.get_params(deep)
        params['n_estimators'] = self.n_estimators
        params['random_state'] = self.random_state
        params['n_jobs'] = self.n_jobs
        params.update(self.rf_params) # Inclui params extras
        return params

    def set_params(self, **params):
        """Define os parâmetros do wrapper e repassa para o pipeline."""
        wrapper_params = {}
        pipeline_params = {}
        for key, value in params.items():
            if key in ['n_estimators', 'random_state', 'n_jobs'] or key in self.rf_params:
                 # Se for um param do RF ou do wrapper, guarda para atualizar o wrapper
                 setattr(self, key, value)
                 if key not in ['n_estimators', 'random_state', 'n_jobs']:
                      self.rf_params[key] = value # Atualiza no dict de params extras
                 wrapper_params[f"model__{key}"] = value # Prepara para passar ao pipeline com prefixo 'model__'
            else:
                 # Se for um param direto do pipeline (ex: 'scaler__with_mean')
                 pipeline_params[key] = value

        # Atualiza o pipeline com os parâmetros corretos
        self.pipeline.set_params(**pipeline_params, **wrapper_params)
        return self

    # --- MÉTODOS DE PERSISTÊNCIA ---

    def save(self, model_path_prefix: str):
        """Salva o wrapper completo (que contém o pipeline) em um único arquivo .joblib."""
        # Garante que o diretório pai exista
        Path(model_path_prefix).parent.mkdir(parents=True, exist_ok=True)
        
        model_path = f"{model_path_prefix}_rf_pipeline.joblib" # Nome padronizado
        try:
            joblib.dump(self, model_path) # Salva a instância inteira do wrapper
            logging.info(f"RFPipelineWrapper salvo em: {model_path}")
        except Exception as e:
            logging.error(f"Erro ao salvar RFPipelineWrapper em {model_path}: {e}", exc_info=True)
            raise

    @classmethod
    def load(cls, model_path_prefix: str):
        """Carrega um RFPipelineWrapper de um arquivo .joblib."""
        model_path = f"{model_path_prefix}_rf_pipeline.joblib"
        logging.info(f"Carregando RFPipelineWrapper de: {model_path}")
        try:
            instance = joblib.load(model_path) # Carrega a instância do wrapper
            if not isinstance(instance, cls):
                logging.error(f"Arquivo {model_path} não contém uma instância de {cls.__name__}, mas sim {type(instance)}")
                raise TypeError(f"Objeto carregado não é do tipo {cls.__name__}")
            logging.info(f"RFPipelineWrapper carregado com sucesso.")
            return instance
        except FileNotFoundError:
            logging.error(f"Arquivo do modelo não encontrado em {model_path}")
            raise
        except Exception as e:
            logging.error(f"Erro ao carregar RFPipelineWrapper de {model_path}: {e}", exc_info=True)
            raise


# --- Implementação da Estratégia RandomForest ---

class RandomForestStrategy(BaseStrategy):
    """
    Estratégia de trading que utiliza um modelo RandomForest com indicadores técnicos.
    """
    def __init__(self, target_period=1, n_estimators=100, random_state=42):
        self.target_period = target_period
        self.n_estimators = n_estimators
        self.random_state = random_state
        # Define os nomes das features aqui para consistência
        self.feature_names = ['sma_9', 'sma_20', 'rsi', 'volatility', 'volume'] 

    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features técnicas simples."""
        df = data.copy()
        
        # Médias Móveis Simples
        df['sma_9'] = df['close'].rolling(window=9).mean()
        df['sma_20'] = df['close'].rolling(window=20).mean()

        # RSI
        rsi_period = 14
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss.replace(0, 1e-6) # Evita divisão por zero
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50) # Preenche NaNs iniciais

        # Volatilidade (desvio padrão dos retornos)
        volatility_window = min(21, len(df) - 1) if len(df) > 1 else 1
        if volatility_window > 0:
            df['volatility'] = df['close'].pct_change().rolling(window=volatility_window).std()
        else:
            df['volatility'] = 0.0

        # Volume (assume que já existe)
        if 'volume' not in df.columns:
            df['volume'] = 0

        # Preenche NaNs restantes (início das rolling windows)
        df.ffill(inplace=True)
        df.bfill(inplace=True)
        
        return df

    def define_target(self, data: pd.DataFrame) -> pd.Series:
        """Define o target como a previsão de alta no(s) próximo(s) período(s)."""
        return calculate_target(data, target_period=self.target_period)

    def define_model(self) -> BaseEstimator:
        """Retorna o wrapper do pipeline (Scaler + RandomForest)."""
        return RFPipelineWrapper(
            n_estimators=self.n_estimators,
            random_state=self.random_state
            # Outros parâmetros do RF podem ser passados aqui, se necessário
        )

    def get_feature_names(self) -> list[str]:
        """Retorna a lista de nomes das features definidas."""
        return self.feature_names

    # --- Implementação dos Métodos de Persistência ---

    def save(self, model: BaseEstimator, model_path_prefix: str): # NOVO MÉTODO
        """Salva o RFPipelineWrapper."""
        logging.info(f"RandomForestStrategy: Iniciando save para prefixo {model_path_prefix}")
        if isinstance(model, RFPipelineWrapper):
             try:
                 model.save(model_path_prefix) # Chama o save do wrapper
                 logging.info(f"RandomForestStrategy: Modelo salvo com sucesso.")
             except Exception as e:
                 logging.error(f"RandomForestStrategy: Falha ao salvar RFPipelineWrapper: {e}", exc_info=True)
                 raise
        else:
             logging.error(f"RandomForestStrategy: Esperado um RFPipelineWrapper, recebeu {type(model)}")
             raise TypeError("Modelo incompatível para salvar com RandomForestStrategy.")

    @classmethod
    def load(cls, model_path_prefix: str) -> BaseEstimator: # NOVO MÉTODO
        """Carrega o RFPipelineWrapper."""
        logging.info(f"RandomForestStrategy: Iniciando load do prefixo {model_path_prefix}")
        try:
             # Chama o load do wrapper
             model_instance = RFPipelineWrapper.load(model_path_prefix) 
             logging.info(f"RandomForestStrategy: Modelo carregado com sucesso.")
             return model_instance
        except Exception as e:
             logging.error(f"RandomForestStrategy: Falha ao carregar RFPipelineWrapper: {e}", exc_info=True)
             raise