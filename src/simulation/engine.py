import sys
import yaml
import logging
from pathlib import Path
import importlib
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

# Adiciona a raiz do projeto ao path para importações
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data_handler.provider import MetaTraderProvider, YFinanceProvider
from src.strategies.lstm import KerasLSTMWrapper # Usado para checagem de tipo e carregamento
from src.setups.analyzer import evaluate_setups # Importa a lógica de avaliação de setups

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
        self.models_dir = project_root / self.config["global_settings"]["model_directory"]
        self.asset_states = {} # Cache para modelos e estratégias carregados

        # Instancia provedores (MT5 é o principal para dados recentes)
        self.mt5_provider = MetaTraderProvider()
        self.yf_provider = YFinanceProvider() # Pode ser necessário para estratégias YF

        self._initialize_mt5()

    def _load_config(self):
        """Carrega o arquivo de configuração YAML."""
        try:
            with open(self.config_path, "r") as file:
                return yaml.safe_load(file)
        except Exception as e:
            logging.error(f"Erro crítico ao carregar configuração {self.config_path}: {e}")
            raise

    def _initialize_mt5(self):
        """Inicializa a conexão com o MetaTrader 5."""
        if not mt5.initialize():
            logging.error(f"Falha na inicialização do MT5: {mt5.last_error()}")
            # Permite continuar sem MT5 para estratégias YFinance, mas loga erro
        else:
            logging.info("Conectado ao MetaTrader 5.")

    def _get_mt5_timeframe_from_string(self, tf_str: str):
        tf_map = { "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
                   "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
                   "D1": mt5.TIMEFRAME_D1 }
        return tf_map.get(tf_str.upper(), mt5.TIMEFRAME_D1)

    def _load_asset_resources(self, data_ticker):
        """Carrega modelo e estratégia para um ativo sob demanda."""
        if data_ticker in self.asset_states:
            return self.asset_states[data_ticker]

        asset_config = next((asset for asset in self.assets_config if asset['ticker'] == data_ticker), None)
        if not asset_config:
            logging.error(f"Configuração não encontrada para {data_ticker}")
            return None

        logging.info(f"Carregando recursos para {data_ticker}...")
        try:
            # Carregar estratégia
            module_path = f"src.strategies.{asset_config['strategy_module']}"
            strategy_module = importlib.import_module(module_path)
            StrategyClass = getattr(strategy_module, asset_config["strategy_name"])
            strategy_instance = StrategyClass()

            # Carregar modelo (assume Keras para LSTM e SentimentLSTM)
            # Adicionar lógica para outros tipos de modelo se necessário
            model = None
            if "lstm" in asset_config['strategy_module'].lower():
                model_path = self.models_dir / f"{data_ticker}_prod_model.keras"
                scaler_path = self.models_dir / f"{data_ticker}_prod_scaler.joblib"
                if not model_path.exists() or not scaler_path.exists():
                    logging.error(f"Modelo/Scaler para {data_ticker} não encontrado.")
                    return None
                model = KerasLSTMWrapper.load_model(str(model_path), str(scaler_path))
            # else: Adicionar carregamento para RandomForest, etc.

            if model is None:
                 logging.warning(f"Não foi possível carregar o modelo para {data_ticker} (tipo não suportado?).")
                 # Poderia retornar None ou apenas a estratégia se setups não dependerem de IA
                 # Por enquanto, retornamos None se o modelo falhar
                 return None


            state = {"config": asset_config, "strategy": strategy_instance, "model": model}
            self.asset_states[data_ticker] = state # Armazena em cache
            logging.info(f"Recursos para {data_ticker} carregados.")
            return state

        except Exception as e:
            logging.error(f"Falha ao carregar recursos para {data_ticker}: {e}", exc_info=True)
            return None

    def run_simulation_cycle(self, data_ticker: str, selected_timeframe_str: str) -> dict:
        """
        Executa um ciclo completo de simulação para um único ativo e timeframe.
        Busca dados, gera features, obtém sinal da IA, avalia setups e retorna
        um dicionário com a sugestão detalhada.
        """
        state = self._load_asset_resources(data_ticker)
        if not state:
            return {"error": f"Não foi possível carregar recursos para {data_ticker}."}

        asset_config = state['config']
        strategy = state['model']
        model = state['model'] # Assume que o modelo está sempre presente por enquanto
        live_config = asset_config['live_trading']
        order_ticker = live_config.get('ticker_order', data_ticker)
        mt5_timeframe = self._get_mt5_timeframe_from_string(selected_timeframe_str)

        result = {
            "ticker": data_ticker,
            "order_ticker": order_ticker,
            "timeframe": selected_timeframe_str,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "signal": "HOLD", # Sinal padrão
            "signal_raw": -1, # -1: Hold, 0: Sell, 1: Buy
            "suggested_price": None,
            "price_source": "N/A",
            "stop_price": None,
            "indicators": {},
            "setup_valid": None,
            "error": None
        }

        try:
            # 1. Buscar Dados Recentes (com lookback suficiente para features e modelo)
            # Usar 300 barras como um valor seguro inicial
            historical_data = self.mt5_provider.get_latest_rates(data_ticker, 300, mt5_timeframe)
            if historical_data.empty:
                result["error"] = "Não foi possível obter dados recentes."
                return result
            
            last_candle_time = historical_data.index[-1]
            result["timestamp"] = last_candle_time.strftime('%Y-%m-%d %H:%M:%S')

            # 2. Gerar Features
            featured_data = strategy.define_features(historical_data)
            X_live = featured_data[strategy.get_feature_names()].dropna()
            
            # Captura indicadores do último candle disponível
            last_indicators = featured_data.iloc[-1]
            indicator_keys = ['sma9', 'ema21', 'ema50', 'ema200', 'rsi', 'volatility', 'sentiment'] # Chaves comuns
            for key in indicator_keys:
                 # Corrigido: usa .get() com valor padrão e formata se não for nulo
                 value = last_indicators.get(key)
                 result["indicators"][key.upper()] = f"{value:.2f}" if pd.notna(value) else "N/A"

            # Verifica se há dados suficientes para a previsão da IA
            # (model.lookback pode não existir para todos os modelos)
            min_lookback = getattr(model, 'lookback', 30) # Usa 30 como padrão se não encontrar
            if len(X_live) <= min_lookback:
                result["error"] = "Dados insuficientes para gerar previsão da IA."
                # Mesmo sem IA, podemos avaliar setups baseados apenas em indicadores
                # return result # Descomente se quiser abortar sem sinal de IA

            # 3. Gerar Sinal da IA (se houver dados suficientes)
            ai_signal_raw = -1 # Sinal padrão Hold/Indefinido
            if len(X_live) > min_lookback:
                 # Garante que predict retorne um array ou similar
                 predictions = model.predict(X_live)
                 if predictions is not None and len(predictions) > 0:
                     ai_signal_raw = int(predictions[-1]) # Pega a última predição (0 ou 1)
                 else:
                     logging.warning(f"Modelo para {data_ticker} não retornou previsões.")
            
            # 4. Avaliar Setups Operacionais
            setup_rules = asset_config.get('setup', [])
            # Passa o sinal da IA (0 ou 1) ou -1 se não houver sinal
            # Passa o dataframe completo com indicadores calculados
            is_setup_valid = evaluate_setups(ai_signal_raw if ai_signal_raw != -1 else None, setup_rules, featured_data)
            result["setup_valid"] = is_setup_valid

            # 5. Determinar Sinal Final e Preços
            # Só gera sinal de Compra/Venda se a IA deu sinal E o setup é válido
            final_signal = "HOLD"
            final_signal_raw = -1
            if ai_signal_raw != -1 and is_setup_valid:
                 final_signal = 'COMPRA' if ai_signal_raw == 1 else 'VENDA'
                 final_signal_raw = ai_signal_raw
            
            result["signal"] = final_signal
            result["signal_raw"] = final_signal_raw

            # Calcula preços apenas se houver sinal de entrada
            if final_signal != "HOLD":
                symbol_info = mt5.symbol_info_tick(order_ticker)
                if symbol_info and symbol_info.ask > 0 and symbol_info.bid > 0:
                    result["suggested_price"] = symbol_info.ask if final_signal == 'COMPRA' else symbol_info.bid
                    result["price_source"] = "Tick"
                elif not historical_data.empty:
                    result["suggested_price"] = historical_data['close'].iloc[-1]
                    result["price_source"] = "Último Fechamento"

                # Calcula Stop Price
                if result["suggested_price"] is not None:
                    stop_loss_pct = asset_config['trading_rules']['stop_loss_pct']
                    entry = result["suggested_price"]
                    result["stop_price"] = entry * (1 - stop_loss_pct) if final_signal == 'COMPRA' else entry * (1 + stop_loss_pct)

        except Exception as e:
            log_err = f"Erro ao simular {data_ticker}: {e}"
            logging.error(log_err, exc_info=True)
            result["error"] = log_err

        return result

    def shutdown(self):
        """Encerra a conexão com o MT5."""
        logging.info("Encerrando conexão do SimulationEngine com o MetaTrader 5...")
        mt5.shutdown()