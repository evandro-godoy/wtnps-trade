# src/data_handler/provider.py
import yfinance as yf
import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class YFinanceProvider:
    def __init__(self, cache_dir: str = ".cache_data"):
        self.cache_path = Path(cache_dir)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        logging.info(f"Diretório de cache de dados inicializado em: {self.cache_path.resolve()}")

    def _get_cache_path(self, ticker: str, start_date: str, end_date: str) -> Path:
        filename = f"{ticker}_{start_date}_{end_date}.parquet"
        return self.cache_path / filename

    def get_data(self, ticker: str, start_date: str, end_date: str, sentiment_ticker: str) -> pd.DataFrame:
        cache_path = self._get_cache_path(ticker, start_date, end_date)
        
        try:
            if not cache_path.exists():
                logging.info(f"Buscando dados de '{ticker}' via yfinance...")
                data = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True, progress=False)
                
                if data.empty:
                    logging.error(f"Nenhum dado retornado para o ticker principal {ticker}.")
                    return pd.DataFrame()

                # --- SOLUÇÃO DEFINITIVA PARA MULTI-INDEX E PADRONIZAÇÃO ---
                # Pega o primeiro nível do MultiIndex (se existir) e converte para minúsculas
                data.columns = [col[0].lower() if isinstance(col, tuple) else col.lower() for col in data.columns]

                if sentiment_ticker:
                    logging.info(f"Buscando dados de sentimento de '{sentiment_ticker}' via yfinance...")
                    sentiment_data = yf.download(sentiment_ticker, start=start_date, end=end_date, auto_adjust=True, progress=False)
                    
                    if not sentiment_data.empty:
                        sentiment_data.columns = [col[0].lower() if isinstance(col, tuple) else col.lower() for col in sentiment_data.columns]
                            
                        sentiment_close = sentiment_data[['close']].rename(columns={'close': 'sentiment'})
                        data = data.join(sentiment_close, how='left')
                        data['sentiment'] = data['sentiment'].ffill()
                    else:
                        logging.warning(f"Nenhum dado retornado para o {sentiment_ticker}. A coluna 'sentiment' não será adicionada.")

                data.to_parquet(cache_path)
                logging.info(f"Dados de '{ticker}' salvos no cache.")

            logging.info(f"Carregando dados de '{ticker}' do cache: {cache_path}")
            data = pd.read_parquet(cache_path)

        except Exception as e:
            logging.error(f"Falha ao obter dados de mercado: {e}")
            return pd.DataFrame()
            
        return data