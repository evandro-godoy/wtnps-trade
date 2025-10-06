# src/simulation/runner.py
import pandas as pd
import logging

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


def run_external_simulation(model, strategy, market_data: pd.DataFrame, config: dict):
    """
    Executa uma simulação de trading completa em um conjunto de dados,
    usando um modelo e uma estratégia pré-definidos. Ideal para notebooks.

    Args:
        model: Um objeto de modelo já treinado (com métodos .fit e .predict).
        strategy: Uma instância da classe de estratégia (ex: SentimentLSTMStrategy()).
        market_data (pd.DataFrame): DataFrame com os dados de mercado para a simulação.
        config (dict): Dicionário de configuração contendo as trading_rules.

    Returns:
        pd.DataFrame: Um DataFrame com o log detalhado das operações.
    """
    logging.info("Iniciando simulação externa...")

    # 1. Preparar os dados e gerar features
    featured_data = strategy.define_features(market_data)
    X_data = featured_data[strategy.get_feature_names()].dropna()

    if X_data.empty:
        logging.warning("Não há dados para fazer previsões após o pré-processamento.")
        return pd.DataFrame()

    # 2. Fazer previsões com o modelo fornecido
    logging.info(f"Gerando previsões para {len(X_data)} pontos de dados...")
    predictions = model.predict(X_data)
    
    # Alinhar as previsões com as datas corretas (considerando o lookback da LSTM)
    prediction_start_index = len(X_data) - len(predictions)
    prediction_dates = X_data.index[prediction_start_index:]
    
    signals = pd.DataFrame({'Prediction': predictions}, index=prediction_dates)

    # 3. Executar a simulação de trades
    trading_rules = config['trading_rules']
    _, trades_log = simulate_trades_with_stops(
        market_data=market_data,
        signals=signals,
        initial_capital=trading_rules['initial_capital'],
        stop_loss_pct=trading_rules['stop_loss_pct'],
        take_profit_pct=trading_rules['take_profit_pct']
    )
    
    logging.info("Simulação externa concluída.")
    return trades_log