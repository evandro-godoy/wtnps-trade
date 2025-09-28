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

    def get_data(self, ticker: str, start_date: str, end_date: str, sentiment_ticker: str = "^VIX") -> pd.DataFrame:
        """
        Busca dados de mercado para um ticker principal e um ticker de sentimento (VIX).
        """
        cache_path = self._get_cache_path(ticker, start_date, end_date)
        
        try:
            if cache_path.exists():
                logging.info(f"Carregando dados de '{ticker}' do cache: {cache_path}")
                data = pd.read_parquet(cache_path)
            else:
                logging.info(f"Buscando dados de '{ticker}' via yfinance...")
                data = yf.download(ticker, start=start_date, end=end_date, progress=False)
                
                # --- NOVA LÓGICA PARA BUSCAR E MESCLAR DADOS DE SENTIMENTO (VIX) ---
                if sentiment_ticker:
                    logging.info(f"Buscando dados de sentimento de '{sentiment_ticker}' via yfinance...")
                    sentiment_data = yf.download(sentiment_ticker, start=start_date, end=end_date, progress=False)
                    # Renomeia a coluna 'Close' do VIX para 'Sentiment' e a mescla
                    data['Sentiment'] = sentiment_data['Close']
                    # Preenche quaisquer dias faltantes (ex: feriados) com o valor anterior
                    data['Sentiment'] = data['Sentiment'].ffill()

                data.to_parquet(cache_path)
                logging.info(f"Dados de '{ticker}' salvos no cache.")

        except Exception as e:
            logging.error(f"Falha ao obter dados de mercado: {e}")
            return pd.DataFrame()
            
        return data