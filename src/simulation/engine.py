# src/simulation/engine.py
import yaml
import logging
from pathlib import Path
import importlib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
# Removido: from tensorflow.keras.models import load_model # Não é mais necessário aqui
# Removido: import joblib # Não é mais necessário aqui
import MetaTrader5 as mt5 # Para conversão de timeframe

# Importações internas do projeto
from src.data_handler.provider import get_provider_instance, BaseDataProvider, MetaTraderProvider # Adicionado MetaTraderProvider para type hint
from src.strategies.base import BaseStrategy # Importa a classe base
from src.setups.analyzer import SetupAnalyzer # Mantém para análise de setups

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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

class SimulationEngine:
    """
    Motor de Simulação para avaliar estratégias de trading ponto a ponto no tempo.
    Projetado para ser usado em dashboards, notebooks e análises "market replay".
    """
    def __init__(self, config_path: str = 'configs/main.yaml'):
        self.config_path = config_path
        self.config = self._load_config()
        self.assets_data = {} # Cache de dados históricos
        self.asset_resources = {} # Cache de modelos, scalers, etc., por ativo
        self.data_providers = {} # Cache de instâncias de provedores de dados
        self.models_dir = Path(self.config.get('global_settings', {}).get('models_directory', 'models'))
        self.setup_analyzer = SetupAnalyzer() # Instância do analisador de setups

    def _load_config(self):
        """Carrega o arquivo de configuração YAML."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Arquivo de configuração não encontrado: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Erro ao carregar configuração YAML: {e}")
            raise

    def _get_provider(self, provider_name: str) -> BaseDataProvider:
        """Obtém ou cria uma instância do provedor de dados."""
        if provider_name not in self.data_providers:
            try:
                self.data_providers[provider_name] = get_provider_instance(provider_name)
                logger.info(f"Provedor de dados '{provider_name}' instanciado.")
            except ValueError as e:
                 logger.error(f"Erro ao obter provedor de dados '{provider_name}': {e}")
                 raise
        return self.data_providers[provider_name]

    def _load_asset_resources(self, asset_symbol: str):
        """
        Carrega os recursos necessários (modelo, estratégia) para um ativo específico.
        Utiliza a interface unificada BaseStrategy.load().
        """
        if asset_symbol in self.asset_resources:
            return self.asset_resources[asset_symbol]

        asset_config = self.config['assets'].get(asset_symbol)
        if not asset_config:
            logger.error(f"Configuração não encontrada para o ativo: {asset_symbol}")
            return None

        strategy_module_name = asset_config.get('strategy_module')
        strategy_class_name = asset_config.get('strategy_name')
        data_ticker = asset_config['data'].get('ticker', asset_symbol) # Ticker usado para treinar

        if not strategy_module_name or not strategy_class_name:
            logger.error(f"Módulo ou nome da classe da estratégia não definidos para {asset_symbol}")
            return None

        try:
            # Carrega a classe da Estratégia dinamicamente
            strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
            StrategyClass = getattr(strategy_module, strategy_class_name)
            
            # Cria uma instância da estratégia (para acessar métodos não-classe se necessário)
            # Ex: strategy_instance = StrategyClass(**asset_config.get('strategy_params', {}))
            strategy_instance: BaseStrategy = StrategyClass() 

            # --- Carregamento Unificado do Modelo ---
            # Define o prefixo do caminho do modelo
            model_path_prefix = str(self.models_dir / f"{asset_symbol}_prod") 
            
            logger.info(f"Carregando modelo para {asset_symbol} usando {strategy_class_name}.load() com prefixo: {model_path_prefix}")
            
            # Chama o método de classe load da ESTRATÉGIA
            model = StrategyClass.load(model_path_prefix) 
            # ----------------------------------------

            resources = {
                'strategy_instance': strategy_instance,
                'strategy_class': StrategyClass, # Guarda a classe também, se necessário
                'model': model,
                'config': asset_config # Guarda config específico do ativo
            }
            self.asset_resources[asset_symbol] = resources
            logger.info(f"Recursos (modelo e estratégia) carregados para {asset_symbol}.")
            return resources

        except FileNotFoundError as e:
             logger.error(f"Erro ao carregar recursos para {asset_symbol}: Arquivo de modelo/scaler não encontrado. Detalhes: {e}")
             # Não adiciona ao cache se falhar
             return None
        except (ImportError, AttributeError, TypeError, Exception) as e:
            logger.error(f"Erro ao carregar recursos para {asset_symbol}: {e}", exc_info=True)
            # Não adiciona ao cache se falhar
            return None

    def _get_market_data(self, ticker: str, start_dt: datetime, end_dt: datetime, timeframe_str: str, provider_name: str) -> pd.DataFrame:
        """Busca dados de mercado usando o provedor apropriado."""
        provider = self._get_provider(provider_name)
        
        # Converte timeframe string para objeto MT5 se necessário
        timeframe_obj = None
        if provider_name == 'MetaTrader5':
            timeframe_obj = _get_mt5_timeframe_from_string(timeframe_str)
            if timeframe_obj is None:
                raise ValueError(f"Timeframe inválido '{timeframe_str}' para MetaTrader5.")
        
        try:
             # Formata datas como string para a função get_data
             start_date_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
             end_date_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')

             logger.debug(f"Buscando dados para {ticker} de {start_date_str} a {end_date_str} @ {timeframe_str} via {provider_name}")

             data = provider.get_data(
                 ticker=ticker,
                 start_date=start_date_str, # Passa como string
                 end_date=end_date_str,   # Passa como string
                 timeframe=timeframe_obj if provider_name == 'MetaTrader5' else timeframe_str # Passa obj ou str
             )
             if data.empty:
                  logger.warning(f"Nenhum dado retornado para {ticker} no período {start_date_str} - {end_date_str} @ {timeframe_str}")
             else:
                  logger.debug(f"Dados recebidos: {len(data)} candles.")
                  # Garante que o índice seja DatetimeIndex e esteja ordenado
                  if not isinstance(data.index, pd.DatetimeIndex):
                       data.index = pd.to_datetime(data.index)
                  data.sort_index(inplace=True)
             return data
             
        except Exception as e:
            logger.error(f"Erro ao buscar dados para {ticker}: {e}", exc_info=True)
            return pd.DataFrame() # Retorna DataFrame vazio em caso de erro

    def run_simulation_cycle(self, asset_symbol: str, timeframe_str: str, target_datetime: datetime) -> dict:
        """
        Executa um ciclo completo de simulação para um ativo e datetime específicos.
        Retorna um dicionário com os resultados da simulação.
        """
        logger.info(f"Iniciando ciclo de simulação para {asset_symbol} @ {timeframe_str} em {target_datetime}")

        # 1. Carregar Recursos (Modelo, Estratégia, Config)
        resources = self._load_asset_resources(asset_symbol)
        if not resources:
            return {"error": f"Falha ao carregar recursos para {asset_symbol}."}
        
        model = resources['model']
        strategy_instance: BaseStrategy = resources['strategy_instance']
        asset_config = resources['config']
        
        # 2. Obter Dados de Mercado Necessários
        # Define quanto tempo para trás precisamos buscar (lookback + indicadores)
        required_periods = 500 # Ajuste conforme necessário
        
        try:
             # Estima data de início
             time_delta = pd.Timedelta(minutes=1) # Default
             if 'M' in timeframe_str.upper():
                  minutes = int(timeframe_str[1:]) if len(timeframe_str) > 1 else 1
                  time_delta = pd.Timedelta(minutes=required_periods * minutes)
             elif 'H' in timeframe_str.upper():
                  hours = int(timeframe_str[1:]) if len(timeframe_str) > 1 else 1
                  time_delta = pd.Timedelta(hours=required_periods * hours)
             elif 'D' in timeframe_str.upper():
                  time_delta = pd.Timedelta(days=required_periods)
             elif 'W' in timeframe_str.upper():
                  time_delta = pd.Timedelta(weeks=required_periods)
             elif 'MN' in timeframe_str.upper():
                   time_delta = pd.Timedelta(days=required_periods * 30) # Aproximação

             start_dt = target_datetime - time_delta * 1.5 # Busca um pouco mais
             end_dt = target_datetime # Busca até o datetime alvo
             
             data_ticker = asset_config['data'].get('ticker', asset_symbol)
             provider_name = asset_config.get('provider', 'MetaTrader5')

             market_data = self._get_market_data(data_ticker, start_dt, end_dt, timeframe_str, provider_name)

             if market_data.empty:
                  logger.warning(f"Dados não encontrados até {target_datetime} para {data_ticker}. Tentando buscar um pouco mais à frente.")
                  # Tenta buscar um pouco mais para frente
                  # **CORREÇÃO APLICADA AQUI**
                  delta_args = {}
                  if 'M' in timeframe_str.upper():
                       delta_args['minutes'] = 5
                  elif 'H' in timeframe_str.upper():
                       delta_args['hours'] = 1
                  else: # Default to days (covers D, W, MN)
                       delta_args['days'] = 1
                  end_dt_extended = target_datetime + pd.Timedelta(**delta_args)
                  # **FIM DA CORREÇÃO**

                  market_data = self._get_market_data(data_ticker, start_dt, end_dt_extended, timeframe_str, provider_name)
                  # Filtra novamente para garantir que não pegamos dados futuros demais
                  # Garante que target_datetime seja comparável com o índice (localize se necessário)
                  target_ts = pd.Timestamp(target_datetime)
                  if market_data.index.tz is not None and target_ts.tz is None:
                        target_ts = target_ts.tz_localize(market_data.index.tz)
                  elif market_data.index.tz is None and target_ts.tz is not None:
                       target_ts = target_ts.tz_localize(None)

                  market_data = market_data[market_data.index <= target_ts] 

             # Verifica se o último timestamp é EXATAMENTE o target_datetime
             if market_data.empty or market_data.index[-1].to_pydatetime().replace(tzinfo=None) != target_datetime.replace(tzinfo=None):
                   last_ts_str = market_data.index[-1].strftime('%Y-%m-%d %H:%M:%S') if not market_data.empty else "Nenhum dado"
                   target_dt_str = target_datetime.strftime('%Y-%m-%d %H:%M:%S')
                   logger.error(f"Dados de mercado para {data_ticker} @ {timeframe_str} não encontrados exatamente em {target_dt_str}. Último timestamp disponível: {last_ts_str}")
                   return {"error": f"Dados não encontrados para {target_dt_str}."}

        except Exception as e:
            logger.error(f"Erro ao obter ou processar dados de mercado para {asset_symbol}: {e}", exc_info=True)
            return {"error": "Erro ao buscar dados de mercado."}


        # 3. Calcular Features
        try:
            data_with_features = strategy_instance.define_features(market_data)
            
            # Localiza o timestamp exato nos dados com features
            # Garante que target_datetime seja comparável com o índice (timezone)
            target_ts = pd.Timestamp(target_datetime)
            if data_with_features.index.tz is not None and target_ts.tz is None:
                 target_ts = target_ts.tz_localize(data_with_features.index.tz)
            elif data_with_features.index.tz is None and target_ts.tz is not None:
                 target_ts = target_ts.tz_localize(None)

            if target_ts not in data_with_features.index:
                 # Se não encontrar exatamente, talvez por ms, tenta o mais próximo? Ou falha?
                 # Por segurança, vamos falhar.
                 logger.error(f"Timestamp {target_ts} não encontrado EXATAMENTE no índice dos dados com features após cálculo. Índices disponíveis: {data_with_features.index}")
                 return {"error": f"Timestamp {target_datetime.strftime('%Y-%m-%d %H:%M:%S')} não localizado nos dados pós-features."}

            current_features_row = data_with_features.loc[[target_ts]] 
            
            # Pega os dados necessários para a previsão (lookback até o atual)
            target_loc = data_with_features.index.get_loc(target_ts)
            
            lookback = getattr(model, 'lookback', 1) # Pega lookback do modelo se existir, default 1
            start_loc = max(0, target_loc - lookback + 1) # Garante não ir abaixo de 0
            
            if target_loc - start_loc + 1 < lookback:
                 logger.warning(f"Dados insuficientes ({target_loc - start_loc + 1} pontos) antes ou até {target_datetime} para o lookback ({lookback}).")
                 return {"error": "Dados insuficientes para lookback."}
                 
            model_input_data = data_with_features.iloc[start_loc : target_loc + 1]
            
            feature_names = strategy_instance.get_feature_names()
            X_predict = model_input_data[feature_names]

            if X_predict.isnull().values.any():
                logger.warning(f"Dados de input para o modelo em {target_datetime} contêm NaNs.")
                return {"error": "NaNs encontrados nos dados de input do modelo."}

        except KeyError as e:
             logger.error(f"Erro ao acessar índice {target_ts} ou coluna de feature: {e}")
             return {"error": f"Timestamp ou feature não encontrada nos dados."}
        except Exception as e:
            logger.error(f"Erro ao calcular features ou preparar dados para predição: {e}", exc_info=True)
            return {"error": "Erro no cálculo de features."}

        # 4. Obter Sinal da IA
        try:
            raw_prediction = model.predict(X_predict)
            
            if isinstance(raw_prediction, np.ndarray) and len(raw_prediction) > 0:
                 # A predição relevante é a última da sequência
                 ai_signal_code = int(raw_prediction[-1]) 
            elif isinstance(raw_prediction, (int, np.integer)):
                 ai_signal_code = int(raw_prediction)
            else:
                 logger.warning(f"Predição inesperada do modelo: {raw_prediction}. Assumindo HOLD (Código 0).")
                 ai_signal_code = 0 # Usar 0 para HOLD/VENDA (depende do treino)

            # Mapeia código (Ex: 1=COMPRA, 0=VENDA/HOLD)
            ai_signal = "COMPRA" if ai_signal_code == 1 else "VENDA" # Ajuste se 0 for HOLD

            logger.info(f"Sinal da IA para {asset_symbol} em {target_datetime}: {ai_signal} (Código: {ai_signal_code})")

        except Exception as e:
            logger.error(f"Erro ao obter predição do modelo para {asset_symbol}: {e}", exc_info=True)
            ai_signal = "ERRO_IA"
            ai_signal_code = -1 

        # 5. Avaliar Setups Técnicos
        setup_rules = asset_config.get('setup', [])
        setup_result = {"is_valid": True, "details": {}, "final_decision": ai_signal}
        
        if setup_rules: 
            try:
                setup_result = self.setup_analyzer.evaluate_setups(current_features_row, setup_rules, ai_signal)
                logger.info(f"Resultado Setup {asset_symbol}: Válido={setup_result['is_valid']}, Decisão={setup_result['final_decision']}")
            except Exception as e:
                logger.error(f"Erro ao avaliar setups para {asset_symbol}: {e}", exc_info=True)
                setup_result = {"is_valid": False, "details": {"erro": str(e)}, "final_decision": "HOLD"} 

        # 6. Calcular Stops (se houver sinal de entrada)
        stop_loss_price = None
        take_profit_price = None
        current_price = current_features_row['close'].iloc[0] 
        final_signal = setup_result["final_decision"] # Decisão após análise de setup

        if final_signal in ["COMPRA", "VENDA"]:
            trading_rules = asset_config.get('trading_rules', {})
            sl_pct = trading_rules.get('stop_loss_pct')
            tp_pct = trading_rules.get('take_profit_pct')
            price_precision = asset_config.get('price_precision', 2) # Pega precisão do config ou default 2

            if sl_pct is not None:
                if final_signal == "COMPRA":
                    stop_loss_price = round(current_price * (1 - sl_pct / 100), price_precision)
                else: # VENDA
                    stop_loss_price = round(current_price * (1 + sl_pct / 100), price_precision)
            
            if tp_pct is not None:
                if final_signal == "COMPRA":
                    take_profit_price = round(current_price * (1 + tp_pct / 100), price_precision)
                else: # VENDA
                    take_profit_price = round(current_price * (1 - tp_pct / 100), price_precision)
                    
            logger.info(f"Preços Calculados: Entrada={current_price}, SL={stop_loss_price}, TP={take_profit_price}")

        # 7. Montar Resultado Final
        indicators_dict = {}
        try:
             # Pega a Series da linha atual, arredonda e converte para dict
             indicators_series = current_features_row.iloc[0].round(5) 
             indicators_dict = {
                 k: (v if pd.notna(v) and np.isfinite(v) else "N/A") 
                 for k, v in indicators_series.items() 
                 if k in strategy_instance.get_feature_names() or k in ['open','high','low','close','volume'] # Inclui OHLCV também
             }
        except Exception as e:
             logger.warning(f"Erro ao extrair indicadores: {e}")
             indicators_dict = {"erro": "Falha ao extrair"}


        result = {
            "asset": asset_symbol,
            "datetime": target_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            "timeframe": timeframe_str,
            "current_price": round(current_price, asset_config.get('price_precision', 2)),
            "ai_signal": ai_signal,
            "ai_signal_code": ai_signal_code,
            "setup_is_valid": setup_result["is_valid"],
            "setup_details": setup_result.get("details", {}),
            "final_signal": final_signal, 
            "stop_loss": stop_loss_price if stop_loss_price is not None else "N/A",
            "take_profit": take_profit_price if take_profit_price is not None else "N/A",
            "indicators": indicators_dict # Dicionário de indicadores já tratado
        }

        return result

    def close(self):
        """Fecha conexões com provedores de dados."""
        logger.info("Encerrando conexões dos provedores de dados...")
        for provider_name, provider_instance in self.data_providers.items():
            if hasattr(provider_instance, 'close_connection'):
                try:
                    provider_instance.close_connection()
                    logger.info(f"Conexão com {provider_name} fechada.")
                except Exception as e:
                    logger.warning(f"Erro ao fechar conexão com {provider_name}: {e}")
        self.data_providers = {} # Limpa o cache de providers


# Exemplo de uso (pode ser executado isoladamente para teste)
if __name__ == '__main__':
    engine = SimulationEngine(config_path='configs/main.yaml')
    
    # Simula para WDO$ no H1 em um datetime específico
    sim_asset = 'WDO$'
    sim_tf = 'H1'
    # Use um datetime que você sabe que existe nos seus dados H1
    sim_dt = datetime(2025, 9, 25, 10, 0, 0) # Exemplo: 25/09/2025 às 10:00:00
    
    # Exemplo para WIN$ no D1
    # sim_asset = 'WIN$'
    # sim_tf = 'D1'
    # sim_dt = datetime(2025, 9, 29, 0, 0, 0) # Exemplo: 29/09/2025 (início do dia)

    try:
        result = engine.run_simulation_cycle(sim_asset, sim_tf, sim_dt)
        
        # Imprime o resultado formatado
        import json
        print(json.dumps(result, indent=4, default=str)) # Usa default=str para lidar com tipos não serializáveis

    except Exception as e:
         print(f"Ocorreu um erro na simulação: {e}")
    finally:
         engine.close() # Garante que as conexões sejam fechadas