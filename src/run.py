# src/run.py
import yaml
import importlib
import logging
import numpy as np # Adicionada importação que estava faltando

from src.data_handler.provider import YFinanceProvider
from src.backtest_engine.engine import WalkForwardBacktester
from src.reporting.plot import generate_report

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """Ponto de entrada principal para a execução do backtest."""
    
    # 1. Carregar configuração
    logging.info("Carregando arquivo de configuração...")
    with open("configs/main.yaml", 'r') as file:
        config = yaml.safe_load(file)

    # 2. Obter dados de mercado
    data_provider = YFinanceProvider()
    market_data = data_provider.get_data(
        ticker=config['data_settings']['ticker'],
        start_date=config['data_settings']['start_date'],
        end_date=config['data_settings']['end_date']
    )

    # 3. Carregar a estratégia dinamicamente (MODO ROBUSTO)
    strategy_name = config['backtest_settings']['strategy_name']
    strategy_module_name = config['backtest_settings']['strategy_module']
    logging.info(f"Carregando classe '{strategy_name}' do módulo '{strategy_module_name}'")
    try:
        # Importa o módulo (ex: src.strategies.random_forest)
        module_path = f"src.strategies.{strategy_module_name}"
        strategy_module = importlib.import_module(module_path)
        # Pega a classe dentro do módulo (ex: RandomForestFeatureStrategy)
        StrategyClass = getattr(strategy_module, strategy_name)
    except (ImportError, AttributeError) as e:
        logging.error(f"Não foi possível carregar a estratégia '{strategy_name}'. Verifique o nome e a estrutura do arquivo. Erro: {e}")
        return

    strategy_instance = StrategyClass()
    
    # 4. Executar o backtest
    backtester = WalkForwardBacktester(
        strategy=strategy_instance,
        n_splits=config['backtest_settings']['n_splits']
    )
    results = backtester.run(market_data)
    
    # Lógica da Estratégia de Retorno (comprar se previsão for 1)
    results['Strategy_Returns'] = np.where(results['Prediction'] == 1, results['Returns'], 0)

    # 5. Gerar o relatório
    logging.info("Gerando relatório de performance...")
    generate_report(results, config['reporting_settings']['output_path'], config)
    logging.info(f"Relatório salvo em: {config['reporting_settings']['output_path']}")

if __name__ == "__main__":
    main()