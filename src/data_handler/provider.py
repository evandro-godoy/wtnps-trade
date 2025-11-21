# src/data_handler/provider.py

import MetaTrader5 as mt5
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz # Para lidar com timezones
import logging
from abc import ABC, abstractmethod
from pathlib import Path
import os # Para criar diretório

# Configuração do logging
# CORREÇÃO APLICADA AQUI: 'asctimes' -> 'asctime'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cache directory (adjust path as needed)
CACHE_DIR = Path(__file__).parent.parent.parent / '.cache_data'

# Garante que o diretório de cache exista
os.makedirs(CACHE_DIR, exist_ok=True)
logger.info(f"Diretório de cache de dados inicializado em: {CACHE_DIR.resolve()}")

# Define o timezone desejado (UTC para consistência)
desired_timezone = pytz.UTC

class BaseDataProvider(ABC):
    """Classe base abstrata para provedores de dados."""

    @abstractmethod
    def get_data(self, ticker: str, start_date: str, end_date: str, timeframe) -> pd.DataFrame:
        """Busca dados históricos."""
        pass

    @abstractmethod
    def get_latest_candles(self, ticker: str, timeframe, count: int) -> pd.DataFrame:
        """Busca os 'count' candles mais recentes."""
        pass

    def close_connection(self):
        """Fecha conexões, se aplicável."""
        pass

    def is_connected(self) -> bool:
        """Verifica o status da conexão."""
        return True


class MetaTraderProvider(BaseDataProvider):
    """Provedor de dados utilizando a API do MetaTrader 5."""

    def __init__(self):
        self.connection_active = self._initialize_mt5()
        if not self.connection_active:
             logger.critical("Falha ao inicializar a conexão com o MetaTrader 5.")

    def _initialize_mt5(self) -> bool:
        """Inicializa a conexão com o MetaTrader 5."""
        if mt5.terminal_info() is not None:
             logger.info("Conexão MT5 já ativa.")
             return True
        if not mt5.initialize():
            logger.error(f"Falha na inicialização do MT5, erro code = {mt5.last_error()}")
            return False
        terminal_info = mt5.terminal_info()
        if terminal_info:
             logger.info(f"MetaTrader 5 Conectado: {terminal_info.name}")
             return True
        else:
             logger.error("mt5.initialize() retornou True, mas terminal_info() é None.")
             return False

    def is_connected(self) -> bool:
        """Verifica se a conexão com o MT5 está ativa."""
        return self.connection_active and mt5.terminal_info() is not None


    def _get_mt5_timeframe(self, tf_str: str):
        """Converte string de timeframe para constante MT5."""
        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
        }
        tf_constant = tf_map.get(tf_str.upper(), None)
        if tf_constant is None:
            logger.warning(f"Timeframe '{tf_str}' não mapeado no MT5.")
        return tf_constant

    def _download_rates_in_chunks(self, ticker: str, timeframe: int, start_dt: datetime, end_dt: datetime, chunk_size_days: int = 183) -> pd.DataFrame:
        """
        Baixa dados do MT5 em pedaços (chunks) para evitar limites de API.
        Útil para períodos longos de dados.
        
        Args:
            ticker: Símbolo do ativo
            timeframe: Constante MT5 de timeframe (ex: mt5.TIMEFRAME_M15)
            start_dt: Data/hora de início (datetime com timezone UTC)
            end_dt: Data/hora de fim (datetime com timezone UTC)
            chunk_size_days: Tamanho do chunk em dias (padrão: 365)
            
        Returns:
            DataFrame com dados consolidados
        """
        rates_list = []
        current_start = start_dt.astimezone(pytz.UTC) if start_dt.tzinfo else pytz.UTC.localize(start_dt)
        final_end = end_dt.astimezone(pytz.UTC) if end_dt.tzinfo else pytz.UTC.localize(end_dt)
        final_end = final_end + timedelta(hours=23, minutes=59)
        
        logger.info(f"Iniciando download em chunks de {chunk_size_days} dias para {ticker}...")
        
        chunk_count = 0
        while current_start < final_end:
            current_end = min(current_start + timedelta(days=chunk_size_days), final_end)
            
            logger.debug(f"  Chunk {chunk_count + 1}: Baixando de {current_start.date()} até {current_end.date()}...")
            
            try:
                chunk = mt5.copy_rates_range(ticker, timeframe, current_start, current_end)
                
                if chunk is not None and len(chunk) > 0:
                    rates_list.append(pd.DataFrame(chunk))
                    logger.debug(f"    OK ({len(chunk)} candles)")
                else:
                    logger.debug(f"    Vazio ou sem dados")
            except Exception as e:
                logger.error(f"    Erro ao buscar chunk: {e}")
            
            # Avança para o próximo chunk
            current_start = current_end
            chunk_count += 1
        
        if not rates_list:
            logger.warning(f"Nenhum dado retornado do MT5 em {chunk_count} chunks para {ticker}.")
            return pd.DataFrame()
        
        # Concatena todos os chunks e remove duplicatas
        df_final = pd.concat(rates_list, ignore_index=True)
        
        # Remove duplicatas baseado no timestamp
        if 'time' in df_final.columns:
            df_final = df_final.drop_duplicates(subset='time').reset_index(drop=True)
        
        logger.info(f"Download em chunks concluído: {len(df_final)} candles consolidados de {chunk_count} chunks.")
        return df_final

    def get_data(self, ticker: str, start_date: str, end_date: str, timeframe: int) -> pd.DataFrame:
        """Busca dados históricos do MT5 com cache e tratamento de timezone."""
        if not self.is_connected():
             logger.warning("MT5 não conectado. Tentando reconectar...")
             if not self._initialize_mt5():
                  logger.error("Falha ao reconectar ao MT5.")
                  return pd.DataFrame()

        try:
             start_dt_utc = pytz.utc.localize(datetime.strptime(start_date, '%Y-%m-%d'))
             end_dt_utc = pytz.utc.localize(datetime.strptime(end_date, '%Y-%m-%d'))
        except ValueError:
             try:
                 start_dt_utc = pytz.utc.localize(datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S').replace(hour=0, minute=0, second=0))
                 end_dt_utc = pytz.utc.localize(datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S').replace(hour=23, minute=59, second=59))
             except ValueError:
                  logger.error(f"Formato de data inválido: {start_date} ou {end_date}.")
                  return pd.DataFrame()

        # Encontra a string do timeframe para o nome do cache
        tf_map_rev = {v: k for k, v in mt5.__dict__.items() if k.startswith('TIMEFRAME_')}
        timeframe_str = tf_map_rev.get(timeframe, f'UNKNOWN_{timeframe}').replace('TIMEFRAME_', '')

        cache_filename = f"MT5_{ticker.replace('$','')}_{timeframe_str}_{start_dt_utc.strftime('%Y%m%d')}_{end_dt_utc.strftime('%Y%m%d')}.parquet"
        cache_filepath = CACHE_DIR / cache_filename

        if cache_filepath.exists():
            try:
                logger.info(f"Carregando dados de {ticker} do cache: {cache_filepath}")
                data = pd.read_parquet(cache_filepath)
                if isinstance(data.index, pd.DatetimeIndex):
                     if data.index.tz is None: data = data.tz_localize('UTC')
                     # Mantém em UTC (sem conversão)
                     # data = data.tz_convert(desired_timezone)
                     logger.info(f"Dados carregados do cache ({len(data)} registros).")
                     return data
                else: logger.warning("Cache corrompido.")
            except Exception as e:
                logger.warning(f"Erro ao ler cache {cache_filepath}: {e}. Buscando novamente.")

        logger.info(f"Buscando dados de {ticker} do MT5 ({start_date} a {end_date} @ {timeframe_str})...")
        
        # Usa download em chunks para períodos longos (melhora confiabilidade)
        data = self._download_rates_in_chunks(ticker, timeframe, start_dt_utc, end_dt_utc)
        
        if data.empty:
            logger.warning(f"Nenhum dado retornado do MT5 para {ticker} no período.")
            # Cria cache vazio para evitar buscar novamente
            pd.DataFrame().to_parquet(cache_filepath, index=False)
            return pd.DataFrame()
        # Remove linhas onde todos os valores OHLC são zero ou nulos (dados inválidos)
        data = data[(data[['open', 'high', 'low', 'close']] != 0).any(axis=1)]
        data = data.dropna(subset=['open', 'high', 'low', 'close'], how='all')

        if data.empty:
            logger.warning(f"MT5: Dados históricos para '{ticker}' ({timeframe_str}) estavam vazios ou inválidos após limpeza.")
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
        try:
             logger.info(f"Salvando dados de {ticker} ({len(data)} registros) em cache: {cache_filepath}")
             data.to_parquet(cache_filepath, index=True, compression='snappy')
        except Exception as e:
            logger.error(f"Erro ao salvar dados no cache {cache_filepath}: {e}")

        logger.info(f"Dados buscados do MT5 e convertidos para {desired_timezone}.")
        return data

    def get_latest_candles(self, ticker: str, timeframe: int, count: int) -> pd.DataFrame:
        """Busca os 'count' candles mais recentes do MT5."""
        if not self.is_connected():
             logger.warning("MT5 não conectado ao buscar candles recentes.")
             if not self._initialize_mt5(): return pd.DataFrame()

        try:
            # Posição 1 é o último candle FECHADO (posição 0 está em formação)
            rates = mt5.copy_rates_from_pos(ticker, timeframe, 1, count)
        except Exception as e:
             logger.error(f"Erro ao chamar mt5.copy_rates_from_pos para {ticker}: {e}")
             return pd.DataFrame()

        if rates is None or len(rates) == 0:
            return pd.DataFrame()

        data = pd.DataFrame(rates)
        data['time'] = pd.to_datetime(data['time'], unit='s', utc=True)
        data.set_index('time', inplace=True)
        data.rename(columns={'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'tick_volume': 'volume'}, inplace=True)
        if 'real_volume' in data.columns and 'volume' not in data.columns: data.rename(columns={'real_volume': 'volume'}, inplace=True)
        elif 'real_volume' in data.columns and 'volume' in data.columns: data = data.drop(columns=['real_volume'])

        required_cols = ['open', 'high', 'low', 'close', 'volume']
        data = data[[col for col in required_cols if col in data.columns]]
        if 'volume' not in data.columns: data['volume'] = 0

        # Mantém dados em UTC (sem conversão de timezone)
        # data = data.tz_convert(desired_timezone)
        return data

    def close_connection(self):
        """Fecha a conexão com o MT5."""
        if self.connection_active and mt5.terminal_info() is not None:
            logger.info("Desligando conexão com MetaTrader 5...")
            mt5.shutdown()
            self.connection_active = False

    # --- Métodos específicos do MT5 Provider ---
    def open_position(self, symbol: str, order_type: str, volume: float, sl_price: float = None, tp_price: float = None, deviation: int = 20, magic: int = 12345):
        """Abre uma posição a mercado."""
        if not self.is_connected():
             logger.error("MT5 não conectado. Impossível abrir posição.")
             return None

        order_type_mt5 = mt5.ORDER_TYPE_BUY if order_type.lower() == 'buy' else mt5.ORDER_TYPE_SELL

        price = mt5.symbol_info_tick(symbol).ask if order_type_mt5 == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid
        point = mt5.symbol_info(symbol).point

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type_mt5,
            "price": price,
            "deviation": deviation,
            "magic": magic,
            "comment": "wtnps_trade_bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC, # Ou FOK, dependendo da corretora
        }

        # Adiciona SL e TP se fornecidos e válidos
        if sl_price is not None and sl_price > 0:
             request["sl"] = sl_price
        if tp_price is not None and tp_price > 0:
             request["tp"] = tp_price
             
        # Verifica se SL/TP estão muito próximos (opcional, mas recomendado)
        min_stop_level = mt5.symbol_info(symbol).trade_stops_level * point
        if order_type_mt5 == mt5.ORDER_TYPE_BUY:
            if sl_price is not None and price - sl_price < min_stop_level:
                logger.warning(f"Stop Loss para {symbol} muito próximo ({price - sl_price:.5f} < {min_stop_level:.5f}). SL será ignorado pela corretora.")
                # request.pop("sl") # Remove ou deixa a corretora rejeitar? Deixar pode ser mais informativo.
            if tp_price is not None and tp_price - price < min_stop_level:
                logger.warning(f"Take Profit para {symbol} muito próximo ({tp_price - price:.5f} < {min_stop_level:.5f}). TP será ignorado pela corretora.")
                # request.pop("tp")
        else: # Sell
             if sl_price is not None and sl_price - price < min_stop_level:
                  logger.warning(f"Stop Loss para {symbol} muito próximo ({sl_price - price:.5f} < {min_stop_level:.5f}). SL será ignorado pela corretora.")
                  # request.pop("sl")
             if tp_price is not None and price - tp_price < min_stop_level:
                  logger.warning(f"Take Profit para {symbol} muito próximo ({price - tp_price:.5f} < {min_stop_level:.5f}). TP será ignorado pela corretora.")
                  # request.pop("tp")


        try:
            result = mt5.order_send(request)
            if result is None:
                 logger.error(f"Falha ao enviar ordem para {symbol}. mt5.order_send() retornou None. Erro MT5: {mt5.last_error()}")
                 return None
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Ordem para {symbol} não executada: {result.comment} (RetCode: {result.retcode})")
                return result # Retorna o resultado mesmo com falha
            else:
                 logger.info(f"Ordem para {symbol} executada com sucesso. Ticket: {result.order}, Preço: {result.price}")
                 return result
        except Exception as e:
             logger.error(f"Exceção ao enviar ordem para {symbol}: {e}", exc_info=True)
             return None

    def close_position(self, symbol: str, ticket: int) -> bool:
        """Fecha uma posição específica pelo ticket."""
        if not self.is_connected() or ticket is None:
             logger.error("MT5 não conectado ou ticket inválido para fechar posição.")
             return False

        try:
            # Busca a posição pelo ticket
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.warning(f"Posição com ticket {ticket} não encontrada para fechamento.")
                # Considera como sucesso se a posição já não existe? Sim.
                return True 
            
            position = position[0] # Pega o primeiro (e único) item da tupla
            position_type = position.type
            volume = position.volume
            
            # Determina o tipo de ordem de fechamento
            close_order_type = mt5.ORDER_TYPE_SELL if position_type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            # Pega o preço atual para fechar a mercado
            price = mt5.symbol_info_tick(symbol).ask if close_order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": ticket, # ID da posição a ser fechada
                "symbol": symbol,
                "volume": volume,
                "type": close_order_type,
                "price": price,
                "deviation": 20,
                "magic": position.magic, # Usa o magic number original
                "comment": "wtnps_trade_bot_close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result is None:
                 logger.error(f"Falha ao enviar ordem de fechamento para ticket {ticket}. mt5.order_send() retornou None. Erro MT5: {mt5.last_error()}")
                 return False
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Ordem de fechamento para ticket {ticket} não executada: {result.comment} (RetCode: {result.retcode})")
                return False
            else:
                logger.info(f"Posição {ticket} fechada com sucesso.")
                return True

        except Exception as e:
             logger.error(f"Exceção ao fechar posição ticket {ticket}: {e}", exc_info=True)
             return False


class YFinanceProvider(BaseDataProvider):
    """Provedor de dados utilizando a biblioteca yfinance."""

    def get_data(self, ticker: str, start_date: str, end_date: str, timeframe: str = '1d') -> pd.DataFrame:
        """Busca dados históricos do Yahoo Finance."""
        # Mapeia timeframe string para intervalo yfinance
        # yfinance usa: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        interval = timeframe.lower()
        if interval == 'd1': interval = '1d'
        elif interval == 'h1': interval = '1h'
        # Adicione outros mapeamentos se necessário

        logger.info(f"Buscando dados de {ticker} do Yahoo Finance ({start_date} a {end_date} @ {interval})...")
        cache_filename = f"YF_{ticker}_{interval}_{start_date}_{end_date}.parquet"
        cache_filepath = CACHE_DIR / cache_filename

        if cache_filepath.exists():
            try:
                logger.info(f"Carregando dados de {ticker} do cache YF: {cache_filepath}")
                data = pd.read_parquet(cache_filepath)
                if isinstance(data.index, pd.DatetimeIndex):
                    # Tenta converter para UTC
                    try:
                         if data.index.tz is None: data = data.tz_localize('UTC') # Assume UTC se não tiver
                         # Mantém em UTC (sem conversão)
                         # data = data.tz_convert(desired_timezone)
                         logger.info(f"Dados YF carregados do cache ({len(data)} registros).")
                         return data
                    except Exception as e_tz:
                         logger.warning(f"Erro ao converter timezone do cache YF: {e_tz}. Retornando como está.")
                         return data
                else: logger.warning("Cache YF corrompido.")
            except Exception as e:
                logger.warning(f"Erro ao ler cache YF {cache_filepath}: {e}. Buscando novamente.")

        try:
            data = yf.download(ticker, start=start_date, end=end_date, interval=interval)
        except Exception as e:
            logger.error(f"Erro ao buscar dados do yfinance para {ticker}: {e}")
            return pd.DataFrame()

        if data.empty:
            logger.warning(f"Nenhum dado retornado do yfinance para {ticker} no período.")
            pd.DataFrame().to_parquet(cache_filepath, index=False) # Cache vazio
            return pd.DataFrame()

        data.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
        
        # yfinance pode retornar índice como DatetimeIndex ou não
        if not isinstance(data.index, pd.DatetimeIndex):
            if 'Datetime' in data.columns:
                 data.index = pd.to_datetime(data['Datetime'])
            elif 'Date' in data.columns:
                 data.index = pd.to_datetime(data['Date'])
            # Se não encontrar, pode falhar ou precisar de mais tratamento

        # Timezone Handling (Pode variar com yfinance)
        if data.index.tz is None:
             try: data = data.tz_localize('UTC', ambiguous='infer') # Assume UTC
             except Exception as e_tz: logger.warning(f"Não foi possível localizar timezone YF para {ticker}: {e_tz}")
        
        # Mantém em UTC (sem conversão)
        # if data.index.tz is not None:
        #      try: data = data.tz_convert(desired_timezone)
        #      except Exception as e_tz_conv: logger.warning(f"Erro ao converter timezone YF para {ticker}: {e_tz_conv}")

        data = data[['open', 'high', 'low', 'close', 'volume']]

        try:
             logger.info(f"Salvando dados YF de {ticker} ({len(data)} registros) em cache: {cache_filepath}")
             data.to_parquet(cache_filepath, index=True, compression='snappy')
        except Exception as e:
            logger.error(f"Erro ao salvar dados YF no cache {cache_filepath}: {e}")

        return data

    def get_latest_candles(self, ticker: str, timeframe: str, count: int) -> pd.DataFrame:
        """Busca candles recentes do Yahoo Finance."""
        interval = timeframe.lower()
        if interval == 'd1': interval = '1d'
        elif interval == 'h1': interval = '1h'

        # Determina período baseado no intervalo para buscar dados suficientes
        period = '7d' if 'm' in interval else '60d' if 'h' in interval else '1y'

        logger.info(f"Buscando dados recentes YF de {ticker} (período {period} @ {interval})...")
        try:
             data = yf.download(ticker, period=period, interval=interval)
             if data.empty: return pd.DataFrame()
             data = data.tail(count) # Pega os últimos 'count'
        except Exception as e:
            logger.error(f"Erro ao buscar dados recentes YF para {ticker}: {e}")
            return pd.DataFrame()

        # Renomeia, ajusta índice e timezone
        data.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
        if not isinstance(data.index, pd.DatetimeIndex):
            if 'Datetime' in data.columns: data.index = pd.to_datetime(data['Datetime'])
            elif 'Date' in data.columns: data.index = pd.to_datetime(data['Date'])
        
        if data.index.tz is None:
             try: data = data.tz_localize('UTC', ambiguous='infer')
             except Exception: logger.warning(f"Não localizou timezone YF recente para {ticker}.")

        # Mantém em UTC (sem conversão)
        # if data.index.tz is not None:
        #     try: data = data.tz_convert(desired_timezone)
        #     except Exception: logger.warning(f"Não converteu timezone YF recente para {ticker}.")
            
        return data[['open', 'high', 'low', 'close', 'volume']]

# --- Função Factory ---
def get_provider_instance(provider_name: str) -> BaseDataProvider:
    """Factory para obter instância do provedor de dados."""
    if provider_name.lower() == 'metatrader5':
        return MetaTraderProvider()
    elif provider_name.lower() == 'yfinance':
        return YFinanceProvider()
    else:
        logger.error(f"Provedor de dados desconhecido solicitado: {provider_name}")
        raise ValueError(f"Provedor de dados desconhecido: {provider_name}")