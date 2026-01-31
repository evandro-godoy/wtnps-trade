# [QA] Criar Teste de Contrato (Contract Test)

## 🎯 Objetivo
Validar que dados de MetaTraderProvider atendem contrato esperado por LSTMAdapter.

## 📂 Contexto & Arquivos
- **Alvo:** `tests/integration/test_mt5_contract.py`
- **Dependências:** `src/data_handler/mt5_provider.py`, `src/modules/strategy/lstm_adapter.py`

## 🛠️ Especificações Técnicas
1. **Teste de Contrato:** Verificar formato de `MarketDataEvent`:
   - Fields: symbol, timeframe, open, high, low, close, volume, timestamp
   - Types: str, str, float, float, float, float, int, datetime
2. **Validação de Shape:** Garantir que após `define_features()`:
   - DataFrame tem colunas esperadas por modelo
   - Shape após `.reshape()` = (1, lookback, n_features)
3. **Teste de Integração:** MT5Provider → EventBus → LSTMAdapter → SignalEvent

## 🔗 Dependências & Bloqueios
- [ ] DATA-001 (MT5Provider) deve estar merged ✅
- [ ] MT5 terminal ativo para teste (ou usar mock controlado)

## 📦 Definition of Done (DoD)
- [ ] Contract test implementado
- [ ] Testa todos os campos de MarketDataEvent
- [ ] Valida shape de dados pós-features
- [ ] Teste passa em CI (Python 3.12)
- [ ] Documentação explica propósito do contract test

## 📊 Estimativa
- **Story Points:** 8
- **Horas:** 10h
- **Prioridade:** 🟡 MÉDIA (paralela após DATA-001)
