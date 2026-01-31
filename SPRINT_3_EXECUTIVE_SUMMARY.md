# Sprint 3: Migration & Clean Up
## Resumo Executivo para Tech Lead

**Status**: 📋 Plano Completo  
**Criação**: Sprint 3 Planning Session  
**Objetivo Final**: Migrar wtnps-trade → wtnps-finadv (Canonical Src Layout)

---

## 🎯 Visão Geral

### Situação Atual
- ❌ wtnps-trade: Poluído, scripts soltos, docs misturados, arquivo backup
- ❌ Estrutura flat-layout: Código, docs, scripts na raiz
- ❌ Múltiplos históricos: archive/, bkp/, modelsbkp/
- ❌ Dependências não explícitas: poetry.lock desatualizado

### Objetivo Sprint 3
- ✅ wtnps-finadv: Limpo, estruturado (Canonical Layout)
- ✅ Documentação centralizada: docs/planning/, docs/architecture/, docs/user/
- ✅ Apenas código ativo: src/, tests/, models/
- ✅ Dependências explícitas: poetry.toml + poetry.lock
- ✅ Testes validados: 100% passing

---

## 📊 4 Tarefas Sprint 3

| # | Task | Owner | Effort | Status | Blocker? |
|---|------|-------|--------|--------|----------|
| 1 | ARCH-001: Setup Infra | ARCHITECT | 5h | 📋 | 🔴 YES |
| 2 | ARCH-002: Migração Docs | ARCHITECT | 3h | 📋 | 🟠 Partial |
| 3 | GUARDIAN-003: Código | GUARDIAN | 6h | 📋 | 🔴 YES |
| 4 | DEVOPS-004: Deps | DEVOPS | 4h | 📋 | 🔴 YES |

**Total Effort**: 18h (2.25 FTE days / 3 calendar days)

---

## 🏗️ Task 1: ARCH-001 - Setup Infraestrutura
**Effort**: 5h | **Priority**: 🔴 CRITICAL (blocker for all)

### Ações
1. Clone `wtnps-finadv` repository
2. Criar Canonical Src Layout (10 diretórios)
3. Validar raiz (4 itens apenas: README.md, pyproject.toml, .gitignore, .env.example)
4. Inicializar git com commit limpo

### Critério Aceite
- ✅ Estrutura Canonical criada
- ✅ Raiz LIMPA (sem arquivos soltos)
- ✅ Git inicializado
- ✅ Nenhum arquivo backup/cache

### Deliverables
```
wtnps-finadv/
├── .github/
├── docs/{planning, architecture, user}
├── src/{15 subdirs}
├── tests/{unit, integration}
├── models/ (vazio, será preenchido por GUARDIAN-003)
├── notebooks/
├── reports/
├── configs/
├── logs/
├── .gitignore
└── (mais 3 files vêm depois)
```

---

## 📚 Task 2: ARCH-002 - Migração Documentação
**Effort**: 3h | **Priority**: 🟠 HIGH (prepara onboarding)

### Ações
1. Mover 13 docs planejamento → docs/planning/
2. Criar 2 docs arquitetura → docs/architecture/
3. Mover 2 docs usuário → docs/user/
4. Criar README.md raiz (entrypoint)
5. Atualizar cross-references

### Documentação Centralizada (17 total)
```
docs/planning/         (13 files)
├── IMPLEMENTATION_PLAN.md
├── PLANO_FASE_*.md (4)
├── FASE_*_STATUS.md (3)
├── RESUMO_*.md (2)
└── CONTEXT_ANALYZER_README.md

docs/architecture/     (2 files - NEW)
├── CANONICAL_LAYOUT.md
└── MIGRATION_GUIDE.md

docs/user/             (2 files)
├── GUIA_USUARIO_CHARTS.md
└── DRL_README.md
```

### Critério Aceite
- ✅ 17 docs migrados/criados
- ✅ Nenhum .md solto na raiz
- ✅ README.md com navegação funcional
- ✅ Links internos válidos

---

## 💻 Task 3: GUARDIAN-003 - Migração & Limpeza Código
**Effort**: 6h | **Priority**: 🔴 CRITICAL (core functionality)

### Ações
1. Copiar src/ (15 subdir, >100 .py files)
2. Copiar tests/ (>10 test files)
3. Copiar models/ (6 artefatos, >100 MB)
4. NÃO copiar: scripts soltos, archive/, bkp/, logs/
5. Validar imports (6 imports críticos)
6. Teste pytest (>=90% pass)

### Arquivos a Copiar
```
src/        (completo, 15 subdir)
tests/      (completo, unit + integration)
models/     (6 arquivos .keras + .joblib)
  - WDO$_*.keras, WDO$_*.joblib (3)
  - WIN$_*.keras, WIN$_*.joblib (3)
```

### Arquivos NÃO Copiar
```
❌ train_model.py, train_drl_model.py, run_monitor_gui.py (scripts soltos)
❌ archive/, bkp/, modelsbkp/ (deprecated)
❌ .cache_data/, __pycache__/ (cache)
❌ newapp/ (separado)
```

### Critério Aceite
- ✅ src/ inteiro copiado
- ✅ tests/ inteiro copiado
- ✅ models/ inteiro (6 arquivos)
- ✅ Nenhum lixo copiado
- ✅ 6 imports críticos validados
- ✅ pytest descobre >= 10 testes
- ✅ >= 90% testes passam

---

## 📦 Task 4: DEVOPS-004 - Configuração Dependências
**Effort**: 4h | **Priority**: 🔴 CRITICAL (execution)

### Ações
1. Inicializar poetry (Python ^3.12)
2. Adicionar 19 dependências ativas
3. Adicionar 8 dev dependencies
4. Gerar poetry.lock
5. Teste install limpo (fresh venv)
6. Validar testes rodam

### 19 Dependências Ativas
```
Data & Math:      pandas, numpy, scipy
ML/AI:            tensorflow, keras, scikit-learn
Trading:          python-metatrader5, pytz
Config:           pydantic, pydantic-settings, python-dotenv
Serialization:    joblib, sqlalchemy
Web/Async:        fastapi, uvicorn, websockets
Visualization:    plotly, mplfinance, bokeh
```

### 8 Dev Dependencies
```
pytest, pytest-cov, pytest-mock, pytest-asyncio
black, flake8, mypy, ipython
```

### Critério Aceite
- ✅ pyproject.toml criado (Python ^3.12)
- ✅ 19 dependências adicionadas
- ✅ 8 dev dependencies adicionadas
- ✅ poetry.lock gerado
- ✅ Fresh install sem erro
- ✅ Imports críticos funcionam
- ✅ pytest descobre >=10 testes
- ✅ >= 90% testes passam

---

## 📅 Roadmap & Timeline

```
Day 1 (5h):
  [###      ] ARCH-001 (5h) - Setup Infra
  
Day 2 (8h):
  [   ##    ] ARCH-002 (3h) - Migração Docs
  [######## ] GUARDIAN-003 (6h) - Código
  
Day 3 (5h):
  [####     ] DEVOPS-004 (4h) - Deps
  [  #      ] Integration & Validation (2h)
  
Total: 18h / 3 days
```

### Critical Path
```
ARCH-001 (5h)
    ↓
ARCH-002 (3h) + GUARDIAN-003 (6h) + DEVOPS-004 (4h)
    ↓
Integration Test + Final Validation (2h)
```

---

## ✅ Critérios Finais de Sucesso

### Estrutura
- [ ] Canonical Src Layout implementado
- [ ] Raiz: APENAS README.md, pyproject.toml, .gitignore, .env.example
- [ ] 10+ diretórios criados

### Documentação
- [ ] 17 docs centralizados em docs/
- [ ] README.md funcional com links
- [ ] Nenhum .md solto

### Código
- [ ] src/, tests/, models/ migrados completos
- [ ] Nenhum arquivo "lixo"
- [ ] Imports validados

### Dependências
- [ ] pyproject.toml com Python ^3.12
- [ ] 27 dependências (19 ativas + 8 dev)
- [ ] poetry.lock gerado

### Testing
- [ ] pytest descobre >= 10 testes
- [ ] >= 90% testes passam
- [ ] Cobertura > 70%

### Git
- [ ] Repositório inicializado
- [ ] Commit limpo com estrutura completa
- [ ] Branch main ativo

---

## 🚨 Riscos & Mitigation

| Risk | Prob | Impact | Mitigation |
|------|------|--------|-----------|
| Arquivo .keras corrompido | Low | Critical | Verificar size > 50MB, testar load |
| Import quebrada | Medium | High | Script de validação antes/depois |
| Dependência com versão errada | Medium | Medium | `poetry lock --no-update`, test fresh install |
| Links quebrados em docs | High | Low | Testar todos os links após migração |
| Script solto copiado acidentalmente | Low | High | Usar rsync filters, checklist final |

---

## 📊 Métricas de Sucesso

### Quantitativas
- ✅ 10+ diretórios criados
- ✅ 17+ documentação files
- ✅ >100 .py files em src/
- ✅ >=10 testes descobertos
- ✅ 27 dependências resolvidas
- ✅ >100 MB models/ preenchido

### Qualitativas
- ✅ Estrutura clara (Canonical Layout)
- ✅ Documentação centralizada
- ✅ Código ativo separado de deprecated
- ✅ Dependências explícitas (poetry.lock)
- ✅ Testes validados (>=90% pass)

---

## 🔄 Next Steps After Sprint 3

### Sprint 4: Production Hardening
- [ ] CI/CD workflow (GitHub Actions)
- [ ] Pre-commit hooks (black, flake8, mypy)
- [ ] Docker setup (containerização)
- [ ] Monitoring & logging

### Sprint 5: Feature Completeness
- [ ] NewApp FastAPI integration
- [ ] WebSocket real-time updates
- [ ] Database schema (SQLAlchemy models)
- [ ] Deployment pipeline

---

## 📞 Team Roles & Responsibilities

| Role | Task | Effort | Days |
|------|------|--------|------|
| ARCHITECT | ARCH-001, ARCH-002 | 8h | D1-D2 |
| GUARDIAN | GUARDIAN-003 | 6h | D2-D3 |
| DEVOPS | DEVOPS-004 | 4h | D3-D4 |
| Tech Lead | Coordination, Validation | 2h | D5 |

### Daily Standup
- 10:00 - Planning & blocking items
- 14:00 - Progress check
- 16:00 - Retro & next day planning

---

## 🎓 Learning & Docs

### Canonical Src Layout
- Reference: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- Benefits: Isolation, proper installation, CI/CD clarity

### Poetry Best Practices
- Use `poetry lock --no-update` for reproducibility
- Keep pyproject.toml organized (groups, comments)
- Test fresh install before deploy

### Git Strategy
- Clean history (no legacy commits)
- Atomic commits (one feature per commit)
- Tag releases (v0.1.0 after Sprint 3)

---

## 📋 Issue Templates

All 4 tasks have detailed GitHub issues (`.github/issues/sprint3/`):
1. **ARCH-001-setup-infra.md** (5h)
2. **ARCH-002-migracao-docs.md** (3h)
3. **GUARDIAN-003-migracao-codigo.md** (6h)
4. **DEVOPS-004-configuracao-deps.md** (4h)

Each issue includes:
- Detailed actions (step-by-step)
- Validation checklist (DoD)
- Risk mitigation
- Blockers & dependencies

---

## ✨ Expected Outcome

After Sprint 3 completion:
```
wtnps-finadv/  (Production-ready repository)
├── 📚 Complete documentation (17 files)
├── 💻 Clean code (src/, tests/, models/)
├── 📦 Explicit dependencies (poetry.lock)
├── ✅ Validated tests (>=90% passing)
├── 🔧 Canonical Src Layout
└── 🚀 Ready for Sprint 4 (Hardening)
```

**Result**: Professional, maintainable, production-grade codebase.

---

**Prepared by**: Tech Lead  
**Date**: Sprint 3 Planning  
**Distribution**: ARCHITECT, GUARDIAN, DEVOPS team
