# ARCH-001: Setup Infraestrutura Limpa

**Epic**: Sprint 3 - Migration & Clean Up  
**Type**: Architecture Task  
**Effort**: 5 Story Points (5h)  
**Priority**: 🔴 Critical (blocker)  
**Assignee**: @ARCHITECT

---

## 📌 Objetivo
Criar infraestrutura limpa em `wtnps-finadv` seguindo **Canonical Src Layout**, garantindo que a raiz do projeto contenha APENAS: `README.md`, `pyproject.toml`, `.gitignore`, `.env.example`.

---

## 📋 Ações

### Ação 1: Clone wtnps-finadv
```bash
git clone https://github.com/evandro-godoy/wtnps-finadv.git wtnps-finadv-new
cd wtnps-finadv-new
```

**Validação**:
- [ ] Repository clonado
- [ ] `.git/` existente
- [ ] `git remote -v` mostra origin → wtnps-finadv
- [ ] `git branch` mostra `main` como ativo

---

### Ação 2: Criar Estrutura Canonical Src Layout

Execute commands para criar estrutura:
```bash
# Core directories
mkdir -p .github/workflows
mkdir -p .github/ISSUE_TEMPLATE
mkdir -p docs/{planning,architecture,user}
mkdir -p src/{agents,analysis,api,backtest_engine,core,data_handler,environments,gui,live,modules,reporting,setups,simulation,strategies,utils}
mkdir -p tests/{unit,integration}
mkdir -p models
mkdir -p notebooks/{analyzes,miscellaneous,simulation,statistics,tests}
mkdir -p reports/{backtest,models}
mkdir -p configs
mkdir -p logs

# Create __init__.py files
touch src/__init__.py
for dir in agents analysis api backtest_engine core data_handler environments gui live modules reporting setups simulation strategies utils; do
  touch src/$dir/__init__.py
done
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py

# Create placeholder files
touch models/.gitkeep
touch reports/.gitkeep
touch logs/.gitkeep
```

**Validação**: Toda estrutura criada (use `tree` ou `dir /s` para verificar)

---

### Ação 3: Validar Raiz do Projeto

**Comandos de Validação**:
```bash
# Lista arquivos na raiz
ls -la | grep "^-"  # Linux/Mac
dir | grep -E "^\d" # Windows PowerShell

# Verificar count (deve ser exatamente 4)
ls -la | grep "^-" | wc -l
```

**Critério**: Raiz contém EXATAMENTE:
- ✅ `.github/` (diretório)
- ✅ `.gitignore` (arquivo)
- ✅ `docs/` (diretório)
- ✅ `src/` (diretório)
- ✅ `tests/` (diretório)
- ✅ `models/` (diretório)
- ✅ `notebooks/` (diretório)
- ✅ `reports/` (diretório)
- ✅ `configs/` (diretório)
- ✅ `logs/` (diretório)
- ✅ `.env.example` (será criado em ARCH-002)
- ✅ `README.md` (será criado em ARCH-002)
- ✅ `pyproject.toml` (será criado em DEVOPS-004)

**NÃO deve conter**:
- ❌ `train_model.py`, `train_drl_model.py`, `run_monitor_gui.py` (scripts soltos)
- ❌ `IMPLEMENTATION_PLAN.md`, `FASE_*.md`, `RESUMO_*.md` (docs soltos)
- ❌ `archive/`, `bkp/`, `modelsbkp/` (deprecated)
- ❌ `newapp/` (separado)
- ❌ `.cache_data/`, `__pycache__/`, `.pytest_cache/`

---

### Ação 4: Inicializar Git

```bash
git init  # Re-initialize se necessário
git add .
git config user.email "your-email@example.com"
git config user.name "Your Name"
git commit -m "feat: Canonical Src Layout setup for wtnps-finadv"
```

**Validação**:
- [ ] `git log --oneline` mostra commit inicial
- [ ] `git branch -a` mostra `main` branch
- [ ] `git status` retorna "nothing to commit"

---

## 🎯 Critério de Aceite (DoD)

- ✅ Estrutura Canonical Src Layout criada
- ✅ Raiz contém APENAS diretórios + `.gitignore`
- ✅ 10+ diretórios criados (src/, tests/, docs/, etc)
- ✅ Todos `__init__.py` presentes em src/
- ✅ Git inicializado com commit limpo
- ✅ Nenhum arquivo "lixo" (archive/, bkp/, logs/, cache)
- ✅ `git log` mostra estrutura completa

---

## 🔗 Dependencies

- ✅ Nenhuma (primeiro task)

## ➡️ Blocks

- ARCH-002 (Documentação)
- GUARDIAN-003 (Código)
- DEVOPS-004 (Dependências)

---

## 📝 Notas

- **Canonical Src Layout**: Isolamento de tests vs código
- **Python 3.12**: Compatibilidade com pyproject.toml
- **Git**: Começar limpo = não importar histórico poluído de wtnps-trade
