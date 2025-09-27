# src/reporting/plot.py
import pandas as pd
import plotly.graph_objects as go
import numpy as np

def generate_report(results: pd.DataFrame, report_path: str, config: dict):
    """
    Gera um relatório HTML interativo com os resultados do backtest.
    """
    # 1. Calcular retornos acumulados
    results['Cumulative_Strategy_Returns'] = (1 + results['Strategy_Returns']).cumprod()
    results['Cumulative_BuyAndHold_Returns'] = (1 + results['Returns']).cumprod()
    
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