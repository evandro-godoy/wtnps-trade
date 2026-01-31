# ARCH-002: Migração de Documentação

**Epic**: Sprint 3 - Migration & Clean Up  
**Type**: Architecture Task  
**Effort**: 3 Story Points (3h)  
**Priority**: 🟠 High (necessária para onboarding)  
**Assignee**: @ARCHITECT  
**Dependency**: ARCH-001 ✅

---

## 📌 Objetivo
Centralizar toda documentação de planejamento, técnica e usuário em `docs/` estruturado, criando `README.md` funcional na raiz como entrypoint.

---

## 📋 Ações

### Ação 1: Mover Docs de Planejamento → docs/planning/

Source: `wtnps-trade/` (raiz)  
Target: `wtnps-finadv/docs/planning/`

**Arquivos a Mover** (13 total):
```bash
cp wtnps-trade/IMPLEMENTATION_PLAN.md wtnps-finadv/docs/planning/
cp wtnps-trade/PLANO_FASE_3.1.md wtnps-finadv/docs/planning/
cp wtnps-trade/PLANO_FASE_3.2.md wtnps-finadv/docs/planning/
cp wtnps-trade/PLANO_SPRINT_3.md wtnps-finadv/docs/planning/
cp wtnps-trade/FASE_3.1_STATUS.md wtnps-finadv/docs/planning/
cp wtnps-trade/FASE_3.2_STATUS.md wtnps-finadv/docs/planning/
cp wtnps-trade/FASE_3.3_CHECKLIST.md wtnps-finadv/docs/planning/
cp wtnps-trade/FASE_3.3_TESTES_RESULTADOS.md wtnps-finadv/docs/planning/
cp wtnps-trade/RESUMO_FASE_2.md wtnps-finadv/docs/planning/
cp wtnps-trade/RESUMO_GERAL_FASES_1_3.2.md wtnps-finadv/docs/planning/
cp wtnps-trade/ITERACAO_FASE_3_RESUMO.md wtnps-finadv/docs/planning/
cp wtnps-trade/SUMARIO_TECNICO_v1.2.0.md wtnps-finadv/docs/planning/
cp wtnps-trade/CONTEXT_ANALYZER_README.md wtnps-finadv/docs/planning/
```

**Validação**:
- [ ] 13 arquivos copiados para `docs/planning/`
- [ ] `ls docs/planning/` mostra todos os 13 files
- [ ] Nenhum arquivo duplicado

---

### Ação 2: Mover Docs Técnicos → docs/architecture/

**Arquivos a Criar** (novos):

#### 2.1: docs/architecture/CANONICAL_LAYOUT.md
```markdown
# Canonical Src Layout - wtnps-finadv

## Estrutura Adotada
- **src/**: Código fonte principal (imports como `from src.core.event_bus import EventBus`)
- **tests/**: Testes unitários e integração (imports como `from src.events import SignalEvent`)
- **docs/**: Documentação (planning, architecture, user)
- **models/**: Artefatos treinados (.keras, .joblib)
- **notebooks/**: Análises e testes jupyter
- **configs/**: YAML configs e .env
- **reports/**: Saídas de análise

## Benefícios
1. **Isolamento**: Testes não importam código não-packaged
2. **Instalação**: `pip install -e .` funciona corretamente
3. **CI/CD**: Workflows sabem onde procurar
4. **Escalabilidade**: Fácil adicionar novos packages

## Referência
https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
```

#### 2.2: docs/architecture/MIGRATION_GUIDE.md
```markdown
# Migration Guide: wtnps-trade → wtnps-finadv

## Histórico
- **wtnps-trade**: Desenvolvimento iterativo (Sprint 1-3)
- **wtnps-finadv**: Repositório oficial final (Canonical Layout)

## Documentação Movida
- Sprint plans → `docs/planning/`
- User guides → `docs/user/`
- Architecture specs → `docs/architecture/`

## Código Movido
- `src/` inteiro copiado preservando estrutura
- `tests/` inteiro copiado
- `models/` com artefatos treinados
- Scripts soltos (train_model.py, etc) mantidos em wtnps-trade como histórico

## Dependências Resolvidas
- `pyproject.toml` com Python ^3.12
- `poetry.lock` com todas as transitive dependencies

## Status
- [x] Infrastructure setup
- [x] Documentation centralized
- [x] Code migrated
- [x] Dependencies resolved
- [ ] Tests passing (próximo: CI validation)
```

**Validação**:
- [ ] `docs/architecture/CANONICAL_LAYOUT.md` criado
- [ ] `docs/architecture/MIGRATION_GUIDE.md` criado

---

### Ação 3: Mover Docs de Usuário → docs/user/

```bash
cp wtnps-trade/GUIA_USUARIO_CHARTS.md wtnps-finadv/docs/user/
cp wtnps-trade/DRL_README.md wtnps-finadv/docs/user/
```

**Validação**:
- [ ] GUIA_USUARIO_CHARTS.md em `docs/user/`
- [ ] DRL_README.md em `docs/user/`

---

### Ação 4: Criar README.md (Raiz) - Entrypoint

**Arquivo**: `wtnps-finadv/README.md`

```markdown
# 🚀 WTNPS FinAdv - Algorithmic Trading Framework

Production-ready **ML/DRL trading system** with MetaTrader5 integration.

**Status**: Sprint 3 - Migration & Clean Up  
**Branch**: main  
**Python**: 3.12+

---

## 📖 Quick Navigation

### 🏗️ Architecture & Setup
- [Canonical Src Layout](docs/architecture/CANONICAL_LAYOUT.md) - Project structure
- [Migration Guide](docs/architecture/MIGRATION_GUIDE.md) - From wtnps-trade to wtnps-finadv

### 📋 Planning & Status
- [Implementation Plan](docs/planning/IMPLEMENTATION_PLAN.md) - Master roadmap
- [Sprint 3 Plan](docs/planning/PLANO_SPRINT_3.md) - Current sprint

### 👤 User Documentation
- [GUI User Guide](docs/user/GUIA_USUARIO_CHARTS.md) - Using dashboards
- [DRL Documentation](docs/user/DRL_README.md) - Deep Reinforcement Learning

---

## ⚡ Quick Start

### 1. Environment Setup
```bash
# Clone repository
git clone https://github.com/evandro-godoy/wtnps-finadv.git
cd wtnps-finadv

# Install dependencies
poetry install

# Setup environment
cp .env.example .env
# Edit .env: configure MT5_PATH, MT5_LOGIN, MT5_SERVER, MT5_PASSWORD
```

### 2. Run Tests
```bash
# All tests
poetry run pytest tests/ -v

# Unit only
poetry run pytest tests/unit/ -v

# Integration (requires MT5 running)
poetry run pytest tests/integration/ -v
```

### 3. Live Trading
```bash
poetry run python src/live_trader.py
```

### 4. View Dashboards
```bash
poetry run python run_monitor_gui.py --mode live
```

---

## 🏛️ Architecture Overview

### Core Components
- **EventBus** (`src/core/event_bus.py`) - Publish/subscribe event dispatcher
- **Strategies** (`src/strategies/`) - ML models (LSTM, RandomForest, DRL)
- **Data Handler** (`src/data_handler/`) - MT5 provider, data fetching
- **Live Trader** (`src/live_trader.py`) - Real-time execution engine
- **Simulation** (`src/simulation/engine.py`) - Backtesting engine

### Execution Modes
1. **Live Trading** - Real-time MT5 orders
2. **Simulation** - Point-in-time analysis
3. **Backtesting** - Historical validation

---

## 📦 Dependencies

**Core**:
- pandas, numpy - Data handling
- tensorflow, keras - Neural networks
- scikit-learn - ML preprocessing
- python-metatrader5 - MT5 API
- pydantic - Config validation

**Development**:
- pytest, pytest-cov - Testing
- black, flake8, mypy - Code quality
- jupyter - Notebooks

See [pyproject.toml](pyproject.toml) for full list.

---

## 🧪 Testing

```bash
# Run all tests with coverage
poetry run pytest tests/ --cov=src --cov-report=html

# Watch mode (requires pytest-watch)
poetry run pytest-watch tests/

# Specific test
poetry run pytest tests/unit/test_workflow.py::TestWorkflow::test_eventbus_publish_subscribe -v
```

### Test Coverage
- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Target: > 80% code coverage

---

## 🔧 Development

### Code Style
```bash
# Format with black
poetry run black src/

# Check with flake8
poetry run flake8 src/

# Type check with mypy
poetry run mypy src/
```

### Adding New Strategy
1. Create `src/strategies/my_strategy.py` inheriting `BaseStrategy`
2. Implement `define_features()`, `define_target()`, `define_model()`, `get_feature_names()`
3. Add to `configs/main.yaml`
4. Train with `poetry run python train_model.py`

---

## 📚 Documentation Structure

```
docs/
├── planning/          # Sprint plans, status reports (13 files)
├── architecture/      # Technical specs, layout, migration
└── user/             # User guides, tutorials
```

---

## 🔗 References

- [Python 3.12 Docs](https://docs.python.org/3.12/)
- [Poetry Docs](https://python-poetry.org/docs/)
- [MetaTrader 5 Python API](https://www.metatrader5.com/en/terminal/help/python_api)
- [TensorFlow Keras](https://keras.io/)

---

## 📞 Support

For questions or issues:
1. Check [Implementation Plan](docs/planning/IMPLEMENTATION_PLAN.md)
2. Review relevant [docs](docs/) section
3. See [PLANO_SPRINT_3.md](docs/planning/PLANO_SPRINT_3.md) for architecture decisions

---

**Maintained by**: evandro-godoy  
**Last Updated**: Sprint 3 - Migration & Clean Up
```

**Validação**:
- [ ] README.md criado na raiz
- [ ] Todos os links apontam para arquivos válidos
- [ ] Formatação markdown correta
- [ ] Seções principais: Quick Navigation, Quick Start, Architecture, Dependencies, Testing, Development, Documentation, References

---

### Ação 5: Atualizar Cross-References

**Checklist de Links Internos**:
- [ ] `IMPLEMENTATION_PLAN.md` em docs/planning/ (update any relative paths)
- [ ] `PLANO_SPRINT_3.md` em docs/planning/ (update any relative paths)
- [ ] README.md links para docs/planning/, docs/architecture/, docs/user/
- [ ] Nenhum link quebrado (testar com `grep -r "\[" docs/` e verificar targets)

**Comando Teste (Linux/Mac)**:
```bash
# Check for broken markdown links
for file in docs/**/*.md README.md; do
  echo "Checking $file..."
  # Extract links and validate
done
```

---

### Ação 6: Validar Documentação Migrada

**Checklist**:
- [ ] 13 arquivos em `docs/planning/`
- [ ] 2 arquivos em `docs/architecture/`
- [ ] 2 arquivos em `docs/user/`
- [ ] README.md na raiz
- [ ] Total: 17+ documentação files
- [ ] Nenhum `.md` solto na raiz de wtnps-finadv

**Comando**:
```bash
# Count docs
find docs -name "*.md" | wc -l  # Should be >= 17
ls -la *.md 2>/dev/null | wc -l # Should be 1 (apenas README.md)
```

---

## 🎯 Critério de Aceite (DoD)

- ✅ 13 docs planejamento migrados → docs/planning/
- ✅ 2 docs arquitetura criados → docs/architecture/
- ✅ 2 docs usuário migrados → docs/user/
- ✅ README.md criado na raiz como entrypoint
- ✅ Todos os links internos válidos (sem quebrados)
- ✅ Cross-references atualizadas
- ✅ Nenhum .md solto na raiz de wtnps-finadv
- ✅ Estrutura docs/ segue padrão: planning/, architecture/, user/

---

## 🔗 Dependencies

- ✅ ARCH-001 (Setup Infraestrutura)

## ➡️ Blocks

- Nenhum (informacional)
- Prepara onboarding para GUARDIAN-003 e DEVOPS-004

---

## 📝 Notas

- Links atualizados = nenhum documento quebrado
- README.md é o entry point = deve ter navegação clara
- 17+ documentação centralizada = fácil onboarding
