# test_context_analyzer.py

"""
Script de teste para o MarketContextAnalyzer.

Demonstra análise técnica em dados históricos do WDO$.
"""

import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from src.analysis.context_analyzer import MarketContextAnalyzer
from src.data_handler.provider import MetaTraderProvider

def test_context_analyzer():
    """Testa o analisador de contexto com dados reais."""
    
    print("=" * 80)
    print("TESTE DO MARKET CONTEXT ANALYZER")
    print("=" * 80)
    
    # Inicializa provider
    print("\n1. Conectando ao MT5...")
    provider = MetaTraderProvider()
    
    if not provider.is_connected():
        print("❌ Erro: MT5 não conectado. Abra o terminal e faça login.")
        return
    
    print("✅ MT5 conectado!")
    
    # Busca dados históricos
    print("\n2. Buscando dados históricos do WDO$ (M5)...")
    data = provider.get_latest_candles(
        ticker="WDO$",
        timeframe=mt5.TIMEFRAME_M5,
        count=200
    )
    
    if data.empty:
        print("❌ Erro: Nenhum dado retornado.")
        return
    
    print(f"✅ {len(data)} candles carregados")
    print(f"   Período: {data.index[0]} até {data.index[-1]}")
    
    # Inicializa analisador
    print("\n3. Inicializando MarketContextAnalyzer...")
    analyzer = MarketContextAnalyzer(
        ema_fast=9,
        sma_slow=50,
        rsi_period=14,
        lookback_levels=20
    )
    print("✅ Analisador inicializado!")
    
    # Executa análise
    print("\n4. Executando análise técnica completa...")
    context = analyzer.analyze(data)
    
    # Exibe resultados
    print("\n" + "=" * 80)
    print("RESULTADO DA ANÁLISE")
    print("=" * 80)
    
    print(f"\n📊 PREÇO ATUAL: R$ {context['current_price']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
    
    print(f"\n📈 TENDÊNCIA")
    print(f"   Direção: {context['trend']}")
    print(f"   Força: {context['trend_strength']}")
    print(f"   EMA(9): {context['ema_fast']:.2f}")
    print(f"   SMA(50): {context['sma_slow']:.2f}")
    
    print(f"\n💪 FORÇA DO MERCADO")
    print(f"   RSI(14): {context['rsi']:.2f}")
    print(f"   Condição: {context['rsi_condition']}")
    
    print(f"\n🎯 NÍVEIS CHAVE (Últimos 20 períodos)")
    print(f"   Suporte: R$ {context['support']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
    print(f"   Resistência: R$ {context['resistance']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
    print(f"   Distância do Suporte: {context['distance_to_support']:.2f}%")
    print(f"   Distância da Resistência: {context['distance_to_resistance']:.2f}%")
    
    print(f"\n🕯️ PRICE ACTION")
    print(f"   Padrão: {context['pattern']}")
    
    # Testa validação de sinais
    print("\n" + "=" * 80)
    print("TESTE DE VALIDAÇÃO DE SINAIS")
    print("=" * 80)
    
    # Testa sinal de CALL
    valid_call, reason_call = analyzer.validate_signal('CALL', context, require_trend_alignment=False)
    print(f"\n🔼 SINAL DE CALL:")
    print(f"   Válido: {'✅ SIM' if valid_call else '❌ NÃO'}")
    print(f"   Razão: {reason_call}")
    
    # Testa sinal de PUT
    valid_put, reason_put = analyzer.validate_signal('PUT', context, require_trend_alignment=False)
    print(f"\n🔽 SINAL DE PUT:")
    print(f"   Válido: {'✅ SIM' if valid_put else '❌ NÃO'}")
    print(f"   Razão: {reason_put}")
    
    # Fecha conexão
    provider.close_connection()
    
    print("\n" + "=" * 80)
    print("TESTE CONCLUÍDO!")
    print("=" * 80)


if __name__ == "__main__":
    test_context_analyzer()
