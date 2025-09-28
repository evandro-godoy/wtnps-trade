# src/run.py
import yaml
import importlib
import logging
import numpy as np
import pandas as pd # Adicionado

from src.data_handler.provider import YFinanceProvider
from src.backtest_engine.engine import WalkForwardBacktester
from src.reporting.plot import generate_report

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Dentro do arquivo src/run.py

def simulate_trades_with_stops(market_data: pd.DataFrame, signals: pd.DataFrame, stop_loss_pct: float, take_profit_pct: float) -> pd.DataFrame:
    """
    Simula trades com base nos sinais do modelo, aplicando regras de stop-loss e take-profit.
    """
    logging.info(f"Simulando trades com SL={stop_loss_pct:.2%} e TP={take_profit_pct:.2%}")
    
    trade_data = market_data.loc[signals.index].copy()
    trade_data['Prediction'] = signals['Prediction']
    
    position_open = False
    entry_price = 0
    trade_returns = []
    
    for i in range(len(trade_data)):
        current_date = trade_data.index[i]
        
        if position_open:
            # --- CORREÇÃO AQUI ---
            current_low = trade_data['low'].iloc[i]
            current_high = trade_data['high'].iloc[i]
            
            # Checa Stop Loss
            if current_low <= entry_price * (1 - stop_loss_pct):
                exit_price = entry_price * (1 - stop_loss_pct)
                trade_return = (exit_price / entry_price) - 1
                trade_returns.append({'Date': current_date, 'Strategy_Returns': trade_return})
                position_open = False
                continue

            # Checa Take Profit
            if current_high >= entry_price * (1 + take_profit_pct):
                exit_price = entry_price * (1 + take_profit_pct)
                trade_return = (exit_price / entry_price) - 1
                trade_returns.append({'Date': current_date, 'Strategy_Returns': trade_return})
                position_open = False
                continue

        if not position_open and trade_data['Prediction'].iloc[i] == 1:
            if i + 1 < len(trade_data):
                position_open = True
                # --- CORREÇÃO AQUI ---
                entry_price = trade_data['open'].iloc[i+1]
    
    if not trade_returns:
        logging.warning("Nenhum trade foi executado na simulação.")
        return pd.DataFrame(columns=['Strategy_Returns'])

    results_df = pd.DataFrame(trade_returns).set_index('Date')
    
    all_days_returns = pd.Series(0.0, index=trade_data.index, name="Strategy_Returns")
    all_days_returns.update(results_df['Strategy_Returns'])
    
    return all_days_returns.to_frame()


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

    # 3. Carregar a estratégia dinamicamente
    strategy_name = config['backtest_settings']['strategy_name']
    strategy_module_name = config['backtest_settings']['strategy_module']
    logging.info(f"Carregando classe '{strategy_name}' do módulo '{strategy_module_name}'")
    try:
        module_path = f"src.strategies.{strategy_module_name}"
        strategy_module = importlib.import_module(module_path)
        StrategyClass = getattr(strategy_module, strategy_name)
    except (ImportError, AttributeError) as e:
        logging.error(f"Não foi possível carregar a estratégia '{strategy_name}'. Erro: {e}")
        return

    strategy_instance = StrategyClass()
    
    # 4. Executar o backtest para obter os sinais
    backtester = WalkForwardBacktester(
        strategy=strategy_instance,
        n_splits=config['backtest_settings']['n_splits']
    )
    results_signals = backtester.run(market_data)
    
    # 5. Simular a estratégia de trading com Stop Loss e Take Profit
    stop_loss_pct = config['trading_rules']['stop_loss_pct']
    take_profit_pct = config['trading_rules']['take_profit_pct']
    
    strategy_returns = simulate_trades_with_stops(market_data, results_signals, stop_loss_pct, take_profit_pct)

    # Juntar os resultados para o relatório
    results_report = results_signals.join(strategy_returns, how='left').fillna(0)
    
    # 6. Gerar o relatório
    logging.info("Gerando relatório de performance...")
    generate_report(results_report, config['reporting_settings']['output_path'], config)
    logging.info(f"Relatório salvo em: {config['reporting_settings']['output_path']}")

if __name__ == "__main__":
    main()