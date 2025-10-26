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
# Importa KerasLSTMWrapper apenas onde necessário para evitar dependência global
# from src.strategies.lstm import KerasLSTMWrapper
from src.setups.analyzer import evaluate_setups

# Configuração do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s")
log = logging.getLogger(__name__)

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
        """Inicializa a conexão com o MetaTrader 5, se necessário e ainda não conectado."""
        needs_mt5 = any(asset['provider'] == 'MetaTrader5' for asset in self.assets_config)
        if needs_mt5 and not mt5.terminal_info():
            log.info("Tentando inicializar conexão com o MetaTrader 5...")
            if not mt5.initialize():
                log.error(f"Engine: Falha na inicialização do MT5: {mt5.last_error()}")
                return False
            else:
                log.info("Engine: Conectado ao MetaTrader 5.")
                return True
        elif needs_mt5:
            # log.debug("Engine: Conexão com MetaTrader 5 já ativa.")
            return True
        else:
             log.info("Engine: Nenhum ativo configurado requer MetaTrader 5.")
             return True # Não precisa de MT5, então é 'bem-sucedido'

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

            # Carregar modelo (se aplicável)
            model = None
            model_loaded = False
            # Verifica se a estratégia *deveria* ter um modelo (heuristicamente)
            needs_model = "lstm" in asset_config['strategy_module'].lower() or \
                          "forest" in asset_config['strategy_module'].lower()

            if needs_model:
                try:
                    # Tenta carregar modelo Keras/LSTM
                    model_path = self.models_dir / f"{data_ticker}_prod_model.keras"
                    scaler_path = self.models_dir / f"{data_ticker}_prod_scaler.joblib"
                    if model_path.exists() and scaler_path.exists():
                        # Importa KerasLSTMWrapper dinamicamente APENAS quando necessário
                        from src.strategies.lstm import KerasLSTMWrapper
                        model = KerasLSTMWrapper.load_model(str(model_path), str(scaler_path))
                        model_loaded = True
                        log.info(f"Modelo Keras carregado para {data_ticker}.")
                    else:
                        log.error(f"Arquivos de modelo/scaler Keras não encontrados para {data_ticker} em {self.models_dir}.")
                except ImportError as ie:
                    log.warning(f"KerasLSTMWrapper não pôde ser importado (TensorFlow/Keras instalado?). Modelo para {data_ticker} não carregado. Erro: {ie}")
                except Exception as load_err:
                     log.error(f"Erro ao carregar modelo Keras para {data_ticker}: {load_err}")

            if not model_loaded and needs_model:
                 log.warning(f"Não foi possível carregar o modelo de IA necessário para {data_ticker}.")

            state = {"config": asset_config, "strategy": strategy_instance, "model": model}
            self.asset_states[data_ticker] = state
            log.info(f"Recursos para {data_ticker} carregados (Modelo {'OK' if model else 'N/A'}).")
            return state

        except Exception as e:
            log.critical(f"Falha crítica ao carregar recursos para {data_ticker}: {e}", exc_info=True)
            return None

    def run_simulation_cycle(self, data_ticker: str, selected_timeframe_str: str, simulation_datetime_local: datetime = None) -> dict:
        """
        Executa um ciclo completo de simulação para um único ativo e timeframe.
        Aceita um datetime LOCAL (ex: America/Sao_Paulo) e o converte para UTC internamente.
        """
        simulation_datetime_utc: datetime = None
        local_tz_str = "America/Sao_Paulo" # Define o timezone local esperado
        
        # Converte o datetime local para UTC, se fornecido
        if simulation_datetime_local:
            try:
                local_tz = pytz.timezone(local_tz_str)
                # Garante que o datetime local seja 'aware'
                if simulation_datetime_local.tzinfo is None:
                     local_dt = local_tz.localize(simulation_datetime_local)
                else:
                     local_dt = simulation_datetime_local.astimezone(local_tz)
                simulation_datetime_utc = local_dt.astimezone(pytz.utc) # Converte para UTC
                log.info(f"Simulação solicitada para {local_dt.strftime('%Y-%m-%d %H:%M %Z')}, convertida para {simulation_datetime_utc.strftime('%Y-%m-%d %H:%M %Z')}")
            except Exception as e:
                 log.error(f"Erro ao converter datetime local para UTC: {e}", exc_info=True)
                 return {"error": "Erro na conversão de fuso horário."}

        # Log de início do ciclo
        log.info(f"Iniciando ciclo: {data_ticker} @ {selected_timeframe_str}"
                 f"{' em ' + simulation_datetime_utc.strftime('%Y-%m-%d %H:%M %Z') if simulation_datetime_utc else ' (tempo real)'}")


        state = self._load_asset_resources(data_ticker)
        if not state:
            return {"error": f"Não foi possível carregar recursos para {data_ticker}."}

        asset_config = state['config']
        strategy = state['strategy']
        model = state.get('model')
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
            # --- AJUSTE NA BUSCA DE DADOS ---
            # Define a quantidade de barras a buscar (700) e a usar (300)
            bars_to_fetch = 700
            bars_to_use = 300

            # 1. Buscar Dados Recentes (período estendido)
            if asset_config['provider'] == 'MetaTrader5':
                provider = self.mt5_provider
                if not self._initialize_mt5():
                    result["error"] = "Falha ao conectar ao MT5."; return result
                
                # Busca 'bars_to_fetch' barras terminando no tempo especificado (ou mais recentes)
                historical_data_full = provider.get_latest_rates(
                    data_ticker, bars_to_fetch, mt5_timeframe, end_time_utc=simulation_datetime_utc
                )
            elif asset_config['provider'] == 'YFinance':
                provider = self.yf_provider
                # Lógica YFinance (simplificada, busca período maior)
                end_date_dt = simulation_datetime_utc.date() if simulation_datetime_utc else datetime.now().date()
                # Busca mais dias para tentar obter ~700 barras (ex: ~2 anos para D1)
                start_date_dt = end_date_dt - timedelta(days=730)
                end_date_str = end_date_dt.strftime('%Y-%m-%d')
                start_date_str = start_date_dt.strftime('%Y-%m-%d')
                historical_data_full = provider.get_data(data_ticker, start_date_str, end_date_str)
                # Filtra até a hora exata
                if simulation_datetime_utc and not historical_data_full.empty:
                     historical_data_full = historical_data_full[historical_data_full.index <= simulation_datetime_utc]
            else:
                 result["error"] = f"Provedor '{asset_config['provider']}' desconhecido."; return result

            # Verifica se dados suficientes foram retornados
            if historical_data_full.empty or len(historical_data_full) < 5: # Mínimo para cálculo básico
                time_info = f"até {simulation_datetime_utc}" if simulation_datetime_utc else "recentes"
                result["error"] = f"Provedor {asset_config['provider']}: Não foi possível obter dados {time_info} suficientes após busca estendida."; return result
                
            # --- AJUSTE: Usa apenas as últimas 'bars_to_use' para simulação ---
            data_for_simulation = historical_data_full.tail(bars_to_use).copy() # Usa .copy() para evitar SettingWithCopyWarning
            log.info(f"Total de barras buscadas: {len(historical_data_full)}, usando as últimas {len(data_for_simulation)} para análise.")

            last_candle_time = data_for_simulation.index[-1]
            result["timestamp"] = last_candle_time.strftime('%Y-%m-%d %H:%M:%S %Z')

            # 2. Gerar Features (usando dados da simulação)
            log.debug(f"Gerando features para {data_ticker} com {len(data_for_simulation)} barras.")
            # Passa o dataframe JÁ FATIADO para define_features
            featured_data = strategy.define_features(data_for_simulation)
            if featured_data.empty: # Checa se o resultado das features é vazio
                 result["error"] = "Erro ao gerar features (DataFrame vazio)."
                 return result
            # Verifica NaNs na ÚLTIMA linha do dataframe resultante das features
            if featured_data.iloc[-1].isnull().all():
                log.warning(f"NaNs encontrados na última barra de features para {data_ticker}.")
                # Tenta usar a penúltima
                if len(featured_data) > 1 and not featured_data.iloc[-2].isnull().all():
                     last_indicators = featured_data.iloc[-2]
                     log.warning("Usando indicadores da penúltima barra.")
                else:
                     result["error"] = "Não foi possível obter indicadores válidos (NaNs)."
                     return result
            else:
                 last_indicators = featured_data.iloc[-1]

            # Captura indicadores
            indicator_keys = strategy.get_feature_names() if hasattr(strategy, 'get_feature_names') else []
            common_indicators = ['sma9', 'ema21', 'ema50', 'ema200', 'rsi', 'volatility', 'sentiment', 'close', 'open', 'high', 'low', 'volume']
            keys_to_log = sorted(list(set(indicator_keys + common_indicators)))
            for key in keys_to_log:
                if key in last_indicators:
                    value = last_indicators.get(key)
                    if isinstance(value, (float, np.floating)):
                        result["indicators"][key.upper()] = f"{value:.5f}" if pd.notna(value) else "N/A" # Mais precisão
                    elif pd.notna(value): result["indicators"][key.upper()] = str(value)
                    else: result["indicators"][key.upper()] = "N/A"

            # 3. Gerar Sinal da IA (usando dados da simulação)
            ai_signal_raw = -1
            if model:
                # Usa featured_data (que contém apenas os últimos 300 pontos com features)
                X_live = featured_data[strategy.get_feature_names()].dropna()
                min_lookback = getattr(model, 'lookback', 1)
                log.debug(f"Amostras válidas para predição: {len(X_live)} (lookback necessário: {min_lookback}).")
                if len(X_live) >= min_lookback:
                    try:
                        # Pega apenas os últimos dados necessários para o predict (mais eficiente)
                        X_predict = X_live.tail(len(X_live) - min_lookback + 1) # Ajuste para garantir dados suficientes para sequências
                        if len(X_predict) > 0:
                            predictions = model.predict(X_predict)
                            if predictions is not None and len(predictions) > 0:
                                ai_signal_raw = int(predictions[-1]) # Pega a última predição
                                log.info(f"Sinal da IA para {data_ticker}: {'COMPRA' if ai_signal_raw == 1 else 'VENDA'} ({ai_signal_raw})")
                            else: log.warning(f"Modelo {data_ticker} não retornou previsões válidas.")
                        else: log.warning(f"Não há dados suficientes em X_predict após ajuste para lookback em {data_ticker}.")
                    except Exception as e:
                        log.error(f"Erro ao gerar previsão da IA para {data_ticker}: {e}", exc_info=True)
                        result["error"] = "Erro na previsão IA."
                else:
                    log.warning(f"Dados válidos ({len(X_live)} < {min_lookback}) insuficientes para previsão IA em {data_ticker}.")
            else:
                 log.info(f"Sem modelo IA para {data_ticker}.")

            # 4. Avaliar Setups (usando dados da simulação com features)
            setup_rules = asset_config.get('setup', [])
            log.debug(f"Avaliando {len(setup_rules)} regras de setup para {data_ticker}...")
            is_setup_valid = evaluate_setups(ai_signal_raw if ai_signal_raw != -1 else None, setup_rules, featured_data)
            result["setup_valid"] = is_setup_valid
            log.info(f"Setup para {data_ticker}: {'Válido' if is_setup_valid else 'Inválido'}")

            # 5. Determinar Sinal Final e Preços
            final_signal = "HOLD"; final_signal_raw = -1
            if is_setup_valid and (ai_signal_raw != -1 or not setup_rules):
                 if ai_signal_raw != -1:
                      final_signal = 'COMPRA' if ai_signal_raw == 1 else 'VENDA'
                      final_signal_raw = ai_signal_raw

            result["signal"] = final_signal; result["signal_raw"] = final_signal_raw
            log.info(f"Sinal Final para {data_ticker}: {final_signal}")

            if final_signal != "HOLD":
                suggested_price_val = None
                # Tenta obter tick MT5 se aplicável e conectado
                if asset_config['provider'] == 'MetaTrader5' and self._initialize_mt5():
                     symbol_info = mt5.symbol_info_tick(order_ticker)
                     if symbol_info and symbol_info.time_msc > 0:
                         tick_time = datetime.fromtimestamp(symbol_info.time, tz=pytz.utc)
                         # Verifica se o tick é razoavelmente próximo do candle
                         # (Ajuste a tolerância conforme necessário, ex: 1 barra)
                         if abs((last_candle_time - tick_time).total_seconds()) < self.mt5_provider._timeframe_to_minutes(mt5_timeframe) * 60 * 1.5:
                             suggested_price_val = symbol_info.ask if final_signal == 'COMPRA' else symbol_info.bid
                             result["price_source"] = "Tick MT5"
                             log.debug(f"Preço via Tick MT5 para {order_ticker}: {suggested_price_val}")
                         else: log.warning(f"Tick para {order_ticker} defasado ({tick_time}), usando fallback.")
                     else: log.warning(f"Tick inválido para {order_ticker}, usando fallback.")
                
                # Fallback para fechamento (também usado para YFinance)
                if suggested_price_val is None:
                     suggested_price_val = data_for_simulation['close'].iloc[-1] # Usa o fechamento do último candle dos 300 usados
                     result["price_source"] = "Último Fechamento"
                     log.debug(f"Preço via Último Fechamento para {data_ticker}: {suggested_price_val}")

                result["suggested_price"] = suggested_price_val

                # Calcula Stop Price
                stop_loss_pct = asset_config['trading_rules']['stop_loss_pct']
                entry = result["suggested_price"]
                if entry is not None and entry > 0:
                     result["stop_price"] = entry * (1 - stop_loss_pct) if final_signal == 'COMPRA' else entry * (1 + stop_loss_pct)
                     log.debug(f"Stop Price calculado para {data_ticker}: {result['stop_price']:.5f}")
                else:
                     log.warning(f"Stop Price não calculado para {data_ticker} (preço entrada inválido).")


        except Exception as e:
            log_err = f"Erro inesperado ao simular {data_ticker}: {e}"
            logging.critical(log_err, exc_info=True) # Usa CRITICAL para erros inesperados
            result["error"] = str(e)

        return result

    def shutdown(self):
        """Encerra a conexão com o MT5."""
        log.info("Encerrando conexão do SimulationEngine com o MetaTrader 5...")
        mt5.shutdown()

    def __del__(self):
        """Garante o shutdown ao destruir o objeto."""
        self.shutdown()