# src/live_trader.py

import yaml
import logging
from pathlib import Path
import importlib
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
# Removido: from tensorflow.keras.models import load_model
# Removido: import joblib
import MetaTrader5 as mt5 # Essencial para MT5
from threading import Thread, Lock, Event # Para execução em background e controle

# Importações internas do projeto
from src.data_handler.provider import get_provider_instance, BaseDataProvider, MetaTraderProvider
from src.strategies.base import BaseStrategy # Importa a classe base
from src.setups.analyzer import SetupAnalyzer # Para análise de setups

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()]) # Garante output no console
logger = logging.getLogger(__name__)

# --- Função auxiliar para conversão de timeframe (COPIADA) ---
def _get_mt5_timeframe_from_string(tf_str: str):
    """Converte string de timeframe para constante MT5."""
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
    }
    tf_constant = tf_map.get(tf_str.upper(), None)
    if tf_constant is None:
         logging.warning(f"Timeframe '{tf_str}' não mapeado ou inválido.")
    return tf_constant

# --- Classe LiveTrader ---

class LiveTrader:
    """
    Motor principal para execução de estratégias de trading em tempo real
    conectado ao MetaTrader 5.
    """
    def __init__(self, config_path: str = 'configs/main.yaml', callback=None):
        self.config_path = config_path
        self.config = self._load_config()
        self.models_dir = Path(self.config.get('global_settings', {}).get('models_directory', 'models'))
        self.callback = callback # Callback para atualizar a GUI

        self.mt5_provider = None # Instância específica do MT5 provider
        self.asset_resources = {} # Cache de modelos, estratégias, etc.
        self.last_candle_time = {} # Guarda o timestamp do último candle processado por ativo/tf
        self.current_state = {} # Guarda estado como posição atual {asset: {"position": "COMPRADO"/"VENDIDO"/None, "entry_price": float, "trade_id": int}}
        
        self.setup_analyzer = SetupAnalyzer() # Instância do analisador de setups

        self._run_thread = None
        self._stop_event = Event()
        self._lock = Lock() # Lock para proteger acesso a dados compartilhados

        # Inicializa conexão MT5 e carrega recursos em uma thread separada
        self._init_thread = Thread(target=self._initialize_resources, daemon=True)
        self._init_thread.start()


    def _load_config(self):
        """Carrega o arquivo de configuração YAML."""
        logger.info(f"Carregando configuração de: {self.config_path}")
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Arquivo de configuração não encontrado: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Erro ao carregar configuração YAML: {e}")
            raise
            
    def _initialize_mt5(self):
         """Inicializa a conexão com o MetaTrader 5."""
         logger.info("Tentando inicializar conexão com o MetaTrader 5...")
         try:
             provider = get_provider_instance("MetaTrader5")
             if isinstance(provider, MetaTraderProvider):
                 self.mt5_provider = provider 
                 logger.info("Conectado ao MetaTrader 5.")
                 return True
             else:
                 logger.error("Falha ao obter instância correta do MetaTraderProvider.")
                 return False
         except Exception as e:
             logger.error(f"Falha ao conectar com MetaTrader 5: {e}", exc_info=True)
             self.mt5_provider = None
             return False


    def _load_asset_resources(self, asset_symbol: str):
        """
        Carrega os recursos necessários (modelo, estratégia) para um ativo.
        Utiliza a interface unificada BaseStrategy.load().
        """
        if asset_symbol in self.asset_resources and self.asset_resources[asset_symbol].get('model'):
            logger.debug(f"Recursos para {asset_symbol} já carregados.")
            return self.asset_resources[asset_symbol]

        asset_config = self.config['assets'].get(asset_symbol)
        if not asset_config or not asset_config.get('live_trading', {}).get('enabled', False):
            logger.debug(f"Configuração ou live_trading não encontrado/habilitado para {asset_symbol}.")
            return None 

        strategy_module_name = asset_config.get('strategy_module')
        strategy_class_name = asset_config.get('strategy_name')
        # Ticker usado para CARREGAR o modelo
        # data_ticker = asset_config['data'].get('ticker', asset_symbol) # Removido, nome do arquivo usa asset_symbol

        if not strategy_module_name or not strategy_class_name:
            logger.error(f"Módulo ou nome da classe da estratégia não definidos para {asset_symbol}")
            return None

        try:
            strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
            StrategyClass = getattr(strategy_module, strategy_class_name)
            strategy_instance = StrategyClass() 

            # Carregamento Unificado do Modelo 
            model_path_prefix = str(self.models_dir / f"{asset_symbol}_prod")
            logger.info(f"Carregando modelo para {asset_symbol} via {strategy_class_name}.load() com prefixo: {model_path_prefix}")
            
            model = StrategyClass.load(model_path_prefix)

            resources = {
                'strategy_instance': strategy_instance,
                'strategy_class': StrategyClass,
                'model': model,
                'config': asset_config, 
                'live_config': asset_config.get('live_trading', {}), 
                'trading_rules': asset_config.get('trading_rules', {}) 
            }
            self.asset_resources[asset_symbol] = resources
            logger.info(f"Recursos para {asset_symbol} carregados (Modelo OK).")
            return resources

        except FileNotFoundError as e:
             logger.error(f"Erro ao carregar {asset_symbol}: Arquivo de modelo/scaler não encontrado ({model_path_prefix}...). Verifique se o treino foi executado. Detalhes: {e}")
             self.asset_resources[asset_symbol] = {'error': 'Modelo não encontrado'}
             return None 
        except (ImportError, AttributeError, TypeError, Exception) as e:
            logger.error(f"Erro crítico ao carregar recursos para {asset_symbol}: {e}", exc_info=True)
            self.asset_resources[asset_symbol] = {'error': str(e)}
            return None


    def _initialize_resources(self):
        """(Thread) Conecta ao MT5 e carrega recursos para todos os ativos habilitados."""
        logger.info("Thread init LiveTrader iniciada...")
        if not self._initialize_mt5():
            logger.error("Falha na inicialização do MT5. LiveTrader não pode continuar.")
            if self.callback:
                 self.callback({"type": "status", "asset": "GLOBAL", "message": "Erro MT5", "color": "red"})
            return 

        logger.info("Inicializando o LiveTrader Engine...")
        enabled_assets = []
        for asset_symbol, asset_config in self.config.get('assets', {}).items():
            if asset_config.get('live_trading', {}).get('enabled', False):
                logger.info(f"Carregando recursos para {asset_symbol}...")
                if self._load_asset_resources(asset_symbol):
                     enabled_assets.append(asset_symbol)
                     # Inicializa estado e último candle
                     self.last_candle_time[asset_symbol] = None
                     # Bloqueia para garantir escrita segura no estado compartilhado
                     with self._lock: 
                          self.current_state[asset_symbol] = {"position": None, "entry_price": None, "trade_id": None}
                else:
                     logger.error(f"Falha ao carregar recursos para {asset_symbol}. Este ativo será ignorado.")
                     if self.callback:
                         self.callback({"type": "status", "asset": asset_symbol, "message": "Erro Carga", "color": "red"})


        if enabled_assets:
            logger.info(f"LiveTrader Engine inicializado para: {', '.join(enabled_assets)}")
            if self.callback:
                 self.callback({"type": "status", "asset": "GLOBAL", "message": "Iniciado", "color": "green"})
                 for asset in enabled_assets: 
                      self.callback({"type": "status", "asset": asset, "message": "Pronto", "color": "blue"})
        else:
            logger.warning("Nenhum ativo habilitado para live trading ou falha ao carregar recursos.")
            if self.callback:
                 self.callback({"type": "status", "asset": "GLOBAL", "message": "Vazio", "color": "orange"})
                 
        logger.info("Thread init LiveTrader concluída.")


    def _get_latest_candles(self, ticker: str, timeframe_obj: int, count: int) -> pd.DataFrame:
        """Busca os últimos 'count' candles do MT5."""
        if not self.mt5_provider or not self.mt5_provider.is_connected():
            logger.warning("MT5 não conectado ao buscar candles. Tentando reconectar...")
            if not self._initialize_mt5(): 
                 logger.error("Falha ao reconectar MT5.")
                 return pd.DataFrame() 
                 
        try:
             candles = self.mt5_provider.get_latest_candles(ticker, timeframe_obj, count)
             return candles
        except Exception as e:
            logger.error(f"Erro ao buscar candles para {ticker} / {timeframe_obj}: {e}", exc_info=False) # Menos verboso no log
            return pd.DataFrame()


    def _process_asset(self, asset_symbol: str):
        """Processa a lógica de trading para um único ativo."""
        # Acessa recursos sem lock aqui, pois _load_asset_resources já tratou
        resources = self.asset_resources.get(asset_symbol)
             
        if not resources or 'error' in resources:
            # logger.debug(f"Recursos para {asset_symbol} não disponíveis. Pulando.") # Debug em vez de warning
            return 

        live_config = resources['live_config']
        model = resources['model']
        strategy_instance: BaseStrategy = resources['strategy_instance']
        asset_config = resources['config'] 
        trading_rules = resources['trading_rules'] 

        # --- Parâmetros de Live Trading ---
        live_ticker = live_config.get('ticker_order', asset_symbol) 
        timeframe_str = live_config.get('timeframe_str', 'M5')
        execution_mode = live_config.get('execution_mode', 'suggest') 
        trade_volume = live_config.get('trade_volume', 0.1)

        timeframe_obj = _get_mt5_timeframe_from_string(timeframe_str)
        if timeframe_obj is None:
            logger.error(f"Timeframe inválido '{timeframe_str}' para {asset_symbol}. Pulando.")
            return

        # --- Busca de Novos Candles ---
        num_candles_to_fetch = 500 # Suficiente para lookback e indicadores comuns
        candles = self._get_latest_candles(live_ticker, timeframe_obj, num_candles_to_fetch)

        min_required_candles = getattr(model, 'lookback', 1) + 1 # Precisa de lookback + candle atual
        if candles.empty or len(candles) < min_required_candles: 
            # logger.debug(f"Dados insuficientes ({len(candles)}) para {live_ticker} @ {timeframe_str}. Necessário: {min_required_candles}.")
            return

        latest_candle_time = candles.index[-1].to_pydatetime() 

        # --- Verifica se é um novo candle ---
        # Acesso thread-safe ao dicionário compartilhado
        with self._lock:
            last_processed_time = self.last_candle_time.get(asset_symbol)

        if last_processed_time is not None and latest_candle_time <= last_processed_time:
            # logger.debug(f"Nenhum candle novo para {asset_symbol} @ {timeframe_str}. Último: {latest_candle_time}")
            return # Candle já processado

        logger.info(f"Novo candle detectado para {asset_symbol} @ {timeframe_str}: {latest_candle_time}")
        
        # Atualiza o tempo do último candle processado *antes* de processar (thread-safe)
        with self._lock:
            self.last_candle_time[asset_symbol] = latest_candle_time

        # --- Lógica de Decisão (Features, IA, Setup) ---
        try:
            # 1. Calcular Features
            data_with_features = strategy_instance.define_features(candles)

            # 2. Preparar Input para o Modelo (últimos 'lookback' pontos)
            feature_names = strategy_instance.get_feature_names()
            lookback = getattr(model, 'lookback', 1) # Usa 1 se não definido
            
            # Garante que temos dados suficientes após calcular features
            if len(data_with_features) < lookback:
                 logger.warning(f"Dados insuficientes ({len(data_with_features)}) após cálculo de features para lookback ({lookback}) em {asset_symbol}. Pulando.")
                 return

            model_input_data = data_with_features.iloc[-lookback:] 
            X_predict = model_input_data[feature_names]

            if X_predict.isnull().values.any():
                 logger.warning(f"NaNs encontrados no input do modelo para {asset_symbol} em {latest_candle_time}. Pulando decisão.")
                 return

            # 3. Obter Sinal da IA
            raw_prediction = model.predict(X_predict)
            ai_signal_code = int(raw_prediction[-1]) if isinstance(raw_prediction, np.ndarray) and len(raw_prediction) > 0 else int(raw_prediction) if isinstance(raw_prediction, (int, np.integer)) else 0
            ai_signal = "COMPRA" if ai_signal_code == 1 else "VENDA" # Ajuste conforme necessário
            logger.info(f"Sinal IA para {asset_symbol}: {ai_signal} (Code: {ai_signal_code})")

            # 4. **INTEGRAÇÃO SETUP**: Avaliar Setups Técnicos
            setup_rules = asset_config.get('setup', [])
            current_candle_features = data_with_features.iloc[-1:] # Última linha como DataFrame
            
            setup_result = {"is_valid": True, "details": {}, "final_decision": ai_signal} # Default: válido se sem regras
            if setup_rules:
                 try:
                      setup_result = self.setup_analyzer.evaluate_setups(current_candle_features, setup_rules, ai_signal)
                      logger.info(f"Setup {asset_symbol}: Válido={setup_result['is_valid']}, Decisão={setup_result['final_decision']}")
                 except Exception as e_setup:
                      logger.error(f"Erro ao avaliar setups para {asset_symbol}: {e_setup}", exc_info=True)
                      setup_result = {"is_valid": False, "details": {"erro": str(e_setup)}, "final_decision": "HOLD"} # Invalida em caso de erro no setup
            
            # **Usa o sinal FINAL após avaliação do setup**
            final_signal = setup_result["final_decision"] 
            # -----------------------------------------------

            current_price = current_candle_features['close'].iloc[0]
            price_precision = asset_config.get('price_precision', 2)

            # --- Atualiza GUI (com informação do setup) ---
            if self.callback:
                 # Acesso thread-safe ao estado atual
                 with self._lock:
                      current_pos_display = self.current_state.get(asset_symbol, {}).get("position", "---")
                 
                 gui_data = {
                     "type": "update",
                     "asset": asset_symbol,
                     "datetime": latest_candle_time.strftime('%Y-%m-%d %H:%M:%S'),
                     "price": round(current_price, price_precision),
                     "ai_signal": ai_signal, # Mostra sinal original da IA
                     "setup_valid": setup_result["is_valid"], # Informa se o setup validou
                     "final_signal": final_signal, # Mostra sinal após setup
                     "position": current_pos_display, # Posição atual
                     "setup_details": setup_result.get("details", {}) 
                 }
                 self.callback(gui_data)

            # --- Lógica de Execução de Ordem (baseada no final_signal) ---
            # Acesso thread-safe ao estado atual
            with self._lock:
                 current_position = self.current_state.get(asset_symbol, {}).get("position")
                 current_trade_id = self.current_state.get(asset_symbol, {}).get("trade_id")

            order_result = None 

            if execution_mode == 'execute' and self.mt5_provider:
                # Se sinal FINAL for COMPRA e não estiver comprado
                if final_signal == "COMPRA" and current_position != "COMPRADO":
                    # Fecha venda se existir
                    if current_position == "VENDIDO":
                        logger.info(f"[EXEC] Fechando VENDA em {asset_symbol} (ID: {current_trade_id}) antes de comprar.")
                        close_result = self.mt5_provider.close_position(live_ticker, current_trade_id)
                        if close_result:
                             with self._lock: # Atualiza estado global
                                  self.current_state[asset_symbol] = {"position": None, "entry_price": None, "trade_id": None}
                                  current_position = None # Atualiza estado local para próxima verificação
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Fechado"})
                             logger.info(f"[EXEC] Posição VENDIDA {current_trade_id} fechada.")
                        else:
                             logger.error(f"[EXEC] Falha ao fechar VENDA {current_trade_id} em {asset_symbol}. Compra cancelada.")
                             final_signal = "HOLD" # Cancela a intenção de comprar

                    # Abre compra se não houver posição (ou a venda foi fechada)
                    if current_position is None:
                        logger.info(f"[EXEC] Enviando COMPRA {asset_symbol} @ {current_price:.{price_precision}f}, Vol: {trade_volume}")
                        sl_price = round(current_price * (1 - trading_rules.get('stop_loss_pct', 1)/100), price_precision) if trading_rules.get('stop_loss_pct') else None
                        tp_price = round(current_price * (1 + trading_rules.get('take_profit_pct', 1)/100), price_precision) if trading_rules.get('take_profit_pct') else None
                        
                        order_result = self.mt5_provider.open_position(live_ticker, 'buy', trade_volume, sl_price=sl_price, tp_price=tp_price)
                        
                        if order_result and order_result.retcode == mt5.TRADE_RETCODE_DONE:
                             filled_price = order_result.price # Preço que foi executado
                             trade_id = order_result.order # ID da ordem/posição
                             logger.info(f"[EXEC] COMPRA EXECUTADA {asset_symbol}. Preço: {filled_price:.{price_precision}f}, Ticket: {trade_id}")
                             with self._lock: # Atualiza estado global
                                  self.current_state[asset_symbol] = {"position": "COMPRADO", "entry_price": filled_price, "trade_id": trade_id}
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Comprado", "price": filled_price, "trade_id": trade_id})
                        else:
                             retcode = order_result.retcode if order_result else 'N/A'
                             comment = order_result.comment if order_result else 'N/A'
                             logger.error(f"[EXEC] FALHA AO EXECUTAR COMPRA {asset_symbol}. RetCode: {retcode}, Comentário: {comment}")
                             if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": f"Erro Compra ({retcode})", "color": "red"})

                # Se sinal FINAL for VENDA e não estiver vendido
                elif final_signal == "VENDA" and current_position != "VENDIDO":
                    # Fecha compra se existir
                    if current_position == "COMPRADO":
                        logger.info(f"[EXEC] Fechando COMPRA em {asset_symbol} (ID: {current_trade_id}) antes de vender.")
                        close_result = self.mt5_provider.close_position(live_ticker, current_trade_id)
                        if close_result:
                             with self._lock:
                                 self.current_state[asset_symbol] = {"position": None, "entry_price": None, "trade_id": None}
                                 current_position = None 
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Fechado"})
                             logger.info(f"[EXEC] Posição COMPRADA {current_trade_id} fechada.")
                        else:
                             logger.error(f"[EXEC] Falha ao fechar COMPRA {current_trade_id} em {asset_symbol}. Venda cancelada.")
                             final_signal = "HOLD"

                    # Abre venda se não houver posição
                    if current_position is None:
                        logger.info(f"[EXEC] Enviando VENDA {asset_symbol} @ {current_price:.{price_precision}f}, Vol: {trade_volume}")
                        sl_price = round(current_price * (1 + trading_rules.get('stop_loss_pct', 1)/100), price_precision) if trading_rules.get('stop_loss_pct') else None
                        tp_price = round(current_price * (1 - trading_rules.get('take_profit_pct', 1)/100), price_precision) if trading_rules.get('take_profit_pct') else None

                        order_result = self.mt5_provider.open_position(live_ticker, 'sell', trade_volume, sl_price=sl_price, tp_price=tp_price)
                        
                        if order_result and order_result.retcode == mt5.TRADE_RETCODE_DONE:
                             filled_price = order_result.price
                             trade_id = order_result.order
                             logger.info(f"[EXEC] VENDA EXECUTADA {asset_symbol}. Preço: {filled_price:.{price_precision}f}, Ticket: {trade_id}")
                             with self._lock:
                                 self.current_state[asset_symbol] = {"position": "VENDIDO", "entry_price": filled_price, "trade_id": trade_id}
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Vendido", "price": filled_price, "trade_id": trade_id})
                        else:
                             retcode = order_result.retcode if order_result else 'N/A'
                             comment = order_result.comment if order_result else 'N/A'
                             logger.error(f"[EXEC] FALHA AO EXECUTAR VENDA {asset_symbol}. RetCode: {retcode}, Comentário: {comment}")
                             if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": f"Erro Venda ({retcode})", "color": "red"})

            # Modo Sugestão
            elif execution_mode == 'suggest':
                 if final_signal != "HOLD":
                      logger.info(f"SUGESTÃO ({execution_mode}): {final_signal} para {asset_symbol} @ {current_price:.{price_precision}f}")
                      sl_price, tp_price = None, None
                      if trading_rules.get('stop_loss_pct'):
                           sl_price = round(current_price * (1 - trading_rules['stop_loss_pct']/100) if final_signal == "COMPRA" else current_price * (1 + trading_rules['stop_loss_pct']/100), price_precision)
                      if trading_rules.get('take_profit_pct'):
                           tp_price = round(current_price * (1 + trading_rules['take_profit_pct']/100) if final_signal == "COMPRA" else current_price * (1 - trading_rules['take_profit_pct']/100), price_precision)
                      logger.info(f"--> Preços Sugeridos: SL={sl_price if sl_price else 'N/A'}, TP={tp_price if tp_price else 'N/A'}")

        except Exception as e:
            logger.error(f"Erro inesperado no ciclo de processamento para {asset_symbol}: {e}", exc_info=True)
            if self.callback:
                 self.callback({"type": "status", "asset": asset_symbol, "message": "Erro Ciclo", "color": "red"})


    def _run_monitor_thread(self):
        """(Thread) Loop principal que monitora novos candles e dispara o processamento."""
        logger.info("Iniciando thread monitor.")
        
        self._init_thread.join() 
        logger.info("Inicialização concluída. Iniciando monitoramento de candles.")

        # Verifica se algum ativo foi carregado
        with self._lock:
             active_assets = [k for k, v in self.asset_resources.items() if 'error' not in v]

        if not active_assets:
             logger.warning("Nenhum ativo foi carregado com sucesso. Thread monitor encerrando.")
             if self.callback:
                  self.callback({"type": "status", "asset": "GLOBAL", "message": "Parado (Vazio)", "color": "grey"})
             return

        while not self._stop_event.is_set():
            try:
                # Usa a lista de ativos ativos obtida após inicialização
                for asset_symbol in active_assets:
                    if self._stop_event.is_set(): break 
                    self._process_asset(asset_symbol)

                # Pausa antes da próxima verificação
                sleep_time = 5 # Segundos
                self._stop_event.wait(sleep_time) # Espera ou até ser interrompido

            except Exception as e:
                 logger.error(f"Erro inesperado no loop da thread monitor: {e}", exc_info=True)
                 self._stop_event.wait(30) # Pausa maior em caso de erro

        logger.info("Thread monitor encerrada.")
        self._shutdown_mt5() 


    def start(self):
        """Inicia a thread de monitoramento."""
        if self._run_thread is not None and self._run_thread.is_alive():
            logger.warning("Thread monitor já está em execução.")
            return
            
        self._stop_event.clear() 
        self._run_thread = Thread(target=self._run_monitor_thread, daemon=True)
        self._run_thread.start()
        logger.info("LiveTrader iniciado.")

    def stop(self):
        """Sinaliza para a thread de monitoramento parar."""
        logger.info("Recebido comando para parar LiveTrader...")
        self._stop_event.set() 
        
        if self._run_thread is not None and self._run_thread.is_alive():
             logger.info("Aguardando thread monitor finalizar...")
             self._run_thread.join(timeout=10) 
             if self._run_thread.is_alive():
                  logger.warning("Thread monitor não finalizou no tempo esperado.")
             else:
                  logger.info("Thread monitor finalizada.")
        
        logger.info("LiveTrader parado.")
        if self.callback:
             self.callback({"type": "status", "asset": "GLOBAL", "message": "Parado", "color": "grey"})


    def _shutdown_mt5(self):
        """Desconecta do MetaTrader 5."""
        if self.mt5_provider:
             logger.info("Encerrando conexão do LiveTrader com o MetaTrader 5...")
             try:
                 self.mt5_provider.close_connection()
                 logger.info("Desligamento da conexão MT5 concluído.")
             except Exception as e:
                  logger.warning(f"Erro ao desconectar do MT5: {e}")
             finally:
                  self.mt5_provider = None


# --- Bloco de execução principal (para rodar standalone) ---

if __name__ == "__main__":
    
    def simple_console_callback(data):
        """Callback simples para imprimir atualizações no console."""
        ts = datetime.now().strftime('%H:%M:%S')
        if data["type"] == "update":
             print(f"[{ts}] {data['asset']}: Preço={data['price']}, IA={data['ai_signal']}, SetupOK={data['setup_valid']}, Final={data['final_signal']}, Pos={data['position']}")
        elif data["type"] == "position":
             print(f"[{ts}] {data['asset']}: Posição Atualizada -> {data['status']} @ {data.get('price', 'N/A')} (ID: {data.get('trade_id', 'N/A')})")
        elif data["type"] == "status":
             print(f"[{ts}] STATUS ({data['asset']}): {data['message']}")
        else:
             print(f"[{ts}] Callback: {data}")

    print("Iniciando Live Trader Standalone...")
    trader = LiveTrader(config_path='configs/main.yaml', callback=simple_console_callback) 
    
    try:
        trader.start() 
        # Mantém o script principal rodando
        while True:
             # Verifica se a thread de monitoramento ainda está ativa
             if trader._run_thread is None or not trader._run_thread.is_alive():
                  logger.warning("Thread monitor não está mais ativa. Encerrando.")
                  break
             time.sleep(1) 

    except KeyboardInterrupt:
        print("\nInterrupção recebida (Ctrl+C). Parando Live Trader...")
    finally:
        trader.stop() 
        print("Live Trader Standalone finalizado.")