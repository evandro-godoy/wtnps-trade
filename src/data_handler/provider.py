# src/data_handler/provider.py
import yfinance as yf
import pandas as pd
from pathlib import Path
import logging

# Configuração básica do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class YFinanceProvider:
    """
    Um provedor de dados que busca dados do Yahoo Finance e implementa um cache local
    para evitar downloads repetidos.
    """
    def __init__(self, cache_dir: str = ".cache_data"):
        self.cache_path = Path(cache_dir)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        logging.info(f"Diretório de cache de dados inicializado em: {self.cache_path.resolve()}")

    def get_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Busca os dados de um ticker. Primeiro, tenta carregar do cache.
        Se não encontrar, busca via yfinance e salva no cache.
        """
        filename = f"{ticker}_{start_date}_{end_date}.parquet"
        file_path = self.cache_path / filename

        if file_path.exists():
            logging.info(f"Carregando dados de '{ticker}' do cache: {file_path}")
            return pd.read_parquet(file_path)
        
        logging.info(f"Buscando dados de '{ticker}' via API (yfinance)...")
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)

        if data.empty:
            logging.warning(f"Nenhum dado encontrado para '{ticker}' no período especificado.")
            return data

        # Achata as colunas de múltiplos níveis se existirem
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        data.to_parquet(file_path)
        logging.info(f"Dados de '{ticker}' salvos no cache: {file_path}")
        
        return data