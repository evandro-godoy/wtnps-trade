# tests/test_strategies.py
import pytest
import pandas as pd
import numpy as np

# Adiciona o diretório 'src' ao path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.strategies.random_forest import RandomForestFeatureStrategy

@pytest.fixture
def sample_market_data() -> pd.DataFrame:
    """Cria um DataFrame de exemplo com dados de mercado."""
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=100))
    data = {
        'Open': np.random.uniform(95, 105, 100),
        'High': np.random.uniform(100, 110, 100),
        'Low': np.random.uniform(90, 100, 100),
        'Close': np.random.uniform(98, 108, 100),
        'Volume': np.random.uniform(1e6, 5e6, 100)
    }
    return pd.DataFrame(data, index=dates)

def test_random_forest_strategy_feature_generation(sample_market_data):
    """
    Testa se a RandomForestFeatureStrategy adiciona corretamente as colunas de features.
    """
    strategy = RandomForestFeatureStrategy()
    
    # Aplica a engenharia de features
    featured_data = strategy.define_features(sample_market_data)
    
    # Verifica se o DataFrame retornado contém as colunas esperadas
    expected_features = ['MA_Diff', 'RSI', 'Returns', 'MA_Short', 'MA_Long']
    
    assert isinstance(featured_data, pd.DataFrame)
    for feature in expected_features:
        assert feature in featured_data.columns

    # Verifica se o modelo retornado é do tipo correto
    model = strategy.define_model()
    assert hasattr(model, 'fit') and hasattr(model, 'predict')