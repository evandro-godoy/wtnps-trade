# [QUANT] Refinar Carregamento de Modelo (Inference Mode)

## 🎯 Objetivo
Garantir carregamento robusto do modelo LSTM com validação de input_shape e tratamento de erros.

## 📂 Contexto & Arquivos
- **Alvo:** `src/modules/strategy/lstm_adapter.py`
- **Dependências:** `models/` directory, `joblib`, `keras`

## 🛠️ Especificações Técnicas
1. **Exception Handling:** Try/except ao carregar modelo (.keras) e scaler (.joblib)
2. **Validação de Shape:** Verificar `input_shape` do modelo vs. features reais
3. **Fallback:** Se modelo ausente → log CRITICAL + shutdown gracioso (fail-fast)
4. **Conversão Defensiva:** `np.array(X)` antes de `.reshape()` (evitar bug Sprint 1)

## 🔗 Dependências & Bloqueios
- [ ] Modelo treinado existe em `models/WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras`
- [ ] Scaler existe em `models/WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib`

## 📦 Definition of Done (DoD)
- [ ] Exception handling implementado
- [ ] Input shape validado (log se mismatch)
- [ ] Conversão `np.array(X)` adicionada
- [ ] Testes unitários cobrem cenário "modelo ausente"
- [ ] Logs claros guiam usuário ao erro

## 📊 Estimativa
- **Story Points:** 5
- **Horas:** 6h
- **Prioridade:** 🟡 MÉDIA (paralela com DATA-001)
