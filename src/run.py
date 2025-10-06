# src/run.py
from datetime import timedelta
import yaml
import importlib
import logging
import numpy as np
import pandas as pd # Adicionado

from src.data_handler.provider import YFinanceProvider, MetaTraderProvider 
from src.backtest_engine.engine import WalkForwardBacktester
from src.backtest_engine.runner import simulate_trades_with_stops

from src.reporting.plot import generate_report, generate_trades_report

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

"""
# método movido para o arquivo backtest_engine/runner.py
def simulate_trades_with_stops(market_data: pd.DataFrame, signals: pd.DataFrame, initial_capital: float,stop_loss_pct: float, take_profit_pct: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Simula trades com capital inicial, posições compradas e vendidas.
    
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
"""

def main():
    """
    Ponto de entrada principal que agora separa o treino (in-sample)
    da simulação de performance (out-of-sample).
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



    ticker = config['data_settings']['ticker']
    sentiment_ticker = config['data_settings'].get('sentiment_ticker', '') if config['data_settings'].get('use_sentiment', False) else ''
    logging.info("Buscando dados IN-SAMPLE para treino do modelo...")
    market_data_is = data_provider.get_data(
        ticker=ticker,
        start_date=config['data_settings']['in_sample']['start_date'],
        end_date=config['data_settings']['in_sample']['end_date'],
        sentiment_ticker=sentiment_ticker
    )

    logging.info("Buscando dados OUT-OF-SAMPLE para simulação...")
    oos_start_date = config['data_settings']['out_of_sample']['start_date']
    
    # Buscamos dados um pouco antes para garantir o lookback da LSTM
    fetch_start_date = pd.to_datetime(oos_start_date) - timedelta(days=180)
    market_data_oos = data_provider.get_data(
        ticker=ticker,
        start_date=fetch_start_date.strftime('%Y-%m-%d'),
        end_date=config['data_settings']['out_of_sample']['end_date'],
        sentiment_ticker=sentiment_ticker
    )

    if market_data_is.empty or market_data_oos.empty:
        logging.error("Falha ao carregar dados. Abortando.")
        return

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

    # --- FASE 1: TREINO DO MODELO FINAL (IN-SAMPLE) ---
    logging.info("Iniciando a fase de treino com dados In-Sample...")
    
    # Preparar dados de treino
    featured_data_is = strategy_instance.define_features(market_data_is)
    featured_data_is['target'] = (featured_data_is['close'].shift(-1) > featured_data_is['close']).astype(int)
    featured_data_is = featured_data_is.dropna()

    X_is = featured_data_is[strategy_instance.get_feature_names()]
    y_is = featured_data_is['target']

    # Treinar o modelo final
    production_model = strategy_instance.define_model()
    production_model.fit(X_is, y_is)
    logging.info("Modelo final treinado com sucesso.")

    # --- FASE 2: SIMULAÇÃO (OUT-OF-SAMPLE) ---
    logging.info("Iniciando a fase de simulação com dados Out-of-Sample...")

    # Preparar dados de simulação
    featured_data_oos = strategy_instance.define_features(market_data_oos)
    featured_data_oos['target'] = (featured_data_oos['close'].shift(-1) > featured_data_oos['close']).astype(int)
    featured_data_oos = featured_data_oos.dropna()
    
    X_oos = featured_data_oos[strategy_instance.get_feature_names()]
    
    # Garantir que estamos simulando apenas no período OOS correto
    X_oos = X_oos.loc[oos_start_date:]

    if not X_oos.empty:
        predictions_oos = production_model.predict(X_oos)
        
        prediction_start_index = len(X_oos) - len(predictions_oos)
        prediction_dates = X_oos.index[prediction_start_index:]
        
        # --- CORREÇÃO AQUI: Criar o DataFrame de resultados completo ---
        results_signals = pd.DataFrame({
            'Prediction': predictions_oos
        }, index=prediction_dates)
        
        # Adiciona o 'Real_Target' para o cálculo da acurácia no relatório
        results_signals['Real_Target'] = featured_data_oos.loc[prediction_dates, 'target']

        # Simular trades
        trading_rules = config['trading_rules']
        strategy_returns, trades_log = simulate_trades_with_stops(
            market_data_oos, results_signals, 
            trading_rules['initial_capital'], 
            trading_rules['stop_loss_pct'], 
            trading_rules['take_profit_pct']
        )

        # 7. Gerar relatórios da performance OUT-OF-SAMPLE
        if not strategy_returns.empty:
            reporting_cfg = config['reporting_settings']
            # Adiciona a coluna de retornos de mercado para o gráfico de benchmark
            results_signals['returns'] = market_data_oos['close'].pct_change()
            results_report = results_signals.join(strategy_returns, how='left').fillna(0)
            
            logging.info("Gerando relatório de performance OOS...")
            generate_report(results_report, reporting_cfg['performance_report_path'], config)
            logging.info(f"Relatório de performance salvo em: {reporting_cfg['performance_report_path']}")

            logging.info("Gerando relatório de operações OOS...")
            generate_trades_report(trades_log, reporting_cfg['trades_report_path'], config)
            logging.info(f"Relatório de operações salvo em: {reporting_cfg['trades_report_path']}")
        else:
            logging.warning("Nenhum resultado OOS para gerar relatórios.")
    else:
        logging.warning("Não há dados Out-of-Sample para fazer previsões.")

if __name__ == "__main__":
    main()