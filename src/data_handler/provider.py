import yfinance as yf
import pandas as pd
from pathlib import Path
import logging
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pytz
import numpy as np
import sys # Adicionado para checagem de tipo

# Adiciona a raiz do projeto ao path para importações (se necessário)
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# Configuração básica do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__) # Logger específico para o módulo

class YFinanceProvider:
    """Provedor de dados via Yahoo Finance com cache."""
    def __init__(self, cache_dir: str = ".cache_data"):
        self.cache_path = Path(cache_dir)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        log.info(f"Diretório de cache de dados (YFinance) inicializado em: {self.cache_path.resolve()}")

    def _get_cache_path(self, ticker: str, start_date: str, end_date: str) -> Path:
        """Cria um nome de arquivo padronizado para o cache."""
        filename = f"{ticker}_{start_date}_{end_date}.parquet"
        return self.cache_path / filename

    def get_data(self, ticker: str, start_date: str, end_date: str, sentiment_ticker: str = None) -> pd.DataFrame:
        """Busca dados de mercado do Yahoo Finance (usa cache)."""
        # Remove .SA para buscar no yfinance (ex: PETR4.SA -> PETR4)
        yf_ticker = ticker.replace('.SA', '')

        cache_path = self._get_cache_path(yf_ticker, start_date, end_date) # Usa yf_ticker para nome do cache
        try:
            if not cache_path.exists():
                log.info(f"YFinance: Buscando dados de '{yf_ticker}'...")
                data = yf.download(yf_ticker, start=start_date, end=end_date, auto_adjust=True, progress=False)
                if data.empty:
                    log.error(f"YFinance: Nenhum dado retornado para {yf_ticker}.")
                    return pd.DataFrame()
                data.columns = [col.lower() for col in data.columns] # Padroniza colunas

                # Adiciona coluna 'volume' se não existir (necessário para compatibilidade)
                if 'volume' not in data.columns:
                     data['volume'] = 0 # Ou np.nan se preferir

                # Busca dados de sentimento se solicitado
                if sentiment_ticker:
                    log.info(f"YFinance: Buscando dados de sentimento '{sentiment_ticker}'...")
                    yf_sentiment_ticker = sentiment_ticker.replace('.SA', '')
                    sentiment_data = yf.download(yf_sentiment_ticker, start=start_date, end=end_date, auto_adjust=True, progress=False)
                    if not sentiment_data.empty:
                        sentiment_data.columns = [col.lower() for col in sentiment_data.columns]
                        sentiment_close = sentiment_data[['close']].rename(columns={'close': 'sentiment'})
                        data = data.join(sentiment_close, how='left')
                        data['sentiment'] = data['sentiment'].ffill()
                    else:
                        log.warning(f"YFinance: Nenhum dado retornado para {yf_sentiment_ticker}.")

                data.to_parquet(cache_path)
                log.info(f"YFinance: Dados de '{yf_ticker}' salvos no cache.")

            log.info(f"YFinance: Carregando dados de '{yf_ticker}' do cache: {cache_path}")
            data = pd.read_parquet(cache_path)
            # Garante colunas essenciais
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                 if col not in data.columns:
                     data[col] = np.nan # Adiciona coluna vazia se faltar
            return data[required_cols + ([ 'sentiment' ] if 'sentiment' in data.columns else [])] # Retorna colunas na ordem esperada

        except Exception as e:
            log.error(f"YFinance: Falha ao obter dados para {yf_ticker}: {e}", exc_info=True)
            return pd.DataFrame()


class MetaTraderProvider:
    """Provedor de dados via MetaTrader 5 com cache (para dados históricos)."""
    def __init__(self, cache_dir: str = ".cache_data"):
        self.cache_path = Path(cache_dir)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        log.info(f"Diretório de cache de dados (MT5) inicializado em: {self.cache_path.resolve()}")

    def _get_cache_path(self, ticker: str, start_date: str, end_date: str, timeframe_str: str) -> Path:
        """Cria um nome de arquivo padronizado para o cache, incluindo timeframe."""
        # Limpa caracteres inválidos do ticker para nome de arquivo
        safe_ticker = "".join(c for c in ticker if c.isalnum() or c in ('_'))
        filename = f"MT5_{safe_ticker}_{timeframe_str}_{start_date}_{end_date}.parquet"
        return self.cache_path / filename

    def get_data(self, ticker: str, start_date: str, end_date: str, timeframe=mt5.TIMEFRAME_D1) -> pd.DataFrame:
        """Busca dados históricos do MetaTrader 5 (usa cache)."""

        # Converte constante MT5 para string para nome do cache
        timeframe_str = self._mt5_timeframe_to_string(timeframe)
        cache_path = self._get_cache_path(ticker, start_date, end_date, timeframe_str)

        try:
            if cache_path.exists():
                log.info(f"MT5: Carregando dados de '{ticker}' ({timeframe_str}) do cache: {cache_path}")
                return pd.read_parquet(cache_path)

            log.info(f"MT5: Conectando para buscar dados históricos...")
            if not self._ensure_mt5_connection(): return pd.DataFrame()

            log.info(f"MT5: Buscando dados históricos de '{ticker}' ({timeframe_str})...")
            timezone = pytz.timezone("Etc/UTC")
            # Adiciona hora ao start_date para garantir inclusão, e ao end_date para garantir inclusão do dia
            utc_from = timezone.localize(datetime.strptime(start_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0))
            utc_to = timezone.localize(datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
            rates = mt5.copy_rates_range(ticker, timeframe, utc_from, utc_to)
            # Não desliga aqui, pode ser usado por outras funções

            if rates is None or len(rates) == 0:
                log.warning(f"MT5: Nenhum dado histórico retornado para '{ticker}' ({timeframe_str}).")
                return pd.DataFrame()

            data = pd.DataFrame(rates)
            # Remove linhas onde todos os valores OHLC são zero ou nulos (dados inválidos)
            data = data[(data[['open', 'high', 'low', 'close']] != 0).any(axis=1)]
            data = data.dropna(subset=['open', 'high', 'low', 'close'], how='all')

            if data.empty:
                log.warning(f"MT5: Dados históricos para '{ticker}' ({timeframe_str}) estavam vazios ou inválidos após limpeza.")
                return pd.DataFrame()

            data['time'] = pd.to_datetime(data['time'], unit='s', utc=True)
            data.set_index('time', inplace=True)
            data.rename(columns={'open': 'open', 'high': 'high', 'low': 'low',
                                 'close': 'close', 'tick_volume': 'volume'}, inplace=True)
            # Garante colunas essenciais
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                 if col not in data.columns:
                     data[col] = 0 # Preenche volume faltante com 0

            data = data[required_cols] # Seleciona e ordena
            data.to_parquet(cache_path)
            log.info(f"MT5: Dados históricos de '{ticker}' ({timeframe_str}) salvos no cache.")
            return data
        except Exception as e:
            log.error(f"MT5: Falha ao obter dados históricos para {ticker}: {e}", exc_info=True)
            return pd.DataFrame()

    def get_latest_rates(self, ticker: str, count: int, timeframe=mt5.TIMEFRAME_D1, end_time_utc: datetime = None) -> pd.DataFrame:
        """
        Busca os 'count' candles mais recentes ATÉ um determinado tempo (se fornecido),
        ou os mais recentes disponíveis se end_time_utc for None. Não usa cache.
        """
        rates = None
        log.debug(f"MT5-Latest: Buscando {count} barras para {ticker} @ {self._mt5_timeframe_to_string(timeframe)}"
                  f"{' até ' + str(end_time_utc) if end_time_utc else ' (mais recentes)'}")
        try:
            if not self._ensure_mt5_connection(): return pd.DataFrame()

            if end_time_utc:
                # Garante que end_time_utc está ciente do fuso horário UTC
                if end_time_utc.tzinfo is None:
                    end_time_utc = pytz.utc.localize(end_time_utc)
                else:
                    end_time_utc = end_time_utc.astimezone(pytz.utc)

                # Busca um range terminando no tempo especificado
                # Aumenta a janela de busca para garantir 'count' barras válidas antes do end_time
                minutes_per_bar = self._timeframe_to_minutes(timeframe)
                safety_margin = 5 # Adiciona margem de 5 barras
                estimated_duration = timedelta(minutes=minutes_per_bar * (count + safety_margin))
                estimated_start_utc = end_time_utc - estimated_duration
                log.debug(f"MT5-Latest: Buscando range de {estimated_start_utc} até {end_time_utc}")
                rates = mt5.copy_rates_range(ticker, timeframe, estimated_start_utc, end_time_utc)
            else:
                # Busca os 'count' últimos candles a partir da posição 0 (mais recente)
                log.debug(f"MT5-Latest: Buscando {count} barras a partir da posição 0")
                rates = mt5.copy_rates_from_pos(ticker, timeframe, 0, count)

            if rates is None or len(rates) == 0:
                time_str = f"até {end_time_utc}" if end_time_utc else "recentes"
                log.warning(f"MT5-Latest: Nenhum dado {time_str} retornado para '{ticker}'.")
                return pd.DataFrame()

            data = pd.DataFrame(rates)
            # Limpeza de dados inválidos
            data = data[(data[['open', 'high', 'low', 'close']] != 0).any(axis=1)]
            data = data.dropna(subset=['open', 'high', 'low', 'close'], how='all')

            if data.empty:
                 log.warning(f"MT5-Latest: Dados para '{ticker}' estavam vazios ou inválidos após limpeza.")
                 return pd.DataFrame()

            data['time'] = pd.to_datetime(data['time'], unit='s', utc=True)
            data.set_index('time', inplace=True)
            data.rename(columns={'open': 'open', 'high': 'high', 'low': 'low',
                                 'close': 'close', 'tick_volume': 'volume'}, inplace=True)

            # Garante colunas e preenche volume se necessário
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                 if col not in data.columns:
                     data[col] = 0

            # Filtra novamente para garantir que estamos ANTES ou IGUAL a end_time_utc (se fornecido)
            # E retorna apenas as últimas 'count' barras válidas
            if end_time_utc:
                data = data[data.index <= end_time_utc]

            return data[required_cols].tail(count)

        except Exception as e:
            log.error(f"MT5-Latest: Erro ao buscar dados recentes para {ticker}: {e}", exc_info=True)
            return pd.DataFrame()

    def _ensure_mt5_connection(self) -> bool:
        """Verifica se o MT5 está conectado e tenta conectar se não estiver."""
        if not mt5.terminal_info():
            log.warning("MT5 não estava conectado. Tentando inicializar...")
            if not mt5.initialize():
                log.error(f"MT5: Falha na inicialização na verificação: {mt5.last_error()}")
                return False
            else:
                log.info("MT5: Conexão reestabelecida.")
        return True

    def _timeframe_to_minutes(self, timeframe) -> int:
         """Converte constante de timeframe MT5 para minutos (aproximado)."""
         tf_map_minutes = {
             mt5.TIMEFRAME_M1: 1, mt5.TIMEFRAME_M5: 5, mt5.TIMEFRAME_M15: 15,
             mt5.TIMEFRAME_M30: 30, mt5.TIMEFRAME_H1: 60, mt5.TIMEFRAME_H4: 240,
             mt5.TIMEFRAME_D1: 1440 # 24 * 60
         }
         return tf_map_minutes.get(timeframe, 1440) # Padrão para diário

    def _mt5_timeframe_to_string(self, timeframe) -> str:
        """Converte constante de timeframe MT5 para string."""
        tf_map_str = {v: k for k, v in {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1 }.items()
        }
        return tf_map_str.get(timeframe, "D1")

    def shutdown(self):
         """Encerra a conexão com o MT5 se ela foi iniciada por este provider."""
         # O gerenciamento de conexão pode precisar ser mais centralizado
         # Por enquanto, apenas garante que tentamos desligar.
         log.info("Provider solicitando desligamento do MT5...")
         mt5.shutdown()

    def get_rates(self, ticker: str, candle_position: int, count: int, timeframe=mt5.TIMEFRAME_D1) -> pd.DataFrame:
        """Busca os 'count' candles entre um range de posições para um ativo."""
        try:
            # Não é necessário inicializar/desligar aqui, o robô gerenciará a conexão
            rates = mt5.copy_rates_from_pos(ticker, timeframe, candle_position, count)
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