# src/strategies/base.py
import pandas as pd
from abc import ABC, abstractmethod
from sklearn.base import BaseEstimator # Necessário para type hint
import logging # Necessário para logging

class BaseStrategy(ABC):
    """
    Classe base abstrata para todas as estratégias de trading.
    Define a interface comum que todas as estratégias devem implementar.
    """

    @abstractmethod
    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Adiciona colunas de features ao DataFrame de dados de mercado.
        Deve retornar o DataFrame com as novas colunas.
        """
        pass

    def define_target(self, data: pd.DataFrame) -> pd.Series:
        """
        Define a coluna target (o que o modelo deve prever).
        Deve retornar uma Series do Pandas.
        Exemplo: prever se o próximo fechamento será maior que o atual.
        
        Note: Estratégias de RL podem não precisar implementar este método.
        """
        raise NotImplementedError(f"Estratégia {self.__class__.__name__} não implementou 'define_target'.")

    def define_model(self) -> BaseEstimator:
        """
        Retorna uma instância não treinada do modelo de machine learning
        (compatível com a API Scikit-Learn: fit, predict).
        
        Note: Estratégias de RL podem não precisar implementar este método.
        """
        raise NotImplementedError(f"Estratégia {self.__class__.__name__} não implementou 'define_model'.")
    
    @abstractmethod
    def get_feature_names(self) -> list[str]:
        """
        Retorna uma lista com os nomes das colunas que devem ser usadas como
        features para o modelo.
        """
        pass

    # --- NOVOS MÉTODOS PARA PERSISTÊNCIA ---
    
    @abstractmethod
    def save(self, model: BaseEstimator, model_path_prefix: str):
        """
        Salva o modelo treinado. A implementação específica (joblib, keras, etc.)
        fica a cargo da subclasse concreta.

        Args:
            model: A instância do modelo treinado (BaseEstimator).
            model_path_prefix: O caminho base (sem extensão) para salvar o(s) arquivo(s) do modelo.
                               Ex: 'models/WDO$_prod'
        """
        # A implementação concreta deve chamar o método save do *wrapper* do modelo.
        # Exemplo: model.save(model_path_prefix) # Onde model é LSTMWrapper ou RFPipelineWrapper
        logging.info(f"Tentando salvar modelo usando prefixo: {model_path_prefix}")
        if hasattr(model, 'save') and callable(model.save):
             model.save(model_path_prefix)
        else:
             logging.error(f"O modelo {type(model)} não possui um método 'save' implementado.")
             raise NotImplementedError(f"Estratégia {self.__class__.__name__} não implementou corretamente o método 'save' no seu modelo/wrapper.")


    @classmethod
    @abstractmethod
    def load(cls, model_path_prefix: str) -> BaseEstimator:
        """
        Carrega um modelo treinado a partir de um prefixo de caminho.
        Retorna a instância do modelo carregado.

        Args:
            model_path_prefix: O caminho base (sem extensão) de onde carregar o(s) arquivo(s) do modelo.
                               Ex: 'models/WDO$_prod'
        
        Returns:
            Uma instância do modelo treinado (BaseEstimator).
        """
        # A implementação concreta deve saber como carregar seu tipo específico de modelo/wrapper.
        # Exemplo: return LSTMWrapper.load(model_path_prefix)
        raise NotImplementedError(f"Estratégia {cls.__name__} não implementou o método de classe 'load'.")

# --- Função Auxiliar ---

def calculate_target(data: pd.DataFrame, target_period: int = 1) -> pd.Series:
    """
    Função auxiliar para criar um target binário comum:
    1 se o preço de fechamento `target_period` períodos no futuro for maior que o atual,
    0 caso contrário.
    """
    df = data.copy()
    df['future_close'] = df['close'].shift(-target_period)
    df['target'] = (df['future_close'] > df['close']).astype(int)
    return df['target']