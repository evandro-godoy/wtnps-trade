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

    def _get_cache_path(self, ticker: str, start_date: str, end_date: str) -> Path:
        """Cria um nome de arquivo padronizado para o cache."""
        filename = f"{ticker}_{start_date}_{end_date}.parquet"
        return self.cache_path / filename

    def get_data(self, ticker: str, start_date: str, end_date: str, sentiment_ticker: str = "^VIX") -> pd.DataFrame:
        """
        Busca dados de mercado para um ticker principal e um ticker de sentimento (VIX).
        """
        cache_path = self._get_cache_path(ticker, start_date, end_date)
        
        try:
            if not cache_path.exists():
                logging.info(f"Buscando dados de '{ticker}' via yfinance...")
                data = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True, progress=False)
                
                if data.empty:
                    logging.error(f"Nenhum dado retornado para o ticker principal {ticker}.")
                    return pd.DataFrame()

                # --- CORREÇÃO DEFINITIVA: Achata o índice de colunas se for um MultiIndex ---
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.droplevel(0)

                if sentiment_ticker:
                    logging.info(f"Buscando dados de sentimento de '{sentiment_ticker}' via yfinance...")
                    sentiment_data = yf.download(sentiment_ticker, start=start_date, end=end_date, auto_adjust=True, progress=False)
                    
                    if not sentiment_data.empty:
                        if isinstance(sentiment_data.columns, pd.MultiIndex):
                            sentiment_data.columns = sentiment_data.columns.droplevel(0)
                            
                        sentiment_close = sentiment_data[['Close']].rename(columns={'Close': 'Sentiment'})
                        data = data.join(sentiment_close, how='left')
                        data['Sentiment'] = data['Sentiment'].ffill()
                    else:
                        logging.warning(f"Nenhum dado retornado para o {sentiment_ticker}. A coluna 'Sentiment' não será adicionada.")

                data.to_parquet(cache_path)
                logging.info(f"Dados de '{ticker}' salvos no cache.")

            logging.info(f"Carregando dados de '{ticker}' do cache: {cache_path}")
            data = pd.read_parquet(cache_path)

        except Exception as e:
            logging.error(f"Falha ao obter dados de mercado: {e}")
            return pd.DataFrame()
            
        return data