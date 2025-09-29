# src/run.py
import yaml
import importlib
import logging
import numpy as np
import pandas as pd # Adicionado

from src.data_handler.provider import YFinanceProvider
from src.backtest_engine.engine import WalkForwardBacktester
from src.reporting.plot import generate_report, generate_trades_report

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def simulate_trades_with_stops(market_data: pd.DataFrame, signals: pd.DataFrame, initial_capital: float,stop_loss_pct: float, take_profit_pct: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Simula trades com capital inicial, posições compradas e vendidas.
    """
    logging.info(f"Simulando trades com capital inicial de ${initial_capital:,.2f}, SL={stop_loss_pct:.2%} e TP={take_profit_pct:.2%}")
    
    capital = initial_capital
    trade_data = market_data.loc[signals.index].copy()
    trade_data['Prediction'] = signals['Prediction']
    
    position_open = None  # Pode ser 'LONG', 'SHORT', ou None
    entry_price = 0
    entry_date = None
    trades_log = []

    for i in range(len(trade_data)):
        current_date = trade_data.index[i]
        
        # --- LÓGICA DE SAÍDA DE POSIÇÃO ---
        if position_open:
            current_low = trade_data['low'].iloc[i]
            current_high = trade_data['high'].iloc[i]
            exit_reason = "End of Data"
            exit_price = trade_data['close'].iloc[i]
            trade_return_pct = 0

            # Lógica para Posição Comprada (LONG)
            if position_open == 'LONG':
                # Checa Stop Loss
                if current_low <= entry_price * (1 - stop_loss_pct):
                    exit_price = entry_price * (1 - stop_loss_pct)
                    exit_reason = "Stop Loss"
                # Checa Take Profit
                elif current_high >= entry_price * (1 + take_profit_pct):
                    exit_price = entry_price * (1 + take_profit_pct)
                    exit_reason = "Take Profit"
            
            # Lógica para Posição Vendida (SHORT)
            elif position_open == 'SHORT':
                # Checa Stop Loss (preço sobe)
                if current_high >= entry_price * (1 + stop_loss_pct):
                    exit_price = entry_price * (1 + stop_loss_pct)
                    exit_reason = "Stop Loss"
                # Checa Take Profit (preço cai)
                elif current_low <= entry_price * (1 - take_profit_pct):
                    exit_price = entry_price * (1 - take_profit_pct)
                    exit_reason = "Take Profit"

            # Se uma condição de saída foi atingida ou é o último dia
            if exit_reason != "End of Data" or i == len(trade_data) - 1:
                # Calcula o lucro/prejuízo
                if position_open == 'LONG':
                    trade_return_pct = (exit_price / entry_price) - 1
                elif position_open == 'SHORT':
                    trade_return_pct = (entry_price / exit_price) - 1
                
                profit_loss = capital * trade_return_pct
                capital += profit_loss
                
                trades_log.append({
                    'Tipo': "Compra" if position_open == 'LONG' else "Venda",
                    'Data Entrada': entry_date,
                    'Preço Entrada': entry_price,
                    'Data Saída': current_date,
                    'Preço Saída': exit_price,
                    'Resultado ($)': profit_loss,
                    'Resultado (%)': trade_return_pct * 100,
                    'Capital Acumulado': capital,
                    'Motivo Saída': exit_reason
                })
                position_open = None

        # --- LÓGICA DE ENTRADA DE POSIÇÃO ---
        if not position_open and i + 1 < len(trade_data):
            signal = trade_data['Prediction'].iloc[i]
            
            # Sinal de Compra (LONG)
            if signal == 1:
                position_open = 'LONG'
                entry_date = trade_data.index[i+1]
                entry_price = trade_data['open'].iloc[i+1]
            # Sinal de Venda (SHORT)
            elif signal == 0:
                position_open = 'SHORT'
                entry_date = trade_data.index[i+1]
                entry_price = trade_data['open'].iloc[i+1]
    
    # --- GERAÇÃO DOS DOIS DATAFRAMES DE RESULTADO ---
    
    if not trades_log:
        logging.warning("Nenhum trade foi executado na simulação.")
        empty_df = pd.DataFrame()
        return empty_df, empty_df

    # 1. DataFrame com o log de trades
    trades_df = pd.DataFrame(trades_log)
    
    # Cria os retornos diários com base na variação do capital
    daily_returns_df = pd.Series(0.0, index=trade_data.index, name="Strategy_Returns")
    trade_dates = trades_df['Data Saída'].tolist()
    trade_returns = trades_df['Resultado (%)'].tolist()
    
    for date, ret in zip(trade_dates, trade_returns):
        daily_returns_df.loc[date] = ret / 100 # Converte de volta para decimal
    
    return daily_returns_df.to_frame(), trades_df


def main():
    """Ponto de entrada principal para a execução do backtest."""
    
    # 1. Carregar configuração
    logging.info("Carregando arquivo de configuração...")
    with open("configs/main.yaml", 'r') as file:
        config = yaml.safe_load(file)

    # 2. Obter dados de mercado
    data_provider = YFinanceProvider()
    sentiment_ticker = config['data_settings'].get('sentiment_ticker', '') if config['data_settings'].get('use_sentiment', False) else ''
    market_data = data_provider.get_data(
        ticker=config['data_settings']['ticker'],
        start_date=config['data_settings']['start_date'],
        end_date=config['data_settings']['end_date'],
        sentiment_ticker=sentiment_ticker
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
    initial_capital = config['trading_rules']['initial_capital']
    stop_loss_pct = config['trading_rules']['stop_loss_pct']
    take_profit_pct = config['trading_rules']['take_profit_pct']

    # strategy_returns = simulate_trades_with_stops(market_data, results_signals, stop_loss_pct, take_profit_pct)
    strategy_returns, trades_log = simulate_trades_with_stops(market_data, results_signals, initial_capital, stop_loss_pct, take_profit_pct)

    # 6. Gerar os relatórios
    if not strategy_returns.empty:
        # Relatório de performance (gráfico)
        results_report = results_signals.join(strategy_returns, how='left').fillna(0)
        logging.info("Gerando relatório de performance...")
        generate_report(results_report, config['reporting_settings']['performance_report_path'], config)
        logging.info(f"Relatório de performance salvo em: {config['reporting_settings']['performance_report_path']}")

        # Relatório de operações (tabela)
        logging.info("Gerando relatório de operações...")
        generate_trades_report(trades_log, config['reporting_settings']['trades_report_path'], config)
        logging.info(f"Relatório de operações salvo em: {config['reporting_settings']['trades_report_path']}")
    else:
        logging.warning("Nenhum resultado para gerar relatórios.")

    # Juntar os resultados para o relatório
    # results_report = results_signals.join(strategy_returns, how='left').fillna(0)
    
    # 6. Gerar o relatório
    # logging.info("Gerando relatório de performance...")
    # generate_report(results_report, config['reporting_settings']['output_path'], config)
    #logging.info(f"Relatório salvo em: {config['reporting_settings']['output_path']}")

if __name__ == "__main__":
    main()