# tests/test_backtest_engine.py
import pytest
import pandas as pd
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.model_selection import TimeSeriesSplit  # <--- CORREÇÃO AQUI

# Adiciona o diretório 'src' ao path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.strategies.base import BaseStrategy
from src.backtest_engine.engine import WalkForwardBacktester

# --- Componentes Falsos (Mocks) para o Teste ---

class MockPredictor(BaseEstimator):
    """Um modelo falso que sempre prevê a classe 1."""
    def fit(self, X, y):
        return self
    
    def predict(self, X):
        return np.ones(len(X))

class MockStrategy(BaseStrategy):
    """Uma estratégia falsa e simples para testar o motor."""
    def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df['Returns'] = df['Close'].pct_change() # Feature necessária para o resultado
        return df

    def define_model(self) -> BaseEstimator:
        return MockPredictor()

    def get_feature_names(self) -> list[str]:
        return ['Close'] # Usa uma feature qualquer

# --- Teste do Motor ---

def test_walk_forward_backtester_execution():
    """
    Testa se o WalkForwardBacktester executa o loop corretamente e retorna
    um DataFrame de resultados com o formato esperado.
    """
    # 1. Prepara os dados de entrada
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=100))
    market_data = pd.DataFrame({'Close': np.arange(100)}, index=dates)

    # 2. Instancia os componentes
    strategy = MockStrategy()
    n_splits = 5
    backtester = WalkForwardBacktester(strategy=strategy, n_splits=n_splits)

    # 3. Executa o backtest
    results = backtester.run(market_data)

    # 4. Valida os resultados
    assert isinstance(results, pd.DataFrame)
    assert 'Prediction' in results.columns
    assert 'Real_Target' in results.columns
    assert 'Returns' in results.columns
    
    # Recalcula o número de amostras após o dropna para o teste
    # 100 originais - 1 (pct_change) - 1 (shift target) = 98 amostras
    effective_samples = len(market_data) - 2 
    
    total_test_samples = sum(len(test_idx) for _, test_idx in TimeSeriesSplit(n_splits=n_splits).split(np.arange(effective_samples)))
    assert len(results) == total_test_samples

    # Como o MockPredictor sempre prevê 1, a acurácia deve ser a proporção de 1s no target
    expected_accuracy = results['Real_Target'].mean()
    # Importamos a métrica aqui para evitar NameError
    from sklearn.metrics import accuracy_score
    actual_accuracy = accuracy_score(results['Real_Target'], results['Prediction'])
    assert np.isclose(actual_accuracy, expected_accuracy)