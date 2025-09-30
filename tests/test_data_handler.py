# tests/test_data_handler.py
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch
from pathlib import Path
import shutil

# Adiciona o diretório 'src' ao path para que possamos importar nossos módulos
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Importa ambos os provedores
from src.data_handler.provider import YFinanceProvider, MetaTraderProvider

# --- Testes para YFinanceProvider ---

@pytest.fixture
def yfinance_provider():
    """Cria uma instância do YFinanceProvider para os testes em um diretório de cache temporário."""
    test_cache_dir = ".test_cache_yf"
    if Path(test_cache_dir).exists():
        shutil.rmtree(test_cache_dir)
    
    p = YFinanceProvider(cache_dir=test_cache_dir)
    yield p

    shutil.rmtree(test_cache_dir)

def test_get_data_from_api_and_cache(yfinance_provider: YFinanceProvider):
    """
    Testa o fluxo completo do YFinanceProvider: busca da API na primeira chamada e do cache na segunda.
    """
    mock_data = pd.DataFrame({
        'open': [100], 'high': [105], 'low': [99], 'close': [102], 'volume': [1000]
    }, index=[pd.to_datetime("2025-01-01")])

    with patch('yfinance.download', return_value=mock_data) as mock_download:
        # 1. Primeira chamada: Deve chamar a API
        # CORREÇÃO: Adicionado sentiment_ticker=None para corresponder à assinatura do método
        data1 = yfinance_provider.get_data("TEST.SA", "2025-01-01", "2025-01-02", sentiment_ticker=None)
        
        assert not data1.empty
        assert 'close' in data1.columns
        mock_download.assert_called_once()

        # 2. Segunda chamada: Deve carregar do cache, sem chamar a API
        mock_download.reset_mock()
        # CORREÇÃO: Adicionado sentiment_ticker=None
        data2 = yfinance_provider.get_data("TEST.SA", "2025-01-01", "2025-01-02", sentiment_ticker=None)
        
        assert not data2.empty
        pd.testing.assert_frame_equal(data1, data2)
        mock_download.assert_not_called()

def test_get_data_returns_empty_on_failure(yfinance_provider: YFinanceProvider):
    """
    Testa se o provedor retorna um DataFrame vazio em caso de falha na API.
    """
    with patch('yfinance.download', side_effect=Exception("API Error")):
        # CORREÇÃO: Adicionado sentiment_ticker=None
        data = yfinance_provider.get_data("FAIL.SA", "2025-01-01", "2025-01-02", sentiment_ticker=None)
        assert data.empty

# --- Testes para MetaTraderProvider ---

@pytest.fixture
def metatrader_provider():
    """Cria uma instância do MetaTraderProvider para os testes em um diretório de cache temporário."""
    test_cache_dir = ".test_cache_mt5"
    if Path(test_cache_dir).exists():
        shutil.rmtree(test_cache_dir)
    
    p = MetaTraderProvider(cache_dir=test_cache_dir)
    yield p

    shutil.rmtree(test_cache_dir)

@patch('src.data_handler.provider.mt5')
def test_get_data_from_mt5_and_cache(mock_mt5, metatrader_provider: MetaTraderProvider):
    """
    Testa o fluxo completo do MetaTraderProvider: busca do MT5 na primeira chamada e do cache na segunda.
    """
    mock_mt5.initialize.return_value = True
    
    sample_rates = np.array([
        (1704067200, 100.0, 105.0, 99.0, 102.0, 1000, 0, 0),
        (1704153600, 102.0, 108.0, 101.0, 107.0, 1200, 0, 0)
    ], dtype=[('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'), 
              ('close', '<f8'), ('tick_volume', '<u8'), ('spread', '<i4'), ('real_volume', '<i8')])
    mock_mt5.copy_rates_range.return_value = sample_rates
    mock_mt5.shutdown.return_value = True

    ticker = "WINZ24"
    start_date = "2024-01-01"
    end_date = "2024-01-31"

    # 1. Primeira chamada
    data1 = metatrader_provider.get_data(ticker, start_date, end_date)
    
    assert not data1.empty
    assert 'close' in data1.columns
    mock_mt5.initialize.assert_called_once()
    mock_mt5.copy_rates_range.assert_called_once()
    mock_mt5.shutdown.assert_called_once()

    cache_path = metatrader_provider._get_cache_path(ticker, start_date, end_date)
    assert cache_path.exists()

    # 2. Segunda chamada
    mock_mt5.initialize.reset_mock()
    mock_mt5.copy_rates_range.reset_mock()
    mock_mt5.shutdown.reset_mock()

    data2 = metatrader_provider.get_data(ticker, start_date, end_date)
    
    assert not data2.empty
    pd.testing.assert_frame_equal(data1, data2)
    mock_mt5.initialize.assert_not_called()

@patch('src.data_handler.provider.mt5')
def test_mt5_get_data_returns_empty_on_connection_failure(mock_mt5, metatrader_provider: MetaTraderProvider):
    """
    Testa se o provedor MT5 retorna um DataFrame vazio se a conexão falhar.
    """
    mock_mt5.initialize.return_value = False

    data = metatrader_provider.get_data("FAIL", "2024-01-01", "2024-01-31")
    
    assert data.empty
    mock_mt5.initialize.assert_called_once()
    mock_mt5.copy_rates_range.assert_not_called()