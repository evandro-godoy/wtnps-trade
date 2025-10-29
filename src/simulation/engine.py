# src/simulation/engine.py
import yaml
import logging
from pathlib import Path
import importlib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import MetaTrader5 as mt5 # Para conversão de timeframe
import pytz # Para timezones

# Importações internas do projeto
from src.data_handler.provider import get_provider_instance, BaseDataProvider, MetaTraderProvider
from src.strategies.base import BaseStrategy # Importa a classe base
from src.setups.analyzer import SetupAnalyzer # Mantém para análise de setups

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s') # Adicionado [%(name)s]
logger = logging.getLogger(__name__)

# --- Função auxiliar para conversão de timeframe ---
def _get_mt5_timeframe_from_string(tf_str: str):
    """Converte string de timeframe para constante MT5."""
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
    }
    tf_constant = tf_map.get(tf_str.upper(), None)
    if tf_constant is None:
         # Log apenas uma vez por timeframe inválido para evitar spam
         if not hasattr(_get_mt5_timeframe_from_string, 'logged_warnings'):
              _get_mt5_timeframe_from_string.logged_warnings = set()
         if tf_str not in _get_mt5_timeframe_from_string.logged_warnings:
              logger.warning(f"Timeframe '{tf_str}' não mapeado ou inválido.")
              _get_mt5_timeframe_from_string.logged_warnings.add(tf_str)
    return tf_constant

class SimulationEngine:
    """
    Motor de Simulação para avaliar estratégias de trading ponto a ponto no tempo.
    """
    def __init__(self, config_path: str = 'configs/main.yaml'):
        self.config_path = config_path
        self.config = self._load_config()
        self.asset_resources = {} # Cache de recursos por ativo (ticker)
        self.data_providers = {} # Cache de instâncias de provedores
        self.models_dir = Path(self.config.get('global_settings', {}).get('models_directory', 'models'))
        self.setup_analyzer = SetupAnalyzer()
        try:
            self.local_tz_str = self.config.get('global_settings', {}).get('local_timezone', 'America/Sao_Paulo')
            self.local_tz = pytz.timezone(self.local_tz_str)
            logger.info(f"SimulationEngine usando timezone local: {self.local_tz_str}")
        except pytz.UnknownTimeZoneError:
            logger.warning(f"Timezone '{self.local_tz_str}' não encontrado, usando UTC como local.")
            self.local_tz = pytz.utc
            self.local_tz_str = 'UTC'

    def _load_config(self):
        """Carrega o arquivo de configuração YAML."""
        logger.info(f"Carregando config: {self.config_path}")
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.critical(f"CRÍTICO: Config não encontrado: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.critical(f"CRÍTICO: Erro ao carregar YAML: {e}")
            raise

    def _get_provider(self, provider_name: str) -> BaseDataProvider:
        """Obtém ou cria uma instância do provedor de dados."""
        # Lock não estritamente necessário aqui se a inicialização for single-threaded
        if provider_name not in self.data_providers:
            try:
                self.data_providers[provider_name] = get_provider_instance(provider_name)
                logger.info(f"Provedor '{provider_name}' instanciado (SimulationEngine).")
            except ValueError as e:
                 logger.error(f"Erro obter provedor '{provider_name}': {e}")
                 raise
        return self.data_providers[provider_name]

    def _load_asset_resources(self, asset_symbol: str):
        """
        Carrega os recursos (modelo, estratégia, config) para um ativo.
        Acessa a configuração 'assets' como uma LISTA.
        """
        # Verifica cache primeiro
        if asset_symbol in self.asset_resources:
             # Retorna mesmo se for erro cacheado, para evitar recarregar
             return self.asset_resources[asset_symbol]

        # --- CORREÇÃO AQUI: Itera na lista para encontrar o config ---
        asset_config = None
        assets_list = self.config.get('assets', [])
        for cfg in assets_list:
             # Compara ticker principal do ativo
             if cfg.get('ticker') == asset_symbol:
                  asset_config = cfg
                  break # Encontrou
        # --- FIM DA CORREÇÃO ---

        if not asset_config:
            error_msg = f"Configuração não encontrada para '{asset_symbol}' na lista 'assets'."
            logger.error(error_msg)
            self.asset_resources[asset_symbol] = {'error': error_msg} # Cacheia o erro
            return None # Retorna None para indicar falha

        # Verifica se o ativo está habilitado no config (geral, não só live)
        if not asset_config.get('enabled', True):
             error_msg = f"Ativo '{asset_symbol}' está desabilitado no config.yaml."
             logger.warning(error_msg)
             # Não é um erro crítico, mas não deve ser usado
             self.asset_resources[asset_symbol] = {'error': error_msg, 'disabled': True}
             return None # Indica que não deve ser usado

        # Procede com o carregamento...
        strategy_module_name = asset_config.get('strategy_module')
        strategy_class_name = asset_config.get('strategy_name')

        if not strategy_module_name or not strategy_class_name:
            error_msg = f"Configuração de estratégia incompleta para {asset_symbol}."
            logger.error(error_msg)
            self.asset_resources[asset_symbol] = {'error': error_msg}
            return None

        try:
            strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
            StrategyClass = getattr(strategy_module, strategy_class_name)
            strategy_instance: BaseStrategy = StrategyClass(**asset_config.get('strategy_params', {}))

            model_path_prefix = str(self.models_dir / f"{asset_symbol}_prod")
            logger.info(f"Carregando modelo {asset_symbol} via {strategy_class_name}.load() (prefixo: {model_path_prefix})")

            model = StrategyClass.load(model_path_prefix)
            logger.info(f"Modelo {asset_symbol} carregado.")

            resources = { # Guarda tudo que pode ser útil depois
                'strategy_instance': strategy_instance, 'strategy_class': StrategyClass,
                'model': model, 'config': asset_config,
                'live_config': asset_config.get('live_trading', {}),
                'trading_rules': asset_config.get('trading_rules', {}),
                'price_precision': asset_config.get('price_precision', 2)
            }
            self.asset_resources[asset_symbol] = resources # Cacheia sucesso
            logger.info(f"Recursos para {asset_symbol} carregados com sucesso.")
            return resources

        except FileNotFoundError:
             error_msg = f"Modelo/Scaler não encontrado para {asset_symbol} (prefixo: {model_path_prefix}). Treino executado?"
             logger.error(error_msg)
             self.asset_resources[asset_symbol] = {'error': error_msg}
             return None
        except (ImportError, AttributeError, TypeError) as e:
             error_msg = f"Erro ao importar/instanciar estratégia/modelo para {asset_symbol}: {e}"
             logger.error(error_msg, exc_info=True)
             self.asset_resources[asset_symbol] = {'error': error_msg}
             return None
        except Exception as e: # Captura outras exceções de StrategyClass.load()
            error_msg = f"Erro CRÍTICO ao carregar recursos {asset_symbol}: {e}"
            logger.exception(error_msg) # Log com traceback
            self.asset_resources[asset_symbol] = {'error': error_msg}
            return None


    def _get_market_data(self, ticker: str, start_dt_utc: datetime, end_dt_utc: datetime, timeframe_str: str, provider_name: str) -> pd.DataFrame:
        """Busca dados de mercado (espera e retorna dados em UTC)."""
        try:
            provider = self._get_provider(provider_name)
        except ValueError:
            return pd.DataFrame()

        tf_param = timeframe_str # Default para YFinance
        if provider_name == 'MetaTrader5':
            timeframe_obj = _get_mt5_timeframe_from_string(timeframe_str)
            if timeframe_obj is None:
                logger.error(f"Timeframe '{timeframe_str}' inválido para MT5.")
                return pd.DataFrame()
            tf_param = timeframe_obj

        try:
             # Provider espera strings YYYY-MM-DD HH:MM:SS (sem timezone)
             start_date_str = start_dt_utc.strftime('%Y-%m-%d %H:%M:%S')
             end_date_str = end_dt_utc.strftime('%Y-%m-%d %H:%M:%S')

             logger.debug(f"Buscando dados: {ticker} UTC[{start_date_str} a {end_date_str}] @ {timeframe_str} via {provider_name}")

             data = provider.get_data(
                 ticker=ticker, start_date=start_date_str, end_date=end_date_str,
                 timeframe=tf_param
             )

             if data.empty:
                  # logger.warning(f"Nenhum dado retornado: {ticker} ({start_date_str} - {end_date_str} @ {timeframe_str})")
                  return pd.DataFrame() # Retorna vazio, não null

             # logger.debug(f"Dados recebidos ({len(data)} candles) para {ticker}. Verificando índice e timezone...")

             # Garante índice DatetimeIndex e timezone UTC
             if not isinstance(data.index, pd.DatetimeIndex):
                  data.index = pd.to_datetime(data.index)
             if data.index.tz is None: # Se o provider retornou naive
                  logger.warning(f"Provider {provider_name} retornou dados sem timezone para {ticker}. Assumindo UTC.")
                  data = data.tz_localize(pytz.utc)
             else: # Se retornou com timezone, converte para UTC
                  data = data.tz_convert(pytz.utc)

             data.sort_index(inplace=True)
             #logger.debug(f"Dados para {ticker} processados. Índice UTC: {data.index.tz}")
             return data

        except Exception as e:
            logger.error(f"Erro ao buscar/processar dados para {ticker}: {e}", exc_info=False)
            return pd.DataFrame()

    def run_simulation_cycle(self, asset_symbol: str, timeframe_str: str, target_datetime_local: datetime) -> dict:
        """
        Executa um ciclo de simulação para um ativo e datetime LOCAL específico.
        """
        # Garante target_datetime_local aware no timezone correto
        try:
             if target_datetime_local.tzinfo is None:
                  target_datetime_local = self.local_tz.localize(target_datetime_local)
             else:
                  target_datetime_local = target_datetime_local.astimezone(self.local_tz)
        except (pytz.exceptions.NonExistentTimeError, pytz.exceptions.AmbiguousTimeError) as e_tz:
             error_msg = f"Erro de fuso horário para {target_datetime_local}: {e}. Verifique horário de verão."
             logger.error(error_msg)
             return {"error": error_msg}

        target_datetime_utc = target_datetime_local.astimezone(pytz.utc) # Converte para UTC

        logger.info(f"Iniciando ciclo simulação: {asset_symbol} @ {timeframe_str} em {target_datetime_local.strftime('%Y-%m-%d %H:%M:%S %Z')} (UTC: {target_datetime_utc.strftime('%H:%M:%S %Z')})")

        # 1. Carregar Recursos
        resources = self._load_asset_resources(asset_symbol)
        # Verifica se houve erro ou se está desabilitado
        if not resources or 'error' in resources:
            error_msg = resources.get('error', f'Falha ao carregar {asset_symbol}') if resources else f'Falha ao carregar {asset_symbol}'
            logger.error(f"Simulação cancelada para {asset_symbol}: {error_msg}")
            return {"error": error_msg}

        # Desempacota recursos
        model = resources['model']; strategy_instance: BaseStrategy = resources['strategy_instance']
        asset_config = resources['config']; price_precision = resources.get('price_precision', 2)
        trading_rules = resources.get('trading_rules', {})

        # 2. Obter Dados de Mercado (em UTC)
        required_periods = 500
        try:
             # Calcula período necessário para buscar dados
             tf_num = 1; time_unit = 'minutes' # Default M1
             try:
                 tf_prefix = timeframe_str[0].upper()
                 tf_num = int(timeframe_str[1:]) if len(timeframe_str) > 1 else 1
                 if tf_prefix == 'M': time_unit = 'minutes'
                 elif tf_prefix == 'H': time_unit = 'hours'
                 elif tf_prefix == 'D': time_unit = 'days'; tf_num = 1 # days já é multiplicado por periods
                 elif tf_prefix == 'W': time_unit = 'weeks'; tf_num = 1
                 elif tf_prefix == 'MN': time_unit = 'days'; tf_num = 30 # Aproximação
             except (IndexError, ValueError): pass # Usa default
             delta_args = {time_unit: required_periods * tf_num}
             time_delta = pd.Timedelta(**delta_args)

             start_dt_utc = target_datetime_utc - time_delta * 1.5 # Busca ~50% a mais
             end_dt_utc = target_datetime_utc # Busca até o alvo

             data_ticker = asset_config['data'].get('ticker', asset_symbol)
             provider_name = asset_config.get('provider', 'MetaTrader5')

             # Busca dados (retorna df com índice UTC)
             market_data = self._get_market_data(data_ticker, start_dt_utc, end_dt_utc, timeframe_str, provider_name)

             target_ts_utc = pd.Timestamp(target_datetime_utc) # Timestamp UTC

             # Se vazio ou não encontrou exato, tenta buscar um pouco mais
             if market_data.empty or target_ts_utc not in market_data.index:
                  logger.warning(f"Timestamp {target_ts_utc} não encontrado. Buscando adiante...")
                  fwd_delta_args = {time_unit: tf_num * 2} # Ex: busca 2 períodos a mais
                  end_dt_extended_utc = target_datetime_utc + pd.Timedelta(**fwd_delta_args)
                  market_data = self._get_market_data(data_ticker, start_dt_utc, end_dt_extended_utc, timeframe_str, provider_name)
                  # Filtra novamente até o target
                  market_data = market_data[market_data.index <= target_ts_utc]

             if market_data.empty or target_ts_utc not in market_data.index:
                   last_ts_str = market_data.index[-1].strftime('%Y-%m-%d %H:%M:%S %Z') if not market_data.empty else "Nenhum"
                   error_msg = f"Dados não encontrados p/ {data_ticker} @ {timeframe_str} em {target_datetime_local:%Y-%m-%d %H:%M %Z}. Último: {last_ts_str}"
                   logger.error(error_msg)
                   return {"error": error_msg}

        except Exception as e:
            logger.exception(f"Erro obter/processar dados mercado {asset_symbol}: {e}")
            return {"error": "Erro busca/processamento dados."}

        # 3. Calcular Features
        try:
            data_with_features = strategy_instance.define_features(market_data)
            target_ts_utc = pd.Timestamp(target_datetime_utc) # Reafirma UTC

            if target_ts_utc not in data_with_features.index:
                 logger.error(f"Timestamp {target_ts_utc} perdido pós-features {asset_symbol}.")
                 return {"error": f"Timestamp alvo {target_datetime_local:%H:%M} perdido pós-features."}

            current_features_row = data_with_features.loc[[target_ts_utc]]
            lookback = getattr(model, 'lookback', 1)
            target_loc = data_with_features.index.get_loc(target_ts_utc)
            start_loc = max(0, target_loc - lookback + 1)

            if target_loc - start_loc + 1 < lookback:
                 logger.warning(f"Insuficiente pós-features ({target_loc - start_loc + 1}<{lookback}) p/ {asset_symbol} @ {target_datetime_local}.")
                 return {"error": "Insuficiente pós-features para lookback."}

            model_input_data = data_with_features.iloc[start_loc : target_loc + 1]
            feature_names = strategy_instance.get_feature_names()
            X_predict = model_input_data[feature_names]

            if X_predict.isnull().values.any():
                logger.warning(f"NaNs input modelo {asset_symbol} @ {target_datetime_local}.")
                return {"error": "NaNs input modelo."}

        except KeyError as e:
             logger.error(f"Erro chave acesso índice {target_ts_utc} ou feature: {e}")
             return {"error": f"Timestamp/feature não encontrada pós-features."}
        except Exception as e:
            logger.exception(f"Erro cálculo features/preparação {asset_symbol}: {e}")
            return {"error": "Erro cálculo features/preparação."}

        # 4. Obter Sinal da IA
        try:
            raw_prediction = model.predict(X_predict)
            # A predição relevante é a última (índice -1)
            ai_signal_code = int(raw_prediction[-1]) if isinstance(raw_prediction, np.ndarray) and len(raw_prediction) > 0 else int(raw_prediction) if isinstance(raw_prediction, (int, np.integer)) else 0
            # Mapeamento: 1=COMPRA, outro=VENDA (ajuste se necessário)
            ai_signal = "COMPRA" if ai_signal_code == 1 else "VENDA"
            logger.info(f"Sinal IA {asset_symbol}: {ai_signal} ({ai_signal_code})")
        except Exception as e:
            logger.exception(f"Erro predição modelo {asset_symbol}: {e}")
            ai_signal = "ERRO_IA"; ai_signal_code = -1

        # 5. Avaliar Setups
        setup_rules = asset_config.get('setup', [])
        setup_result = {"is_valid": True, "details": {}, "final_decision": ai_signal}
        if setup_rules:
            try:
                # Passa a linha atual (já selecionada)
                setup_result = self.setup_analyzer.evaluate_setups(current_features_row, setup_rules, ai_signal)
                logger.info(f"Setup {asset_symbol}: Valido={setup_result['is_valid']}, Decisao={setup_result['final_decision']}")
            except Exception as e:
                logger.exception(f"Erro avaliar setups {asset_symbol}: {e}")
                setup_result = {"is_valid": False, "details": {"erro": str(e)}, "final_decision": "HOLD"}

        # 6. Calcular Stops
        stop_loss_price, take_profit_price = None, None
        current_price = current_features_row['close'].iloc[0] # Preço de fechamento do candle atual
        final_signal = setup_result["final_decision"]

        if final_signal in ["COMPRA", "VENDA"]:
            sl_pct = trading_rules.get('stop_loss_pct')
            tp_pct = trading_rules.get('take_profit_pct')
            if sl_pct is not None: sl_price = round(current_price * (1 - sl_pct / 100) if final_signal == "COMPRA" else current_price * (1 + sl_pct / 100), price_precision)
            if tp_pct is not None: tp_price = round(current_price * (1 + tp_pct / 100) if final_signal == "COMPRA" else current_price * (1 - tp_pct / 100), price_precision)
            # logger.info(f"Preços Calc: Entrada~={current_price:.{price_precision}f}, SL={sl_price}, TP={tp_price}")

        # 7. Montar Resultado
        indicators_dict = {}
        try:
             indicators_series = current_features_row.iloc[0].round(5)
             indicators_dict = { k: (f"{v:.5f}" if isinstance(v, (float, np.floating)) and pd.notna(v) and np.isfinite(v) else str(v) if pd.notna(v) and np.isfinite(v) else "N/A")
                                 for k, v in indicators_series.items()
                                 if k in strategy_instance.get_feature_names() or k in ['open','high','low','close','volume'] }
        except Exception as e: logger.warning(f"Erro extrair indicadores: {e}"); indicators_dict = {"erro": "Falha"}

        result = {
            "asset": asset_symbol,
            "datetime": target_datetime_local.strftime('%Y-%m-%d %H:%M:%S %Z'), # Hora local
            "timeframe": timeframe_str,
            "current_price": round(current_price, price_precision),
            "ai_signal": ai_signal, "ai_signal_code": ai_signal_code,
            "setup_is_valid": setup_result["is_valid"],
            "setup_details": setup_result.get("details", {}),
            "final_signal": final_signal,
            "stop_loss": stop_loss_price if stop_loss_price is not None else "N/A",
            "take_profit": take_profit_price if take_profit_price is not None else "N/A",
            "indicators": indicators_dict
        }
        return result

    def close(self):
        """Fecha conexões dos provedores."""
        logger.info("Encerrando conexões providers (SimulationEngine)...")
        # Copia as chaves para evitar erro de iteração se dict mudar
        provider_names = list(self.data_providers.keys())
        for provider_name in provider_names:
             provider_instance = self.data_providers.pop(provider_name, None) # Remove do dict
             if provider_instance and hasattr(provider_instance, 'close_connection'):
                 try:
                     provider_instance.close_connection()
                     logger.info(f"Conexão SimulationEngine {provider_name} fechada.")
                 except Exception as e: logger.warning(f"Erro fechar {provider_name}: {e}")
        self.data_providers = {} # Garante limpeza

# Exemplo de uso
if __name__ == '__main__':
    engine = SimulationEngine(config_path='configs/main.yaml')
    sim_asset = 'WDO$'
    sim_tf = 'H1'
    # Cria datetime LOCAL (naive)
    sim_dt_local_naive = datetime(2025, 9, 25, 10, 0, 0)
    try:
        # Passa o datetime local (naive ou aware)
        result = engine.run_simulation_cycle(sim_asset, sim_tf, sim_dt_local_naive)
        import json
        print(json.dumps(result, indent=4, default=str))
    except Exception as e: print(f"Erro simulação: {e}")
    finally: engine.close()