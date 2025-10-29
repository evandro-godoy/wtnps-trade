# train_model.py
import yaml
import logging
from pathlib import Path
import importlib
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from sklearn.model_selection import train_test_split

# Importa o MÓDULO provider
from src.data_handler import provider as data_provider_module
# Importa a classe base da estratégia para type hinting
from src.strategies.base import BaseStrategy

# Configuração básica do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s') # CORRIGIDO AQUI
logger = logging.getLogger(__name__)

# --- Função auxiliar para conversão de timeframe ---
def _get_mt5_timeframe_from_string(tf_str: str):
    """Converte string de timeframe para constante MT5."""
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
    }
    tf_constant = tf_map.get(tf_str.upper(), None)
    if tf_constant is None:
         logging.warning(f"Timeframe '{tf_str}' não mapeado ou inválido. Verifique o config.yaml.")
    return tf_constant

# --- Função principal de treino ---

def train_all_models(config_path: str = 'configs/main.yaml'):
    """
    Carrega configs, busca dados, treina e salva modelos
    para ativos configurados.
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Config não encontrado: {config_path}")
        return
    except yaml.YAMLError as e:
        logger.error(f"Erro ao ler YAML: {e}")
        return

    global_settings = config.get('global_settings', {})
    models_dir = Path(global_settings.get('models_directory', 'models'))
    models_dir.mkdir(parents=True, exist_ok=True)

    for asset_config in config.get('assets', []):
        asset_symbol = asset_config.get('ticker') # Usa o ticker como ID principal
        if not asset_symbol:
             logger.warning("Config de ativo sem 'ticker'. Pulando.")
             continue

        if not asset_config.get('enabled', True):
            logger.info(f"--- Ativo {asset_symbol} desabilitado. Pulando. ---")
            continue

        logger.info(f"--- Iniciando treino para: {asset_symbol} ---")

        # --- Carregamento da Estratégia ---
        strategy_module_name = asset_config.get('strategy_module')
        strategy_class_name = asset_config.get('strategy_name')
        if not strategy_module_name or not strategy_class_name:
            logger.error(f"strategy_module/strategy_name não definido para {asset_symbol}. Pulando.")
            continue

        try:
            strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
            StrategyClass = getattr(strategy_module, strategy_class_name)
            # Passa parâmetros da estratégia do YAML, se existirem
            strategy_params = asset_config.get('strategy_params', {})
            strategy_instance: BaseStrategy = StrategyClass(**strategy_params)
        except (ImportError, AttributeError, TypeError) as e:
            logger.error(f"Erro ao carregar estratégia {strategy_class_name}: {e}")
            continue

        # --- Obtenção de Dados ---
        data_provider_name = asset_config.get('provider', 'MetaTrader5')
        train_cfg = asset_config.get('data', {})
        # Ticker para buscar dados pode ser diferente do symbol principal
        ticker_data = train_cfg.get('ticker_data', asset_symbol) # Usa 'ticker_data' ou fallback para symbol

        # Verifica se as chaves essenciais existem
        required_data_keys = ['start_date', 'end_date', 'timeframe_model']
        if not all(k in train_cfg for k in required_data_keys):
             logger.error(f"Config 'data' incompleta (faltando {', '.join(k for k in required_data_keys if k not in train_cfg)}) para {asset_symbol}. Pulando.")
             continue

        data_provider = None
        try:
            data_provider = data_provider_module.get_provider_instance(data_provider_name)

            # Usa a chave 'timeframe_model' consistentemente
            tf_string = train_cfg['timeframe_model']
            logger.info(f"Buscando dados para {ticker_data} de {train_cfg['start_date']} a {train_cfg['end_date']} @ {tf_string}...")

            mt5_timeframe_obj = _get_mt5_timeframe_from_string(tf_string)

            if mt5_timeframe_obj is None and data_provider_name == 'MetaTrader5':
                logger.error(f"Timeframe '{tf_string}' inválido para MT5 no ativo {asset_symbol}. Pulando.")
                continue

            market_data = data_provider.get_data(
                ticker=ticker_data,
                start_date=train_cfg["start_date"],
                end_date=train_cfg["end_date"],
                timeframe=mt5_timeframe_obj if data_provider_name == 'MetaTrader5' else tf_string
            )

            if market_data.empty:
                logger.warning(f"Nenhum dado retornado para {ticker_data}. Pulando.")
                continue
            logger.info(f"Dados obtidos para {ticker_data}: {len(market_data)} registros.")

        except KeyError as e_key: # Captura KeyError específico
            logger.error(f"Erro ao acessar config de dados para {asset_symbol}: Chave '{e_key}' não encontrada.", exc_info=False)
            continue # Pula para o próximo ativo
        except Exception as e:
            logger.error(f"Erro ao obter dados para {ticker_data} via {data_provider_name}: {e}", exc_info=True)
            continue
        finally:
            if data_provider and hasattr(data_provider, 'close_connection'):
                 try: data_provider.close_connection()
                 except Exception as e_close: logger.warning(f"Erro ao fechar conexão {data_provider_name}: {e_close}")

        # --- Preparação dos Dados ---
        try:
            logger.info(f"Definindo features para {asset_symbol}...")
            data_with_features = strategy_instance.define_features(market_data)

            logger.info(f"Definindo target para {asset_symbol}...")
            target = strategy_instance.define_target(data_with_features)

            feature_names = strategy_instance.get_feature_names()
            missing_features = [f for f in feature_names if f not in data_with_features.columns]
            if missing_features:
                 logger.error(f"Features ausentes para {asset_symbol}: {missing_features}. Verifique {strategy_class_name}.")
                 continue

            features = data_with_features[feature_names]
            combined = pd.concat([features, target.rename('target')], axis=1)
            combined.dropna(inplace=True)

            if combined.empty:
                logger.warning(f"Sem dados restantes após NaNs para {ticker_data}. Pulando.")
                continue

            X = combined[feature_names]
            y = combined['target']
            logger.info(f"Dados preparados para {asset_symbol}: {len(X)} amostras.")

        except Exception as e:
            logger.error(f"Erro ao preparar dados para {ticker_data}: {e}", exc_info=True)
            continue

        # --- Definição e Treino ---
        try:
            logger.info(f"Definindo modelo via {strategy_class_name}...")
            production_model = strategy_instance.define_model()

            logger.info(f"Iniciando treino do modelo para {asset_symbol}...")
            production_model.fit(X, y)
            logger.info(f"Treino para {asset_symbol} concluído.")

        except Exception as e:
            logger.error(f"Erro definição/treino para {asset_symbol}: {e}", exc_info=True)
            continue

        # --- Salvamento ---
        try:
            # Usa asset_symbol (ticker principal) para nomear o arquivo
            model_save_prefix = str(models_dir / f"{asset_symbol}_prod")
            logger.info(f"Salvando modelo para {asset_symbol} -> {model_save_prefix}...")
            strategy_instance.save(production_model, model_save_prefix)
            logger.info(f"Modelo para {asset_symbol} salvo com sucesso.")

        except Exception as e:
            logger.error(f"Erro ao salvar modelo para {asset_symbol}: {e}", exc_info=True)
            continue

    logger.info("--- Treinamento de todos os modelos concluído. ---")


if __name__ == "__main__":
    train_all_models()