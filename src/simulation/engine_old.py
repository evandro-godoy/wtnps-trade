import sys
import yaml
import logging
from pathlib import Path
import importlib
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone, timedelta
import pytz
import numpy as np

# Adiciona a raiz do projeto ao path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data_handler.provider import MetaTraderProvider, YFinanceProvider
from src.strategies.lstm import KerasLSTMWrapper
from src.setups.analyzer import evaluate_setups

# Configuração do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s")
log = logging.getLogger(__name__) # Logger específico para o engine

class SimulationEngine:
    """
    Motor unificado para carregar recursos, gerar sinais de IA,
    avaliar setups e fornecer sugestões detalhadas de operação para simulações.
    """
    def __init__(self, config_path="configs/main.yaml"):
        self.config_path = project_root / config_path
        self.config = self._load_config()
        self.assets_config = [
            asset for asset in self.config["assets"] if asset.get("enabled", False)
        ]
        # Garante que model_directory seja um objeto Path
        self.models_dir = Path(self.config["global_settings"]["model_directory"])
        self.asset_states = {}

        self.mt5_provider = MetaTraderProvider()
        self.yf_provider = YFinanceProvider()

        self._initialize_mt5() # Tenta conectar na inicialização

    def _load_config(self):
        """Carrega o arquivo de configuração YAML."""
        log.info(f"Carregando configuração de: {self.config_path}")
        try:
            with open(self.config_path, "r") as file:
                return yaml.safe_load(file)
        except Exception as e:
            log.critical(f"Erro crítico ao carregar configuração: {e}", exc_info=True)
            raise

    def _initialize_mt5(self):
        """Inicializa a conexão com o MetaTrader 5, se ainda não estiver conectado."""
        if not mt5.terminal_info():
            log.info("Tentando inicializar conexão com o MetaTrader 5...")
            if not mt5.initialize():
                log.error(f"Engine: Falha na inicialização do MT5: {mt5.last_error()}")
                return False
            else:
                log.info("Engine: Conectado ao MetaTrader 5.")
                return True
        # log.debug("Engine: Conexão com MetaTrader 5 já ativa.")
        return True

    def _get_mt5_timeframe_from_string(self, tf_str: str):
        """Converte string de timeframe para constante MT5."""
        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        default_tf = mt5.TIMEFRAME_D1
        tf_constant = tf_map.get(tf_str.upper(), default_tf)
        if tf_constant == default_tf and tf_str.upper() != "D1":
             log.warning(f"Timeframe '{tf_str}' não mapeado, usando D1 como padrão.")
        return tf_constant

    def _load_asset_resources(self, data_ticker):
        """Carrega modelo e estratégia para um ativo sob demanda."""
        if data_ticker in self.asset_states:
            return self.asset_states[data_ticker]

        asset_config = next((asset for asset in self.assets_config if asset['ticker'] == data_ticker), None)
        if not asset_config:
            log.error(f"Configuração não encontrada para {data_ticker}")
            return None

        log.info(f"Carregando recursos para {data_ticker}...")
        try:
            # Carregar estratégia
            module_path = f"src.strategies.{asset_config['strategy_module']}"
            strategy_module = importlib.import_module(module_path)
            StrategyClass = getattr(strategy_module, asset_config["strategy_name"])
            strategy_instance = StrategyClass()

            # Carregar modelo
            model = None
            model_loaded = False
            # Verifica se a estratégia *deveria* ter um modelo (baseado no nome ou tipo)
            needs_model = "lstm" in asset_config['strategy_module'].lower() or \
                          "forest" in asset_config['strategy_module'].lower() # Adicione outras condições se necessário

            if needs_model:
                try:
                    # Tenta carregar modelo Keras/LSTM
                    model_path = self.models_dir / f"{data_ticker}_prod_model.keras"
                    scaler_path = self.models_dir / f"{data_ticker}_prod_scaler.joblib"
                    if model_path.exists() and scaler_path.exists():
                        # Assume KerasLSTMWrapper para carregar
                        from src.strategies.lstm import KerasLSTMWrapper
                        model = KerasLSTMWrapper.load_model(str(model_path), str(scaler_path))
                        model_loaded = True
                        log.info(f"Modelo Keras carregado para {data_ticker}.")
                    else:
                        log.error(f"Arquivos de modelo/scaler Keras não encontrados para {data_ticker} em {self.models_dir}.")
                except ImportError:
                    log.warning(f"KerasLSTMWrapper não pôde ser importado. Modelo para {data_ticker} não carregado.")
                except Exception as load_err:
                     log.error(f"Erro ao carregar modelo Keras para {data_ticker}: {load_err}")

                # Adicionar lógica para carregar outros tipos de modelo (ex: joblib para RandomForest)
                # elif "forest" in asset_config['strategy_module'].lower(): ...

            if not model_loaded and needs_model:
                 log.warning(f"Não foi possível carregar o modelo de IA necessário para {data_ticker}.")
                 # Considerar se deve retornar None ou permitir continuar só com setups
                 # return None # Descomente se um modelo for estritamente necessário

            state = {"config": asset_config, "strategy": strategy_instance, "model": model}
            self.asset_states[data_ticker] = state
            log.info(f"Recursos para {data_ticker} carregados (Modelo {'OK' if model else 'N/A'}).")
            return state

        except Exception as e:
            log.error(f"Falha crítica ao carregar recursos para {data_ticker}: {e}", exc_info=True)
            return None

    def run_simulation_cycle(self, data_ticker: str, selected_timeframe_str: str, simulation_datetime_utc: datetime = None) -> dict:
        """
        Executa um ciclo completo de simulação para um único ativo e timeframe.
        """
        log.info(f"Iniciando ciclo de simulação para {data_ticker} @ {selected_timeframe_str}"
                 f"{' em ' + simulation_datetime_utc.strftime('%Y-%m-%d %H:%M UTC') if simulation_datetime_utc else ' (tempo real)'}")

        state = self._load_asset_resources(data_ticker)
        if not state:
            return {"error": f"Não foi possível carregar recursos para {data_ticker}."}

        asset_config = state['config']
        strategy = state['strategy']
        model = state.get('model') # Pode ser None
        live_config = asset_config['live_trading']
        order_ticker = live_config.get('ticker_order', data_ticker)
        mt5_timeframe = self._get_mt5_timeframe_from_string(selected_timeframe_str)

        result = {
            "ticker": data_ticker, "order_ticker": order_ticker, "timeframe": selected_timeframe_str,
            "timestamp": "N/A", "signal": "HOLD", "signal_raw": -1,
            "suggested_price": None, "price_source": "N/A", "stop_price": None,
            "indicators": {}, "setup_valid": None, "error": None
        }

        try:
            # 1. Buscar Dados Recentes
            if asset_config['provider'] == 'MetaTrader5':
                provider = self.mt5_provider
                # Garante conexão MT5 ativa
                if not self._initialize_mt5():
                    result["error"] = "Falha ao conectar ao MT5 para buscar dados."
                    return result
                # Busca 300 barras (suficiente para EMA200 e lookback LSTM)
                historical_data = provider.get_latest_rates(
                    data_ticker, 300, mt5_timeframe, end_time_utc=simulation_datetime_utc
                )
            elif asset_config['provider'] == 'YFinance':
                provider = self.yf_provider
                # Adapta busca para YFinance (simplificado, pega histórico recente)
                end_date_dt = simulation_datetime_utc.date() if simulation_datetime_utc else datetime.now().date()
                start_date_dt = end_date_dt - timedelta(days=400) # Busca ~400 dias
                end_date_str = end_date_dt.strftime('%Y-%m-%d')
                start_date_str = start_date_dt.strftime('%Y-%m-%d')
                historical_data = provider.get_data(data_ticker, start_date_str, end_date_str)
                # Filtra até a hora exata, se fornecida (requer dados intra-diários no YF)
                if simulation_datetime_utc and not historical_data.empty:
                     historical_data = historical_data[historical_data.index <= simulation_datetime_utc]
            else:
                 result["error"] = f"Provedor '{asset_config['provider']}' desconhecido."; return result

            if historical_data.empty:
                time_info = f"até {simulation_datetime_utc}" if simulation_datetime_utc else "recentes"
                result["error"] = f"Provedor {asset_config['provider']}: Não foi possível obter dados {time_info}."; return result

            last_candle_time = historical_data.index[-1]
            result["timestamp"] = last_candle_time.strftime('%Y-%m-%d %H:%M:%S')

            # 2. Gerar Features
            log.debug(f"Gerando features para {data_ticker} com {len(historical_data)} barras.")
            featured_data = strategy.define_features(historical_data)
            if featured_data.empty or featured_data.iloc[-1].isnull().all(): # Verifica se a última linha tem NaNs
                result["error"] = "Erro ao gerar features ou dados insuficientes."
                # Tenta pegar indicadores da penúltima linha se a última falhar
                if len(featured_data) > 1 and not featured_data.iloc[-2].isnull().all():
                     last_indicators = featured_data.iloc[-2]
                     log.warning("Usando indicadores da penúltima barra devido a NaNs na última.")
                else:
                     return result # Aborta se não conseguir indicadores
            else:
                 last_indicators = featured_data.iloc[-1]


            # Captura indicadores
            indicator_keys = strategy.get_feature_names() if hasattr(strategy, 'get_feature_names') else []
            common_indicators = ['sma9', 'ema21', 'ema50', 'ema200', 'rsi', 'volatility', 'sentiment', 'close', 'open', 'high', 'low'] # Adiciona OHLC
            keys_to_log = sorted(list(set(indicator_keys + common_indicators)))

            for key in keys_to_log:
                if key in last_indicators:
                    value = last_indicators.get(key)
                    # Formata floats, mantém outros tipos como estão (ex: volume int)
                    if isinstance(value, (float, np.floating)):
                        result["indicators"][key.upper()] = f"{value:.2f}" if pd.notna(value) else "N/A"
                    elif pd.notna(value):
                         result["indicators"][key.upper()] = str(value)
                    else:
                         result["indicators"][key.upper()] = "N/A"

            # 3. Gerar Sinal da IA
            ai_signal_raw = -1
            if model:
                # Usa featured_data que já contém NaNs tratados pela estratégia (se houver)
                X_live = featured_data[strategy.get_feature_names()].dropna() # Remove linhas com NaN para o predict
                min_lookback = getattr(model, 'lookback', 1)
                log.debug(f"Tentando prever com {len(X_live)} amostras (lookback={min_lookback}).")
                if len(X_live) >= min_lookback:
                    try:
                        predictions = model.predict(X_live)
                        if predictions is not None and len(predictions) > 0:
                            ai_signal_raw = int(predictions[-1])
                            log.info(f"Sinal da IA para {data_ticker}: {'COMPRA' if ai_signal_raw == 1 else 'VENDA'} ({ai_signal_raw})")
                        else: log.warning(f"Modelo para {data_ticker} não retornou previsões.")
                    except Exception as e:
                        log.error(f"Erro ao gerar previsão da IA para {data_ticker}: {e}")
                        result["error"] = "Erro na previsão da IA."
                else:
                    log.warning(f"Dados insuficientes ({len(X_live)} < {min_lookback}) para previsão da IA em {data_ticker}.")
            else:
                 log.info(f"Nenhum modelo de IA para {data_ticker}, usando apenas setups.")

            # 4. Avaliar Setups
            setup_rules = asset_config.get('setup', [])
            log.debug(f"Avaliando {len(setup_rules)} regras de setup para {data_ticker}...")
            # Passa featured_data completo, analyzer lida com NaNs se necessário
            is_setup_valid = evaluate_setups(ai_signal_raw if ai_signal_raw != -1 else None, setup_rules, featured_data)
            result["setup_valid"] = is_setup_valid
            log.info(f"Resultado da avaliação do Setup para {data_ticker}: {'Válido' if is_setup_valid else 'Inválido'}")

            # 5. Determinar Sinal Final e Preços
            final_signal = "HOLD"; final_signal_raw = -1
            if is_setup_valid and (ai_signal_raw != -1 or not setup_rules):
                 if ai_signal_raw != -1: # Usa sinal da IA se disponível e setup OK
                      final_signal = 'COMPRA' if ai_signal_raw == 1 else 'VENDA'
                      final_signal_raw = ai_signal_raw
                 # Adicionar lógica aqui se quiser sinal APENAS de setup (sem IA)

            result["signal"] = final_signal; result["signal_raw"] = final_signal_raw
            log.info(f"Sinal Final para {data_ticker}: {final_signal}")

            if final_signal != "HOLD":
                suggested_price_val = None
                if asset_config['provider'] == 'MetaTrader5':
                     symbol_info = mt5.symbol_info_tick(order_ticker)
                     if symbol_info and symbol_info.time > 0: # Verifica se o tick é válido
                         suggested_price_val = symbol_info.ask if final_signal == 'COMPRA' else symbol_info.bid
                         result["price_source"] = "Tick MT5"
                         log.debug(f"Preço via Tick MT5 para {order_ticker}: {suggested_price_val}")

                if suggested_price_val is None: # Fallback para fechamento
                     suggested_price_val = historical_data['close'].iloc[-1]
                     result["price_source"] = "Último Fechamento"
                     log.debug(f"Preço via Último Fechamento para {data_ticker}: {suggested_price_val}")

                result["suggested_price"] = suggested_price_val

                # Calcula Stop Price
                stop_loss_pct = asset_config['trading_rules']['stop_loss_pct']
                entry = result["suggested_price"]
                # Adiciona verificação para evitar stop inválido se entry for None ou 0
                if entry is not None and entry > 0:
                     result["stop_price"] = entry * (1 - stop_loss_pct) if final_signal == 'COMPRA' else entry * (1 + stop_loss_pct)
                     log.debug(f"Stop Price calculado para {data_ticker}: {result['stop_price']:.2f}")
                else:
                     log.warning(f"Não foi possível calcular o Stop Price para {data_ticker} devido ao preço de entrada inválido.")


        except Exception as e:
            log_err = f"Erro inesperado ao simular {data_ticker}: {e}"
            logging.error(log_err, exc_info=True)
            result["error"] = log_err

        return result

    def shutdown(self):
        """Encerra a conexão com o MT5."""
        log.info("Encerrando conexão do SimulationEngine com o MetaTrader 5...")
        mt5.shutdown()

    def __del__(self):
        """Garante o shutdown ao destruir o objeto."""
        self.shutdown()