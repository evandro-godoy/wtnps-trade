# tests/test_data_handler.py
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path
import shutil

# Adiciona o diretório 'src' ao path para que possamos importar nosso módulo
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_handler.provider import YFinanceProvider

@pytest.fixture
def provider():
    """Cria uma instância do YFinanceProvider para os testes em um diretório de cache temporário."""
    test_cache_dir = ".test_cache"
    # Garante que o diretório de cache esteja limpo antes de cada teste
    if Path(test_cache_dir).exists():
        shutil.rmtree(test_cache_dir)
    
    p = YFinanceProvider(cache_dir=test_cache_dir)
    yield p # Fornece o objeto para o teste

    # Limpeza: remove o diretório de cache após a execução do teste
    shutil.rmtree(test_cache_dir)


def test_get_data_from_api_and_cache(provider: YFinanceProvider):
    """
    Testa o fluxo completo: busca da API na primeira chamada e do cache na segunda.
    """
    # Cria um DataFrame falso que o yfinance.download "retornará"
    mock_data = pd.DataFrame({
        'Open': [100], 'High': [105], 'Low': [99], 'Close': [102], 'Volume': [1000]
    }, index=[pd.to_datetime("2025-01-01")])

    # Usa o 'patch' para substituir temporariamente o yf.download
    with patch('yfinance.download', return_value=mock_data) as mock_download:
        # 1. Primeira chamada: Deve chamar a API
        data1 = provider.get_data("TEST.SA", "2025-01-01", "2025-01-02")
        mock_download.assert_called_once() # Verifica se a API foi chamada
        pd.testing.assert_frame_equal(data1, mock_data)

        # 2. Segunda chamada: NÃO deve chamar a API, deve usar o cache
        data2 = provider.get_data("TEST.SA", "2025-01-01", "2025-01-02")
        mock_download.assert_called_once() # O contador de chamadas não deve ter aumentado
        pd.testing.assert_frame_equal(data2, mock_data)