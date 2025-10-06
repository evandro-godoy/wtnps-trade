# train_model.py
import yaml
import logging
from pathlib import Path
import importlib
from src.data_handler.provider import YFinanceProvider, MetaTraderProvider 
from src.strategies.sentiment_lstm import SentimentLSTMStrategy

def train_and_save_production_model():
    """
    Script para treinar o modelo de produção com todos os dados históricos
    e salvá-lo para uso futuro pelo robô de trading.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # 1. Carregar configuração
    logging.info("Carregando arquivo de configuração...")
    with open("configs/main.yaml", 'r') as file:
        config = yaml.safe_load(file)

    # 2. Obter dados de mercado para os dois períodos
    provider_name = config['data_settings'].get('provider', 'metatrader5') # Padrão para MetaTrader5
    if provider_name == 'metatrader5':
        data_provider = MetaTraderProvider()
        logging.info("Usando o provedor de dados: MetaTrader 5")
    else:
        data_provider = YFinanceProvider()
        logging.info("Usando o provedor de dados: Yahoo Finance")

    train_cfg = config['data_settings']['in_sample']
    market_data_is = data_provider.get_data(
        ticker=config['data_settings']['ticker'],
        start_date=train_cfg['start_date'],
        end_date=train_cfg['end_date'],
        sentiment_ticker=config['data_settings'].get('sentiment_ticker', '')
    )

    # 3. Carregar a estratégia dinamicamente
    try:
        strategy_name = config['backtest_settings']['strategy_name']
        module_path = f"src.strategies.{config['backtest_settings']['strategy_module']}"
        strategy_module = importlib.import_module(module_path)
        StrategyClass = getattr(strategy_module, strategy_name)
        strategy_instance = StrategyClass()
    except (ImportError, AttributeError) as e:
        logging.error(f"Não foi possível carregar a estratégia. Erro: {e}")
        return

    # 3. Preparar dados
    strategy = strategy_instance
    featured_data = strategy.define_features(market_data_is)
    featured_data['target'] = (featured_data['close'].shift(-1) > featured_data['close']).astype(int)
    featured_data = featured_data.dropna()

    X_train = featured_data[strategy.get_feature_names()]
    y_train = featured_data['target']

    # 4. Treinar o modelo
    logging.info(f"Treinando modelo de produção com {len(X_train)} amostras...")
    production_model = strategy.define_model()
    production_model.fit(X_train, y_train)

    # 5. Salvar o modelo
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)
    production_model.save_model(
        model_path=str(models_dir / "prod_model.keras"),
        scaler_path=str(models_dir / "prod_scaler.joblib")
    )
    logging.info("Modelo de produção treinado e salvo com sucesso.")

if __name__ == "__main__":
    train_and_save_production_model()