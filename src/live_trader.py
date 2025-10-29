# src/live_trader.py

import yaml
import logging # <- Garante que logging está importado
from pathlib import Path
import importlib
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from threading import Thread, Lock, Event
# REMOVIDO: import tkinter.messagebox as messagebox (Não deve estar aqui)

# Importações internas do projeto
from src.data_handler.provider import get_provider_instance, BaseDataProvider, MetaTraderProvider
from src.strategies.base import BaseStrategy
from src.setups.analyzer import SetupAnalyzer

# Configuração do logging (usará 'logger')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__) # <- Define 'logger'

# --- Função auxiliar para timeframe ---
# (Mantida igual)
def _get_mt5_timeframe_from_string(tf_str: str):
    tf_map = { "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
               "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
               "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1 }
    tf_constant = tf_map.get(tf_str.upper(), None)
    if tf_constant is None: logger.warning(f"Timeframe '{tf_str}' inválido.")
    return tf_constant

# --- Classe LiveTrader ---
class LiveTrader:
    """ Motor backend para execução de estratégias em tempo real via MT5. """
    def __init__(self, config_path: str = 'configs/main.yaml', callback=None):
        self.config_path = config_path
        self.config = self._load_config()
        self.models_dir = Path(self.config.get('global_settings', {}).get('models_directory', 'models'))
        self.callback = callback # Função para enviar atualizações para a GUI

        self.mt5_provider = None
        self.asset_resources = {}
        self.last_candle_time = {}
        self.current_state = {} # {asset: {"position":..., "entry_price":..., "trade_id":..., "sl_pct":..., "tp_pct":...}}
        self.setup_analyzer = SetupAnalyzer()

        self._run_thread = None
        self._init_thread = None # Referência para a thread de inicialização
        self._stop_event = Event()
        self._lock = Lock() # Protege current_state, last_candle_time, asset_resources

        # Flag para indicar se a inicialização foi concluída (com ou sem sucesso)
        self.is_trader_initialized = False

        # Inicia inicialização em background
        self._start_initialization_thread()

    def _start_initialization_thread(self):
        """Inicia a thread que conecta ao MT5 e carrega recursos."""
        if self._init_thread and self._init_thread.is_alive():
             logger.warning("Thread de inicialização já está em execução.")
             return
        self._init_thread = Thread(target=self._initialize_resources, daemon=True, name="LiveTraderInitThread")
        self._init_thread.start()

    def _load_config(self):
        """Carrega configuração YAML."""
        logger.info(f"Carregando config: {self.config_path}")
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.critical(f"CRÍTICO: Config não encontrado: {self.config_path}")
            raise # Re-levanta para falhar rápido se o config não existe
        except yaml.YAMLError as e:
            logger.critical(f"CRÍTICO: Erro ao carregar YAML: {e}")
            raise

    def _initialize_mt5(self):
         """Inicializa conexão com MT5."""
         # Prevenção contra inicialização dupla
         with self._lock: # Protege acesso a self.mt5_provider
             if self.mt5_provider and self.mt5_provider.is_connected():
                 #logger.debug("Conexão MT5 já ativa.")
                 return True

         logger.info("Tentando inicializar conexão MT5...")
         try:
             provider = get_provider_instance("MetaTrader5")
             if isinstance(provider, MetaTraderProvider) and provider.is_connected():
                  with self._lock: self.mt5_provider = provider # Armazena se sucesso
                  logger.info("Conectado ao MetaTrader 5.")
                  return True
             else:
                  logger.error("Falha ao obter/conectar instância do MetaTraderProvider.")
                  with self._lock: self.mt5_provider = None # Garante que está None
                  return False
         except Exception as e:
             logger.error(f"Exceção ao inicializar MT5: {e}", exc_info=False)
             with self._lock: self.mt5_provider = None
             return False

    def _load_asset_resources(self, asset_symbol: str, asset_config: dict):
        """Carrega recursos para um ativo."""
        with self._lock: # Protege leitura/escrita do cache
             if asset_symbol in self.asset_resources and 'error' not in self.asset_resources[asset_symbol]:
                  # logger.debug(f"Recursos {asset_symbol} já em cache.")
                  return self.asset_resources[asset_symbol]

        if not asset_config or not asset_config.get('live_trading', {}).get('enabled', False):
            return None # Não carrega se não habilitado para live

        strategy_module_name = asset_config.get('strategy_module')
        strategy_class_name = asset_config.get('strategy_name')
        if not strategy_module_name or not strategy_class_name:
            logger.error(f"Configuração de estratégia incompleta para {asset_symbol}")
            with self._lock: self.asset_resources[asset_symbol] = {'error': 'Config estratégia incompleta'}
            return None

        try:
            strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
            StrategyClass = getattr(strategy_module, strategy_class_name)
            strategy_instance: BaseStrategy = StrategyClass(**asset_config.get('strategy_params', {}))

            model_path_prefix = str(self.models_dir / f"{asset_symbol}_prod")
            logger.info(f"Carregando modelo {asset_symbol} via {strategy_class_name}.load()...")
            model = StrategyClass.load(model_path_prefix)
            logger.info(f"Modelo {asset_symbol} carregado.")

            resources = {
                'strategy_instance': strategy_instance, 'strategy_class': StrategyClass,
                'model': model, 'config': asset_config,
                'live_config': asset_config.get('live_trading', {}),
                'trading_rules': asset_config.get('trading_rules', {}),
                'price_precision': asset_config.get('price_precision', 2)
            }
            with self._lock: self.asset_resources[asset_symbol] = resources # Atualiza cache
            return resources

        except FileNotFoundError:
             logger.error(f"Erro {asset_symbol}: Modelo não encontrado ({model_path_prefix}...). Treino executado?")
             with self._lock: self.asset_resources[asset_symbol] = {'error': 'Modelo não encontrado'}
             return None
        except Exception as e:
            logger.exception(f"Erro CRÍTICO ao carregar recursos {asset_symbol}: {e}")
            with self._lock: self.asset_resources[asset_symbol] = {'error': f'Erro carga: {e}'}
            return None

    def _initialize_resources(self):
        """(Thread) Conecta MT5 e carrega recursos."""
        logger.info("Thread init LiveTrader: Iniciando...")
        init_success = False
        try:
            # 1. Conectar MT5
            if not self._initialize_mt5():
                logger.critical("Falha MT5. LiveTrader não pode operar.")
                if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Erro MT5", "color": "red"})
                return # Aborta

            logger.info("Thread init LiveTrader: Carregando modelos...")
            enabled_assets = []
            assets_list = self.config.get('assets', [])

            # 2. Carregar Recursos dos Ativos
            for asset_config in assets_list:
                if self._stop_event.is_set(): # Verifica se foi pedido para parar durante o carregamento
                     logger.warning("Inicialização interrompida.")
                     return

                asset_symbol = asset_config.get('ticker')
                if not asset_symbol: continue

                if asset_config.get('live_trading', {}).get('enabled', False):
                    #logger.debug(f"Carregando {asset_symbol}...")
                    # Passa asset_symbol e asset_config
                    loaded_res = self._load_asset_resources(asset_symbol, asset_config)
                    if loaded_res and 'error' not in loaded_res:
                         enabled_assets.append(asset_symbol)
                         # Inicializa estado (com lock)
                         with self._lock:
                              sl_pct_cfg = asset_config.get('trading_rules', {}).get('stop_loss_pct')
                              tp_pct_cfg = asset_config.get('trading_rules', {}).get('take_profit_pct')
                              self.last_candle_time[asset_symbol] = None
                              self.current_state[asset_symbol] = {
                                   "position": None, "entry_price": None, "trade_id": None,
                                   "sl_pct": sl_pct_cfg, "tp_pct": tp_pct_cfg
                              }
                    else:
                         logger.error(f"Falha ao carregar {asset_symbol}. Será ignorado.")
                         if self.callback: self.callback({"type": "status", "asset": asset_symbol, "message": "Erro Carga", "color": "red"})

            # 3. Finaliza e Sinaliza Status
            if enabled_assets:
                logger.info(f"LiveTrader pronto: {', '.join(enabled_assets)}")
                if self.callback:
                     self.callback({"type": "status", "asset": "GLOBAL", "message": "Iniciado", "color": "green"})
                     for asset in enabled_assets:
                          self.callback({"type": "status", "asset": asset, "message": "Pronto", "color": "blue"})
                init_success = True # Marcar como sucesso
            elif not self._stop_event.is_set(): # Só avisa de vazio se não foi cancelado
                logger.warning("Nenhum ativo habilitado/carregado para live trading.")
                if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Vazio", "color": "orange"})
                init_success = True # Inicialização ok, mas sem ativos

        except Exception as e:
             logger.critical(f"Erro CRÍTICO na inicialização: {e}", exc_info=True)
             if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Erro Crítico Init", "color": "red"})
        finally:
            self.is_trader_initialized = True # Marca que a tentativa terminou (mesmo se falhou)
            logger.info(f"Thread init LiveTrader: Concluída (Sucesso={init_success}).")


    def _get_latest_candles(self, ticker: str, timeframe_obj: int, count: int) -> pd.DataFrame:
        """Busca candles recentes do MT5."""
        # Acesso seguro ao provider
        with self._lock:
             provider = self.mt5_provider

        if not provider or not provider.is_connected():
            logger.warning("MT5 não conectado ao buscar candles. Tentando reconectar...")
            if not self._initialize_mt5():
                 logger.error("Falha ao reconectar MT5.")
                 return pd.DataFrame()
            # Pega a nova instância do provider após reconectar
            with self._lock: provider = self.mt5_provider
            if not provider: return pd.DataFrame() # Falhou mesmo assim

        try:
             candles = provider.get_latest_candles(ticker, timeframe_obj, count)
             return candles
        except Exception as e:
            logger.debug(f"Erro ao buscar candles {ticker}: {e}", exc_info=False)
            return pd.DataFrame()

    def _check_sl_tp(self, asset_symbol: str):
        """Verifica SL/TP para posições abertas."""
        with self._lock: # Leitura segura do estado e recursos
            state = self.current_state.get(asset_symbol)
            resources = self.asset_resources.get(asset_symbol)

        # Validações iniciais (fora do lock se possível)
        if not state or not resources or 'error' in resources or state["position"] is None: return
        live_ticker = resources['live_config'].get('ticker_order', asset_symbol)
        trade_id = state["trade_id"]; entry_price = state["entry_price"]
        sl_pct = state.get("sl_pct"); tp_pct = state.get("tp_pct")
        position_type = state["position"]
        price_precision = resources.get('price_precision', 2)

        if (sl_pct is None and tp_pct is None) or not entry_price or entry_price <= 0: return

        # Busca tick (precisa do provider)
        with self._lock: provider = self.mt5_provider
        if not provider or not provider.is_connected():
             # logger.warning("MT5 não conectado para check SL/TP.") # Log muito frequente?
             return

        current_tick = None
        try: current_tick = mt5.symbol_info_tick(live_ticker)
        except Exception as e: logger.warning(f"Erro obter tick {live_ticker} (SL/TP): {e}"); return
        if not current_tick or current_tick.time == 0: return # Tick inválido

        current_price = current_tick.bid if position_type == "COMPRADO" else current_tick.ask
        if current_price <= 0: return # Preço inválido

        sl_price = round(entry_price * (1 - sl_pct / 100) if position_type == "COMPRADO" else entry_price * (1 + sl_pct / 100), price_precision) if sl_pct is not None else None
        tp_price = round(entry_price * (1 + tp_pct / 100) if position_type == "COMPRADO" else entry_price * (1 - tp_pct / 100), price_precision) if tp_pct is not None else None

        close_reason = None
        # Verifica SL
        if sl_price is not None and sl_price != 0:
            if (position_type == "COMPRADO" and current_price <= sl_price) or \
               (position_type == "VENDIDO" and current_price >= sl_price):
                close_reason = f"STOP LOSS ({current_price:.{price_precision}f} {'<=' if position_type=='COMPRADO' else '>='} {sl_price:.{price_precision}f})"
        # Verifica TP
        if close_reason is None and tp_price is not None and tp_price != 0:
            if (position_type == "COMPRADO" and current_price >= tp_price) or \
               (position_type == "VENDIDO" and current_price <= tp_price):
                close_reason = f"TAKE PROFIT ({current_price:.{price_precision}f} {'>=' if position_type=='COMPRADO' else '<='} {tp_price:.{price_precision}f})"

        # Fecha posição se necessário
        if close_reason:
            logger.info(f"[RISCO] {close_reason} para {asset_symbol} (ID: {trade_id}). Fechando...")
            if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": close_reason, "color": "orange"})

            close_success = False
            # Re-verifica provider dentro do if para garantir
            with self._lock: provider = self.mt5_provider
            if provider:
                try: close_success = provider.close_position(live_ticker, trade_id)
                except Exception as e_close: logger.error(f"Exceção fechar {trade_id} (SL/TP): {e_close}", exc_info=True)

            if close_success:
                logger.info(f"[RISCO] Posição {trade_id} ({asset_symbol}) fechada: {close_reason}.")
                with self._lock: # Atualiza estado
                    self.current_state[asset_symbol].update({"position": None, "entry_price": None, "trade_id": None})
                if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": f"Fechado ({('SL' if 'STOP' in close_reason else 'TP')})"})
            else:
                logger.error(f"[RISCO] Falha ao fechar {trade_id} ({asset_symbol}) após: {close_reason}.")
                if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": f"Erro Fechar {('SL' if 'STOP' in close_reason else 'TP')}", "color": "red"})

    def _process_asset(self, asset_symbol: str):
        """Processa a lógica de decisão E execução para um único ativo."""
        with self._lock: resources = self.asset_resources.get(asset_symbol)
        if not resources or 'error' in resources: return

        live_config = resources['live_config']
        model = resources['model']
        strategy_instance: BaseStrategy = resources['strategy_instance']
        asset_config = resources['config']
        trading_rules = resources['trading_rules']
        price_precision = resources.get('price_precision', 2)

        live_ticker = live_config.get('ticker_order', asset_symbol)
        timeframe_str = live_config.get('timeframe_str', 'M5')
        execution_mode = live_config.get('execution_mode', 'suggest')
        trade_volume = live_config.get('trade_volume', 0.1)

        timeframe_obj = _get_mt5_timeframe_from_string(timeframe_str)
        if timeframe_obj is None: return

        num_candles_to_fetch = 500
        candles = self._get_latest_candles(live_ticker, timeframe_obj, num_candles_to_fetch)

        min_required_candles = getattr(model, 'lookback', 1) + 1 # +1 for current candle features
        if candles.empty or len(candles) < min_required_candles: return

        latest_candle_time = candles.index[-1].to_pydatetime()

        with self._lock: last_processed = self.last_candle_time.get(asset_symbol)
        if last_processed is not None and latest_candle_time <= last_processed: return

        #logger.info(f"Novo candle {asset_symbol} @ {timeframe_str}: {latest_candle_time}")
        with self._lock: self.last_candle_time[asset_symbol] = latest_candle_time

        try:
            data_with_features = strategy_instance.define_features(candles)
            feature_names = strategy_instance.get_feature_names()
            lookback = getattr(model, 'lookback', 1)

            if len(data_with_features) < lookback: return

            model_input_data = data_with_features.iloc[-lookback:]
            X_predict = model_input_data[feature_names]
            if X_predict.isnull().values.any(): return # Log já feito se acontecer

            raw_prediction = model.predict(X_predict)
            ai_signal_code = int(raw_prediction[-1]) if isinstance(raw_prediction, np.ndarray) and len(raw_prediction) > 0 else int(raw_prediction) if isinstance(raw_prediction, (int, np.integer)) else 0
            ai_signal = "COMPRA" if ai_signal_code == 1 else "VENDA"
            #logger.debug(f"Sinal IA {asset_symbol}: {ai_signal} ({ai_signal_code})")

            setup_rules = asset_config.get('setup', [])
            current_candle_features = data_with_features.iloc[-1:]
            setup_result = {"is_valid": True, "details": {}, "final_decision": ai_signal}
            if setup_rules:
                 try:
                      setup_result = self.setup_analyzer.evaluate_setups(current_candle_features, setup_rules, ai_signal)
                      # logger.info(f"Setup {asset_symbol}: Valido={setup_result['is_valid']}, Decisao={setup_result['final_decision']}")
                 except Exception as e_setup:
                      logger.error(f"Erro avaliar setups {asset_symbol}: {e_setup}", exc_info=True)
                      setup_result = {"is_valid": False, "details": {"erro": str(e_setup)}, "final_decision": "HOLD"}

            final_signal = setup_result["final_decision"]
            current_price = current_candle_features['close'].iloc[0]

            # Atualiza GUI (callback)
            if self.callback:
                 with self._lock: current_pos_display = self.current_state.get(asset_symbol, {}).get("position", "---")
                 gui_data = { "type": "update", "asset": asset_symbol,
                              "datetime": latest_candle_time.strftime('%Y-%m-%d %H:%M:%S'),
                              "price": round(current_price, price_precision), "ai_signal": ai_signal,
                              "setup_valid": setup_result["is_valid"], "final_signal": final_signal,
                              "position": current_pos_display, "setup_details": setup_result.get("details", {}) }
                 self.callback(gui_data)

            # Lógica de Execução
            with self._lock:
                 current_position = self.current_state.get(asset_symbol, {}).get("position")
                 current_trade_id = self.current_state.get(asset_symbol, {}).get("trade_id")
                 provider = self.mt5_provider # Pega instância segura

            if execution_mode == 'execute' and provider:
                sl_pct = trading_rules.get('stop_loss_pct')
                tp_pct = trading_rules.get('take_profit_pct')

                if final_signal == "COMPRA" and current_position != "COMPRADO":
                    if current_position == "VENDIDO":
                        logger.info(f"[EXEC] Fechando VENDA {asset_symbol} ({current_trade_id})...")
                        close_result = provider.close_position(live_ticker, current_trade_id)
                        if close_result:
                             with self._lock: self.current_state[asset_symbol].update({"position": None, "entry_price": None, "trade_id": None}); current_position = None
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Fechado"})
                             logger.info(f"[EXEC] Venda {current_trade_id} fechada.")
                        else: logger.error(f"[EXEC] Falha fechar VENDA {current_trade_id}. Compra cancelada."); final_signal = "HOLD"

                    if current_position is None:
                        logger.info(f"[EXEC] Enviando COMPRA {asset_symbol} @ ~{current_price:.{price_precision}f} Vol:{trade_volume}")
                        sl_price = round(current_price * (1 - sl_pct / 100), price_precision) if sl_pct else None
                        tp_price = round(current_price * (1 + tp_pct / 100), price_precision) if tp_pct else None
                        order_result = provider.open_position(live_ticker, 'buy', trade_volume, sl_price=sl_price, tp_price=tp_price)
                        if order_result and order_result.retcode == mt5.TRADE_RETCODE_DONE:
                             filled_price, trade_id = order_result.price, order_result.order
                             logger.info(f"[EXEC] COMPRA OK {asset_symbol}: P={filled_price:.{price_precision}f}, T={trade_id}")
                             with self._lock: self.current_state[asset_symbol].update({"position": "COMPRADO", "entry_price": filled_price, "trade_id": trade_id, "sl_pct": sl_pct, "tp_pct": tp_pct})
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Comprado", "price": filled_price, "trade_id": trade_id})
                        else:
                             retcode = order_result.retcode if order_result else 'N/A'; comment = order_result.comment if order_result else 'N/A'
                             logger.error(f"[EXEC] FALHA COMPRA {asset_symbol}: Ret={retcode}, Com={comment}")
                             if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": f"Erro Compra ({retcode})", "color": "red"})

                elif final_signal == "VENDA" and current_position != "VENDIDO":
                    if current_position == "COMPRADO":
                        logger.info(f"[EXEC] Fechando COMPRA {asset_symbol} ({current_trade_id})...")
                        close_result = provider.close_position(live_ticker, current_trade_id)
                        if close_result:
                             with self._lock: self.current_state[asset_symbol].update({"position": None, "entry_price": None, "trade_id": None}); current_position = None
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Fechado"})
                             logger.info(f"[EXEC] Compra {current_trade_id} fechada.")
                        else: logger.error(f"[EXEC] Falha fechar COMPRA {current_trade_id}. Venda cancelada."); final_signal = "HOLD"

                    if current_position is None:
                        logger.info(f"[EXEC] Enviando VENDA {asset_symbol} @ ~{current_price:.{price_precision}f} Vol:{trade_volume}")
                        sl_price = round(current_price * (1 + sl_pct / 100), price_precision) if sl_pct else None
                        tp_price = round(current_price * (1 - tp_pct / 100), price_precision) if tp_pct else None
                        order_result = provider.open_position(live_ticker, 'sell', trade_volume, sl_price=sl_price, tp_price=tp_price)
                        if order_result and order_result.retcode == mt5.TRADE_RETCODE_DONE:
                             filled_price, trade_id = order_result.price, order_result.order
                             logger.info(f"[EXEC] VENDA OK {asset_symbol}: P={filled_price:.{price_precision}f}, T={trade_id}")
                             with self._lock: self.current_state[asset_symbol].update({"position": "VENDIDO", "entry_price": filled_price, "trade_id": trade_id, "sl_pct": sl_pct, "tp_pct": tp_pct})
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Vendido", "price": filled_price, "trade_id": trade_id})
                        else:
                             retcode = order_result.retcode if order_result else 'N/A'; comment = order_result.comment if order_result else 'N/A'
                             logger.error(f"[EXEC] FALHA VENDA {asset_symbol}: Ret={retcode}, Com={comment}")
                             if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": f"Erro Venda ({retcode})", "color": "red"})

            elif execution_mode == 'suggest' and final_signal != "HOLD":
                 logger.info(f"SUGESTÃO ({execution_mode}): {final_signal} {asset_symbol} @ {current_price:.{price_precision}f}")
                 sl_price = round(current_price * (1 - sl_pct / 100) if final_signal == "COMPRA" else current_price * (1 + sl_pct / 100), price_precision) if sl_pct else None
                 tp_price = round(current_price * (1 + tp_pct / 100) if final_signal == "COMPRA" else current_price * (1 - tp_pct / 100), price_precision) if tp_pct else None
                 #logger.info(f"--> Preços Sugeridos: SL={sl_price if sl_price else 'N/A'}, TP={tp_price if tp_price else 'N/A'}")

        except Exception as e:
            logger.exception(f"Erro ciclo {asset_symbol}: {e}")
            if self.callback: self.callback({"type": "status", "asset": asset_symbol, "message": "Erro Ciclo", "color": "red"})

    def _run_monitor_thread(self):
        """(Thread) Loop principal: verifica SL/TP e processa candles."""
        logger.info("Thread monitor: Iniciando loop principal.")
        # Espera init terminar (redundante se start() já espera, mas seguro)
        if self._init_thread and self._init_thread.is_alive():
             logger.info("Thread monitor: Aguardando inicialização...")
             self._init_thread.join()
             logger.info("Thread monitor: Inicialização concluída.")

        # Pega a lista de ativos após a inicialização ter terminado
        with self._lock:
             active_assets = [k for k, v in self.asset_resources.items() if v and 'error' not in v]

        if not active_assets:
             logger.warning("Nenhum ativo carregado. Thread monitor encerrando.")
             if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Parado (Vazio)", "color": "grey"})
             # Finaliza aqui se não há ativos
             self._shutdown_mt5() # Garante desconexão
             return

        logger.info(f"Thread monitor: Monitorando {len(active_assets)} ativo(s)...")
        while not self._stop_event.is_set():
            try:
                # Copia a lista para evitar problemas se ela mudar (improvável aqui)
                assets_to_check = list(active_assets)
                for asset_symbol in assets_to_check:
                    if self._stop_event.is_set(): break
                    self._check_sl_tp(asset_symbol)
                    # Não processa candle se SL/TP acabou de fechar a posição
                    with self._lock: still_open = self.current_state.get(asset_symbol,{}).get("position") is not None
                    if still_open or self.current_state.get(asset_symbol,{}).get("position") is None: # Processa se aberto ou se nunca abriu
                         self._process_asset(asset_symbol)

                # Pausa controlada pelo evento de parada
                sleep_time = 5 # segundos
                # wait retorna True se o evento foi setado, False se timeout
                if self._stop_event.wait(sleep_time):
                     logger.info("Thread monitor: Sinal de parada recebido durante sleep.")
                     break # Sai do loop while

            except Exception as e:
                 logger.critical(f"Erro CRÍTICO no loop monitor: {e}", exc_info=True)
                 # Pausa mais longa antes de tentar de novo
                 if self._stop_event.wait(60): break # Sai se for parado durante a pausa

        logger.info("Thread monitor: Loop principal encerrado.")
        self._shutdown_mt5() # Desconecta ao final do loop

    def start(self):
        """Inicia a thread de monitoramento, esperando a inicialização."""
        # Garante que a inicialização terminou antes de iniciar o monitoramento
        if self._init_thread and self._init_thread.is_alive():
            logger.info("Aguardando inicialização antes de iniciar o monitoramento...")
            self._init_thread.join() # Espera aqui

        # Verifica se já está rodando
        if self._run_thread and self._run_thread.is_alive():
            logger.warning("Monitoramento já está ativo.")
            return

        # Verifica se a inicialização falhou
        if not self.is_trader_initialized:
             logger.error("LiveTrader não inicializado. Não é possível iniciar monitoramento.")
             # REMOVIDO: messagebox.showerror(...) - Não usar GUI aqui
             # Sinaliza erro via callback se disponível
             if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Falha Init", "color": "red"})
             return

        # Verifica se há ativos
        with self._lock: active = [k for k,v in self.asset_resources.items() if v and 'error' not in v]
        if not active:
             logger.warning("Nenhum ativo carregado. Monitoramento não iniciado.")
             # REMOVIDO: messagebox.showinfo(...)
             if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Vazio", "color": "orange"})
             return

        logger.info("Iniciando monitoramento de trades...")
        self._stop_event.clear()
        self._run_thread = Thread(target=self._run_monitor_thread, daemon=True, name="LiveTraderMonitorThread")
        self._run_thread.start()
        # Callback de status é enviado pela própria thread _run_monitor_thread


    def stop(self):
        """Sinaliza para as threads pararem."""
        logger.info("Comando PARAR recebido. Sinalizando threads...")
        self._stop_event.set() # Sinaliza para init e run pararem

        # Espera as threads terminarem (com timeout)
        threads_to_join = [self._init_thread, self._run_thread]
        for thread in threads_to_join:
             if thread and thread.is_alive():
                  logger.info(f"Aguardando thread {thread.name} finalizar...")
                  thread.join(timeout=10) # Timeout para cada thread
                  if thread.is_alive():
                       logger.warning(f"Thread {thread.name} não finalizou no tempo.")
                  else:
                       logger.info(f"Thread {thread.name} finalizada.")

        # Desconexão MT5 ocorre no final da _run_monitor_thread se ela rodou
        # Garante desconexão caso _run_monitor_thread não tenha chegado ao fim
        self._shutdown_mt5()

        logger.info("LiveTrader parado.")
        if self.callback:
             self.callback({"type": "status", "asset": "GLOBAL", "message": "Parado", "color": "grey"})

    def _shutdown_mt5(self):
        """Desconecta do MT5."""
        with self._lock: # Protege acesso ao provider
             provider = self.mt5_provider
             # Só tenta desligar se existir a instância
             if provider:
                  logger.info("Encerrando conexão MT5...")
                  try:
                      if hasattr(provider, 'close_connection'): provider.close_connection()
                      else: mt5.shutdown()
                      logger.info("Desligamento MT5 concluído.")
                  except Exception as e: logger.warning(f"Erro ao desconectar MT5: {e}")
                  finally:
                       self.mt5_provider = None # Garante que a referência seja removida

# --- Bloco Standalone ---
if __name__ == "__main__":
    def simple_console_callback(data):
        ts = datetime.now().strftime('%H:%M:%S')
        if data["type"] == "update": print(f"[{ts}] {data['asset']}: P={data['price']}, IA={data['ai_signal']}, SOK={data['setup_valid']}, Fin={data['final_signal']}, Pos={data.get('position','---')}")
        elif data["type"] == "position": print(f"[{ts}] {data['asset']}: POS -> {data.get('status','?')} @{data.get('price','?')} (ID:{data.get('trade_id','?')})")
        elif data["type"] == "status": print(f"[{ts}] STATUS ({data.get('asset','?')}) : {data.get('message','?')}")
        else: print(f"[{ts}] Callback: {data}")

    print("Iniciando Live Trader Standalone...")
    # Cria a instância (inicia _init_thread)
    trader = LiveTrader(config_path='configs/main.yaml', callback=simple_console_callback)
    try:
        # Espera a inicialização terminar antes de chamar start()
        if trader._init_thread and trader._init_thread.is_alive():
            print("Aguardando inicialização...")
            trader._init_thread.join() # Espera aqui
            print("Inicialização concluída.")

        # Inicia o monitoramento SE a inicialização foi OK e não foi parado
        if trader.is_trader_initialized and not trader._stop_event.is_set():
             # Verifica se há ativos antes de iniciar o monitor
             with trader._lock: active = [k for k,v in trader.asset_resources.items() if v and 'error' not in v]
             if active:
                  trader.start() # Inicia _run_monitor_thread
                  # Mantém loop principal vivo enquanto monitora
                  while trader._run_thread and trader._run_thread.is_alive():
                      time.sleep(1)
             else:
                  logger.warning("Nenhum ativo carregado. Encerrando.")
        else:
             logger.critical("Falha na inicialização ou parada solicitada antes do start. Encerrando.")

    except KeyboardInterrupt: print("\nCtrl+C. Parando...")
    except Exception as main_e: logger.critical(f"Erro não tratado: {main_e}", exc_info=True)
    finally:
        if 'trader' in locals() and trader: trader.stop()
        print("Live Trader Standalone finalizado.")