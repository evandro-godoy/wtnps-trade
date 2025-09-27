# src/strategies/base.py
from abc import ABC, abstractmethod
import pandas as pd
from sklearn.base import BaseEstimator

class BaseStrategy(ABC):
    """
    Classe base abstrata que define a interface para todas as estratégias de trading.
    """
    
    @abstractmethod
    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Recebe um DataFrame com dados de mercado brutos (OHLCV) e retorna
        um DataFrame com as features de engenharia adicionadas.
        """
        pass

    @abstractmethod
    def define_model(self) -> BaseEstimator:
        """
        Retorna uma instância não treinada do modelo de machine learning
        (deve ser compatível com a API do scikit-learn: .fit(), .predict()).
        """
        pass

    @abstractmethod
    def get_feature_names(self) -> list[str]:
        """
        Retorna uma lista com os nomes das colunas que devem ser usadas como features.
        """
        pass