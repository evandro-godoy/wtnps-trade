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
        # Resolve caminhos relativos em relação à raiz do projeto (…/wtnps-trade)
        project_root = Path(__file__).resolve().parents[2]
        cfg_path = Path(config_path)
        if not cfg_path.is_absolute():
            cfg_path = (project_root / cfg_path).resolve()
        self.config_path = str(cfg_path)

        self.config = self._load_config()
        self.asset_resources = {} # Cache de recursos por ativo (ticker)
        self.data_providers = {} # Cache de instâncias de provedores

        # models_directory pode vir relativo; garante caminho absoluto
        configured_models_dir = self.config.get('global_settings', {}).get('models_directory', 'models')
        models_dir_path = Path(configured_models_dir)
        if not models_dir_path.is_absolute():
            models_dir_path = (project_root / models_dir_path).resolve()
        self.models_dir = models_dir_path
        logger.info(f"Models dir resolvido para: {self.models_dir}")
        self.setup_analyzer = SetupAnalyzer()

        # Rastreamento de posições para estratégias DRL (stateful)
        self.asset_positions = {}  # {asset_symbol: posição_atual} onde 0=Venda, 1=Hold, 2=Compra

        # Timezone padrão: UTC (removido suporte a timezone local)
        self.local_tz = pytz.utc
        self.local_tz_str = 'UTC'
        logger.info(f"Timezone padrão definido para {self.local_tz_str}.")

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

    def _load_asset_resources(self, asset_symbol: str, strategy_name: str = None):
        """
        Carrega os recursos (modelo, estratégia, config) para um ativo e estratégia específica.
        
        Args:
            asset_symbol: Ticker do ativo (ex: 'WDO$')
            strategy_name: Nome da estratégia (ex: 'LSTMStrategy', 'DRLStrategy').
                          Se None, usa a primeira estratégia da lista.
        
        Returns:
            Dict com recursos carregados ou None em caso de erro
        """
        # Cria chave de cache combinando ticker e estratégia
        cache_key = (asset_symbol, strategy_name) if strategy_name else asset_symbol
        
        # Verifica cache primeiro
        if cache_key in self.asset_resources:
             # Retorna mesmo se for erro cacheado, para evitar recarregar
             return self.asset_resources[cache_key]

        # Busca configuração do ativo
        asset_config = None
        assets_list = self.config.get('assets', [])
        for cfg in assets_list:
             if cfg.get('ticker') == asset_symbol:
                  asset_config = cfg
                  break

        if not asset_config:
            error_msg = f"Configuração não encontrada para '{asset_symbol}' na lista 'assets'."
            logger.error(error_msg)
            self.asset_resources[cache_key] = {'error': error_msg}
            return None

        # Verifica se o ativo está habilitado
        if not asset_config.get('enabled', True):
             error_msg = f"Ativo '{asset_symbol}' está desabilitado no config.yaml."
             logger.warning(error_msg)
             self.asset_resources[cache_key] = {'error': error_msg, 'disabled': True}
             return None

        # Busca lista de estratégias
        strategies_list = asset_config.get('strategies', [])
        
        if not strategies_list:
            error_msg = f"Nenhuma estratégia configurada para '{asset_symbol}'."
            logger.error(error_msg)
            self.asset_resources[cache_key] = {'error': error_msg}
            return None

        # Seleciona estratégia específica ou primeira da lista
        strategy_config = None
        if strategy_name:
            # Busca estratégia pelo nome
            for strat in strategies_list:
                if strat.get('name') == strategy_name:
                    strategy_config = strat
                    break
            if not strategy_config:
                error_msg = f"Estratégia '{strategy_name}' não encontrada para '{asset_symbol}'. Disponíveis: {[s.get('name') for s in strategies_list]}"
                logger.error(error_msg)
                self.asset_resources[cache_key] = {'error': error_msg}
                return None
        else:
            # Usa primeira estratégia
            strategy_config = strategies_list[0]
            strategy_name = strategy_config.get('name')
            logger.info(f"Nenhuma estratégia especificada. Usando primeira: {strategy_name}")

        # Extrai informações da estratégia
        strategy_module_name = strategy_config.get('module')
        strategy_class_name = strategy_config.get('name')

        if not strategy_module_name or not strategy_class_name:
            error_msg = f"Configuração de estratégia incompleta para {asset_symbol}/{strategy_name}."
            logger.error(error_msg)
            self.asset_resources[cache_key] = {'error': error_msg}
            return None

        try:
            # Importa e instancia a estratégia
            strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
            StrategyClass = getattr(strategy_module, strategy_class_name)
            strategy_instance: BaseStrategy = StrategyClass(**strategy_config.get('strategy_params', {}))

            # Define prefixo do modelo: ticker_strategy_prod
            # Ex: WDO$_LSTMStrategy_prod ou WDO$_DRLStrategy_prod
            model_path_prefix = str(self.models_dir / f"{asset_symbol}_{strategy_class_name}_prod")
            logger.info(f"Carregando modelo {asset_symbol}/{strategy_class_name} (prefixo: {model_path_prefix})")

            model = StrategyClass.load(model_path_prefix)
            logger.info(f"Modelo {asset_symbol}/{strategy_class_name} carregado.")

            # Monta dict de recursos
            resources = {
                'strategy_instance': strategy_instance,
                'strategy_class': StrategyClass,
                'strategy_name': strategy_class_name,
                'model': model,
                'asset_config': asset_config,  # Config completo do ativo
                'strategy_config': strategy_config,  # Config específico da estratégia
                'live_config': asset_config.get('live_trading', {}),
                'trading_rules': asset_config.get('trading_rules', {}),
                'price_precision': asset_config.get('price_precision', 2)
            }
            
            self.asset_resources[cache_key] = resources
            logger.info(f"Recursos para {asset_symbol}/{strategy_class_name} carregados com sucesso.")
            return resources

        except FileNotFoundError:
             error_msg = f"Modelo/Scaler não encontrado para {asset_symbol}/{strategy_name} (prefixo: {model_path_prefix}). Treino executado?"
             logger.error(error_msg)
             self.asset_resources[cache_key] = {'error': error_msg}
             return None
        except (ImportError, AttributeError, TypeError) as e:
             error_msg = f"Erro ao importar/instanciar estratégia/modelo para {asset_symbol}/{strategy_name}: {e}"
             logger.error(error_msg, exc_info=True)
             self.asset_resources[cache_key] = {'error': error_msg}
             return None
        except Exception as e:
            error_msg = f"Erro CRÍTICO ao carregar recursos {asset_symbol}/{strategy_name}: {e}"
            logger.exception(error_msg)
            self.asset_resources[cache_key] = {'error': error_msg}
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
                 ticker=ticker, 
                 start_date=start_date_str, 
                 end_date=end_date_str,
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

    def run_simulation_cycle(self, asset_symbol: str, timeframe_str: str, target_datetime_local: datetime, strategy_name: str = None) -> dict:
        """
        Executa um ciclo de simulação para um ativo em um datetime em UTC.
        
        Args:
            asset_symbol: Ticker do ativo (ex: 'WDO$')
            timeframe_str: String do timeframe (ex: 'D1', 'M5')
            target_datetime_local: Datetime para simulação (naive=UTC ou aware)
            strategy_name: Nome da estratégia (ex: 'LSTMStrategy', 'DRLStrategy').
                          Se None, usa a primeira estratégia configurada.
        
        Returns:
            Dict com resultados da simulação ou {'error': msg} em caso de erro
        
        Observação: para compatibilidade, o parâmetro aceita datetime naive ou aware.
        - Se for naive, será interpretado como UTC.
        - Se for aware, será convertido para UTC.
        """
        # Normaliza input para UTC
        if isinstance(target_datetime_local, datetime):
            if target_datetime_local.tzinfo is None:
                target_datetime_utc = pytz.utc.localize(target_datetime_local)
            else:
                target_datetime_utc = target_datetime_local.astimezone(pytz.utc)
        else:
            raise TypeError("target_datetime_local deve ser um datetime")

        strategy_label = f"/{strategy_name}" if strategy_name else ""
        logger.info(f"Iniciando ciclo simulação: {asset_symbol}{strategy_label} @ {timeframe_str} em {target_datetime_utc.strftime('%Y-%m-%d %H:%M %Z')}")

        # 1. Carregar Recursos
        resources = self._load_asset_resources(asset_symbol, strategy_name)
        # Verifica se houve erro ou se está desabilitado
        if not resources or 'error' in resources:
            error_msg = resources.get('error', f'Falha ao carregar {asset_symbol}{strategy_label}') if resources else f'Falha ao carregar {asset_symbol}{strategy_label}'
            logger.error(f"Simulação cancelada para {asset_symbol}{strategy_label}: {error_msg}")
            return {"error": error_msg}

        # Desempacota recursos
        model = resources['model'] 
        strategy_instance: BaseStrategy = resources['strategy_instance']
        asset_config = resources['asset_config']  # Config completo do ativo
        strategy_config = resources['strategy_config']  # Config da estratégia
        price_precision = resources.get('price_precision', 2)
        trading_rules = resources.get('trading_rules', {})

        # 2. Obter Dados de Mercado (em UTC)
        required_periods = 600
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

             # Extrai ticker e provider da config da estratégia
             data_ticker = strategy_config.get('data', {}).get('ticker', asset_symbol)
             provider_name = strategy_config.get('provider', 'MetaTrader5')

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
                   last_ts_str = market_data.index[-1].strftime('%Y-%m-%d %H:%M') if not market_data.empty else "Nenhum"
                   error_msg = f"Dados não encontrados p/ {data_ticker} @ {timeframe_str} em {target_datetime_utc:%Y-%m-%d %H:%M %Z}. Último: {last_ts_str}"
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
                 return {"error": f"Timestamp alvo {target_datetime_utc:%H:%M} perdido pós-features."}

            current_features_row = data_with_features.loc[[target_ts_utc]]
            lookback = getattr(model, 'lookback', 1)
            target_loc = data_with_features.index.get_loc(target_ts_utc)
            start_loc = max(0, target_loc - lookback + 1)

            if target_loc - start_loc + 1 < lookback:
                 logger.warning(f"Insuficiente pós-features ({target_loc - start_loc + 1}<{lookback}) p/ {asset_symbol} @ {target_datetime_utc}.")
                 return {"error": "Insuficiente pós-features para lookback."}

            model_input_data = data_with_features.iloc[start_loc : target_loc + 1]
            feature_names = strategy_instance.get_feature_names()
            X_predict = model_input_data[feature_names]

            if X_predict.isnull().values.any():
                logger.warning(f"NaNs input modelo {asset_symbol} @ {target_datetime_utc}.")
                return {"error": "NaNs input modelo."}

        except KeyError as e:
             logger.error(f"Erro chave acesso índice {target_ts_utc} ou feature: {e}")
             return {"error": f"Timestamp/feature não encontrada pós-features."}
        except Exception as e:
            logger.exception(f"Erro cálculo features/preparação {asset_symbol}: {e}")
            return {"error": "Erro cálculo features/preparação."}

        # 4. Obter Sinal da IA
        try:
            # --- Inicializa posição para DRL se necessário ---
            if asset_symbol not in self.asset_positions:
                self.asset_positions[asset_symbol] = 1  # Inicia em HOLD (1)
            
            current_position = self.asset_positions[asset_symbol]
            
            # --- Verifica se é DRLStrategy (requer lógica especial) ---
            strategy_class_name = strategy_instance.__class__.__name__
            
            if strategy_class_name == 'DRLStrategy':
                # DRL: Constrói estado completo (market_features + position_feature)
                logger.debug(f"DRL inference para {asset_symbol} @ posição={current_position}")
                
                # Market features: última linha de X_predict
                market_features = X_predict.iloc[-1].values  # Shape: (num_market_features,)
                
                # Position feature: one-hot encoding [venda, hold, compra]
                position_feature = np.zeros(3, dtype=np.float32)
                position_feature[current_position] = 1.0
                
                # Estado completo
                state_vector = np.concatenate([market_features, position_feature]).reshape(1, -1)
                
                # Predição: Q-values para cada ação
                q_values = model.predict(state_vector)[0]  # Shape: (3,)
                
                # Escolhe ação com maior Q-value
                action = int(np.argmax(q_values))  # 0, 1, ou 2
                
                # Atualiza posição rastreada
                self.asset_positions[asset_symbol] = action
                
                # Mapeia ação para sinal
                action_to_signal = {0: "VENDA", 1: "HOLD", 2: "COMPRA"}
                ai_signal = action_to_signal[action]
                ai_signal_code = action
                
                logger.info(f"DRL {asset_symbol}: Q={q_values}, Ação={action} ({ai_signal})")
            
            else:
                # Estratégias tradicionais (LSTM, RF, etc.)
                raw_prediction = model.predict(X_predict)
                # A predição relevante é a última (índice -1)
                ai_signal_code = int(raw_prediction[-1]) if isinstance(raw_prediction, np.ndarray) and len(raw_prediction) > 0 else int(raw_prediction) if isinstance(raw_prediction, (int, np.integer)) else 0
                # Mapeamento: 1=COMPRA, outro=VENDA (ajuste se necessário)
                ai_signal = "COMPRA" if ai_signal_code == 1 else "VENDA"
                
                # Atualiza posição rastreada para estratégias tradicionais também
                # (para consistência, embora não seja stateful)
                self.asset_positions[asset_symbol] = 2 if ai_signal == "COMPRA" else 0
                
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
            if sl_pct is not None:
                stop_loss_price = round(
                    current_price * (1 - sl_pct / 100) if final_signal == "COMPRA" else current_price * (1 + sl_pct / 100),
                    price_precision,
                )
            if tp_pct is not None:
                take_profit_price = round(
                    current_price * (1 + tp_pct / 100) if final_signal == "COMPRA" else current_price * (1 - tp_pct / 100),
                    price_precision,
                )
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
            "datetime": target_datetime_utc.strftime('%Y-%m-%d %H:%M %Z'), # UTC
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
    # Cria datetime UTC
    sim_dt_utc = pytz.utc.localize(datetime(2025, 9, 25, 10, 0, 0))
    try:
        # Passa o datetime em UTC
        result = engine.run_simulation_cycle(sim_asset, sim_tf, sim_dt_utc)
        import json
        print(json.dumps(result, indent=4, default=str))
    except Exception as e: print(f"Erro simulação: {e}")
    finally: engine.close()