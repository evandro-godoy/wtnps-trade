# [QUANT] Refinar Carregamento de Modelo (Inference Mode)

## 🎯 Objetivo
Garantir carregamento robusto do modelo LSTM com validação de input_shape e tratamento de erros.

## 📂 Contexto & Arquivos
- **Alvo:** `src/modules/strategy/lstm_adapter.py`
- **Dependências:** `models/` directory, `joblib`, `keras`

## 🛠️ Especificações Técnicas
1. **Carregamento de Modelo:**
   ```python
   from keras.models import load_model
   model = load_model("models/WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras")
   ```
   - Se arquivo não existir → `FileNotFoundError` com path completo
   - Logar logger.critical("Modelo não encontrado em {path}")

2. **Carregamento de Scaler:**
   ```python
   import joblib
   scaler = joblib.load("models/WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib")
   ```
   - Se arquivo não existir → `FileNotFoundError` com path completo

3. **Validação ESTRITA de Input Shape:**
   - Após `define_features()`:
     - Obter shape esperado: `model.input_shape`  # Ex: (None, 108, 15)
     - Validar dados reais: `X.shape[1] == model.input_shape[1]` (lookback)
     - Validar features: `X.shape[2] == model.input_shape[2]` (n_features)
   - Se shape mismatch → lançar `ValueError` com:
     ```python
     raise ValueError(
         f"Shape mismatch: Modelo espera {model.input_shape}, "
         f"mas dados têm shape {X.shape}. "
         f"Verifique define_features() e retrain se necessário."
     )
     ```

4. **Conversão Defensiva:**
   - Antes de `.reshape()`: `X = np.array(X, dtype=np.float32)`
   - Garante compatibilidade mesmo se entrada for list

5. **Fail Fast:**
   - Qualquer erro de validação → lançar exceção imediatamente
   - NÃO usar valores default silenciosos

## 🔗 Dependências & Bloqueios
- [ ] Modelo treinado existe em `models/WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras`
- [ ] Scaler existe em `models/WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib`

## 📦 Definition of Done (DoD)
- [ ] Try/except ao carregar modelo e scaler
- [ ] Validação de input_shape implementada (comparação estrita)
- [ ] ValueError lançado se shape != esperado
- [ ] Conversão `np.array(X, dtype=np.float32)` adicionada
- [ ] Teste unitário: modelo ausente → FileNotFoundError
- [ ] Teste unitário: shape errado → ValueError com mensagem clara
- [ ] Logs mostram shape esperado vs recebido em caso de erro
- [ ] Docstrings documentam todas as exceções possíveis

## 📊 Estimativa
- **Story Points:** 5
- **Horas:** 6h
- **Prioridade:** 🟡 MÉDIA (paralela com DATA-001)
