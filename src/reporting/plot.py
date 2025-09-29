# src/reporting/plot.py
import logging
import pandas as pd
import plotly.graph_objects as go
import numpy as np

def generate_report(results: pd.DataFrame, report_path: str, config: dict):
    """
    Gera um relatório HTML interativo com os resultados do backtest.
    """
    # 1. Calcular retornos acumulados
    results['Cumulative_Strategy_Returns'] = (1 + results['Strategy_Returns']).cumprod()
    results['Cumulative_BuyAndHold_Returns'] = (1 + results['returns']).cumprod()
    
    # 2. Criar a figura do Plotly
    fig = go.Figure()

    # Adicionar linha da estratégia
    fig.add_trace(go.Scatter(
        x=results.index,
        y=results['Cumulative_Strategy_Returns'],
        mode='lines',
        name='Nossa Estratégia',
        line=dict(color='royalblue', width=2)
    ))

    # Adicionar linha do Buy and Hold
    fig.add_trace(go.Scatter(
        x=results.index,
        y=results['Cumulative_BuyAndHold_Returns'],
        mode='lines',
        name='Comprar e Segurar (Buy and Hold)',
        line=dict(color='darkorange', width=2)
    ))

    # 3. Calcular Métricas
    accuracy = results['Real_Target'].eq(results['Prediction']).mean()
    strategy_returns = results['Strategy_Returns']
    sharpe_ratio = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252)

    # 4. Customizar o layout
    fig.update_layout(
        title=f"Performance da Estratégia '{config['backtest_settings']['strategy_name']}' vs. Buy and Hold para {config['data_settings']['ticker']}<br>"
              f"<b>Acurácia: {accuracy:.2%} | Sharpe Ratio Anualizado: {sharpe_ratio:.2f}</b>",
        xaxis_title='Data',
        yaxis_title='Retorno Acumulado',
        legend_title='Série',
        template='plotly_dark'
    )

    # 5. Salvar o arquivo HTML
    fig.write_html(report_path)

# Adicione esta nova função ao final de src/reporting/plot.py

def generate_trades_report(trades_df: pd.DataFrame, output_path: str, config: dict):
    """
    Gera um relatório HTML com a lista detalhada de todas as operações.
    """
    if trades_df.empty:
        logging.warning("O DataFrame de trades está vazio. Nenhum relatório de operações será gerado.")
        return

    # Formatação das colunas para melhor visualização
    trades_to_display = trades_df.copy()
    trades_to_display['Preço Entrada'] = trades_to_display['Preço Entrada'].map('${:,.2f}'.format)
    trades_to_display['Preço Saída'] = trades_to_display['Preço Saída'].map('${:,.2f}'.format)
    trades_to_display['Resultado (%)'] = trades_to_display['Resultado (%)'].map('{:,.2f}%'.format)
    
    # Formatação de datas
    trades_to_display['Data Entrada'] = trades_to_display['Data Entrada'].dt.strftime('%Y-%m-%d')
    trades_to_display['Data Saída'] = trades_to_display['Data Saída'].dt.strftime('%Y-%m-%d')

    # Seleciona e renomeia as colunas para o relatório final
    trades_to_display = trades_to_display[[
        'Tipo', 'Data Entrada', 'Preço Entrada', 'Data Saída', 'Preço Saída',
        'Resultado (%)', 'Motivo Saída'
    ]]

    # Estilização da tabela HTML
    html_table = trades_to_display.to_html(index=False, classes='styled-table', border=0)
    
    # Template HTML completo
    html_template = f"""
    <html>
    <head>
        <title>Relatório de Operações</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f4f9; margin: 20px; }}
            h1 {{ color: #333; }}
            .styled-table {{
                border-collapse: collapse;
                margin: 25px 0;
                font-size: 0.9em;
                min-width: 400px;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
                width: 100%;
            }}
            .styled-table thead tr {{
                background-color: #009879;
                color: #ffffff;
                text-align: left;
            }}
            .styled-table th, .styled-table td {{
                padding: 12px 15px;
            }}
            .styled-table tbody tr {{
                border-bottom: 1px solid #dddddd;
            }}
            .styled-table tbody tr:nth-of-type(even) {{
                background-color: #f3f3f3;
            }}
            .styled-table tbody tr:last-of-type {{
                border-bottom: 2px solid #009879;
            }}
        </style>
    </head>
    <body>
        <h1>Relatório de Operações - {config['data_settings']['ticker']}</h1>
        {html_table}
    </body>
    </html>
    """

    with open(output_path, 'w') as f:
        f.write(html_template)