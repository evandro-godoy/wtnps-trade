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
        self.current_state = {} # Guarda estado como posição atual {asset: {"position": "COMPRADO"/"VENDIDO"/None, "entry_price": float}}
        
        self.setup_analyzer = SetupAnalyzer() # Instância do analisador de setups

        self._run_thread = None
        self._stop_event = Event()
        self._lock = Lock() # Lock para proteger acesso a dados compartilhados se necessário

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
             # Usa get_provider_instance para garantir consistência
             provider = get_provider_instance("MetaTrader5")
             if isinstance(provider, MetaTraderProvider):
                 self.mt5_provider = provider # Guarda a instância específica
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
        # Verifica se já está carregado
        if asset_symbol in self.asset_resources and self.asset_resources[asset_symbol].get('model'):
            logger.debug(f"Recursos para {asset_symbol} já carregados.")
            return self.asset_resources[asset_symbol]

        asset_config = self.config['assets'].get(asset_symbol)
        if not asset_config or not asset_config.get('live_trading', {}).get('enabled', False):
            logger.warning(f"Configuração ou live_trading não encontrado/habilitado para {asset_symbol}.")
            return None # Retorna None se não configurado ou desabilitado para live

        strategy_module_name = asset_config.get('strategy_module')
        strategy_class_name = asset_config.get('strategy_name')
        # Ticker usado para CARREGAR o modelo (geralmente o mesmo do treino)
        data_ticker = asset_config['data'].get('ticker', asset_symbol) 

        if not strategy_module_name or not strategy_class_name:
            logger.error(f"Módulo ou nome da classe da estratégia não definidos para {asset_symbol}")
            return None

        try:
            # Carrega a classe da Estratégia
            strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
            StrategyClass = getattr(strategy_module, strategy_class_name)
            strategy_instance = StrategyClass() # Instancia para ter acesso a métodos

            # --- Carregamento Unificado do Modelo ---
            model_path_prefix = str(self.models_dir / f"{asset_symbol}_prod")
            logger.info(f"Carregando modelo para {asset_symbol} via {strategy_class_name}.load() com prefixo: {model_path_prefix}")
            
            # Chama o método de classe load da ESTRATÉGIA
            model = StrategyClass.load(model_path_prefix)
            # ----------------------------------------

            resources = {
                'strategy_instance': strategy_instance,
                'strategy_class': StrategyClass,
                'model': model,
                'config': asset_config, # Guarda config específico do ativo
                'live_config': asset_config.get('live_trading', {}), # Config de live trading
                'trading_rules': asset_config.get('trading_rules', {}) # Regras de SL/TP
            }
            self.asset_resources[asset_symbol] = resources
            logger.info(f"Recursos para {asset_symbol} carregados (Modelo OK).")
            return resources

        except FileNotFoundError as e:
             logger.error(f"Erro ao carregar {asset_symbol}: Arquivo de modelo/scaler não encontrado. Verifique se o treino foi executado. Detalhes: {e}")
             self.asset_resources[asset_symbol] = {'error': 'Modelo não encontrado'}
             return None # Indica falha
        except (ImportError, AttributeError, TypeError, Exception) as e:
            logger.error(f"Erro crítico ao carregar recursos para {asset_symbol}: {e}", exc_info=True)
            self.asset_resources[asset_symbol] = {'error': str(e)}
            return None # Indica falha


    def _initialize_resources(self):
        """(Thread) Conecta ao MT5 e carrega recursos para todos os ativos habilitados."""
        logger.info("Thread init LiveTrader iniciada...")
        if not self._initialize_mt5():
            logger.error("Falha na inicialização do MT5. LiveTrader não pode continuar.")
            if self.callback:
                 self.callback({"type": "status", "asset": "GLOBAL", "message": "Erro MT5", "color": "red"})
            return # Aborta se MT5 falhar

        logger.info("Inicializando o LiveTrader Engine...")
        enabled_assets = []
        for asset_symbol, asset_config in self.config.get('assets', {}).items():
            # Carrega apenas se habilitado para live trading
            if asset_config.get('live_trading', {}).get('enabled', False):
                logger.info(f"Carregando recursos para {asset_symbol}...")
                if self._load_asset_resources(asset_symbol):
                     enabled_assets.append(asset_symbol)
                     # Inicializa estado e último candle
                     self.last_candle_time[asset_symbol] = None
                     self.current_state[asset_symbol] = {"position": None, "entry_price": None, "trade_id": None}
                else:
                     logger.error(f"Falha ao carregar recursos para {asset_symbol}. Este ativo será ignorado.")
                     if self.callback:
                         self.callback({"type": "status", "asset": asset_symbol, "message": "Erro Carga", "color": "red"})


        if enabled_assets:
            logger.info(f"LiveTrader Engine inicializado para: {', '.join(enabled_assets)}")
            if self.callback:
                 self.callback({"type": "status", "asset": "GLOBAL", "message": "Iniciado", "color": "green"})
                 for asset in enabled_assets: # Sinaliza assets carregados
                      self.callback({"type": "status", "asset": asset, "message": "Pronto", "color": "blue"})
        else:
            logger.warning("Nenhum ativo habilitado para live trading ou falha ao carregar recursos.")
            if self.callback:
                 self.callback({"type": "status", "asset": "GLOBAL", "message": "Vazio", "color": "orange"})
                 
        logger.info("Thread init LiveTrader concluída.")


    def _get_latest_candles(self, ticker: str, timeframe_obj: int, count: int) -> pd.DataFrame:
        """Busca os últimos 'count' candles do MT5."""
        if not self.mt5_provider or not self.mt5_provider.is_connected():
            logger.warning("MT5 não conectado ao buscar candles.")
            # Tenta reconectar silenciosamente? Ou só loga?
            if not self._initialize_mt5(): # Tenta reconectar
                 return pd.DataFrame() # Retorna vazio se falhar
                 
        try:
             # A função do provider já deve tratar o retorno do MT5
             candles = self.mt5_provider.get_latest_candles(ticker, timeframe_obj, count)
             return candles
        except Exception as e:
            logger.error(f"Erro ao buscar candles para {ticker} / {timeframe_obj}: {e}", exc_info=True)
            return pd.DataFrame()


    def _process_asset(self, asset_symbol: str):
        """Processa a lógica de trading para um único ativo."""
        with self._lock: # Garante que o acesso aos recursos seja seguro se houver outras threads
             resources = self.asset_resources.get(asset_symbol)
             
        if not resources or 'error' in resources:
            # logger.warning(f"Recursos para {asset_symbol} não disponíveis ou com erro. Pulando.")
            return # Não processa se os recursos não foram carregados

        live_config = resources['live_config']
        model = resources['model']
        strategy_instance: BaseStrategy = resources['strategy_instance']
        asset_config = resources['config'] # Config geral do ativo
        trading_rules = resources['trading_rules'] # Regras de SL/TP

        # --- Parâmetros de Live Trading ---
        live_ticker = live_config.get('ticker_order', asset_symbol) # Ticker para buscar dados/ordens
        timeframe_str = live_config.get('timeframe_str', 'M5')
        execution_mode = live_config.get('execution_mode', 'suggest') # 'suggest' or 'execute'
        trade_volume = live_config.get('trade_volume', 0.1)

        timeframe_obj = _get_mt5_timeframe_from_string(timeframe_str)
        if timeframe_obj is None:
            logger.error(f"Timeframe inválido '{timeframe_str}' para {asset_symbol}. Pulando.")
            return

        # --- Busca de Novos Candles ---
        # Busca um número suficiente de candles para features e lookback
        # Ex: lookback 60 + MA 200 => precisa de ~260. Buscar 500 por segurança.
        num_candles_to_fetch = 500 
        candles = self._get_latest_candles(live_ticker, timeframe_obj, num_candles_to_fetch)

        if candles.empty or len(candles) < getattr(model, 'lookback', 60): # Verifica se temos o mínimo para o lookback
            # logger.warning(f"Dados insuficientes ({len(candles)}) para {live_ticker} @ {timeframe_str}. Necessário: {getattr(model, 'lookback', 60)}.")
            return

        latest_candle_time = candles.index[-1].to_pydatetime() # Timestamp do último candle fechado

        # --- Verifica se é um novo candle ---
        last_processed_time = self.last_candle_time.get(asset_symbol)
        if last_processed_time is not None and latest_candle_time <= last_processed_time:
            # logger.debug(f"Nenhum candle novo para {asset_symbol} @ {timeframe_str} desde {last_processed_time}. Último recebido: {latest_candle_time}")
            return # Ainda não é um novo candle

        logger.info(f"Novo candle detectado para {asset_symbol} @ {timeframe_str}: {latest_candle_time}")
        
        # Atualiza o tempo do último candle processado *antes* de processar
        with self._lock:
            self.last_candle_time[asset_symbol] = latest_candle_time

        # --- Lógica de Decisão (Features, IA, Setup) ---
        try:
            # 1. Calcular Features nos dados recebidos
            data_with_features = strategy_instance.define_features(candles)

            # 2. Preparar Input para o Modelo (últimos 'lookback' pontos)
            feature_names = strategy_instance.get_feature_names()
            lookback = getattr(model, 'lookback', 60)
            
            # Pega as últimas 'lookback' linhas
            model_input_data = data_with_features.iloc[-lookback:] 
            X_predict = model_input_data[feature_names]

            # Validação rápida de NaNs no input final
            if X_predict.isnull().values.any():
                 logger.warning(f"NaNs encontrados no input do modelo para {asset_symbol} em {latest_candle_time}. Pulando decisão.")
                 # Preencher NaNs aqui é arriscado, melhor pular
                 return

            # 3. Obter Sinal da IA
            raw_prediction = model.predict(X_predict)
            ai_signal_code = int(raw_prediction[-1]) if isinstance(raw_prediction, np.ndarray) and len(raw_prediction) > 0 else int(raw_prediction) if isinstance(raw_prediction, (int, np.integer)) else 0
            
            # Mapeamento do sinal (ajuste conforme a saída do seu modelo)
            # Assumindo 1=COMPRA, 0=VENDA/HOLD (para LSTM binário)
            ai_signal = "COMPRA" if ai_signal_code == 1 else "VENDA" 
            
            logger.info(f"Sinal IA para {asset_symbol}: {ai_signal} (Code: {ai_signal_code})")

            # 4. Avaliar Setups Técnicos
            setup_rules = asset_config.get('setup', [])
            current_candle_features = data_with_features.iloc[-1:] # Pega a última linha como DataFrame
            
            setup_result = {"is_valid": True, "details": {}, "final_decision": ai_signal} # Default
            if setup_rules:
                 setup_result = self.setup_analyzer.evaluate_setups(current_candle_features, setup_rules, ai_signal)
                 logger.info(f"Setup {asset_symbol}: Válido={setup_result['is_valid']}, Decisão={setup_result['final_decision']}")
            
            final_signal = setup_result["final_decision"] # COMPRA, VENDA ou HOLD

            # Pega o preço de fechamento atual para referência e stops
            current_price = current_candle_features['close'].iloc[0]

            # --- Atualiza GUI (antes de executar a ordem) ---
            if self.callback:
                 gui_data = {
                     "type": "update",
                     "asset": asset_symbol,
                     "datetime": latest_candle_time.strftime('%Y-%m-%d %H:%M:%S'),
                     "price": current_price,
                     "ai_signal": ai_signal,
                     "setup_valid": setup_result["is_valid"],
                     "final_signal": final_signal,
                     "position": self.current_state.get(asset_symbol, {}).get("position", "---"),
                     # Adiciona detalhes do setup se existirem
                     "setup_details": setup_result.get("details", {}) 
                 }
                 self.callback(gui_data)


            # --- Lógica de Execução de Ordem ---
            current_position = self.current_state.get(asset_symbol, {}).get("position")
            order_result = None # Guarda resultado do envio de ordem

            if execution_mode == 'execute' and self.mt5_provider:
                if final_signal == "COMPRA" and current_position != "COMPRADO":
                    # Se estava vendido, fecha a venda antes de comprar
                    if current_position == "VENDIDO":
                        logger.info(f"Fechando posição VENDIDA em {asset_symbol} antes de comprar.")
                        close_result = self.mt5_provider.close_position(live_ticker, self.current_state[asset_symbol].get("trade_id"))
                        if close_result:
                             with self._lock:
                                  self.current_state[asset_symbol] = {"position": None, "entry_price": None, "trade_id": None}
                                  current_position = None # Atualiza estado local
                                  if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Fechado"})
                        else:
                             logger.error(f"Falha ao fechar posição VENDIDA em {asset_symbol}. Compra cancelada.")
                             final_signal = "HOLD" # Cancela a compra

                    # Abre a compra (se não estava comprado ou se fechou a venda)
                    if current_position is None:
                        logger.info(f"Executando ORDEM DE COMPRA para {asset_symbol} @ {current_price}, Vol: {trade_volume}")
                        # Calcula stops ANTES de enviar a ordem
                        sl_price = round(current_price * (1 - trading_rules.get('stop_loss_pct', 1)/100), 2) if trading_rules.get('stop_loss_pct') else None
                        tp_price = round(current_price * (1 + trading_rules.get('take_profit_pct', 1)/100), 2) if trading_rules.get('take_profit_pct') else None
                        
                        order_result = self.mt5_provider.open_position(
                             symbol=live_ticker, 
                             order_type='buy', 
                             volume=trade_volume,
                             sl_price=sl_price, # Passa SL
                             tp_price=tp_price  # Passa TP
                        )
                        if order_result and order_result.retcode == mt5.TRADE_RETCODE_DONE:
                             logger.info(f"COMPRA EXECUTADA para {asset_symbol}. Ticket: {order_result.order}")
                             with self._lock:
                                  self.current_state[asset_symbol] = {"position": "COMPRADO", "entry_price": order_result.price, "trade_id": order_result.order}
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Comprado", "price": order_result.price, "trade_id": order_result.order})
                        else:
                             logger.error(f"FALHA AO EXECUTAR COMPRA para {asset_symbol}. Result: {order_result}")
                             if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": "Erro Compra", "color": "red"})


                elif final_signal == "VENDA" and current_position != "VENDIDO":
                    # Se estava comprado, fecha a compra antes de vender
                    if current_position == "COMPRADO":
                        logger.info(f"Fechando posição COMPRADA em {asset_symbol} antes de vender.")
                        close_result = self.mt5_provider.close_position(live_ticker, self.current_state[asset_symbol].get("trade_id"))
                        if close_result:
                             with self._lock:
                                 self.current_state[asset_symbol] = {"position": None, "entry_price": None, "trade_id": None}
                                 current_position = None
                                 if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Fechado"})
                        else:
                             logger.error(f"Falha ao fechar posição COMPRADA em {asset_symbol}. Venda cancelada.")
                             final_signal = "HOLD"

                    # Abre a venda
                    if current_position is None:
                        logger.info(f"Executando ORDEM DE VENDA para {asset_symbol} @ {current_price}, Vol: {trade_volume}")
                        # Calcula stops ANTES de enviar a ordem
                        sl_price = round(current_price * (1 + trading_rules.get('stop_loss_pct', 1)/100), 2) if trading_rules.get('stop_loss_pct') else None
                        tp_price = round(current_price * (1 - trading_rules.get('take_profit_pct', 1)/100), 2) if trading_rules.get('take_profit_pct') else None

                        order_result = self.mt5_provider.open_position(
                             symbol=live_ticker, 
                             order_type='sell', 
                             volume=trade_volume,
                             sl_price=sl_price, # Passa SL
                             tp_price=tp_price  # Passa TP
                        )
                        if order_result and order_result.retcode == mt5.TRADE_RETCODE_DONE:
                             logger.info(f"VENDA EXECUTADA para {asset_symbol}. Ticket: {order_result.order}")
                             with self._lock:
                                 self.current_state[asset_symbol] = {"position": "VENDIDO", "entry_price": order_result.price, "trade_id": order_result.order}
                             if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Vendido", "price": order_result.price, "trade_id": order_result.order})
                        else:
                             logger.error(f"FALHA AO EXECUTAR VENDA para {asset_symbol}. Result: {order_result}")
                             if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": "Erro Venda", "color": "red"})
                
                # --- Lógica para FECHAR posição se sinal for HOLD e estiver posicionado ---
                #    (OPCIONAL: dependendo da estratégia, pode querer manter a posição até sinal contrário)
                # elif final_signal == "HOLD" and current_position is not None:
                #     logger.info(f"Sinal HOLD recebido para {asset_symbol} enquanto estava {current_position}. Fechando posição.")
                #     close_result = self.mt5_provider.close_position(live_ticker, self.current_state[asset_symbol].get("trade_id"))
                #     if close_result:
                #          with self._lock:
                #               self.current_state[asset_symbol] = {"position": None, "entry_price": None, "trade_id": None}
                #          if self.callback: self.callback({"type":"position", "asset": asset_symbol, "status": "Fechado (Hold)"})
                #     else:
                #          logger.error(f"Falha ao fechar posição {current_position} em {asset_symbol} devido a sinal HOLD.")
                #          if self.callback: self.callback({"type":"status", "asset": asset_symbol, "message": "Erro Fechar (Hold)", "color": "red"})


            elif execution_mode == 'suggest':
                 if final_signal != "HOLD":
                      logger.info(f"SUGESTÃO ({execution_mode}): {final_signal} para {asset_symbol} @ {current_price}")
                      # Calcula stops para mostrar na sugestão
                      sl_price, tp_price = None, None
                      if trading_rules.get('stop_loss_pct'):
                           sl_price = round(current_price * (1 - trading_rules['stop_loss_pct']/100) if final_signal == "COMPRA" else current_price * (1 + trading_rules['stop_loss_pct']/100), 2)
                      if trading_rules.get('take_profit_pct'):
                           tp_price = round(current_price * (1 + trading_rules['take_profit_pct']/100) if final_signal == "COMPRA" else current_price * (1 - trading_rules['take_profit_pct']/100), 2)
                      logger.info(f"--> Preços Sugeridos: SL={sl_price if sl_price else 'N/A'}, TP={tp_price if tp_price else 'N/A'}")


        except Exception as e:
            logger.error(f"Erro inesperado no ciclo de processamento para {asset_symbol}: {e}", exc_info=True)
            if self.callback:
                 self.callback({"type": "status", "asset": asset_symbol, "message": "Erro Ciclo", "color": "red"})


    def _run_monitor_thread(self):
        """(Thread) Loop principal que monitora novos candles e dispara o processamento."""
        logger.info("Iniciando thread monitor.")
        
        # Aguarda a inicialização dos recursos terminar
        self._init_thread.join() 
        logger.info("Inicialização concluída. Iniciando monitoramento de candles.")

        if not self.asset_resources:
             logger.warning("Nenhum ativo foi carregado com sucesso. Thread monitor encerrando.")
             if self.callback:
                  self.callback({"type": "status", "asset": "GLOBAL", "message": "Parado (Vazio)", "color": "grey"})
             return

        while not self._stop_event.is_set():
            try:
                # Itera sobre uma cópia das chaves para evitar problemas se o dict mudar
                assets_to_check = list(self.asset_resources.keys()) 
                
                for asset_symbol in assets_to_check:
                    # Verifica se o evento de parada foi setado DENTRO do loop
                    if self._stop_event.is_set():
                        break 
                        
                    # Pula ativos que tiveram erro no carregamento
                    if 'error' in self.asset_resources.get(asset_symbol, {}):
                        continue

                    # Processa o ativo (busca candle, decide, executa/sugere)
                    self._process_asset(asset_symbol)

                # Pausa antes da próxima verificação
                # O ideal é sincronizar com o início do próximo candle, mas um sleep curto funciona
                # Considera o timeframe mais curto entre os ativos monitorados?
                # Por simplicidade, um sleep fixo (ex: 5 segundos).
                time.sleep(5) 

            except Exception as e:
                 logger.error(f"Erro inesperado no loop da thread monitor: {e}", exc_info=True)
                 # Pausa mais longa em caso de erro para evitar spam de logs
                 time.sleep(30) 

        logger.info("Thread monitor encerrada.")
        self._shutdown_mt5() # Desconecta do MT5 ao final


    def start(self):
        """Inicia a thread de monitoramento."""
        if self._run_thread is not None and self._run_thread.is_alive():
            logger.warning("Thread monitor já está em execução.")
            return
            
        self._stop_event.clear() # Garante que o evento de parada esteja limpo
        self._run_thread = Thread(target=self._run_monitor_thread, daemon=True)
        self._run_thread.start()
        logger.info("LiveTrader iniciado.")

    def stop(self):
        """Sinaliza para a thread de monitoramento parar."""
        logger.info("Recebido comando para parar LiveTrader...")
        self._stop_event.set() # Sinaliza para a thread parar
        
        # Espera a thread de monitoramento terminar (com timeout)
        if self._run_thread is not None and self._run_thread.is_alive():
             logger.info("Aguardando thread monitor finalizar...")
             self._run_thread.join(timeout=10) # Espera até 10 segundos
             if self._run_thread.is_alive():
                  logger.warning("Thread monitor não finalizou no tempo esperado.")
             else:
                  logger.info("Thread monitor finalizada.")

        # A desconexão do MT5 agora ocorre no final da _run_monitor_thread
        # self._shutdown_mt5() # Movido para o final da thread
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
    
    # Callback simples para imprimir atualizações no console (exemplo)
    def simple_console_callback(data):
        if data["type"] == "update":
             print(f"[{data['datetime']}] {data['asset']}: Preço={data['price']}, IA={data['ai_signal']}, SetupOK={data['setup_valid']}, Final={data['final_signal']}, Pos={data['position']}")
        elif data["type"] == "position":
             print(f"[{datetime.now()}] {data['asset']}: Posição Atualizada -> {data['status']} @ {data.get('price', 'N/A')} (ID: {data.get('trade_id', 'N/A')})")
        elif data["type"] == "status":
             print(f"[{datetime.now()}] STATUS ({data['asset']}): {data['message']}")
        else:
             print(f"Callback Recebido: {data}")

    print("Iniciando Live Trader Standalone...")
    # Cria instância com o callback
    trader = LiveTrader(config_path='configs/main.yaml', callback=simple_console_callback) 
    
    try:
        # Inicia o monitoramento (a inicialização ocorre em background)
        trader.start() 
        
        # Mantém o script principal rodando enquanto a thread monitora
        while True:
            time.sleep(1) 
            # Aqui você poderia adicionar lógica para comandos externos, etc.
            # Ex: input("Pressione Enter para parar...\n") break

    except KeyboardInterrupt:
        print("\nInterrupção recebida (Ctrl+C). Parando Live Trader...")
    finally:
        # Garante que o trader seja parado corretamente ao sair
        trader.stop() 
        print("Live Trader Standalone finalizado.")