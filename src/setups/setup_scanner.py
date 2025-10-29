import yaml
import logging
from pathlib import Path
import importlib
import MetaTrader5 as mt5
import pandas as pd

from src.data_handler.provider import MetaTraderProvider
from src.strategies.lstm import KerasLSTMWrapper
from src.setups.analyzer import evaluate_setups

class SetupScanner:
    def __init__(self, config_path="configs/main.yaml"):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

        project_root = Path(__file__).resolve().parent.parent
        with open(project_root / config_path, "r") as file:
            self.config = yaml.safe_load(file)

        self.assets_config = [asset for asset in self.config["assets"] if asset.get("enabled", False)]
        self.provider = MetaTraderProvider()
        self.asset_states = {}

    def _get_mt5_timeframe_from_string(self, tf_str: str):
        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        return tf_map.get(tf_str.upper(), mt5.TIMEFRAME_D1)

    def initialize_assets(self):
        """Carrega os modelos para cada ativo habilitado."""
        logging.info("Inicializando o Scanner de Setups...")
        models_dir = Path(self.config["global_settings"]["model_directory"])

        for asset_config in self.assets_config:
            ticker = asset_config["ticker"]
            logging.info(f"  > Carregando recursos para {ticker}...")
            try:
                module_path = f"src.strategies.{asset_config['strategy_module']}"
                strategy_module = importlib.import_module(module_path)
                StrategyClass = getattr(strategy_module, asset_config["strategy_name"])
                
                model_path = models_dir / f"{ticker}_prod_model.keras"
                scaler_path = models_dir / f"{ticker}_prod_scaler.joblib"

                if not model_path.exists() or not scaler_path.exists():
                    logging.error(f"Modelo ou scaler para {ticker} não encontrado.")
                    continue
                
                model = KerasLSTMWrapper.load_model(str(model_path), str(scaler_path))
                self.asset_states[ticker] = {"config": asset_config, "strategy": StrategyClass(), "model": model}
            except Exception as e:
                logging.error(f"Falha ao carregar recursos para {ticker}: {e}")
        
        if not self.asset_states:
            logging.error("Nenhum ativo foi carregado. Encerrando.")
            return False
        return True

    def scan_all_assets(self):
        """Verifica todos os ativos configurados em busca de setups operacionais."""
        if not self.initialize_assets():
            return
            
        if not mt5.initialize():
            logging.error(f"Falha na inicialização do MT5: {mt5.last_error()}")
            return

        logging.info("\n--- INICIANDO SCAN DE SETUPS OPERACIONAIS ---")
        
        for ticker, state in self.asset_states.items():
            asset_config = state["config"]
            live_config = asset_config["live_trading"]
            timeframe_str = live_config["timeframe_str"]
            order_ticker = live_config.get('ticker_order', ticker)
            mt5_timeframe = self._get_mt5_timeframe_from_string(timeframe_str)
            
            # 1. Obter dados
            historical_data = self.provider.get_latest_rates(ticker, 300, mt5_timeframe)
            if historical_data.empty: continue
            
            # 2. Obter sinal da IA
            featured_data = state["strategy"].define_features(historical_data)
            X_live = featured_data[state["strategy"].get_feature_names()].dropna()
            if X_live.empty: continue
            ai_signal = state["model"].predict(X_live)[-1]
            
            # 3. Avaliar as regras do setup
            setup_rules = asset_config.get('setup', [])
            is_setup_valid = evaluate_setups(ai_signal, setup_rules, historical_data)
            
            # 4. Apresentar sugestão se o setup for válido
            if is_setup_valid:
                signal_text = 'COMPRA' if ai_signal == 1 else 'VENDA'
                tick = mt5.symbol_info_tick(order_ticker)
                price = tick.ask if ai_signal == 1 else tick.bid
                
                print("\n" + "="*50)
                print(f"  SUGESTÃO DE SETUP ENCONTRADA!")
                print(f"  Ativo: {ticker} (Ordem em {order_ticker})")
                print(f"  Sinal: {signal_text}")
                print(f"  Preço Atual: {price:.2f}")
                print(f"  Timeframe: {timeframe_str}")
                print("="*50)

        mt5.shutdown()
        logging.info("\n--- SCAN DE SETUPS CONCLUÍDO ---")


if __name__ == "__main__":
    scanner = SetupScanner()
    scanner.scan_all_assets()