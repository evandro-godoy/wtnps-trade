import yaml
import logging
import time
from pathlib import Path
import importlib
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone

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

        # Instancia o provedor de dados do MT5, que será o principal para live trading
        from src.data_handler.provider import MetaTraderProvider
        self.provider = MetaTraderProvider()
        self.asset_states = {}

    def _get_mt5_timeframe_from_string(self, tf_str: str):
        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        return tf_map.get(tf_str.upper(), mt5.TIMEFRAME_D1)

    def initialize(self):
        logging.info("Inicializando o robô trader multi-ativo...")
        if not mt5.initialize():
            logging.error(f"Falha na inicialização do MT5: {mt5.last_error()}")
            return False

        models_dir = Path(self.config["global_settings"]["model_directory"])

        for asset_config in self.assets_config:
            # Ticker para dados históricos e nome do modelo
            data_ticker = asset_config["ticker"]
            logging.info(f"  > Carregando recursos para {data_ticker}...")

            try:
                # Carregar estratégia
                module_path = f"src.strategies.{asset_config['strategy_module']}"
                strategy_module = importlib.import_module(module_path)
                StrategyClass = getattr(strategy_module, asset_config["strategy_name"])

                # Carregar modelo (nome do arquivo usa o ticker de dados)
                model_path = models_dir / f"{data_ticker}_prod_model.keras"
                scaler_path = models_dir / f"{data_ticker}_prod_scaler.joblib"

                if not model_path.exists() or not scaler_path.exists():
                    logging.error(f"Modelo ou scaler para {data_ticker} não encontrado. Execute o train_model.py.")
                    continue
                
                from src.strategies.lstm import KerasLSTMWrapper
                model = KerasLSTMWrapper.load_model(str(model_path), str(scaler_path))

                self.asset_states[data_ticker] = {
                    "config": asset_config,
                    "strategy": StrategyClass(),
                    "model": model,
                    "position": None,
                    "last_processed_time": None,
                }
            except Exception as e:
                logging.error(f"Falha ao carregar recursos para {data_ticker}: {e}", exc_info=True)

        if not self.asset_states:
            logging.error("Nenhum ativo foi carregado com sucesso. Encerrando.")
            return False
        
        logging.info("Robô inicializado para: " + ", ".join(self.asset_states.keys()))
        return True

    def run(self):
        if not self.initialize():
            return
        logging.info("Iniciando loop de trading...")

        while True:
            try:
                for data_ticker, state in self.asset_states.items():
                    asset_config = state["config"]
                    timeframe_str = asset_config["live_trading"]["timeframe_str"]
                    mt5_timeframe = self._get_mt5_timeframe_from_string(timeframe_str)
                    
                    latest_candle = self.provider.get_latest_rates(data_ticker, 1, mt5_timeframe)
                    if latest_candle.empty:
                        continue
                    latest_candle_time = latest_candle.index[0]

                    if state["last_processed_time"] == latest_candle_time:
                        continue

                    logging.info(f"--- Novo Candle para {data_ticker} ({timeframe_str}) em {latest_candle_time} ---")
                    
                    historical_data = self.provider.get_latest_rates(data_ticker, 300, mt5_timeframe)
                    if historical_data.empty: continue
                    
                    featured_data = state["strategy"].define_features(historical_data)
                    X_live = featured_data[state["strategy"].get_feature_names()].dropna()
                    if X_live.empty:
                        logging.warning(f"Dados insuficientes para gerar features para {data_ticker}.")
                        continue

                    signal = state["model"].predict(X_live)[-1]
                    logging.info(f"Sinal para {data_ticker}: {'COMPRA' if signal == 1 else 'VENDA'}")

                    if state["position"] is None:
                        if signal == 1: self._execute_trade(data_ticker, "BUY")
                        elif signal == 0: self._execute_trade(data_ticker, "SELL")
                    else:
                        logging.info(f"Posição já aberta para {data_ticker} ({state['position']}).")

                    state["last_processed_time"] = latest_candle_time

                time.sleep(5)

            except KeyboardInterrupt:
                logging.info("Desligando o robô...")
                mt5.shutdown()
                break
            except Exception as e:
                logging.error(f"Erro no loop principal: {e}", exc_info=True)
                time.sleep(60)

    def _execute_trade(self, data_ticker, order_type):
        """Usa o ticker de dados para encontrar a configuração e o ticker de ordem para executar."""
        state = self.asset_states[data_ticker]
        asset_config = state['config']
        live_config = asset_config['live_trading']

        # --- LÓGICA CENTRAL DA ALTERAÇÃO ---
        # Usa 'ticker_order' se existir, senão usa o ticker principal.
        order_ticker = live_config.get('ticker_order', data_ticker)
        
        trade_type = mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL
        
        symbol_info = mt5.symbol_info(order_ticker)
        if symbol_info is None:
            logging.error(f"Não foi possível obter informações para o ativo de ordem '{order_ticker}'")
            return

        price = symbol_info.ask if order_type == "BUY" else symbol_info.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order_ticker, # Usa o ticker de ordem
            "volume": float(live_config["trade_volume"]),
            "type": trade_type,
            "price": price,
            "deviation": 20,
            "magic": 123456,
            "comment": f"Bot {data_ticker}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if live_config["execution_mode"] == "suggest":
            logging.info(
                f"[SUGESTÃO] Ordem de {order_type} para {live_config['trade_volume']} lotes de {order_ticker} a ~${price}"
            )
        elif live_config["execution_mode"] == "execute":
            logging.info(f"[EXECUÇÃO] Enviando ordem de {order_type} para {order_ticker}...")
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logging.error(f"Falha ao enviar ordem para {order_ticker}: {result.comment}")
            else:
                logging.info(f"Ordem para {order_ticker} enviada com sucesso: {result}")
                state["position"] = "LONG" if order_type == "BUY" else "SHORT"
        else:
            logging.warning(f"Modo de execução não reconhecido para {data_ticker}.")

if __name__ == "__main__":
    trader = LiveTrader()
    trader.run()