# src/live_trader.py

import yaml
import logging
from pathlib import Path
import importlib
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from threading import Thread, Lock, Event

# Importações internas
from src.data_handler.provider import get_provider_instance, BaseDataProvider, MetaTraderProvider
from src.strategies.base import BaseStrategy
from src.setups.analyzer import SetupAnalyzer

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__) # Logger específico para este módulo

# --- Função Auxiliar Timeframe ---
def _get_mt5_timeframe_from_string(tf_str: str):
    tf_map = { "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
               "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
               "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1 }
    tf_constant = tf_map.get(tf_str.upper(), None)
    if tf_constant is None:
        # Loga apenas uma vez por TF inválido
        if not hasattr(_get_mt5_timeframe_from_string, 'logged_tf_warnings'): _get_mt5_timeframe_from_string.logged_tf_warnings = set()
        if tf_str not in _get_mt5_timeframe_from_string.logged_tf_warnings:
            logger.warning(f"Timeframe '{tf_str}' inválido.")
            _get_mt5_timeframe_from_string.logged_tf_warnings.add(tf_str)
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
        self.asset_resources = {} # Cache thread-safe via _lock
        self.last_candle_time = {} # Cache thread-safe via _lock
        self.current_state = {} # Cache thread-safe via _lock
        self.setup_analyzer = SetupAnalyzer()

        self._run_thread = None # Thread de monitoramento
        self._init_thread = None # Thread de inicialização
        self._stop_event = Event() # Sinalizador para parar threads
        self._lock = Lock() # Protege dados compartilhados

        self.is_trader_initialized = False # Indica se init concluiu (com ou sem sucesso)

        self._start_initialization_thread() # Inicia a inicialização

    def _start_initialization_thread(self):
        """Inicia a thread de inicialização (conectar MT5, carregar modelos)."""
        # Evita iniciar múltiplas threads de init
        with self._lock:
            if self._init_thread and self._init_thread.is_alive():
                logger.warning("Thread de inicialização já está em execução.")
                return
            self._init_thread = Thread(target=self._initialize_resources, daemon=True, name="LiveTraderInitThread")
            self._init_thread.start()
            logger.info("Thread de inicialização do LiveTrader iniciada.")

    def _load_config(self):
        """Carrega configuração YAML."""
        logger.info(f"Carregando config: {self.config_path}")
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError: logger.critical(f"CRÍTICO: Config não encontrado: {self.config_path}"); raise
        except yaml.YAMLError as e: logger.critical(f"CRÍTICO: Erro ao carregar YAML: {e}"); raise

    def _initialize_mt5(self):
         """Inicializa conexão com MT5 (thread-safe)."""
         with self._lock: # Garante acesso exclusivo ao provider
             if self.mt5_provider and self.mt5_provider.is_connected(): return True
         logger.info("Tentando inicializar conexão MT5...")
         try:
             provider = get_provider_instance("MetaTrader5") # Pode levantar ValueError
             if isinstance(provider, MetaTraderProvider) and provider.is_connected():
                  with self._lock: self.mt5_provider = provider
                  logger.info("Conectado ao MetaTrader 5.")
                  return True
             else: logger.error("Falha ao conectar instância MetaTraderProvider."); return False
         except Exception as e:
             logger.error(f"Exceção ao inicializar MT5: {e}", exc_info=False)
             with self._lock: self.mt5_provider = None # Garante que está None
             return False

    def _load_asset_resources(self, asset_symbol: str, asset_config: dict):
        """
        Carrega recursos para um ativo (chamado pela thread de init).
        Usa a PRIMEIRA estratégia da lista strategies[] para live trading.
        """
        # Verifica cache (leitura inicial sem lock é aceitável, escrita requer lock)
        with self._lock:
             if asset_symbol in self.asset_resources and 'error' not in self.asset_resources[asset_symbol]:
                  return self.asset_resources[asset_symbol]

        if not asset_config or not asset_config.get('live_trading', {}).get('enabled', False): 
            return None

        # Busca lista de estratégias
        strategies_list = asset_config.get('strategies', [])
        
        if not strategies_list:
            error_msg = f"Nenhuma estratégia configurada para {asset_symbol}."
            logger.error(error_msg)
            with self._lock: self.asset_resources[asset_symbol] = {'error': error_msg}
            return None
        
        # Usa a PRIMEIRA estratégia para live trading
        strategy_config = strategies_list[0]
        strategy_module_name = strategy_config.get('module')
        strategy_class_name = strategy_config.get('name')
        
        logger.info(f"Live trading {asset_symbol}: Usando estratégia '{strategy_class_name}'")
        
        if not strategy_module_name or not strategy_class_name:
            error_msg = f"Config estratégia incompleta {asset_symbol}/{strategy_class_name}."
            logger.error(error_msg)
            with self._lock: self.asset_resources[asset_symbol] = {'error': error_msg}
            return None

        try:
            strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
            StrategyClass = getattr(strategy_module, strategy_class_name)
            strategy_instance: BaseStrategy = StrategyClass(**strategy_config.get('strategy_params', {}))
            
            # NOVO FORMATO: ticker_StrategyName_prod
            model_path_prefix = str(self.models_dir / f"{asset_symbol}_{strategy_class_name}_prod")
            logger.info(f"Carregando modelo {asset_symbol}/{strategy_class_name}...")
            model = StrategyClass.load(model_path_prefix)
            logger.info(f"Modelo {asset_symbol}/{strategy_class_name} OK.")

            resources = {
                'strategy_instance': strategy_instance,
                'strategy_class': StrategyClass,
                'strategy_name': strategy_class_name,
                'model': model,
                'config': asset_config,  # Config completo do ativo
                'strategy_config': strategy_config,  # Config da estratégia
                'live_config': asset_config.get('live_trading', {}),
                'trading_rules': asset_config.get('trading_rules', {}),
                'price_precision': asset_config.get('price_precision', 2)
            }
            with self._lock: self.asset_resources[asset_symbol] = resources # Atualiza cache
            return resources
        except FileNotFoundError:
             error_msg = f"Modelo {asset_symbol}/{strategy_class_name} não encontrado ({model_path_prefix}...). Treino ok?"
             logger.error(error_msg)
             with self._lock: self.asset_resources[asset_symbol] = {'error': error_msg}
             return None
        except Exception as e:
            error_msg = f"Erro CRÍTICO carga {asset_symbol}/{strategy_class_name}: {e}"
            logger.exception(error_msg) # Log com traceback
            with self._lock: self.asset_resources[asset_symbol] = {'error': error_msg}
            return None

    def _initialize_resources(self):
        """(Thread) Conecta MT5 e carrega recursos."""
        logger.info("Thread init LiveTrader: Iniciando...")
        init_success = False
        self.is_trader_initialized = False # Reseta flag no início
        try:
            if not self._initialize_mt5():
                logger.critical("Falha MT5. LiveTrader inoperante.")
                if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Erro MT5", "color": "red"})
                return # Aborta

            logger.info("Thread init LiveTrader: Carregando modelos...")
            enabled_assets = []
            assets_list = self.config.get('assets', [])
            for asset_config in assets_list:
                if self._stop_event.is_set(): logger.warning("Inicialização interrompida."); break
                asset_symbol = asset_config.get('ticker')
                if not asset_symbol: continue
                if asset_config.get('live_trading', {}).get('enabled', False):
                    #logger.debug(f"Carregando {asset_symbol}...")
                    loaded_res = self._load_asset_resources(asset_symbol, asset_config)
                    if loaded_res and 'error' not in loaded_res:
                         enabled_assets.append(asset_symbol)
                         with self._lock:
                              sl_pct = asset_config.get('trading_rules', {}).get('stop_loss_pct')
                              tp_pct = asset_config.get('trading_rules', {}).get('take_profit_pct')
                              self.last_candle_time[asset_symbol] = None
                              self.current_state[asset_symbol] = {"position": None, "entry_price": None, "trade_id": None, "sl_pct": sl_pct, "tp_pct": tp_pct}
                    else:
                         # Erro já logado por _load_asset_resources
                         if self.callback: self.callback({"type": "status", "asset": asset_symbol, "message": "Erro Carga", "color": "red"})

            if enabled_assets:
                logger.info(f"LiveTrader pronto: {', '.join(enabled_assets)}")
                if self.callback:
                     self.callback({"type": "status", "asset": "GLOBAL", "message": "Iniciado", "color": "green"})
                     for asset in enabled_assets: self.callback({"type": "status", "asset": asset, "message": "Pronto", "color": "blue"})
                init_success = True
            elif not self._stop_event.is_set():
                logger.warning("Nenhum ativo habilitado/carregado para live.")
                if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Vazio", "color": "orange"})
                init_success = True # Init ok, mas vazio

        except Exception as e:
             logger.critical(f"Erro CRÍTICO na inicialização: {e}", exc_info=True)
             if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Erro Crítico Init", "color": "red"})
        finally:
            self.is_trader_initialized = True # Marca que terminou (mesmo c/ falha)
            logger.info(f"Thread init LiveTrader: Concluída (Sucesso={init_success}).")


    def _get_latest_candles(self, ticker: str, timeframe_obj: int, count: int) -> pd.DataFrame:
        """Busca candles recentes do MT5 (thread-safe)."""
        with self._lock: provider = self.mt5_provider
        if not provider or not provider.is_connected():
            # logger.debug("MT5 não conectado, tentando reconectar para buscar candles...")
            if not self._initialize_mt5(): return pd.DataFrame() # Falha ao reconectar
            with self._lock: provider = self.mt5_provider # Pega nova instância
            if not provider: return pd.DataFrame()
        try: return provider.get_latest_candles(ticker, timeframe_obj, count)
        except Exception: return pd.DataFrame() # Silencia erros frequentes de busca

    def _check_sl_tp(self, asset_symbol: str):
        """Verifica SL/TP para posições abertas (thread-safe)."""
        with self._lock: # Leitura segura do estado/recursos
            state = self.current_state.get(asset_symbol); resources = self.asset_resources.get(asset_symbol)
        if not state or not resources or 'error' in resources or state["position"] is None: return
        live_ticker = resources['live_config'].get('ticker_order', asset_symbol)
        trade_id = state["trade_id"]; entry_price = state["entry_price"]
        sl_pct = state.get("sl_pct"); tp_pct = state.get("tp_pct")
        position_type = state["position"]; price_precision = resources.get('price_precision', 2)
        if (sl_pct is None and tp_pct is None) or not entry_price or entry_price <= 0: return

        with self._lock: provider = self.mt5_provider # Pega provider seguro
        if not provider or not provider.is_connected(): return

        current_tick = None
        try: current_tick = mt5.symbol_info_tick(live_ticker)
        except Exception: return # Ignora falha ao pegar tick
        if not current_tick or current_tick.time == 0: return

        current_price = current_tick.bid if position_type == "COMPRADO" else current_tick.ask
        if current_price <= 0: return

        sl_price = round(entry_price*(1-sl_pct/100) if position_type=="COMPRADO" else entry_price*(1+sl_pct/100), price_precision) if sl_pct is not None else None
        tp_price = round(entry_price*(1+tp_pct/100) if position_type=="COMPRADO" else entry_price*(1-tp_pct/100), price_precision) if tp_pct is not None else None

        close_reason = None
        if sl_price and sl_price != 0 and ((position_type == "COMPRADO" and current_price <= sl_price) or (position_type == "VENDIDO" and current_price >= sl_price)):
            close_reason = f"STOP LOSS ({current_price:.{price_precision}f} {'<=' if position_type=='COMPRADO' else '>='} {sl_price:.{price_precision}f})"
        if not close_reason and tp_price and tp_price != 0 and ((position_type == "COMPRADO" and current_price >= tp_price) or (position_type == "VENDIDO" and current_price <= tp_price)):
            close_reason = f"TAKE PROFIT ({current_price:.{price_precision}f} {'>=' if position_type=='COMPRADO' else '<='} {tp_price:.{price_precision}f})"

        if close_reason:
            logger.info(f"[RISCO] {close_reason} {asset_symbol} (ID:{trade_id}). Fechando...")
            if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": close_reason, "color": "orange"})
            close_success = False
            try: close_success = provider.close_position(live_ticker, trade_id) # Usa provider pego com lock
            except Exception as e_close: logger.error(f"Exceção fechar {trade_id} (SL/TP): {e_close}", exc_info=True)

            if close_success:
                logger.info(f"[RISCO] Posição {trade_id} ({asset_symbol}) fechada: {close_reason}.")
                with self._lock: self.current_state[asset_symbol].update({"position": None, "entry_price": None, "trade_id": None})
                if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": f"Fechado ({('SL' if 'STOP' in close_reason else 'TP')})"})
            else:
                logger.error(f"[RISCO] Falha fechar {trade_id} ({asset_symbol}) após: {close_reason}.")
                if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": f"Erro Fechar {('SL' if 'STOP' in close_reason else 'TP')}", "color": "red"})

    def _process_asset(self, asset_symbol: str):
        """Processa lógica de decisão/execução para um ativo."""
        with self._lock: resources = self.asset_resources.get(asset_symbol)
        if not resources or 'error' in resources: return # Já logado se erro

        live_config=resources['live_config']; model=resources['model']; strategy_instance=resources['strategy_instance']
        asset_config=resources['config']; trading_rules=resources['trading_rules']; price_precision=resources.get('price_precision', 2)
        live_ticker=live_config.get('ticker_order', asset_symbol); timeframe_str=live_config.get('timeframe_str', 'M5')
        execution_mode=live_config.get('execution_mode', 'suggest'); trade_volume=live_config.get('trade_volume', 0.1)
        timeframe_obj = _get_mt5_timeframe_from_string(timeframe_str);
        if timeframe_obj is None: return

        candles = self._get_latest_candles(live_ticker, timeframe_obj, 500)
        min_candles = getattr(model, 'lookback', 1) + 1
        if candles.empty or len(candles) < min_candles: return

        latest_candle_time = candles.index[-1].to_pydatetime()
        with self._lock: last_processed = self.last_candle_time.get(asset_symbol)
        if last_processed is not None and latest_candle_time <= last_processed: return

        #logger.debug(f"Novo candle {asset_symbol} @ {timeframe_str}: {latest_candle_time}") # Log menos verboso
        with self._lock: self.last_candle_time[asset_symbol] = latest_candle_time

        try:
            data_with_features = strategy_instance.define_features(candles)
            lookback = getattr(model, 'lookback', 1)
            if len(data_with_features) < lookback: return

            X_predict = data_with_features.iloc[-lookback:][strategy_instance.get_feature_names()]
            if X_predict.isnull().values.any(): logger.warning(f"NaNs input {asset_symbol} @ {latest_candle_time}."); return

            raw_prediction = model.predict(X_predict)
            ai_signal_code = int(raw_prediction[-1]) if isinstance(raw_prediction, np.ndarray) and len(raw_prediction) > 0 else int(raw_prediction) if isinstance(raw_prediction, (int, np.integer)) else 0
            ai_signal = "COMPRA" if ai_signal_code == 1 else "VENDA"
            #logger.debug(f"IA {asset_symbol}: {ai_signal} ({ai_signal_code})")

            setup_rules = asset_config.get('setup', [])
            current_candle = data_with_features.iloc[-1:]
            setup_result = {"is_valid": True, "details": {}, "final_decision": ai_signal}
            if setup_rules:
                 try: setup_result = self.setup_analyzer.evaluate_setups(current_candle, setup_rules, ai_signal)
                 except Exception as e: logger.error(f"Erro setups {asset_symbol}: {e}", exc_info=True); setup_result = {"is_valid": False, "details": {"erro": str(e)}, "final_decision": "HOLD"}
            final_signal = setup_result["final_decision"]; current_price = current_candle['close'].iloc[0]
            # logger.info(f"{asset_symbol}: IA={ai_signal}, SetupOK={setup_result['is_valid']}, Final={final_signal}") # Log mais conciso

            if self.callback:
                 with self._lock: pos_display = self.current_state.get(asset_symbol, {}).get("position", "---")
                 gui_data = { "type": "update", "asset": asset_symbol, "datetime": latest_candle_time.strftime('%Y-%m-%d %H:%M:%S'),
                              "price": round(current_price, price_precision), "ai_signal": ai_signal,
                              "setup_valid": setup_result["is_valid"], "final_signal": final_signal,
                              "position": pos_display, "setup_details": setup_result.get("details", {}) }
                 self.callback(gui_data)

            with self._lock: current_position = self.current_state.get(asset_symbol, {}).get("position"); current_trade_id = self.current_state.get(asset_symbol, {}).get("trade_id"); provider = self.mt5_provider
            sl_pct = trading_rules.get('stop_loss_pct'); tp_pct = trading_rules.get('take_profit_pct')

            if execution_mode == 'execute' and provider:
                if final_signal == "COMPRA" and current_position != "COMPRADO":
                    if current_position == "VENDIDO":
                        logger.info(f"[EXEC] Fechando VENDA {asset_symbol} ({current_trade_id})...")
                        if provider.close_position(live_ticker, current_trade_id):
                             with self._lock: self.current_state[asset_symbol].update({"position": None, "entry_price": None, "trade_id": None}); current_position = None
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Fechado"})
                             logger.info(f"[EXEC] Venda {current_trade_id} fechada.")
                        else: logger.error(f"[EXEC] Falha fechar VENDA {current_trade_id}. Compra cancelada."); final_signal = "HOLD"
                    if current_position is None:
                        logger.info(f"[EXEC] Enviando COMPRA {asset_symbol} @ ~{current_price:.{price_precision}f} Vol:{trade_volume}")
                        sl = round(current_price*(1-sl_pct/100), price_precision) if sl_pct else None; tp = round(current_price*(1+tp_pct/100), price_precision) if tp_pct else None
                        res = provider.open_position(live_ticker, 'buy', trade_volume, sl_price=sl, tp_price=tp)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                             fp, tid = res.price, res.order; logger.info(f"[EXEC] COMPRA OK {asset_symbol}: P={fp:.{price_precision}f}, T={tid}")
                             with self._lock: self.current_state[asset_symbol].update({"position": "COMPRADO", "entry_price": fp, "trade_id": tid, "sl_pct": sl_pct, "tp_pct": tp_pct})
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Comprado", "price": fp, "trade_id": tid})
                        else: rc = res.retcode if res else 'N/A'; cm = res.comment if res else 'N/A'; logger.error(f"[EXEC] FALHA COMPRA {asset_symbol}: Ret={rc}, Com={cm}");
                        if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": f"Erro Compra ({rc})", "color": "red"})

                elif final_signal == "VENDA" and current_position != "VENDIDO":
                    if current_position == "COMPRADO":
                        logger.info(f"[EXEC] Fechando COMPRA {asset_symbol} ({current_trade_id})...")
                        if provider.close_position(live_ticker, current_trade_id):
                             with self._lock: self.current_state[asset_symbol].update({"position": None, "entry_price": None, "trade_id": None}); current_position = None
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Fechado"})
                             logger.info(f"[EXEC] Compra {current_trade_id} fechada.")
                        else: logger.error(f"[EXEC] Falha fechar COMPRA {current_trade_id}. Venda cancelada."); final_signal = "HOLD"
                    if current_position is None:
                        logger.info(f"[EXEC] Enviando VENDA {asset_symbol} @ ~{current_price:.{price_precision}f} Vol:{trade_volume}")
                        sl = round(current_price*(1+sl_pct/100), price_precision) if sl_pct else None; tp = round(current_price*(1-tp_pct/100), price_precision) if tp_pct else None
                        res = provider.open_position(live_ticker, 'sell', trade_volume, sl_price=sl, tp_price=tp)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                             fp, tid = res.price, res.order; logger.info(f"[EXEC] VENDA OK {asset_symbol}: P={fp:.{price_precision}f}, T={tid}")
                             with self._lock: self.current_state[asset_symbol].update({"position": "VENDIDO", "entry_price": fp, "trade_id": tid, "sl_pct": sl_pct, "tp_pct": tp_pct})
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Vendido", "price": fp, "trade_id": tid})
                        else: rc = res.retcode if res else 'N/A'; cm = res.comment if res else 'N/A'; logger.error(f"[EXEC] FALHA VENDA {asset_symbol}: Ret={rc}, Com={cm}");
                        if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": f"Erro Venda ({rc})", "color": "red"})

            elif execution_mode == 'suggest' and final_signal != "HOLD":
                 sl = round(current_price*(1-sl_pct/100) if final_signal=="COMPRA" else current_price*(1+sl_pct/100), price_precision) if sl_pct else None
                 tp = round(current_price*(1+tp_pct/100) if final_signal=="COMPRA" else current_price*(1-tp_pct/100), price_precision) if tp_pct else None
                 logger.info(f"SUGESTÃO: {final_signal} {asset_symbol} @ {current_price:.{price_precision}f} (SL:{sl if sl else 'N/A'}, TP:{tp if tp else 'N/A'})")

        except Exception as e: logger.exception(f"Erro ciclo {asset_symbol}: {e}");
        if self.callback: self.callback({"type": "status", "asset": asset_symbol, "message": "Erro Ciclo", "color": "red"})

    def _run_monitor_thread(self):
        """(Thread) Loop principal: verifica SL/TP e processa candles."""
        logger.info("Thread monitor: Iniciando loop...")
        # Espera init terminar (importante)
        if self._init_thread and self._init_thread.is_alive():
             logger.info("Thread monitor: Aguardando inicialização...")
             self._init_thread.join()
             logger.info("Thread monitor: Inicialização concluída.")

        with self._lock: active = [k for k, v in self.asset_resources.items() if v and 'error' not in v]
        if not active:
             logger.warning("Nenhum ativo carregado. Thread monitor encerrando.")
             if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Parado (Vazio)", "color": "grey"})
             self._shutdown_mt5(); return

        logger.info(f"Thread monitor: Monitorando {len(active)} ativo(s)...")
        while not self._stop_event.is_set():
            try:
                assets_to_check = list(active) # Usa cópia
                for asset_symbol in assets_to_check:
                    if self._stop_event.is_set(): break
                    self._check_sl_tp(asset_symbol)
                    # Verifica se ainda está posicionado antes de processar candle
                    with self._lock: still_open = self.current_state.get(asset_symbol,{}).get("position") is not None
                    # Processa candle se não estiver posicionado ou se acabou de abrir (para pegar próximo sinal)
                    # Esta lógica pode precisar de ajuste fino dependendo da estratégia exata
                    # Processar sempre é mais simples, mas pode gerar sinais redundantes se já posicionado.
                    # Vamos processar sempre por enquanto.
                    self._process_asset(asset_symbol)

                if self._stop_event.wait(5): break # Pausa controlada

            except Exception as e: logger.critical(f"Erro CRÍTICO loop monitor: {e}", exc_info=True);
            if self._stop_event.wait(60): break # Pausa longa

        logger.info("Thread monitor: Loop principal encerrado.")
        self._shutdown_mt5()

    def start(self):
        """Inicia a thread de monitoramento, esperando a inicialização."""
        # Espera init terminar
        if self._init_thread and self._init_thread.is_alive():
            logger.info("Aguardando inicialização antes de iniciar monitoramento...")
            self._init_thread.join()

        # Verifica estado após init
        with self._lock: is_connected = self.mt5_provider is not None and self.mt5_provider.is_connected()
        if not self.is_trader_initialized or not is_connected:
             logger.error("LiveTrader não inicializado ou MT5 desconectado. Não é possível iniciar.")
             if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Falha Init/MT5", "color": "red"})
             return

        # Verifica se já está rodando
        if self._run_thread and self._run_thread.is_alive(): logger.warning("Monitoramento já ativo."); return

        with self._lock: active = [k for k,v in self.asset_resources.items() if v and 'error' not in v]
        if not active:
             logger.warning("Nenhum ativo carregado. Monitoramento não iniciado.")
             if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Vazio", "color": "orange"})
             return

        logger.info("Iniciando monitoramento de trades...")
        self._stop_event.clear()
        self._run_thread = Thread(target=self._run_monitor_thread, daemon=True, name="LiveTraderMonitorThread")
        self._run_thread.start()
        # REMOVIDO controle de botão daqui
        if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Monitorando...", "color": "green"})


    def stop(self):
        """Sinaliza para as threads pararem."""
        if self._stop_event.is_set(): return # Já está parando
        logger.info("Comando PARAR recebido. Sinalizando threads...")
        self._stop_event.set()

        threads = [self._init_thread, self._run_thread]
        for t in threads:
             if t and t.is_alive():
                  logger.info(f"Aguardando thread {t.name} finalizar...")
                  t.join(timeout=10)
                  if t.is_alive(): logger.warning(f"Thread {t.name} não finalizou.")
                  else: logger.info(f"Thread {t.name} finalizada.")

        self._shutdown_mt5() # Garante desconexão
        logger.info("LiveTrader parado.")
        if self.callback: self.callback({"type": "status", "asset": "GLOBAL", "message": "Parado", "color": "grey"})
        # REMOVIDO controle de botão daqui


    def _shutdown_mt5(self):
        """Desconecta do MT5 (thread-safe)."""
        with self._lock:
             provider = self.mt5_provider
             if provider:
                  logger.info("Encerrando conexão MT5...")
                  try:
                      if hasattr(provider, 'close_connection'): provider.close_connection()
                      else: mt5.shutdown() # Fallback
                      logger.info("Desligamento MT5 concluído.")
                  except Exception as e: logger.warning(f"Erro ao desconectar MT5: {e}")
                  finally: self.mt5_provider = None # Limpa referência

# --- Bloco Standalone ---
if __name__ == "__main__":
    def simple_console_callback(data):
        ts = datetime.now().strftime('%H:%M:%S')
        if data["type"] == "update": print(f"[{ts}] {data['asset']}: P={data['price']}, IA={data['ai_signal']}, SOK={data['setup_valid']}, Fin={data['final_signal']}, Pos={data.get('position','---')}")
        elif data["type"] == "position": print(f"[{ts}] {data['asset']}: POS -> {data.get('status','?')} @{data.get('price','?')} (ID:{data.get('trade_id','?')})")
        elif data["type"] == "status": print(f"[{ts}] STATUS ({data.get('asset','?')}) : {data.get('message','?')}")
        else: print(f"[{ts}] Callback: {data}")

    print("Iniciando Live Trader Standalone...")
    trader = LiveTrader(config_path='configs/main.yaml', callback=simple_console_callback)
    try:
        # Espera a inicialização terminar
        if trader._init_thread and trader._init_thread.is_alive():
            print("Aguardando inicialização...")
            trader._init_thread.join()
            print("Inicialização concluída.")

        # Inicia o monitoramento se init OK
        if trader.is_trader_initialized:
             with trader._lock: active = [k for k,v in trader.asset_resources.items() if v and 'error' not in v]
             if active:
                  trader.start()
                  while trader._run_thread and trader._run_thread.is_alive(): time.sleep(1) # Mantém vivo
             else: logger.warning("Nenhum ativo carregado.")
        else: logger.critical("Falha na inicialização.")

    except KeyboardInterrupt: print("\nCtrl+C. Parando...")
    except Exception as main_e: logger.critical(f"Erro não tratado: {main_e}", exc_info=True)
    finally:
        if 'trader' in locals() and trader: trader.stop()
        print("Live Trader Standalone finalizado.")