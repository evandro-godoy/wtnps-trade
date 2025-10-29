from sklearn import logger
import yaml
import logging
from pathlib import Path
import importlib

from src.data_handler.provider import YFinanceProvider, MetaTraderProvider
from src.strategies.lstm import KerasLSTMWrapper


def train_all_models():
    """
    Itera sobre todos os ativos habilitados no main.yaml,
    treina um modelo para cada um e o salva em um arquivo específico.
    """
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    with open("configs/main.yaml", "r") as file:
        config = yaml.safe_load(file)

    models_dir = Path(config["global_settings"]["model_directory"])
    models_dir.mkdir(exist_ok=True)

    # Itera sobre cada ativo configurado
    for asset_config in config["assets"]:
        if not asset_config.get("enabled", False):
            continue

        ticker = asset_config["ticker"]
        logging.info(f"--- Iniciando treino para o ativo: {ticker} ---")

        # 1. Seleciona o provedor de dados
        provider_name = asset_config.get("provider", "YFinance")
        if provider_name == "MetaTrader5":
            data_provider = MetaTraderProvider()
        else:
            data_provider = YFinanceProvider()


        # 2. Busca dados de treino
        # train_cfg = asset_config["data"]
        # market_data_is = data_provider.get_data(
        #     ticker=ticker,
        #     start_date=train_cfg["start_date"],
        #     end_date=train_cfg["end_date"],
        #     timeframe_str=train_cfg.get("timeframe_model", "H1")
        # )
        
        # 2. Busca dados de treino
        train_cfg = asset_config["data"]

        logging.info(f"Buscando dados para {ticker} de {train_cfg['start_date']} a {train_cfg['end_date']} @ {train_cfg['timeframe_model']}...")

        # 2.1. Obter a string do timeframe do config
        tf_string = train_cfg["timeframe_model"]

        # 2.2. Converter a string (ex: "H1") para o objeto MT5 (ex: mt5.TIMEFRAME_H1)
        mt5_timeframe = data_provider._get_mt5_timeframe_from_string(tf_string)
        
        if mt5_timeframe is None:
            logging.error(f"Timeframe inválido '{tf_string}' no config.yaml para {ticker}. Pulando.")
            continue # Pula para o próximo ativo

        # 2.3. Chamar a função do provedor de dados
        market_data_is = data_provider.get_data(
            ticker=ticker,
            start_date=train_cfg["start_date"],
            end_date=train_cfg["end_date"],
            timeframe=mt5_timeframe  # Usando o objeto timeframe convertido
        )

        if market_data_is.empty:
            logging.error(f"Não foi possível obter dados para {ticker}. Pulando treino.")
            continue

        # 3. Carrega a estratégia e prepara os dados
        try:
            module_path = f"src.strategies.{asset_config['strategy_module']}"
            strategy_module = importlib.import_module(module_path)
            StrategyClass = getattr(strategy_module, asset_config["strategy_name"])
            strategy = StrategyClass()
        except (ImportError, AttributeError) as e:
            logging.error(
                f"Não foi possível carregar a estratégia para {ticker}. Erro: {e}"
            )
            continue

        featured_data = strategy.define_features(market_data_is)
        featured_data["target"] = (
            featured_data["close"].shift(-1) > featured_data["close"]
        ).astype(int)
        featured_data = featured_data.dropna()

        X_train = featured_data[strategy.get_feature_names()]
        y_train = featured_data["target"]

        if X_train.empty:
            logging.warning(f"Não há dados de treino suficientes para {ticker} após o pré-processamento.")
            continue

        # 4. Treina o modelo
        logging.info(
            f"Treinando modelo de produção para {ticker} com {len(X_train)} amostras..."
        )
        production_model = strategy.define_model()
        production_model.fit(X_train, y_train)

        # 5. Salva o modelo com nome específico do ativo
        model_path = str(models_dir / f"{ticker}_prod_model.keras")
        scaler_path = str(models_dir / f"{ticker}_prod_scaler.joblib")
        
        # Garante que o modelo tenha o método save_model (caso seja um KerasLSTMWrapper)
        if hasattr(production_model, 'save_model'):
            production_model.save_model(model_path, scaler_path)
            logging.info(f"Modelo para {ticker} salvo com sucesso.")
        else:
            logging.warning(f"A estratégia para {ticker} não suporta salvar o modelo (sem método save_model).")


if __name__ == "__main__":
    train_all_models()