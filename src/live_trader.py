import yaml
import logging
import time
from pathlib import Path
import importlib
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone

from src.data_handler.provider import MetaTraderProvider

class LiveTrader:
    def __init__(self, config_path="configs/main.yaml"):
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )

        project_root = Path(__file__).resolve().parent.parent
        with open(project_root / config_path, "r") as file:
            self.config = yaml.safe_load(file)

        self.assets_config = [
            asset for asset in self.config["assets"] if asset.get("enabled", False)
        ]

        self.provider = MetaTraderProvider()
        self.asset_states = {}  # Dicionário para guardar o estado de cada ativo

    def _get_mt5_timeframe_from_string(self, tf_str: str):
        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        return tf_map.get(tf_str.upper(), mt5.TIMEFRAME_D1)

    def initialize(self):
        """Conecta ao MT5 e carrega os modelos para cada ativo habilitado."""
        logging.info("Inicializando o robô trader multi-ativo...")
        if not mt5.initialize():
            logging.error(f"Falha na inicialização do MT5: {mt5.last_error()}")
            return False

        models_dir = Path(self.config["global_settings"]["model_directory"])

        for asset_config in self.assets_config:
            ticker = asset_config["ticker"]
            logging.info(f"  > Carregando recursos para {ticker}...")

            try:
                # Carregar estratégia
                module_path = f"src.strategies.{asset_config['strategy_module']}"
                strategy_module = importlib.import_module(module_path)
                StrategyClass = getattr(strategy_module, asset_config["strategy_name"])

                # Carregar modelo
                model_path = models_dir / f"{ticker}_prod_model.keras"
                scaler_path = models_dir / f"{ticker}_prod_scaler.joblib"

                if not model_path.exists() or not scaler_path.exists():
                    logging.error(f"Modelo ou scaler para {ticker} não encontrado. Execute o train_model.py.")
                    continue
                
                # Importa o KerasLSTMWrapper dinamicamente para usar o load_model
                from src.strategies.lstm import KerasLSTMWrapper
                model = KerasLSTMWrapper.load_model(str(model_path), str(scaler_path))

                # Inicializar estado do ativo
                self.asset_states[ticker] = {
                    "config": asset_config,
                    "strategy": StrategyClass(),
                    "model": model,
                    "position": None,  # 'LONG', 'SHORT', ou None
                    "last_processed_time": None,
                }
            except Exception as e:
                logging.error(f"Falha ao carregar recursos para {ticker}: {e}", exc_info=True)

        if not self.asset_states:
            logging.error("Nenhum ativo foi carregado com sucesso. Encerrando.")
            return False
        
        logging.info("Robô inicializado para: " + ", ".join(self.asset_states.keys()))
        return True

    def run(self):
        """Inicia o loop principal, verificando cada ativo em seu próprio ciclo."""
        if not self.initialize():
            return

        logging.info("Iniciando loop de trading...")

        while True:
            try:
                for ticker, state in self.asset_states.items():
                    asset_config = state["config"]
                    timeframe_str = asset_config["live_trading"]["timeframe_str"]
                    mt5_timeframe = self._get_mt5_timeframe_from_string(timeframe_str)
                    
                    # Busca o último candle para verificar se é um novo candle
                    latest_candle = self.provider.get_latest_rates(ticker, 1, mt5_timeframe)
                    if latest_candle.empty:
                        continue

                    latest_candle_time = latest_candle.index[0]

                    # Verifica se este candle já foi processado
                    if state["last_processed_time"] == latest_candle_time:
                        continue # Pula para o próximo ativo se não for um novo candle

                    logging.info(f"--- Novo Candle para {ticker} ({timeframe_str}) em {latest_candle_time} ---")
                    
                    # 1. Buscar e preparar dados
                    historical_data = self.provider.get_latest_rates(ticker, 300, mt5_timeframe)
                    if historical_data.empty: continue
                    
                    featured_data = state["strategy"].define_features(historical_data)
                    X_live = featured_data[state["strategy"].get_feature_names()].dropna()
                    if X_live.empty:
                        logging.warning(f"Dados insuficientes para gerar features para {ticker}.")
                        continue

                    # 2. Gerar sinal
                    signal = state["model"].predict(X_live)[-1]
                    logging.info(f"Sinal para {ticker}: {'COMPRA' if signal == 1 else 'VENDA'}")

                    # 3. Lógica de decisão
                    if state["position"] is None:
                        if signal == 1: self._execute_trade(ticker, "BUY")
                        elif signal == 0: self._execute_trade(ticker, "SELL")
                    else:
                        logging.info(f"Posição já aberta para {ticker} ({state['position']}).")

                    # Atualiza o tempo do último candle processado
                    state["last_processed_time"] = latest_candle_time

                # Aguarda um curto período antes de verificar novamente
                time.sleep(5) # Verifica por novos candles a cada 5 segundos

            except KeyboardInterrupt:
                logging.info("Desligando o robô...")
                mt5.shutdown()
                break
            except Exception as e:
                logging.error(f"Erro no loop principal: {e}", exc_info=True)
                time.sleep(60)

    def _execute_trade(self, ticker, order_type):
        """Envia a ordem para o MetaTrader 5 para um ativo específico."""
        state = self.asset_states[ticker]
        asset_config = state['config']
        live_config = asset_config['live_trading']

        trade_type = mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL
        
        symbol_info = mt5.symbol_info(live_config.ticker_order)
        if symbol_info is None:
            logging.error(f"Não foi possível obter informações para o ativo {ticker}")
            return

        price = symbol_info.ask if order_type == "BUY" else symbol_info.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": ticker,
            "volume": float(live_config["trade_volume"]),
            "type": trade_type,
            "price": price,
            "deviation": 20,
            "magic": 123456,
            "comment": "Sent by Python Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if live_config["execution_mode"] == "suggest":
            logging.info(
                f"[SUGESTÃO] Ordem de {order_type} para {live_config['trade_volume']} lotes de {ticker} a ~${price}"
            )
        elif live_config["execution_mode"] == "execute":
            logging.info(f"[EXECUÇÃO] Enviando ordem de {order_type} para {ticker}...")
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logging.error(f"Falha ao enviar ordem para {ticker}: {result.comment}")
            else:
                logging.info(f"Ordem para {ticker} enviada com sucesso: {result}")
                state["position"] = "LONG" if order_type == "BUY" else "SHORT"
        else:
            logging.warning(f"Modo de execução não reconhecido para {ticker}.")

if __name__ == "__main__":
    trader = LiveTrader()
    trader.run()