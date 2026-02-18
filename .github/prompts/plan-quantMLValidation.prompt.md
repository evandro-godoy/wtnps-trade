# 📊 Prompt QUANT - Validação ML & Estratégias

**Agent:** QUANT  
**Escopo:** Testes LSTM + Configuração Estratégias  
**Prazo:** 2-3 dias  
**Deliverable:** ML validation report + configs verified

---

## 📋 Missão

Executar suite de validação ML/Trading Fase 3.3:
- ✅ LSTM strategies (WDO$, WIN$) executam sem erro
- ✅ Configs [configs/main.yaml](../../configs/main.yaml) validam
- ✅ Data providers (MT5/YFinance) acessíveis
- ✅ Model artifacts (keras, scaler, params) existem e carregam
- ✅ Relatório técnico gera sem falhas

**NÃO depende de DEVOPS CI** — roda paralelo com FULLSTACK testing.

---

## 🎯 Tarefas Específicas

### Task 1: Validar Configs
**Objetivo:** [configs/main.yaml](../../configs/main.yaml) sem erros  
**Entrada:** YAML file  
**Saída:** Validation pass/fail + parsed config object

**Passo a passo:**
1. Ler [configs/main.yaml](../../configs/main.yaml) completo
2. Validar estrutura YAML:
   ```bash
   python -c "import yaml; yaml.safe_load(open('configs/main.yaml'))"
   ```
3. Verificar campos obrigatórios:
   - `assets[]` → tickers habilitados
   - `assets[].strategy` → module name existe
   - `assets[].provider` → "MetaTrader5" ou "YFinance"
   - `assets[].data` → start_date, end_date, timeframe_model
   - `trading_rules` → initial_capital, stop_loss_pct, take_profit_pct
   - `execution_mode` → "suggest" ou "execute"

4. Validar valores:
   - Timeframes válidos: M1/M5/M15/M30/H1/H4/D1/W1/MN1 ✅
   - Datas: start < end ✅
   - Regras: stop_loss_pct > 0, take_profit_pct > 0 ✅

5. **Output:** `config_validation_report.txt`
   ```
   ✅ YAML parsa corretamente
   ✅ 2 assets configurados (WDO$, WIN$)
   ✅ Strategy: LSTMVolatilityStrategy encontrado
   ✅ Todas datas válidas
   ✅ Trading rules sane
   ```

### Task 2: Verificar Model Artifacts
**Objetivo:** Keras models, scalers, params carregam sem erro  
**Entrada:** `models/` directory  
**Saída:** Model load test report

**Passo a passo:**
1. Listar models (pattern: `<TICKER>_<STRATEGY>_<TIMEFRAME>_prod_*`):
   ```bash
   ls -la models/ | grep prod
   ```
   Expected:
   - `WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras`
   - `WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib`
   - `WDO$_LSTMVolatilityStrategy_M5_prod_params.joblib`
   - `WIN$_LSTMVolatilityStrategy_M5_prod_*` (similar)

2. Teste carregar cada model:
   ```python
   from src.strategies.lstm_volatility import LSTMVolatilityStrategy
   
   for ticker in ["WDO$", "WIN$"]:
       strategy = LSTMVolatilityStrategy(ticker=ticker, timeframe="M5")
       strategy.load()  # Deve não lançar exceção
       print(f"✅ {ticker} model loaded")
   ```

3. Verificar integridade:
   - Model file size > 0 bytes ✅
   - Scaler file size > 0 bytes ✅
   - Params file size > 0 bytes ✅
   - File modification date recente (< 3 meses) ✅

4. **Output:** `model_artifacts_report.txt`
   ```
   ✅ WDO$ LSTM model loads (keras file valid)
   ✅ WDO$ scaler loads (joblib file valid)
   ✅ WDO$ params load (joblib file valid)
   ✅ WIN$ model loads (keras file valid)
   ✅ WIN$ scaler loads (joblib file valid)
   ✅ WIN$ params load (joblib file valid)
   ⚠️ Model files 3 months old (consider retraining)
   ```

### Task 3: Test Strategy Execution
**Objetivo:** Estratégias LSTM executam get_signal() sem erro  
**Entrada:** Strategy classes, mock data  
**Saída:** Signal generation test

**Passo a passo:**
1. Load strategy + dados mock (ou últimas 200 candles):
   ```python
   strategy = LSTMVolatilityStrategy(ticker="WDO$", timeframe="M5")
   strategy.load()
   
   # Get últimas 200 candles (M5)
   # Pode usar MT5 provider ou mock data
   features = strategy.define_features()
   X = ...  # Load/generate X (n_samples, n_features)
   signal = strategy.get_signal(X[-1:])  # Último candle
   ```

2. Validar signal output:
   - Signal ∈ {"COMPRA", "VENDA", "HOLD"} ✅
   - Confidence score ∈ [0, 1] (se aplicável) ✅
   - Sem NaN/None ✅

3. Teste ambas strategies:
   - WDO$ LSTMVolatilityStrategy M5 → signal ✅
   - WIN$ LSTMVolatilityStrategy M5 → signal ✅

4. **Output:** `strategy_signal_test.txt`
   ```
   ✅ WDO$ returns signal "COMPRA" (confidence: 0.87)
   ✅ WIN$ returns signal "HOLD" (confidence: 0.52)
   ```

### Task 4: Data Provider Check
**Objetivo:** MT5 e/ou YFinance acessíveis  
**Entrada:** Provider configs em main.yaml  
**Saída:** Provider connectivity report

**Passo a passo:**
1. **MT5 Provider:**
   - Verificar if MT5 terminal running (Windows):
     ```bash
     tasklist | find "terminal64.exe"  # Win
     ```
   - Se sim, tentar conectar:
     ```python
     from src.data_handler.provider import MT5Provider
     provider = MT5Provider()
     data = provider.get_data("WDO$", "M5", start="2025-11-01")
     print(f"✅ MT5 connected: {len(data)} candles")
     ```
   - Se não: "⚠️ MT5 terminal not running (sim mode)"

2. **YFinance Fallback:**
   - Tentar YFinance (sempre deve funcionar):
     ```python
     from src.data_handler.provider import YFinanceProvider
     provider = YFinanceProvider()
     data = provider.get_data("WDOZ25.BVMF", "1d", start="2025-11-01")
     print(f"✅ YFinance connected: {len(data)} candles")
     ```

3. **Output:** `provider_connectivity_report.txt`
   ```
   ✅ MT5 terminal running on port 19532
   ✅ MT5 WDO$ M5 data accessible (1000+ candles cached)
   ✅ YFinance fallback working
   ⚠️ Cache age: 5 days (consider refresh)
   ```

### Task 5: Integration Test (Simulation Mode)
**Objetivo:** Simular 1 dia trading com strategies  
**Entrada:** Sim engine, 1 dia dados, 2 stratégies  
**Saída:** Sim trade log + PnL report

**Passo a passo:**
1. Executar mini-simulation (1 dia, tanto WDO$ e WIN$):
   ```bash
   poetry run python src/simulation/engine.py \
     --start 2025-11-10 \
     --end 2025-11-11 \
     --tickers WDO$ WIN$ \
     --timeframe M5 \
     --output /tmp/sim_report.html
   ```

2. Verificar output:
   - [ ] Simulation completa sem crash
   - [ ] Trades gerados (entrada/crítica > 0)
   - [ ] PnL não é absurdo (±20% realistic)
   - [ ] Report HTML valida

3. **Output:** `simulation_test.txt`
   ```
   ✅ 1-day simulation completed
   ✅ WDO$ 3 trades (2 lucro, 1 prejuízo) = +$50
   ✅ WIN$ 1 trade (prejuízo) = -$20
   ✅ Total PnL: +$30 (0.3% capital)
   ✅ Report HTML generated at .../sim_report.html
   ```

### Task 6: Technical Report Generation
**Objetivo:** Consolidar todos testes em relatório académico  
**Entrada:** Todos outputs acima  
**Saída:** QUANT_Phase3.3_ML_Validation_Report.md

**Template esperado:**
```markdown
# QUANT Phase 3.3 - ML Validation Report

## Executive Summary
- All 5 validation tests PASSED
- 2 strategies (WDO$, WIN$ LSTM M5) operational
- Data pipeline healthy
- Ready for Fase 3.3 completion

## 1. Configuration Validation
[Table com resultado configs check]

## 2. Model Artifacts
[Table com keras/scaler/params status]

## 3. Strategy Signals
[Table com signal outputs WDO$, WIN$]

## 4. Data Providers
[Table com MT5/YFinance status]

## 5. Integration Test
[Sim PnL results]

## Recommendations
- ⚠️ Consider retraining models (3 months old)
- ✅ Ready for Fase 4 (live money)
```

---

## 🔬 Convenções Códigas Preservadas

Ref: [.github/copilot-instructions.md](../../.github/copilot-instructions.md)

- ✅ Signals uppercase português: COMPRA/VENDA/HOLD
- ✅ Model naming: `<TICKER>_<STRATEGY>_<TIMEFRAME>_prod_*`
- ✅ Timeframes: M1/M5/M15/M30/H1/H4/D1/W1/MN1 only
- ✅ Timezone: Simulation local (America/Sao_Paulo)
- ✅ Provider chain: MT5 → cache → YFinance

**Todos tests devem respeitar.**

---

## 🔄 Dependências

| Agente | Tarefa | Impacto |
|--------|--------|---------|
| FULLSTACK | Phase 3.3 Testing | Independente (paralelo) |
| DEVOPS | CI green | **NÃO depende** |
| GUARDIAN | QA audit | Recebe outputs QUANT |

**Não bloqueado.** Comece testes agora.

---

## ✅ Critérios de Aceitação

- [ ] configs/main.yaml valida (YAML + fields + values)
- [ ] Model artifacts load (keras, scaler, params)
- [ ] 2 strategies executam get_signal() → válide signals
- [ ] MT5 ou YFinance acessível
- [ ] 1-day integration test passa (PnL reasonable)
- [ ] Technical report (.md) gerado
- [ ] Nenhum erro crítico; todos tests PASS

---

## 📌 Referências

- Configs: [configs/main.yaml](../../configs/main.yaml)
- Strategy Base: [src/strategies/base.py](../../src/strategies/base.py)
- LSTM Strategy: [src/strategies/lstm_volatility.py](../../src/strategies/lstm_volatility.py)
- Simulation Engine: [src/simulation/engine.py](../../src/simulation/engine.py)
- Copilot Instructions: [.github/copilot-instructions.md](../../.github/copilot-instructions.md)
- Mestre: `plan-masterOrchestration.prompt.md`

---

**Próximo:** QUANT fornece ML validation report → consolidado em Phase 3.3 completion.
