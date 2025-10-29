# train_model.py
import yaml
import logging
from pathlib import Path
import importlib
import pandas as pd
import numpy as np
# Removido: from tensorflow.keras.models import load_model
# Removido: import joblib
import MetaTrader5 as mt5 # Mantém para conversão de timeframe
from sklearn.model_selection import train_test_split # Ainda útil para avaliação opcional

# Importa o MÓDULO provider
from src.data_handler import provider as data_provider_module # <-- CORREÇÃO 1
# Importa a classe base da estratégia para type hinting
from src.strategies.base import BaseStrategy

# Configuração básica do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Função auxiliar para conversão de timeframe (COPIADA) ---
# (Esta função permanece a mesma, pois foi definida localmente)
def _get_mt5_timeframe_from_string(tf_str: str):
    """Converte string de timeframe para constante MT5."""
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
    }
    default_tf = mt5.TIMEFRAME_D1 # Define um padrão caso não encontre
    tf_constant = tf_map.get(tf_str.upper(), None) # Retorna None se não encontrar
    if tf_constant is None:
         logging.warning(f"Timeframe '{tf_str}' não mapeado ou inválido. Verifique o config.yaml.")
    return tf_constant

# --- Função principal de treino ---

def train_all_models(config_path: str = 'configs/main.yaml'):
    """
    Carrega as configurações, busca os dados, treina e salva os modelos
    para todos os ativos configurados.
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Arquivo de configuração não encontrado em {config_path}")
        return
    except yaml.YAMLError as e:
        logger.error(f"Erro ao ler o arquivo YAML de configuração: {e}")
        return

    global_settings = config.get('global_settings', {})
    models_dir = Path(global_settings.get('models_directory', 'models'))
    models_dir.mkdir(parents=True, exist_ok=True) # Garante que o diretório exista

    for asset_symbol, asset_config in config.get('assets', {}).items():
        if not asset_config.get('enabled', True):
            logger.info(f"--- Ativo {asset_symbol} desabilitado no config.yaml. Pulando. ---")
            continue
            
        logger.info(f"--- Iniciando treino para o ativo: {asset_symbol} ---")

        # --- Carregamento da Estratégia ---
        strategy_module_name = asset_config.get('strategy_module')
        strategy_class_name = asset_config.get('strategy_name')
        if not strategy_module_name or not strategy_class_name:
            logger.error(f"strategy_module ou strategy_name não definidos para {asset_symbol}. Pulando.")
            continue
            
        try:
            strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
            StrategyClass = getattr(strategy_module, strategy_class_name)
            strategy_instance: BaseStrategy = StrategyClass() 
        except (ImportError, AttributeError) as e:
            logger.error(f"Erro ao carregar a classe de estratégia {strategy_class_name} do módulo {strategy_module_name}: {e}")
            continue

        # --- Obtenção de Dados ---
        data_provider_name = asset_config.get('provider', 'MetaTrader5')
        train_cfg = asset_config.get('data', {})
        ticker = train_cfg.get('ticker', asset_symbol) # Usa ticker do config de treino

        if not all([train_cfg.get('start_date'), train_cfg.get('end_date'), train_cfg.get('timeframe')]):
             logger.error(f"Configuração de dados (start_date, end_date, timeframe) incompleta para {asset_symbol}. Pulando.")
             continue

        data_provider = None # Inicializa provider fora do try
        try:
            # Chama a função a partir do módulo importado # <-- CORREÇÃO 2
            data_provider = data_provider_module.get_provider_instance(data_provider_name)
            
            logger.info(f"Buscando dados para {ticker} de {train_cfg['start_date']} a {train_cfg['end_date']} @ {train_cfg['timeframe']}...")

            tf_string = train_cfg['timeframe']
            mt5_timeframe_obj = _get_mt5_timeframe_from_string(tf_string)
            
            if mt5_timeframe_obj is None and data_provider_name == 'MetaTrader5':
                logger.error(f"Timeframe '{tf_string}' inválido para MetaTrader5 no ativo {asset_symbol}. Pulando.")
                continue

            market_data = data_provider.get_data(
                ticker=ticker,
                start_date=train_cfg["start_date"],
                end_date=train_cfg["end_date"],
                timeframe=mt5_timeframe_obj if data_provider_name == 'MetaTrader5' else tf_string 
            )

            if market_data.empty:
                logger.warning(f"Nenhum dado retornado para {ticker} no período especificado. Pulando.")
                continue
            logger.info(f"Dados obtidos para {ticker}: {len(market_data)} registros.")

        except Exception as e:
            logger.error(f"Erro ao obter dados para {ticker} via {data_provider_name}: {e}", exc_info=True)
            continue
        finally:
            # Fecha conexão se o provider foi instanciado e tem o método
            if data_provider and hasattr(data_provider, 'close_connection'):
                 try:
                      data_provider.close_connection() 
                 except Exception as e_close:
                      logger.warning(f"Erro ao fechar conexão do provider {data_provider_name}: {e_close}")

        # --- Preparação dos Dados (Features e Target) ---
        try:
            logger.info("Definindo features...")
            data_with_features = strategy_instance.define_features(market_data)
            
            logger.info("Definindo target...")
            target = strategy_instance.define_target(data_with_features)
            
            feature_names = strategy_instance.get_feature_names()
            features = data_with_features[feature_names]

            combined = pd.concat([features, target.rename('target')], axis=1)
            combined.dropna(inplace=True) 
            
            if combined.empty:
                logger.warning(f"Após adicionar features/target e remover NaNs, não restaram dados para {ticker}. Pulando.")
                continue

            X = combined[feature_names]
            y = combined['target']
            
            logger.info(f"Dados preparados: {len(X)} amostras para treino.")

        except Exception as e:
            logger.error(f"Erro ao preparar features/target para {ticker}: {e}", exc_info=True)
            continue
            
        # --- Definição e Treino do Modelo ---
        try:
            logger.info(f"Definindo modelo via {strategy_class_name}...")
            production_model = strategy_instance.define_model() 
            
            logger.info("Iniciando treino do modelo...")
            production_model.fit(X, y) 
            logger.info("Treino concluído.")

        except Exception as e:
            logger.error(f"Erro durante a definição ou treino do modelo para {ticker}: {e}", exc_info=True)
            continue

        # --- Salvamento do Modelo (Usando a Estratégia) ---
        try:
            model_save_prefix = str(models_dir / f"{asset_symbol}_prod") 
            logger.info(f"Salvando modelo treinado para {asset_symbol} usando prefixo: {model_save_prefix}")
            strategy_instance.save(production_model, model_save_prefix) 
            logger.info(f"Modelo para {asset_symbol} salvo com sucesso.")

        except Exception as e:
            logger.error(f"Erro ao salvar o modelo treinado para {asset_symbol}: {e}", exc_info=True)
            continue 

    logger.info("--- Treinamento de todos os modelos concluído. ---")


if __name__ == "__main__":
    train_all_models()