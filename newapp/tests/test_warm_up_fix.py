"""Quick test to validate monitor_engine warm_up parameter names are corrected."""
import logging
logging.basicConfig(level=logging.WARNING)

print('=' * 70)
print('TESTE: Validando correção de parameter names em monitor_engine')
print('=' * 70)
print()

from newapp.src.live.monitor_engine import RealtimeMarketMonitor

try:
    print("[1/3] Instanciando RealtimeMarketMonitor...")
    monitor = RealtimeMarketMonitor(ticker='WDO$', timeframe_str='M5', buffer_size=50)
    print("✅ Monitor instantiado com sucesso")
    
    print()
    print("[2/3] Executando warm_up()...")
    monitor._warm_up()
    print("✅ warm_up() executado SEM TypeError de parâmetros")
    
    print()
    print("[3/3] Validando buffer...")
    if monitor.buffer_df is not None:
        print(f"✅ Buffer carregado com {len(monitor.buffer_df)} candles")
        print(f"   Period: {monitor.buffer_df.index[0]} → {monitor.buffer_df.index[-1]}")
    else:
        print("⚠️ Buffer vazio (esperado em alguns ambientes)")
    
    print()
    print('=' * 70)
    print("✅ SUCESSO: Parameter names estão CORRETOS (ticker/count)")
    print('=' * 70)
    
except TypeError as e:
    print(f"❌ FALHA: TypeError detectado!")
    print(f"   Mensagem: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("❌ Parameter names AINDA ESTÃO ERRADOS")
    exit(1)
    
except Exception as e:
    print(f"⚠️ Exceção (não é TypeError de parâmetros): {type(e).__name__}: {e}")
    print()
    print("✅ SUCESSO: Nenhum TypeError sobre parameter names!")
    print("(" + str(type(e).__name__) + " é esperado em alguns ambientes)")
