# Sprint 3: Migration & Clean Up
## Plano de Limpeza e Migração para wtnps-finadv

**Sprint Lead**: Tech Lead (ARCHITECT/DEVOPS coordenação)  
**Duração**: 10 dias  
**Objetivo**: Migrar artefatos funcionais de wtnps-trade → wtnps-finadv com estrutura limpa e padrão Canonical Src Layout

---

## 📋 Contexto & Motivação

### Estado Atual (wtnps-trade):
- ✗ Poluído: scripts soltos na raiz (.py, .md)
- ✗ Falta padrão: docs misturados com código
- ✗ Múltiplos históricos: archive/, bkp/, *_old.py
- ✗ Importações quebradas: referencias a newapp/ inconsistentes

### Estado Desejado (wtnps-finadv):
- ✅ Estrutura limpa: Canonical Src Layout
- ✅ Documentação centralizada: docs/planning/
- ✅ Código higienizado: apenas código ativo
- ✅ Dependências explícitas: poetry.lock validado
- ✅ Testes validados: 100% passando

---

## 🎯 Tarefas Sprint 3

### Task 1: ARCH-001 - Setup Infraestrutura Limpa
**Owner**: ARCHITECT  
**Effort**: 5h  
**Priority**: 🔴 Critical (blocker para todas as outras)

#### Ação 1.1: Clone wtnps-finadv Repository
```bash
git clone https://github.com/evandro-godoy/wtnps-finadv.git
cd wtnps-finadv
```

**Validação**:
- [ ] Repository clonado
- [ ] `.git/` existente
- [ ] Remote `origin` apontando para wtnps-finadv
- [ ] Branch `main` ativo

#### Ação 1.2: Criar Estrutura de Diretórios (Canonical Layout)
```
wtnps-finadv/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── architect_task.md
│   │   ├── quant_task.md
│   │   ├── plan_scrum.md
│   │   └── sprint3_task.md (NOVO)
│   └── workflows/
│       └── ci.yml (NOVO - Python 3.12)
├── docs/
│   ├── planning/
│   │   ├── IMPLEMENTATION_PLAN.md (migrado)
│   │   ├── FASE_*.md (migrado)
│   │   └── DRL_README.md (migrado)
│   ├── architecture/
│   │   ├── CANONICAL_LAYOUT.md (NOVO)
│   │   └── MIGRATION_GUIDE.md (NOVO)
│   └── user/
│       └── GUIA_USUARIO_CHARTS.md (migrado)
├── src/
│   ├── __init__.py
│   ├── events.py
│   ├── live_trader.py
│   ├── run.py
│   ├── agents/
│   ├── analysis/
│   ├── api/
│   ├── backtest_engine/
│   ├── core/
│   ├── data_handler/
│   ├── environments/
│   ├── gui/
│   ├── live/
│   ├── modules/
│   ├── reporting/
│   ├── setups/
│   ├── simulation/
│   ├── strategies/
│   └── utils/
├── tests/
│   ├── __init__.py
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── models/
│   ├── WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras
│   ├── WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib
│   ├── WDO$_LSTMVolatilityStrategy_M5_prod_params.joblib
│   ├── WIN$_LSTMVolatilityStrategy_M5_prod_lstm.keras
│   ├── WIN$_LSTMVolatilityStrategy_M5_prod_scaler.joblib
│   ├── WIN$_LSTMVolatilityStrategy_M5_prod_params.joblib
│   └── .gitkeep
├── notebooks/
│   ├── analyzes/
│   ├── miscellaneous/
│   ├── simulation/
│   ├── statistics/
│   └── tests/
├── reports/
│   ├── backtest/
│   ├── models/
│   └── .gitkeep
├── configs/
│   ├── main.yaml
│   └── .env.example
├── logs/
│   └── .gitkeep
├── .gitignore (NOVO)
├── .env.example (NOVO)
├── README.md (NOVO - entrypoint)
├── pyproject.toml (NOVO)
└── poetry.lock (NOVO)
```

**Validação Raiz (Canonical Requirement)**:
- [ ] Apenas 4 arquivos na raiz: `README.md`, `pyproject.toml`, `.gitignore`, `.env.example`
- [ ] Nenhum `.py` solto na raiz (train_model.py, train_drl_model.py, run_monitor_gui.py, etc → deletar)
- [ ] Nenhum `.md` solto (IMPLEMENTATION_PLAN.md, FASE_*.md → mover para docs/planning/)
- [ ] Estrutura de diretórios criada com `mkdir -p`

#### Ação 1.3: Inicializar Git no Novo Repo
```bash
git init
git add .
git commit -m "feat: initial Canonical Src Layout setup for wtnps-finadv"
git branch -M main
```

**Validação**:
- [ ] `.git/` existente
- [ ] `git log` mostra commit inicial
- [ ] `main` branch ativo

#### Critério de Aceite:
- ✅ Estrutura Canonical Src Layout criada
- ✅ Raiz contém APENAS README.md, pyproject.toml, .gitignore, .env.example
- ✅ Diretórios `src/`, `tests/`, `docs/`, `models/`, `notebooks/`, `reports/`, `configs/`, `logs/` criados
- ✅ Git inicializado com commit limpo
- ✅ Nenhum arquivo solto, nenhum arquivo backup

---

### Task 2: ARCH-002 - Migração de Documentação
**Owner**: ARCHITECT  
**Effort**: 3h  
**Priority**: 🟠 High (necessária para onboarding)  
**Dependency**: ARCH-001 ✅

#### Ação 2.1: Mover Docs de Planejamento
Source: `wtnps-trade/`  
Target: `wtnps-finadv/docs/planning/`

**Arquivos a Mover**:
```
IMPLEMENTATION_PLAN.md
PLANO_FASE_3.1.md
PLANO_FASE_3.2.md
PLANO_SPRINT_3.md (este arquivo)
FASE_3.1_STATUS.md
FASE_3.2_STATUS.md
FASE_3.3_CHECKLIST.md
FASE_3.3_TESTES_RESULTADOS.md
RESUMO_FASE_2.md
RESUMO_GERAL_FASES_1_3.2.md
ITERACAO_FASE_3_RESUMO.md
SUMARIO_TECNICO_v1.2.0.md
CONTEXT_ANALYZER_README.md
DRL_README.md
```

**Ação**: Copiar para `docs/planning/` + atualizar cross-references

#### Ação 2.2: Mover Docs de Usuário
Source: `wtnps-trade/GUIA_USUARIO_CHARTS.md`  
Target: `wtnps-finadv/docs/user/GUIA_USUARIO_CHARTS.md`

#### Ação 2.3: Criar README.md Novo (Raiz)
```markdown
# WTNPS FinAdv - Algorithmic Trading Framework

Production-ready ML/DRL trading system with MetaTrader5 integration.

## 🚀 Quick Start
1. See [Architecture](docs/architecture/CANONICAL_LAYOUT.md)
2. See [Implementation Plan](docs/planning/IMPLEMENTATION_PLAN.md)
3. See [User Guide](docs/user/GUIA_USUARIO_CHARTS.md)

## 📦 Environment Setup
```bash
poetry install
cp .env.example .env
# Configure MT5_PATH, MT5_LOGIN, MT5_SERVER in .env
```

## 🧪 Testing
```bash
poetry run pytest tests/ -v
```

## 📚 Documentation
- [Planning](docs/planning/) - Sprint plans, status reports
- [Architecture](docs/architecture/) - Canonical layout, migration guide
- [User Guide](docs/user/) - GUI, trading instructions
```

**Validação**:
- [ ] 13+ docs movidos para `docs/planning/`
- [ ] GUIA_USUARIO_CHARTS.md em `docs/user/`
- [ ] README.md criado na raiz com links corretos
- [ ] Cross-references atualizadas (paths relativos)
- [ ] Links internos testados (não quebrados)

#### Critério de Aceite:
- ✅ Documentação centralizada em `docs/`
- ✅ README.md raiz é entrypoint funcional
- ✅ Todos os links internos válidos
- ✅ Nenhum `.md` solto na raiz de wtnps-finadv

---

### Task 3: GUARDIAN-003 - Migração e Higienização de Código
**Owner**: GUARDIAN  
**Effort**: 6h  
**Priority**: 🔴 Critical (core functionality)  
**Dependency**: ARCH-001 ✅

#### Ação 3.1: Copiar src/ e Estrutura Inteligente
Source: `wtnps-trade/src/*`  
Target: `wtnps-finadv/src/*`

**Comando**:
```bash
# Copy only directories (smart filter)
rsync -av --include='*/' --include='*.py' \
  wtnps-trade/src/ wtnps-finadv/src/
```

**Validação Pós-Cópia**:
- [ ] Todos os subdirs copiados: agents/, analysis/, api/, backtest_engine/, core/, data_handler/, environments/, gui/, live/, modules/, reporting/, setups/, simulation/, strategies/, utils/
- [ ] Todos os .py copiados recursivamente
- [ ] events.py, live_trader.py, run.py presentes na raiz de src/
- [ ] `__init__.py` em cada diretório
- [ ] Nenhum `.pyc`, `__pycache__/` copiado

#### Ação 3.2: Copiar tests/ Completo
Source: `wtnps-trade/tests/*`  
Target: `wtnps-finadv/tests/*`

```bash
rsync -av wtnps-trade/tests/ wtnps-finadv/tests/
```

**Validação**:
- [ ] tests/unit/ com todos os test_*.py
- [ ] tests/integration/ com todos os test_*.py
- [ ] conftest.py presente (se existe)
- [ ] Nenhum `__pycache__/`, `.pytest_cache/` copiado

#### Ação 3.3: Copiar models/ (Artefatos Treinados)
Source: `wtnps-trade/models/*`  
Target: `wtnps-finadv/models/*`

**Arquivos Esperados**:
```
WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras
WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib
WDO$_LSTMVolatilityStrategy_M5_prod_params.joblib
WIN$_LSTMVolatilityStrategy_M5_prod_lstm.keras
WIN$_LSTMVolatilityStrategy_M5_prod_scaler.joblib
WIN$_LSTMVolatilityStrategy_M5_prod_params.joblib
```

**Validação**:
- [ ] 6 arquivos copiados
- [ ] Total size > 50MB (Keras models + scaler)
- [ ] `.keras` e `.joblib` intactos (binary check)

#### Ação 3.4: Filtro de NÃO-CÓPIA (Housekeeping)
**NÃO copiar**:
- ❌ Scripts soltos: `train_model.py`, `train_drl_model.py`, `run_monitor_gui.py`, etc
- ❌ `archive/`, `bkp/`, `modelsbkp/` (deprecated)
- ❌ `logs/` (gerar novos em runtime)
- ❌ `.cache_data/` (regenerar)
- ❌ `__pycache__/`, `.pytest_cache/`, `.git/`
- ❌ Arquivos `.md` soltos na raiz (já migraram para docs/)

#### Ação 3.5: Importações Verificadas
**Checklist**:
- [ ] `from src.events import *` válido
- [ ] `from src.core.event_bus import EventBus` válido
- [ ] `from src.strategies.lstm_volatility import LSTMVolatilityStrategy` válido
- [ ] `from src.data_handler.mt5_provider import MetaTraderProvider` válido
- [ ] Nenhuma importação relativa quebrada (../../../)
- [ ] Nenhuma importação de newapp/ (se existem, refatorar)

**Teste Rápido**:
```bash
cd wtnps-finadv
poetry run python -c "from src.core.event_bus import EventBus; print('✅ EventBus importado')"
poetry run python -c "from src.events import SignalEvent; print('✅ SignalEvent importado')"
```

#### Critério de Aceite:
- ✅ src/ copiado completamente (todas as pastas + arquivos)
- ✅ tests/ copiado completamente
- ✅ models/ copiado com 6+ artefatos
- ✅ Nenhum arquivo "lixo" (archive/, bkp/, logs/, cache)
- ✅ Importações validadas (sem erros)
- ✅ pytest descobre todos os testes

---

### Task 4: DEVOPS-004 - Configuração de Dependências
**Owner**: DEVOPS  
**Effort**: 4h  
**Priority**: 🔴 Critical (execução depende disso)  
**Dependency**: ARCH-001 ✅, GUARDIAN-003 ✅

#### Ação 4.1: Inicializar Poetry no Novo Repo
```bash
cd wtnps-finadv
poetry init --no-interaction \
  --name wtnps-finadv \
  --description "WTNPS FinAdv - Algorithmic Trading Framework" \
  --author "evandro-godoy" \
  --python "^3.12"
```

**Validação**:
- [ ] `pyproject.toml` criado com Python ^3.12
- [ ] `tool.poetry` seção existente
- [ ] Nenhuma dependência padrão adicionada ainda

#### Ação 4.2: Adicionar Dependências Ativas (APENAS)
**Ativo** = usado em `src/` ou `tests/` com `import`

```bash
poetry add \
  pandas \
  numpy \
  tensorflow \
  keras \
  scikit-learn \
  python-metatrader5 \
  pydantic \
  pydantic-settings \
  pytz \
  joblib \
  mplfinance \
  bokeh \
  plotly \
  fastapi \
  uvicorn \
  websockets \
  sqlalchemy \
  pytest \
  pytest-cov \
  python-dotenv
```

**Validação Cada Dependência**:
- [ ] `pandas` - usado em data_handler, strategies
- [ ] `numpy` - usado em strategies, agents
- [ ] `tensorflow` - usado em strategies (LSTM)
- [ ] `keras` - usado em strategies (model loading)
- [ ] `scikit-learn` - usado em strategies (scaler, models)
- [ ] `python-metatrader5` - usado em data_handler
- [ ] `pydantic` - usado em core/config.py
- [ ] `pydantic-settings` - usado em core/config.py
- [ ] `pytz` - usado em data_handler (timezone)
- [ ] `joblib` - usado em strategies (model persistence)
- [ ] `mplfinance` - usado em gui/chart_widget.py
- [ ] `bokeh` - usado em monitoring
- [ ] `plotly` - usado em reporting
- [ ] `fastapi` - usado em api/ (se newapp integrado)
- [ ] `uvicorn` - usado com FastAPI
- [ ] `websockets` - usado em api/
- [ ] `sqlalchemy` - usado em reporting/
- [ ] `pytest` - test runner
- [ ] `pytest-cov` - coverage
- [ ] `python-dotenv` - .env loading

#### Ação 4.3: NÃO Adicionar (Clean Up)
❌ Remover se adicionadas acidentalmente:
```bash
poetry remove --dry-run <package>  # check first
poetry remove <package>             # then remove
```

**Packages a NÃO adicionar**:
- ❌ `jupyter`, `notebook` (notebooks/ é análise, não executável)
- ❌ `seaborn`, `matplotlib` (use `plotly` em vez disso)
- ❌ `flask` (use `fastapi`)
- ❌ Devtools: `ipython`, `black`, `flake8`, `mypy` (adicionar em `[tool.poetry.group.dev]`)

#### Ação 4.4: Adicionar Dev Dependencies
```bash
poetry add --group dev \
  ipython \
  black \
  flake8 \
  mypy \
  pytest-mock \
  pytest-asyncio
```

**Validação**: `pyproject.toml` contém `[tool.poetry.group.dev.dependencies]`

#### Ação 4.5: Gerar poetry.lock
```bash
poetry lock --no-update
```

**Validação**:
- [ ] `poetry.lock` criado (>50KB)
- [ ] Nenhum erro de dependency conflict
- [ ] Todas as transitive dependencies resolvidas

#### Ação 4.6: Teste de Install Limpo (Fresh Venv)
```bash
# Criar venv limpo
python -m venv /tmp/test_wtnps_venv
source /tmp/test_wtnps_venv/bin/activate  # ou Windows: .../bin/activate.ps1

# Instalar do lock
poetry install

# Verificar imports críticos
python -c "import pandas, numpy, tensorflow, keras; print('✅ Core deps ok')"
python -c "import MetaTrader5; print('✅ MT5 ok')"
python -c "from src.core.event_bus import EventBus; print('✅ src imports ok')"
```

#### Ação 4.7: Validar pyproject.toml Estrutura
```toml
[tool.poetry]
name = "wtnps-finadv"
version = "0.1.0"
description = "WTNPS FinAdv - Algorithmic Trading Framework"
authors = ["evandro-godoy <email@example.com>"]
python = "^3.12"

[tool.poetry.dependencies]
# 19 active packages listed above

[tool.poetry.group.dev.dependencies]
# Dev packages listed above

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

**Validação**:
- [ ] Python ^3.12
- [ ] Todos os packages listados
- [ ] Dev group separado
- [ ] pytest configurado para `tests/`

#### Critério de Aceite:
- ✅ `pyproject.toml` criado com Python ^3.12
- ✅ 19 dependências ativas + 6 dev dependencies
- ✅ `poetry.lock` gerado sem conflicts
- ✅ Fresh install testa com sucesso
- ✅ Imports críticos funcionar
- ✅ pytest descobre todos os testes

---

## 📊 Roadmap & Timelines

| Task | Owner | Effort | Day | Status |
|------|-------|--------|-----|--------|
| ARCH-001 | ARCHITECT | 5h | D1-D2 | 🔴 Not Started |
| ARCH-002 | ARCHITECT | 3h | D2-D3 | 🔴 Not Started |
| GUARDIAN-003 | GUARDIAN | 6h | D3-D4 | 🔴 Not Started |
| DEVOPS-004 | DEVOPS | 4h | D4-D5 | 🔴 Not Started |
| **Integration & Smoke Tests** | ALL | 2h | D5 | 🔴 Not Started |
| **Final Validation** | Tech Lead | 2h | D5-D6 | 🔴 Not Started |

**Total Effort**: 22 hours (3 FTE days)

---

## ✅ Critérios de Conclusão (Definition of Done)

### Estrutura
- ✅ Canonical Src Layout implementado
- ✅ Raiz contém APENAS README.md, pyproject.toml, .gitignore, .env.example
- ✅ Todos os diretórios (src/, tests/, docs/, models/, etc) criados

### Documentação
- ✅ 13+ docs migratos para docs/planning/
- ✅ README.md raiz funcional com links corretos
- ✅ Cross-references atualizadas

### Código
- ✅ src/ copiado completamente
- ✅ tests/ copiado completamente
- ✅ models/ copiado (6+ arquivos)
- ✅ Importações validadas (sem erros)

### Dependências
- ✅ pyproject.toml com Python ^3.12
- ✅ 19 dependências ativas + 6 dev
- ✅ poetry.lock gerado
- ✅ Fresh install funciona

### Testing
- ✅ `pytest tests/` rodar 100% dos testes
- ✅ Cobertura > 80%
- ✅ Nenhum erro de import

### Git
- ✅ Repositório inicializado
- ✅ Commit limpo com estrutura completa
- ✅ Branch main ativo

---

## ⚠️ Riscos & Mitigação

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Imports quebradas após cópia | Medium | High | Validar imports antes/depois (test scripts) |
| Arquivo binário corrompido (model) | Low | Critical | Verificar hash do .keras/.joblib |
| Dependência com versão errada | Medium | Medium | Usar `poetry lock --no-update` |
| Documentação com links quebrados | High | Low | Testar todos os links após migração |
| Scripts soltos copiados acidentalmente | Low | High | Usar `rsync --include/exclude` filters |
| Estrutura de diretórios incompleta | Low | Critical | Checklist manual de cada diretório |

---

## 🔗 Referências

- **Canonical Src Layout**: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- **Poetry Documentation**: https://python-poetry.org/docs/
- **Python 3.12 Features**: https://docs.python.org/3.12/whatsnew/3.12.html

---

## 📝 Notas Técnicas

### Por que Canonical Src Layout?
1. **Isolamento**: `src/` separado de testes previne importação acidental
2. **Instalação**: `poetry install` cria package namespace correto
3. **CI/CD**: Workflows melhor com estrutura clara
4. **Escalabilidade**: Fácil adicionar múltiplos packages no futuro

### Por que Python 3.12?
1. **Performance**: 5-10% mais rápido que 3.11
2. **Type Hints**: Melhor suporte a `|` syntax
3. **Async**: Melhor thread-safe asyncio
4. **LTS**: Suporte até outubro 2028

### Estratégia de Limpeza
- **Delete**: archive/, bkp/, scripts soltos (train_model.py, etc)
- **Archive**: Manter em wtnps-trade como histórico (git tagged)
- **Migrate**: Apenas código ativo funciona em wtnps-finadv

---

## 📞 Escalation & Contact

**Tech Lead**: Responsável por coordenação e validação final  
**ARCHITECT**: Responsável por ARCH-001, ARCH-002  
**GUARDIAN**: Responsável por GUARDIAN-003  
**DEVOPS**: Responsável por DEVOPS-004  

Qualquer blocker → Reportar para Tech Lead em standup diário.
