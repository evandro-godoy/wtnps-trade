# src/reporting/plot.py
import logging
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# Dentro de src/reporting/plot.py

def generate_report(results: pd.DataFrame, output_path: str, config: dict):
    """
    Gera um relatório HTML com gráficos de performance da estratégia.
    """
    if results.empty:
        logging.warning("DataFrame de resultados vazio. Nenhum relatório de performance será gerado.")
        return
    
    # --- CORREÇÃO AQUI: Cálculo de acurácia mais robusto ---
    accuracy_text = ""
    if 'Real_Target' in results.columns and 'Prediction' in results.columns:
        accuracy = results['Real_Target'].eq(results['Prediction']).mean()
        accuracy_text = f"Acurácia: {accuracy:.2%}"
        strategy_returns = results['Strategy_Returns']
        sharpe_ratio = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252)

    # Adiciona os retornos de Buy & Hold para comparação
    if 'returns' not in results.columns:
        logging.warning("Coluna 'returns' não encontrada. O benchmark Buy & Hold não será plotado.")
        results['Buy_and_Hold_Returns'] = 0
    else:
        results['Buy_and_Hold_Returns'] = results['returns']

    results['Strategy_Cumulative'] = (1 + results['Strategy_Returns']).cumprod() - 1
    results['Buy_and_Hold_Cumulative'] = (1 + results['Buy_and_Hold_Returns']).cumprod() - 1

    # Cria o gráfico
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=results.index, y=results['Strategy_Cumulative'], mode='lines', name='Estratégia'))
    fig.add_trace(go.Scatter(x=results.index, y=results['Buy_and_Hold_Cumulative'], mode='lines', name='Buy and Hold'))

    fig.update_layout(
        title=f"Performance da Estratégia vs. Buy and Hold - {accuracy_text} | Sharpe Ratio Anualizado: {sharpe_ratio:.2f}",
        xaxis_title="Data",
        yaxis_title="Retorno Acumulado",
        template="plotly_dark"
    )

    fig.write_html(output_path)

def generate_trades_report(trades_df: pd.DataFrame, output_path: str, config: dict):
    """
    Gera um relatório HTML com a lista detalhada de todas as operações.
    """
    if trades_df.empty:
        logging.warning("O DataFrame de trades está vazio. Nenhum relatório de operações será gerado.")
        return

    # Formatação das colunas
    trades_to_display = trades_df.copy()
    trades_to_display['Preço Entrada'] = trades_to_display['Preço Entrada'].map('${:,.2f}'.format)
    trades_to_display['Preço Saída'] = trades_to_display['Preço Saída'].map('${:,.2f}'.format)
    trades_to_display['Resultado ($)'] = trades_to_display['Resultado ($)'].map('${:,.2f}'.format)
    trades_to_display['Resultado (%)'] = trades_to_display['Resultado (%)'].map('{:,.2f}%'.format)
    trades_to_display['Capital Acumulado'] = trades_to_display['Capital Acumulado'].map('${:,.2f}'.format)
    
    trades_to_display['Data Entrada'] = trades_to_display['Data Entrada'].dt.strftime('%Y-%m-%d')
    trades_to_display['Data Saída'] = trades_to_display['Data Saída'].dt.strftime('%Y-%m-%d')

    # Seleciona e renomeia as colunas para o relatório final
    trades_to_display = trades_to_display[[
        'Tipo', 'Data Entrada', 'Preço Entrada', 'Data Saída', 'Preço Saída',
        'Resultado ($)', 'Resultado (%)', 'Capital Acumulado', 'Motivo Saída'
    ]]
    
    # Adiciona cor para lucro/prejuízo
    def style_result(val):
        color = 'red' if val.startswith('$-') else 'green'
        return f'color: {color}'

    styled_html = (trades_to_display.style
                   .applymap(style_result, subset=['Resultado ($)'])
                   .to_html(index=False, classes='styled-table', border=0))

    # Template HTML
    html_template = f"""
    <html>
    <head>
        <title>Relatório de Operações</title>
        <style>
            /* ... (mesmo CSS de antes) ... */
        </style>
    </head>
    <body>
        <h1>Relatório de Operações - {config['data_settings']['ticker']}</h1>
        <h3>Capital Inicial: ${config['trading_rules']['initial_capital']:,.2f}</h3>
        {styled_html}
    </body>
    </html>
    """

    with open(output_path, 'w') as f:
        f.write(html_template)