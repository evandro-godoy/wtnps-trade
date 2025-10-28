import sys # Adicionado para importar path
import yaml
import logging
import time
from pathlib import Path
import importlib
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone, timedelta # Adicionado timedelta
import pytz # Adicionado pytz
import numpy as np # Adicionado numpy

# Adiciona a raiz do projeto ao path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data_handler.provider import MetaTraderProvider
# Importa KerasLSTMWrapper dinamicamente onde necessário
# from src.strategies.lstm import KerasLSTMWrapper
from src.setups.analyzer import evaluate_setups # Importa analyzer para setups

# Configuração do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s")
log = logging.getLogger(__name__) # Logger específico

class LiveTrader:
    def __init__(self, config_path="configs/main.yaml"):
        log.info(f"Inicializando LiveTrader com config: {config_path}")
        self.config_path = project_root / config_path
        self.config = self._load_config()
        self.assets_config = [
            asset for asset in self.config["assets"] if asset.get("enabled", False)
        ]
        self.models_dir = Path(self.config["global_settings"]["model_directory"])
        self.asset_states = {}

        self.provider = MetaTraderProvider()
        # A conexão MT5 será gerenciada nos métodos que a utilizam

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
        """Garante que a conexão com o MetaTrader 5 esteja ativa."""
        if not mt5.terminal_info():
            log.info("Tentando inicializar conexão com o MetaTrader 5...")
            if not mt5.initialize():
                log.error(f"Falha na inicialização do MT5: {mt5.last_error()}")
                return False
            else:
                log.info("Conectado ao MetaTrader 5.")
                return True
        # log.debug("Conexão com MetaTrader 5 já ativa.")
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
            # Verifica se o modelo/estratégia já foi carregado
            if self.asset_states[data_ticker].get('strategy') and self.asset_states[data_ticker].get('model'):
                 return self.asset_states[data_ticker]
            # Se não, força recarregamento (caso tenha falhado antes)

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
            needs_model = "lstm" in asset_config['strategy_module'].lower()

            if needs_model:
                try:
                    model_path = self.models_dir / f"{data_ticker}_prod_model.keras"
                    scaler_path = self.models_dir / f"{data_ticker}_prod_scaler.joblib"
                    if model_path.exists() and scaler_path.exists():
                        from src.strategies.lstm import KerasLSTMWrapper
                        model = KerasLSTMWrapper.load_model(str(model_path), str(scaler_path))
                        model_loaded = True
                        log.info(f"Modelo Keras carregado para {data_ticker}.")
                    else:
                        log.error(f"Arquivos Keras não encontrados para {data_ticker} em {self.models_dir}.")
                except ImportError as ie:
                    log.warning(f"KerasLSTMWrapper não importado. Modelo {data_ticker} não carregado. Erro: {ie}")
                except Exception as load_err:
                     log.error(f"Erro ao carregar modelo Keras para {data_ticker}: {load_err}")

            if not model_loaded and needs_model:
                 log.warning(f"Não foi possível carregar modelo IA para {data_ticker}.")

            # Atualiza ou cria o estado
            self.asset_states[data_ticker] = {
                "config": asset_config,
                "strategy": strategy_instance,
                "model": model,
                "position": self.asset_states.get(data_ticker, {}).get("position"), # Mantem posição se já existir
                "last_processed_time": self.asset_states.get(data_ticker, {}).get("last_processed_time"),
            }
            log.info(f"Recursos para {data_ticker} carregados (Modelo {'OK' if model else 'N/A'}).")
            return self.asset_states[data_ticker]

        except Exception as e:
            log.critical(f"Falha crítica ao carregar recursos para {data_ticker}: {e}", exc_info=True)
            return None

    def initialize(self):
        """Conecta ao MT5 e carrega os modelos para cada ativo habilitado."""
        log.info("Inicializando o LiveTrader Engine...")
        if not self._initialize_mt5(): return False # Tenta conectar

        # Pré-carrega recursos para todos os ativos habilitados
        loaded_tickers = []
        for asset_config in self.assets_config:
            if self._load_asset_resources(asset_config['ticker']):
                loaded_tickers.append(asset_config['ticker'])

        if not loaded_tickers:
            log.error("Nenhum ativo foi carregado com sucesso.")
            return False

        log.info("LiveTrader Engine inicializado para: " + ", ".join(loaded_tickers))
        return True

    # --- NOVO MÉTODO PARA SIMULAÇÃO DE CICLO ÚNICO ---
    def simulate_single_cycle(self, data_ticker: str, selected_timeframe_str: str, simulation_datetime_local: datetime) -> dict:
        """
        Executa um ciclo único de busca de dados, geração de sinal e avaliação
        para um ativo específico, retornando um dicionário com os resultados detalhados.
        Similar à lógica do run_single_tick do notebook.
        """
        log.info(f"Simulando ciclo único para {data_ticker} @ {selected_timeframe_str}")

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
            "timestamp": simulation_datetime_local, "signal": "HOLD", "signal_raw": -1, "ai_signal_text": "N/A",
            "suggested_price": None, "price_source": "N/A", "stop_price": None,
            "indicators": {}, "setup_valid": None, "error": None
        }

        try:
            # 1. Buscar Dados Recentes (300 barras)
            if not self._initialize_mt5(): # Garante conexão
                 result["error"] = "Falha ao conectar ao MT5."; return result

            # Usa o provider interno da classe LiveTrader
            latest_data = self.provider.get_latest_rates(data_ticker, 300, mt5_timeframe, simulation_datetime_local)
            if latest_data.empty:
                result["error"] = "Não foi possível obter dados suficientes." 
                return result

            last_candle_time = latest_data.index[-1]
            result["timestamp"] = last_candle_time.strftime('%Y-%m-%d %H:%M:%S %Z')

            # 2. Gerar Features
            log.debug(f"Gerando features para {data_ticker} com {len(latest_data)} barras.")

            # 2. Gerar features (usando a estratégia carregada pelo LiveTrader)
            featured_data = strategy.define_features(latest_data)
            X_live = featured_data[strategy.get_feature_names()].dropna()
            if X_live.empty:
                result["error"]= (f"Dados insuficientes para features em {data_ticker}.")
                return result

            # 3. Gerar sinal (usando o modelo carregado pelo LiveTrader)
            if not model:
                    self.log_message(f"Modelo não carregado para {data_ticker}, pulando predição.")
                    ai_signal_raw = -1 # Sinal de Hold/Erro
                    ai_signal_text = "N/A (sem modelo)"
            else:
                # Verifica lookback antes de prever
                min_lookback = getattr(model, 'lookback', 1)
                if len(X_live) < min_lookback:
                    self.log_message(f"Dados insuficientes ({len(X_live)}<{min_lookback}) para predição IA em {data_ticker}.")
                    ai_signal_raw = -1
                    ai_signal_text = "N/A (dados insuficientes)"
                else:
                    predictions = model.predict(X_live)
                    if predictions is not None and len(predictions) > 0:
                        ai_signal_raw = int(predictions[-1])
                        ai_signal_text = 'COMPRA' if ai_signal_raw == 1 else 'VENDA'
                    else:
                        self.log_message(f"Modelo {data_ticker} não retornou predições.")
                        ai_signal_raw = -1
                        ai_signal_text = "N/A (erro predição)"
            result["ai_signal_text"] = ai_signal_text # Guarda texto do sinal IA

            # 4. Avaliar Setups
            setup_rules = asset_config.get('setup', [])
            log.debug(f"Avaliando {len(setup_rules)} regras setup para {data_ticker}...")
            is_setup_valid = evaluate_setups(ai_signal_raw if ai_signal_raw != -1 else None, setup_rules, featured_data)
            result["setup_valid"] = is_setup_valid
            log.info(f"Setup {data_ticker}: {'Válido' if is_setup_valid else 'Inválido'}")

            # 5. Determinar Sinal Final e Preços
            final_signal = "HOLD"; final_signal_raw = -1
            if is_setup_valid and ai_signal_raw in [0, 1]: # Setup OK E IA deu sinal claro
                 final_signal = ai_signal_text
                 final_signal_raw = ai_signal_raw

            result["signal"] = final_signal; result["signal_raw"] = final_signal_raw
            log.info(f"Sinal Final {data_ticker}: {final_signal}")

            if final_signal != "HOLD":
                suggested_price_val = None
                symbol_info = mt5.symbol_info_tick(order_ticker)
                if symbol_info and symbol_info.time_msc > 0:
                    tick_time = datetime.fromtimestamp(symbol_info.time, tz=pytz.utc)
                    if abs((last_candle_time - tick_time).total_seconds()) < self.provider._timeframe_to_minutes(mt5_timeframe) * 60 * 1.5:
                        suggested_price_val = symbol_info.ask if final_signal == 'COMPRA' else symbol_info.bid
                        result["price_source"] = "Tick MT5"
                        log.debug(f"Preço Tick MT5 {order_ticker}: {suggested_price_val}")
                    else: log.warning(f"Tick {order_ticker} defasado ({tick_time}), fallback.")
                else: log.warning(f"Tick inválido {order_ticker}, fallback.")

                if suggested_price_val is None: # Fallback
                     suggested_price_val = featured_data['close'].iloc[-1]
                     result["price_source"] = "Último Fechamento"
                     log.debug(f"Preço Fechamento {data_ticker}: {suggested_price_val}")

                result["suggested_price"] = suggested_price_val

                # Coleta indicadores
                last_indicators = featured_data.iloc[-1]
                indicator_keys = strategy.get_feature_names() if hasattr(strategy, 'get_feature_names') else []
                common_indicators = ['ema_9', 'sma_20', 'sma_50', 'sma_200', 'close', 'high', 'low']
                keys_to_log = sorted(list(set(indicator_keys + common_indicators)))
                indicators_dict = {}
                for key in keys_to_log:
                     if key in last_indicators:
                          value = last_indicators.get(key)
                          if isinstance(value, (float, np.floating)):
                               indicators_dict[key.upper()] = f"{value:.5f}" if pd.notna(value) else "N/A"
                          elif pd.notna(value): indicators_dict[key.upper()] = str(value)
                          else: indicators_dict[key.upper()] = "N/A"
                indicators_str = " | ".join([f"{k}={v}" for k, v in indicators_dict.items()]) if indicators_dict else "Nenhum"

                if indicators_dict:
                    result["indicators"] = indicators_dict 

                # Calcula Stop
                stop_loss_pct = asset_config['trading_rules']['stop_loss_pct']
                entry = result["suggested_price"]
                if entry is not None and entry > 0:
                     result["stop_price"] = entry * (1 - stop_loss_pct) if final_signal == 'COMPRA' else entry * (1 + stop_loss_pct)
                     log.debug(f"Stop Price {data_ticker}: {result['stop_price']:.5f}")
                else: log.warning(f"Stop Price não calculado {data_ticker}.")

        except Exception as e:
            log_err = f"Erro inesperado ao simular {data_ticker}: {e}"
            logging.critical(log_err, exc_info=True)
            result["error"] = str(e)

        return result


    # --- Métodos do Loop de Trading Real (run, _execute_trade) ---
    # Estes métodos permanecem os mesmos da versão anterior do live_trader.py
    # Eles NÃO são usados pelo dashboard, apenas se você rodar `python src/live_trader.py`
    def run(self):
        """Inicia o loop principal do robô, iterando sobre os ativos."""
        if not self.initialize(): return
        log.info(f"Iniciando loop de trading...")

        while True:
            try:
                for data_ticker, state in self.asset_states.items():
                    asset_config = state["config"]
                    live_config = asset_config["live_trading"]
                    timeframe_str = live_config["timeframe_str"]
                    mt5_timeframe = self._get_mt5_timeframe_from_string(timeframe_str)

                    # Busca apenas o último candle para checar o tempo
                    latest_candle = self.provider.get_latest_rates(data_ticker, 1, mt5_timeframe)
                    if latest_candle.empty: continue
                    latest_candle_time = latest_candle.index[0]

                    # Verifica se é um novo candle
                    if state.get("last_processed_time") == latest_candle_time: continue

                    log.info(f"--- Novo Candle para {data_ticker} ({timeframe_str}) em {latest_candle_time} ---")

                    # Executa a lógica de simulação para obter o sinal
                    # (Poderia chamar self.simulate_single_cycle aqui, mas
                    # duplicamos a lógica para manter o run() focado no trading real)

                    # 1. Buscar dados (mais barras para análise)
                    historical_data = self.provider.get_latest_rates(data_ticker, 300, mt5_timeframe)
                    if historical_data.empty: continue

                    # 2. Gerar features
                    strategy = state["strategy"]
                    featured_data = strategy.define_features(historical_data)
                    X_live = featured_data[strategy.get_feature_names()].dropna()
                    if X_live.empty:
                         log.warning(f"Live: Dados insuficientes p/ features {data_ticker}"); continue

                    # 3. Gerar sinal IA
                    ai_signal_raw = -1
                    model = state.get("model")
                    if model:
                         min_lookback = getattr(model, 'lookback', 1)
                         if len(X_live) >= min_lookback:
                              try:
                                  X_predict = X_live.tail(len(X_live) - min_lookback + 1)
                                  if len(X_predict) > 0:
                                       predictions = model.predict(X_predict)
                                       if predictions is not None and len(predictions) > 0:
                                            ai_signal_raw = int(predictions[-1])
                              except Exception as e: log.error(f"Live: Erro previsão IA {data_ticker}: {e}")
                         else: log.warning(f"Live: Dados insuf. ({len(X_live)}<{min_lookback}) p/ IA {data_ticker}")

                    # 4. Avaliar Setups
                    setup_rules = asset_config.get('setup', [])
                    is_setup_valid = evaluate_setups(ai_signal_raw if ai_signal_raw != -1 else None, setup_rules, featured_data)

                    # 5. Determinar Sinal Final
                    final_signal_raw = -1
                    if is_setup_valid and ai_signal_raw in [0, 1]:
                        final_signal_raw = ai_signal_raw

                    log.info(f"Live Sinal Final {data_ticker}: {'COMPRA' if final_signal_raw == 1 else ('VENDA' if final_signal_raw == 0 else 'HOLD')}")

                    # 6. Lógica de decisão (Execução Real)
                    # Adicionar lógica para FECHAR posições existentes (SL/TP ou sinal contrário) aqui
                    # ...

                    # Abrir nova posição se não houver uma
                    if state["position"] is None:
                        if final_signal_raw == 1: self._execute_trade(data_ticker, "BUY")
                        elif final_signal_raw == 0: self._execute_trade(data_ticker, "SELL")
                    else:
                        log.info(f"Live: Posição já aberta {data_ticker} ({state['position']}).")


                    # Atualiza o tempo do último candle processado
                    state["last_processed_time"] = latest_candle_time

                # Calcula o tempo de espera até o próximo candle (simplificado)
                # Idealmente, calcularia o tempo exato para o fechamento do próximo candle M1/M5
                sleep_time = 30 # Verifica a cada 30 segundos por novos candles
                log.debug(f"Ciclo completo. Aguardando {sleep_time} segundos...")
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                log.info("Desligando o robô...")
                self.shutdown() # Chama o método de desligamento
                break
            except Exception as e:
                log.critical(f"Erro CRÍTICO no loop principal: {e}", exc_info=True)
                time.sleep(60) # Aguarda antes de tentar novamente


    def _execute_trade(self, data_ticker, order_type):
        """Envia a ordem para o MetaTrader 5 para um ativo específico."""
        if data_ticker not in self.asset_states:
            log.error(f"Tentativa de executar trade para ativo não carregado: {data_ticker}")
            return

        state = self.asset_states[data_ticker]
        asset_config = state['config']
        live_config = asset_config['live_trading']
        order_ticker = live_config.get('ticker_order', data_ticker) # Usa ticker de ordem

        log.info(f"Preparando ordem {order_type} para {order_ticker} (baseado em {data_ticker})...")

        # Garante conexão MT5
        if not self._initialize_mt5():
             log.error(f"Não foi possível enviar ordem para {order_ticker}: Sem conexão MT5.")
             return

        trade_type = mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL

        symbol_info = mt5.symbol_info(order_ticker)
        if symbol_info is None:
            log.error(f"Não foi possível obter informações para o ativo de ordem '{order_ticker}'")
            return
            
        # Verifica se o ativo está disponível para negociação
        if not symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
             log.warning(f"Ativo {order_ticker} não está disponível para negociação no momento (modo: {symbol_info.trade_mode}). Ordem não enviada.")
             return


        # Obtém preço atual para a ordem
        tick = mt5.symbol_info_tick(order_ticker)
        if not tick or tick.time == 0:
             log.error(f"Não foi possível obter tick atual para {order_ticker}. Ordem não enviada.")
             return
        price = tick.ask if order_type == "BUY" else tick.bid

        # Monta a requisição
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order_ticker,
            "volume": float(live_config["trade_volume"]),
            "type": trade_type,
            "price": price,
            "deviation": 20, # Slippage permitido (ajustar conforme necessário)
            "magic": asset_config.get('magic_number', 123456), # Usa número mágico da config ou padrão
            "comment": f"WtnpsTrade Bot {data_ticker} {order_type}",
            "type_time": mt5.ORDER_TIME_GTC, # Good Till Cancelled
            "type_filling": mt5.ORDER_FILLING_IOC, # Immediate Or Cancel
        }

        # Verifica modo de execução
        execution_mode = live_config.get("execution_mode", "suggest")
        if execution_mode == "suggest":
            log.info(
                f"[SUGESTÃO] Ordem de {order_type} para {live_config['trade_volume']} lotes de {order_ticker} a ~${price:.5f}"
            )
        elif execution_mode == "execute":
            log.info(f"[EXECUÇÃO] Enviando ordem de {order_type} para {order_ticker}...")
            result = mt5.order_send(request)
            if result is None:
                 log.error(f"Falha ao enviar ordem para {order_ticker}. mt5.order_send() retornou None. Erro: {mt5.last_error()}")
            elif result.retcode != mt5.TRADE_RETCODE_DONE:
                log.error(f"Falha ao enviar ordem para {order_ticker}: {result.comment} (RetCode: {result.retcode})")
            else:
                log.info(f"Ordem para {order_ticker} enviada com sucesso! Ticket: {result.order}")
                # Atualiza o estado da posição APENAS se a ordem foi executada
                state["position"] = "LONG" if order_type == "BUY" else "SHORT"
                # Adicionar lógica futura para SL/TP aqui se necessário via ordens pendentes ou monitoramento
        else:
            log.warning(f"Modo de execução '{execution_mode}' não reconhecido para {data_ticker}.")


    def shutdown(self):
        """Encerra a conexão com o MT5."""
        log.info("Encerrando conexão do LiveTrader com o MetaTrader 5...")
        mt5.shutdown()

    def __del__(self):
        """Garante o shutdown ao destruir o objeto."""
        self.shutdown()


if __name__ == "__main__":
    trader = LiveTrader()
    trader.run()