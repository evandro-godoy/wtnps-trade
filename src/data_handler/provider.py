# src/data_handler/provider.py

import MetaTrader5 as mt5
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz # Para lidar com timezones
import logging
from abc import ABC, abstractmethod
from pathlib import Path
import os # Para criar diretório

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctimes)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cache directory (adjust path as needed)
# Usa Path para criar o caminho relativo à raiz do projeto
CACHE_DIR = Path(__file__).parent.parent.parent / '.cache_data'

# Garante que o diretório de cache exista
os.makedirs(CACHE_DIR, exist_ok=True)
logger.info(f"Diretório de cache de dados (MT5) inicializado em: {CACHE_DIR.resolve()}")

# Define o timezone desejado (ex: Brazil/East para B3)
# Ajuste conforme o mercado que está operando
desired_timezone = pytz.timezone('America/Sao_Paulo')


def _get_mt5_timeframe(tf_str: str):
    """Converte string de timeframe para constante MT5."""
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
    }
    return tf_map.get(tf_str.upper())


class BaseDataProvider(ABC):
    """Classe base abstrata para provedores de dados."""

    @abstractmethod
    def get_data(self, ticker: str, start_date: str, end_date: str, timeframe) -> pd.DataFrame:
        """
        Método abstrato para buscar dados históricos.
        Deve retornar um DataFrame pandas com colunas OHLCV e índice DatetimeIndex.
        """
        pass

    @abstractmethod
    def get_latest_candles(self, ticker: str, timeframe, count: int) -> pd.DataFrame:
        """
        Método abstrato para buscar os 'count' candles mais recentes.
        """
        pass

    def close_connection(self):
        """Método opcional para fechar conexões, se aplicável."""
        pass

    def is_connected(self) -> bool:
        """Método opcional para verificar o status da conexão."""
        return True # Default para providers que não mantêm conexão ativa


class MetaTraderProvider(BaseDataProvider):
    """Provedor de dados utilizando a API do MetaTrader 5."""

    def __init__(self):
        self.connection_active = self._initialize_mt5()
        if not self.connection_active:
             # Opcional: Levantar exceção se a conexão inicial falhar?
             # raise ConnectionError("Não foi possível conectar ao MetaTrader 5.")
             logger.critical("Falha ao inicializar a conexão com o MetaTrader 5.")


    def _initialize_mt5(self) -> bool:
        """Inicializa a conexão com o MetaTrader 5."""
        if not mt5.initialize():
            logger.error(f"Falha na inicialização do MT5, erro code = {mt5.last_error()}")
            return False
        logger.info(f"MetaTrader 5 Conectado: {mt5.terminal_info().name}")
        return True

    def is_connected(self) -> bool:
        """Verifica se a conexão com o MT5 está ativa."""
        # Considera ativo se a inicialização foi bem sucedida
        # Pode adicionar verificações adicionais se necessário (ex: terminal_state())
        return self.connection_active and mt5.terminal_info() is not None


    def get_data(self, ticker: str, start_date: str, end_date: str, timeframe: int) -> pd.DataFrame:
        """Busca dados históricos do MT5 com cache e tratamento de timezone."""
        if not self.is_connected():
             logger.error("MetaTrader 5 não está conectado. Tentando reconectar...")
             if not self._initialize_mt5():
                  logger.error("Falha ao reconectar ao MT5.")
                  return pd.DataFrame() # Retorna vazio se não conseguir reconectar

        # Converte strings de data para objetos datetime com timezone
        try:
             # Assume que as strings de entrada NÃO têm timezone e as localiza para UTC
             start_dt_utc = pytz.utc.localize(datetime.strptime(start_date, '%Y-%m-%d'))
             end_dt_utc = pytz.utc.localize(datetime.strptime(end_date, '%Y-%m-%d'))
        except ValueError:
             # Tenta formato com hora
             try:
                 start_dt_utc = pytz.utc.localize(datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S'))
                 end_dt_utc = pytz.utc.localize(datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S'))
             except ValueError:
                  logger.error(f"Formato de data inválido: {start_date} ou {end_date}. Use YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS.")
                  return pd.DataFrame()

        # Cria nome do arquivo de cache
        timeframe_str = [k for k, v in mt5.__dict__.items() if v == timeframe][0].replace('TIMEFRAME_', '') # Ex: 'H1'
        cache_filename = f"MT5_{ticker.replace('$','')}_{timeframe_str}_{start_dt_utc.strftime('%Y-%m-%d')}_{end_dt_utc.strftime('%Y-%m-%d')}.parquet"
        cache_filepath = CACHE_DIR / cache_filename

        # Verifica se o arquivo de cache existe e é válido
        if cache_filepath.exists():
            try:
                logger.info(f"Carregando dados de {ticker} do cache: {cache_filepath}")
                data = pd.read_parquet(cache_filepath)
                # Verifica se o DataFrame lido tem índice de data/hora
                if isinstance(data.index, pd.DatetimeIndex):
                     # Converte para o timezone desejado APÓS ler do cache
                     if data.index.tz is None: # Se não tiver tz, assume UTC (como salvamos)
                          data = data.tz_localize('UTC').tz_convert(desired_timezone)
                     else: # Se já tiver, apenas converte
                          data = data.tz_convert(desired_timezone)
                     logger.info(f"Dados carregados do cache e convertidos para {desired_timezone}.")
                     return data
                else:
                     logger.warning("Arquivo de cache corrompido ou sem DatetimeIndex. Buscando novamente.")
            except Exception as e:
                logger.warning(f"Erro ao ler cache {cache_filepath}: {e}. Buscando dados novamente.")

        # Busca dados do MT5 se não houver cache válido
        logger.info(f"Buscando dados de {ticker} do MetaTrader 5 ({start_date} a {end_date} @ {timeframe_str})...")
        try:
            rates = mt5.copy_rates_range(ticker, timeframe, start_dt_utc, end_dt_utc)
        except Exception as e:
             logger.error(f"Erro ao chamar mt5.copy_rates_range para {ticker}: {e}")
             return pd.DataFrame() # Retorna vazio em caso de erro na API

        if rates is None or len(rates) == 0:
            logger.warning(f"Nenhum dado retornado do MT5 para {ticker} no período.")
            return pd.DataFrame()

        # Converte para DataFrame
        data = pd.DataFrame(rates)
        # Converte a coluna 'time' para datetime (segundos UNIX) e define como índice
        data['time'] = pd.to_datetime(data['time'], unit='s', utc=True) # MT5 retorna em UTC
        data.set_index('time', inplace=True)

        # Renomeia colunas para o padrão OHLCV (minúsculo)
        data.rename(columns={
            'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close',
            'tick_volume': 'volume' # Ou 'real_volume' se disponível e preferido
        }, inplace=True)

        # Seleciona apenas as colunas desejadas
        data = data[['open', 'high', 'low', 'close', 'volume']]

        # Salva em cache (formato parquet é eficiente)
        try:
             logger.info(f"Salvando dados de {ticker} em cache: {cache_filepath}")
             # Salva com índice e compressão
             data.to_parquet(cache_filepath, index=True, compression='snappy')
        except Exception as e:
            logger.error(f"Erro ao salvar dados no cache {cache_filepath}: {e}")

        # Converte para o timezone desejado ANTES de retornar
        data = data.tz_convert(desired_timezone)
        logger.info(f"Dados buscados do MT5 e convertidos para {desired_timezone}.")

        return data

    def get_latest_candles(self, ticker: str, timeframe: int, count: int) -> pd.DataFrame:
        """Busca os 'count' candles mais recentes do MT5."""
        if not self.is_connected():
             logger.error("MetaTrader 5 não está conectado.")
             # Tentar reconectar?
             if not self._initialize_mt5(): return pd.DataFrame()

        try:
            rates = mt5.copy_rates_from_pos(ticker, timeframe, 0, count)
        except Exception as e:
             logger.error(f"Erro ao chamar mt5.copy_rates_from_pos para {ticker}: {e}")
             return pd.DataFrame()

        if rates is None or len(rates) == 0:
            #logger.warning(f"Nenhum candle recente retornado do MT5 para {ticker}.")
            return pd.DataFrame()

        data = pd.DataFrame(rates)
        data['time'] = pd.to_datetime(data['time'], unit='s', utc=True) # Mantém UTC aqui
        data.set_index('time', inplace=True)
        data.rename(columns={
            'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close',
            'tick_volume': 'volume'
        }, inplace=True)
        data = data[['open', 'high', 'low', 'close', 'volume']]
        
        # Converte para o timezone desejado
        data = data.tz_convert(desired_timezone)

        return data


    def close_connection(self):
        """Fecha a conexão com o MT5."""
        if self.connection_active:
            logger.info("Desligando conexão com MetaTrader 5...")
            mt5.shutdown()
            self.connection_active = False


class YFinanceProvider(BaseDataProvider):
    """Provedor de dados utilizando a biblioteca yfinance."""

    def get_data(self, ticker: str, start_date: str, end_date: str, timeframe: str) -> pd.DataFrame:
        """Busca dados históricos do Yahoo Finance."""
        logger.info(f"Buscando dados de {ticker} do Yahoo Finance ({start_date} a {end_date} @ {timeframe})...")
        try:
            # yfinance geralmente lida bem com strings 'YYYY-MM-DD'
            data = yf.download(ticker, start=start_date, end=end_date, interval=timeframe)
        except Exception as e:
            logger.error(f"Erro ao buscar dados do yfinance para {ticker}: {e}")
            return pd.DataFrame()

        if data.empty:
            logger.warning(f"Nenhum dado retornado do yfinance para {ticker} no período.")
            return pd.DataFrame()

        # Renomeia colunas para o padrão OHLCV (minúsculo)
        data.rename(columns={
            'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
        }, inplace=True)
        
        # Ajusta o nome da coluna de data/hora se necessário e define como índice
        if 'Datetime' in data.columns: # Para alguns intervalos intraday
             data.index = pd.to_datetime(data['Datetime'])
             data = data.drop(columns=['Datetime'])
        elif 'Date' in data.columns: # Para intervalos diários
             data.index = pd.to_datetime(data['Date'])
             data = data.drop(columns=['Date'])
        # Se o índice já for DatetimeIndex, não faz nada

        # Garante que o índice tem timezone (yfinance pode retornar com ou sem)
        if data.index.tz is None:
             # Assume UTC ou timezone local? Depende da fonte do YFinance.
             # Para B3, geralmente é America/Sao_Paulo. Para US, America/New_York.
             # É mais seguro converter para o timezone desejado explicitamente.
             try:
                 # Tenta localizar como timezone de SP (para B3)
                 data = data.tz_localize('America/Sao_Paulo', ambiguous='infer')
             except pytz.exceptions.AmbiguousTimeError:
                 logger.warning(f"Tempo ambíguo encontrado para {ticker} no yfinance. Usando 'infer'.")
                 data = data.tz_localize('America/Sao_Paulo', ambiguous='infer')
             except Exception: # Fallback mais genérico
                  try:
                     # Tenta localizar como UTC
                     data = data.tz_localize('UTC', ambiguous='infer')
                  except Exception as e_tz:
                      logger.error(f"Falha ao localizar timezone para dados yfinance de {ticker}: {e_tz}")
                      # Retorna sem timezone ou falha? Por ora, retorna sem.
        
        # Converte para o timezone desejado, se já tiver um timezone
        if data.index.tz is not None:
             data = data.tz_convert(desired_timezone)


        # Seleciona apenas as colunas desejadas (remove 'Adj Close')
        data = data[['open', 'high', 'low', 'close', 'volume']]

        return data

    def get_latest_candles(self, ticker: str, timeframe: str, count: int) -> pd.DataFrame:
        """
        Busca os candles mais recentes do Yahoo Finance.
        Nota: yfinance pode ter limitações para buscar por 'count'. Usamos período.
        """
        # Estima um período para buscar baseado no timeframe e count
        # Ex: Se timeframe='1h' e count=10, busca '1d' ou '2d' de dados
        # A lógica exata pode precisar de ajuste
        period_map = {'m': '7d', 'h': '60d', 'd': '1y', 'wk': '5y', 'mo': 'max'}
        tf_unit = timeframe[-1].lower() if timeframe else 'd'
        period = period_map.get(tf_unit, '1mo') # Default 1 mês

        logger.info(f"Buscando dados recentes de {ticker} do Yahoo Finance (período {period} @ {timeframe})...")
        try:
             # Busca um período e pega os últimos 'count'
             data = yf.download(ticker, period=period, interval=timeframe)
             if data.empty: return pd.DataFrame()

             # Pega os últimos 'count' registros
             data = data.tail(count)

        except Exception as e:
            logger.error(f"Erro ao buscar dados recentes do yfinance para {ticker}: {e}")
            return pd.DataFrame()

        # Renomeia e ajusta índice/timezone como em get_data
        data.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
        if 'Datetime' in data.columns: data.index = pd.to_datetime(data['Datetime']); data = data.drop(columns=['Datetime'])
        elif 'Date' in data.columns: data.index = pd.to_datetime(data['Date']); data = data.drop(columns=['Date'])
        
        if data.index.tz is None:
             try: data = data.tz_localize('America/Sao_Paulo', ambiguous='infer')
             except Exception:
                  try: data = data.tz_localize('UTC', ambiguous='infer')
                  except Exception: logger.warning(f"Não foi possível localizar timezone para {ticker} (latest).")

        if data.index.tz is not None: data = data.tz_convert(desired_timezone)
            
        return data[['open', 'high', 'low', 'close', 'volume']]


# --- Função Factory --- ADDED BACK ---

def get_provider_instance(provider_name: str) -> BaseDataProvider:
    """
    Factory function para obter uma instância de um provedor de dados.

    Args:
        provider_name (str): O nome do provedor ('MetaTrader5' ou 'YFinance').

    Returns:
        BaseDataProvider: Uma instância do provedor de dados solicitado.

    Raises:
        ValueError: Se o nome do provedor for desconhecido.
    """
    if provider_name.lower() == 'metatrader5':
        return MetaTraderProvider()
    elif provider_name.lower() == 'yfinance':
        return YFinanceProvider()
    else:
        # Loga o erro antes de levantar a exceção
        logger.error(f"Tentativa de usar um provedor de dados desconhecido: {provider_name}")
        raise ValueError(f"Provedor de dados desconhecido: {provider_name}")