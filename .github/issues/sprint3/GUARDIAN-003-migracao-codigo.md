# GUARDIAN-003: Migração e Higienização de Código

**Epic**: Sprint 3 - Migration & Clean Up  
**Type**: Quality Assurance Task  
**Effort**: 6 Story Points (6h)  
**Priority**: 🔴 Critical (core functionality)  
**Assignee**: @GUARDIAN  
**Dependency**: ARCH-001 ✅

---

## 📌 Objetivo
Migrar código-fonte (`src/`, `tests/`, `models/`) de `wtnps-trade` para `wtnps-finadv` com higienização (sem scripts soltos, sem lixo, sem arquivo corrompido).

---

## 📋 Ações

### Ação 1: Copiar src/ - Estrutura Inteligente

Source: `wtnps-trade/src/*`  
Target: `wtnps-finadv/src/*`

**Comando** (rsync com filtros):
```bash
# Linux/Mac
rsync -av --include='*/' --include='*.py' --exclude='*' \
  wtnps-trade/src/ wtnps-finadv/src/

# Windows PowerShell (alternativa)
Get-ChildItem wtnps-trade/src -Recurse -Include '*.py' | 
  ForEach-Object { 
    $dest = $_.FullName -replace '^.*?wtnps-trade', 'wtnps-finadv'
    Copy-Item $_.FullName -Destination $dest -Force
  }
```

**Validação Pós-Cópia**:
```bash
# Verificar diretórios principais
for dir in agents analysis api backtest_engine core data_handler environments gui live modules reporting setups simulation strategies utils; do
  if [ -d "src/$dir" ]; then echo "✓ src/$dir/"; else echo "✗ MISSING src/$dir/"; fi
done

# Verificar arquivos principais
for file in __init__.py events.py live_trader.py run.py; do
  if [ -f "src/$file" ]; then echo "✓ src/$file"; else echo "✗ MISSING src/$file"; fi
done

# Contar .py files
find src -name "*.py" | wc -l  # Should be > 100
```

**Checklist**:
- [ ] 15 subdirs copiados (agents/, analysis/, ..., utils/)
- [ ] >100 arquivos .py copiados
- [ ] `src/__init__.py` presente
- [ ] `src/events.py` presente
- [ ] `src/live_trader.py` presente
- [ ] `src/run.py` presente
- [ ] `src/*/(__init__.py)` presente em cada subdir
- [ ] Nenhum `__pycache__/` copiado
- [ ] Nenhum `.pyc` copiado

---

### Ação 2: Copiar tests/ - Completo

Source: `wtnps-trade/tests/*`  
Target: `wtnps-finadv/tests/*`

**Comando**:
```bash
# Linux/Mac
rsync -av wtnps-trade/tests/ wtnps-finadv/tests/

# Windows PowerShell
Copy-Item -Path wtnps-trade/tests -Destination wtnps-finadv/tests -Recurse -Force
```

**Validação**:
```bash
# Verificar estrutura
ls -la tests/unit/
ls -la tests/integration/

# Contar test files
find tests -name "test_*.py" | wc -l  # Should be >= 10
```

**Checklist**:
- [ ] `tests/unit/` com todos test_*.py
- [ ] `tests/integration/` com todos test_*.py
- [ ] `tests/__init__.py` presente
- [ ] `tests/unit/__init__.py` presente
- [ ] `tests/integration/__init__.py` presente
- [ ] `tests/conftest.py` (se existe em wtnps-trade)
- [ ] Nenhum `__pycache__/` ou `.pytest_cache/` copiado
- [ ] Mínimo 6 unit tests
- [ ] Mínimo 4 integration tests

---

### Ação 3: Copiar models/ - Artefatos Treinados

Source: `wtnps-trade/models/*`  
Target: `wtnps-finadv/models/*`

**Arquivos Esperados** (6 total):
```
models/
├── WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras       (80-150 MB)
├── WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib    (1-5 KB)
├── WDO$_LSTMVolatilityStrategy_M5_prod_params.joblib    (1-5 KB)
├── WIN$_LSTMVolatilityStrategy_M5_prod_lstm.keras       (80-150 MB)
├── WIN$_LSTMVolatilityStrategy_M5_prod_scaler.joblib    (1-5 KB)
└── WIN$_LSTMVolatilityStrategy_M5_prod_params.joblib    (1-5 KB)
```

**Comando**:
```bash
# Linux/Mac
cp -v wtnps-trade/models/*.keras wtnps-finadv/models/
cp -v wtnps-trade/models/*.joblib wtnps-finadv/models/

# Windows PowerShell
Copy-Item -Path wtnps-trade/models/* -Destination wtnps-finadv/models/ -Force
```

**Validação**:
```bash
# Listar arquivos
ls -lh models/

# Verificar tamanho (deve ser > 100 MB total)
du -sh models/  # Linux/Mac
(Get-ChildItem models -Recurse | Measure-Object -Sum Length).Sum / 1MB  # Windows

# Verificar integridade (arquivos não corrompidos)
file models/*.keras  # Linux/Mac
Get-Item models/*.keras  # Windows
```

**Checklist**:
- [ ] 6 arquivos copiados (2 tickers × 3 arquivos cada)
- [ ] WDO$ files presentes (lstm, scaler, params)
- [ ] WIN$ files presentes (lstm, scaler, params)
- [ ] Total size > 100 MB
- [ ] Nenhum arquivo corrompido (tamanho > 0 KB)
- [ ] Nenhum `.md5` ou `.sha` copiado (apenas binários)

---

### Ação 4: Validação de NÃO-CÓPIA (Housekeeping)

**NÃO deve estar em wtnps-finadv**:

```bash
# Verificar que estes NÃO existem
for item in train_model.py train_drl_model.py run_monitor_gui.py run_monitor.py \
            finalize_model.py inspect_model.py debug_server.py check_db.py \
            archive/ bkp/ modelsbkp/ .cache_data/ newapp/; do
  if [ -e "$item" ]; then
    echo "✗ ERRO: $item ainda existe em wtnps-finadv"
  else
    echo "✓ Correto: $item não existe"
  fi
done

# Verificar logs/ está vazio (não copiar old logs)
if [ -z "$(ls -A logs/)" ]; then echo "✓ logs/ vazio"; else echo "✗ logs/ contém arquivos"; fi
```

**Checklist**:
- [ ] ❌ train_model.py NÃO existe
- [ ] ❌ train_drl_model.py NÃO existe
- [ ] ❌ run_monitor_gui.py NÃO existe
- [ ] ❌ run_monitor.py NÃO existe
- [ ] ❌ finalize_model.py NÃO existe
- [ ] ❌ inspect_model.py NÃO existe
- [ ] ❌ archive/ NÃO existe
- [ ] ❌ bkp/ NÃO existe
- [ ] ❌ modelsbkp/ NÃO existe
- [ ] ❌ .cache_data/ NÃO existe
- [ ] ❌ newapp/ NÃO existe
- [ ] ❌ logs/*.txt NÃO copiados (apenas .gitkeep)
- [ ] ✅ __pycache__/ NÃO existe
- [ ] ✅ .pytest_cache/ NÃO existe

---

### Ação 5: Importações Verificadas - Critical!

**Teste cada import crítico**:

```bash
cd wtnps-finadv
poetry install  # Deve estar configurado por DEVOPS-004

# Test 1: Event Bus
poetry run python -c "from src.core.event_bus import EventBus; print('✓ EventBus importado')"

# Test 2: Events
poetry run python -c "from src.events import MarketDataEvent, SignalEvent, OrderEvent; print('✓ Events importados')"

# Test 3: Strategies
poetry run python -c "from src.strategies.lstm_volatility import LSTMVolatilityStrategy; print('✓ LSTMVolatilityStrategy importado')"

# Test 4: Data Handler
poetry run python -c "from src.data_handler.mt5_provider import MetaTraderProvider; print('✓ MetaTraderProvider importado')"

# Test 5: Live Trader
poetry run python -c "from src.live_trader import LiveTrader; print('✓ LiveTrader importado')"

# Test 6: Simulation
poetry run python -c "from src.simulation.engine import SimulationEngine; print('✓ SimulationEngine importado')"
```

**Checklist**:
- [ ] ✅ EventBus importa sem erro
- [ ] ✅ Events importa sem erro
- [ ] ✅ LSTMVolatilityStrategy importa sem erro
- [ ] ✅ MetaTraderProvider importa sem erro
- [ ] ✅ LiveTrader importa sem erro
- [ ] ✅ SimulationEngine importa sem erro
- [ ] ✅ Nenhuma importação relativa quebrada (`../../../`)
- [ ] ✅ Nenhuma importação de `newapp/` (se existir)

---

### Ação 6: Teste de Descoberta pytest

```bash
cd wtnps-finadv

# Descobrir testes
poetry run pytest --collect-only tests/

# Contar testes descobertos
poetry run pytest --collect-only tests/ | grep "test session starts" -A 2
```

**Validação**:
- [ ] pytest descobre >= 6 unit tests
- [ ] pytest descobre >= 4 integration tests
- [ ] Total >= 10 tests

---

### Ação 7: Executar Testes (Smoke Test)

```bash
cd wtnps-finadv

# Run all tests
poetry run pytest tests/ -v

# Run with coverage
poetry run pytest tests/ --cov=src --cov-report=term
```

**Checklist**:
- [ ] ✅ 10/10 tests passam (ou >= 90% pass rate)
- [ ] ✅ Nenhum erro de import
- [ ] ✅ Nenhum erro de missing dependency
- [ ] ✅ Coverage > 70%

---

## 🎯 Critério de Aceite (DoD)

- ✅ src/ copiado COMPLETAMENTE (15 subdir + >100 .py files)
- ✅ tests/ copiado COMPLETAMENTE (>=10 test files)
- ✅ models/ copiado (6 arquivos, >100 MB, sem corrupção)
- ✅ Nenhum arquivo "lixo": sem scripts soltos, sem archive/, sem cache/
- ✅ Importações validadas (6 imports críticos funcionam)
- ✅ pytest descobre todos os testes
- ✅ >=90% testes passam (10/10 ou similar)
- ✅ Nenhum erro de import ou missing module
- ✅ Nenhum arquivo corrompido (binários intactos)

---

## 🔗 Dependencies

- ✅ ARCH-001 (Setup Infraestrutura)
- ✅ DEVOPS-004 (Poetry configurado)

## ➡️ Blocks

- Nenhum (validação no final)

---

## ⚠️ Riscos

| Risk | Mitigation |
|------|-----------|
| .py file corrompido durante cópia | Usar rsync/copy-item com checksums |
| Import quebrada (`from newapp`) | Grep para `newapp` em src/, fix se encontrado |
| arquivo .keras corrompido | Verificar size > 50 MB e testar load com keras.models.load_model() |
| __pycache__ copiado | Incluir `--exclude '__pycache__'` em rsync |
| Teste quebrado após migração | Executar pytest antes/depois, comparar resultados |

---

## 📝 Notas

- **Não copiar scripts soltos**: train_model.py, etc ficam em wtnps-trade como histórico
- **Não copiar archive/**: Código deprecated, confunde onboarding
- **Copiar apenas active code**: src/, tests/, models/ (dados treinados)
- **Validação crítica**: Imports devem funcionar após cópia
