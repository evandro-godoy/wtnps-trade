# [DATA] Implementar MetaTraderProvider

## 🎯 Objetivo
Criar classe MetaTraderProvider que conecta ao MT5 e publica dados reais no EventBus.

## 📂 Contexto & Arquivos
- **Alvo:** `src/data_handler/mt5_provider.py`
- **Dependências:** `MetaTrader5`, `src/core/event_bus.py`, `src/events.py`

## 🛠️ Especificações Técnicas
1. **Biblioteca:** Usar `MetaTrader5` (import mt5)
2. **Inicialização:** `mt5.initialize()`
   - Se falhar → lançar `ConnectionError` com mensagem clara
   - NÃO implementar retry loops (Fail Fast)
3. **Buscar Candles:** `mt5.copy_rates_from_pos(symbol, MT5_TIMEFRAME_M5, start_pos, count)`
   - Converter para pandas DataFrame
   - Validar colunas: time, open, high, low, close, volume
4. **Publicação EventBus:**
   - Para cada candle → criar `MarketDataEvent`
   - `event_bus.publish(event)`
5. **Estratégia Fail Fast:** 
   - Qualquer erro de conexão/dados → lançar exceção
   - Logar erro com logger.critical() antes de lançar

## 🔗 Dependências & Bloqueios
- [ ] MT5 terminal instalado e rodando
- [ ] Credenciais configuradas em `.env`
- [ ] EventBus operacional (Sprint 1 ✅)

## 📦 Definition of Done (DoD)
- [ ] Classe implementada com método `get_latest_candles(symbol, timeframe, count)`
- [ ] `mt5.initialize()` lança `ConnectionError` se falhar (sem retry)
- [ ] DataFrame convertido para `MarketDataEvent` corretamente
- [ ] Validação de dtypes: float64 para OHLC, int64 para volume, datetime64 para time
- [ ] Teste unitário simula MT5 offline → exceção capturada
- [ ] Teste de integração com MT5 real (requer terminal ativo)
- [ ] Docstrings explicam exceções que podem ser lançadas
- [ ] README atualizado: "Se MT5 não conectar, sistema para imediatamente"

## 📊 Estimativa
- **Story Points:** 13
- **Horas:** 16h
- **Prioridade:** 🔴 ALTA (bloqueia ARCH-003)
