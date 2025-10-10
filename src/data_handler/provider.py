# src/data_handler/provider.py
import yfinance as yf
import pandas as pd
from pathlib import Path
import logging
import MetaTrader5 as mt5
from datetime import datetime
import pytz

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
    

class MetaTraderProvider:
    """
    Provedor de dados que busca dados históricos diretamente da plataforma MetaTrader 5.
    """
    def __init__(self, cache_dir: str = ".cache_data"):
        self.cache_path = Path(cache_dir)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        logging.info(f"Diretório de cache de dados inicializado em: {self.cache_path.resolve()}")

    def _get_cache_path(self, ticker: str, start_date: str, end_date: str) -> Path:
        """Cria um nome de arquivo padronizado para o cache."""
        filename = f"MT5_{ticker}_{start_date}_{end_date}.parquet"
        return self.cache_path / filename

    def get_data(self, ticker: str, start_date: str, end_date: str, sentiment_ticker: str) -> pd.DataFrame:
        """
        Busca dados de mercado do MetaTrader 5.
        """
        timeframe=mt5.TIMEFRAME_D1
        
        cache_path = self._get_cache_path(ticker, start_date, end_date)
        
        try:
            if cache_path.exists():
                logging.info(f"Carregando dados de '{ticker}' do cache: {cache_path}")
                return pd.read_parquet(cache_path)

            logging.info(f"Conectando ao MetaTrader 5...")
            if not mt5.initialize():
                logging.error(f"Falha na inicialização do MetaTrader 5, erro: {mt5.last_error()}")
                return pd.DataFrame()

            logging.info(f"Buscando dados de '{ticker}' via MetaTrader 5...")
            
            # Define o fuso horário para UTC para evitar problemas com a localização
            timezone = pytz.timezone("Etc/UTC")
            utc_from = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone)
            utc_to = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone)
            
            rates = mt5.copy_rates_range(ticker, timeframe, utc_from, utc_to)
            
            # Desliga a conexão com o MetaTrader 5
            mt5.shutdown()
            logging.info("Conexão com o MetaTrader 5 encerrada.")

            if rates is None or len(rates) == 0:
                logging.warning(f"Nenhum dado retornado para '{ticker}' do MetaTrader 5.")
                return pd.DataFrame()

            # Converte para DataFrame e padroniza as colunas
            data = pd.DataFrame(rates)
            data['time'] = pd.to_datetime(data['time'], unit='s')
            data.set_index('time', inplace=True)
            
            # Renomeia as colunas para o padrão do nosso framework (minúsculas)
            data.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'tick_volume': 'volume'
            }, inplace=True)
            
            # Mantém apenas as colunas que o framework utiliza
            data = data[['open', 'high', 'low', 'close', 'volume']]

            data.to_parquet(cache_path)
            logging.info(f"Dados de '{ticker}' salvos no cache.")
            return data

        except Exception as e:
            logging.error(f"Falha ao obter dados do MetaTrader 5: {e}")
            # Garante que a conexão seja encerrada em caso de erro
            mt5.shutdown()
            return pd.DataFrame()
        

    def get_latest_rates(self, ticker: str, count: int, timeframe=mt5.TIMEFRAME_D1) -> pd.DataFrame:
        """Busca os 'count' candles mais recentes de um ativo."""
        try:
            # Não é necessário inicializar/desligar aqui, o robô gerenciará a conexão
            rates = mt5.copy_rates_from_pos(ticker, timeframe, 0, count)
            if rates is None or len(rates) == 0:
                logging.warning(f"Nenhum dado recente retornado para '{ticker}'.")
                return pd.DataFrame()

            data = pd.DataFrame(rates)
            data['time'] = pd.to_datetime(data['time'], unit='s')
            data.set_index('time', inplace=True)
            data.rename(columns={'tick_volume': 'volume'}, inplace=True)
            return data[['open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            logging.error(f"Erro ao buscar dados recentes do MT5: {e}")
            return pd.DataFrame()        
    