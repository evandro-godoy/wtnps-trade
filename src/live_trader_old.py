import yaml
import logging
import time
from pathlib import Path
import importlib
import MetaTrader5 as mt5

from src.data_handler.provider import MetaTraderProvider
from src.strategies.lstm import KerasLSTMWrapper

class LiveTrader:
    def __init__(self, config_path="configs/main.yaml"):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        
        # Armazena a raiz do projeto ---
        self.project_root = Path(__file__).parent.parent
        absolute_config_path = self.project_root / config_path

        try:
            with open(absolute_config_path, 'r') as file:
                self.config = yaml.safe_load(file)
        except FileNotFoundError:
            # Fallback para quando executado de um notebook
            self.project_root = Path.cwd() # Assume que a raiz é o diretório do notebook
            absolute_config_path = self.project_root / config_path
            with open(absolute_config_path, 'r') as file:
                self.config = yaml.safe_load(file)

        self.live_config = self.config['live_trading']
        self.ticker = self.config['data_settings']['ticker']
        self.provider = MetaTraderProvider()
        self.ticker_order = self.config['live_trading']['ticker_order']

        # 3. Carregar a estratégia dinamicamente
        try:
            strategy_name = self.config['backtest_settings']['strategy_name']
            module_path = f"src.strategies.{self.config['backtest_settings']['strategy_module']}"
            strategy_module = importlib.import_module(module_path)
            StrategyClass = getattr(strategy_module, strategy_name)
            strategy_instance = StrategyClass()
        except (ImportError, AttributeError) as e:
            logging.error(f"Não foi possível carregar a estratégia. Erro: {e}")
            return
        
        self.strategy = strategy_instance
        self.model = None
        self.current_position = None
        self.timeframe_seconds = self._get_timeframe_seconds()

    def _get_timeframe_seconds(self):
        tf_map = { mt5.TIMEFRAME_M1: 60, mt5.TIMEFRAME_M5: 300, mt5.TIMEFRAME_H1: 3600, mt5.TIMEFRAME_D1: 86400 }
        return tf_map.get(self.live_config['timeframe'], 86400)

    def initialize(self):
        """Conecta ao MT5 e carrega o modelo pré-treinado usando caminhos absolutos."""
        logging.info("Inicializando o robô trader...")
        if not mt5.initialize():
            logging.error(f"Falha na inicialização do MetaTrader 5: {mt5.last_error()}")
            return False
        
        # Constrói os caminhos absolutos para o modelo e o scaler ---
        relative_model_path = self.live_config['model_path']
        relative_scaler_path = self.live_config['scaler_path']
        
        absolute_model_path = self.project_root / relative_model_path
        absolute_scaler_path = self.project_root / relative_scaler_path
        
        self.model = KerasLSTMWrapper.load_model(absolute_model_path, absolute_scaler_path)
        logging.info("Robô inicializado com sucesso.")
        return True

    def run(self):
        """Inicia o loop principal do robô."""
        if not self.initialize():
            return

        logging.info(f"Iniciando o loop de trading para o ativo {self.ticker} no timeframe {self.live_config['timeframe']}.")
        
        while True:
            try:
                # 1. Buscar dados recentes (suficientes para os indicadores)
                # A EMA de 200 é nosso maior indicador, então buscamos mais que isso.
                latest_data = self.provider.get_latest_rates(self.ticker, 300, self.live_config['timeframe'])
                
                if latest_data.empty:
                    logging.warning("Não foi possível obter dados recentes. Aguardando próximo ciclo.")
                    time.sleep(self.timeframe_seconds)
                    continue

                # 2. Gerar features
                featured_data = self.strategy.define_features(latest_data)
                X_live = featured_data[self.strategy.get_feature_names()].dropna()
                
                if X_live.empty:
                    logging.info("Aguardando dados suficientes para gerar features...")
                    time.sleep(self.timeframe_seconds)
                    continue

                # 3. Fazer a previsão (sinal)
                signal = self.model.predict(X_live)[-1] # Pega a última predição
                logging.info(f"Sinal gerado: {'COMPRA' if signal == 1 else 'VENDA'}")

                # 4. Lógica de decisão
                # (Simplificado: só opera se não houver posição aberta)
                if self.current_position is None:
                    if signal == 1: # Sinal de Compra
                        self._execute_trade('BUY')
                    elif signal == 0: # Sinal de Venda
                        self._execute_trade('SELL')
                else:
                    logging.info(f"Já existe uma posição aberta ({self.current_position}). Nenhuma nova ordem será enviada.")

                # Aguarda o próximo candle
                logging.info(f"Aguardando {self.timeframe_seconds / 60:.1f} minutos para o próximo candle...")
                time.sleep(self.timeframe_seconds)

            except KeyboardInterrupt:
                logging.info("Desligando o robô...")
                mt5.shutdown()
                break
            except Exception as e:
                logging.error(f"Ocorreu um erro no loop principal: {e}")
                time.sleep(60) # Aguarda um minuto em caso de erro

    def _execute_trade(self, order_type):
        """Envia a ordem para o MetaTrader 5."""
        trade_type = mt5.ORDER_TYPE_BUY if order_type == 'BUY' else mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(self.ticker_order).ask if order_type == 'BUY' else mt5.symbol_info_tick(self.ticker_order).bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.ticker_order,
            "volume": self.live_config['trade_volume'],
            "type": trade_type,
            "price": price,
            "deviation": 20,
            "magic": 123456,
            "comment": "Sent by Python Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if self.live_config['execution_mode'] == 'suggest':
            logging.info(f"[MODO SUGESTÃO] Ordem de {order_type} para {self.live_config['trade_volume']} lotes de {self.ticker} a ~${price}")
            logging.info(f"Detalhes da ordem: {request}")
        else:
            logging.warning("Modo de execução não reconhecido.")

        """
        elif self.live_config['execution_mode'] == 'execute':
            logging.info(f"[MODO EXECUÇÃO] Enviando ordem de {order_type} para {self.ticker}...")
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logging.error(f"Falha ao enviar ordem: {result.comment}")
            else:
                logging.info(f"Ordem enviada com sucesso: {result}")
                self.current_position = 'LONG' if order_type == 'BUY' else 'SHORT'
        """
        
if __name__ == "__main__":
    trader = LiveTrader()
    trader.run()