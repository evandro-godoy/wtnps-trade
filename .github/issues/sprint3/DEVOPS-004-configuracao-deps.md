# DEVOPS-004: Configuração de Dependências

**Epic**: Sprint 3 - Migration & Clean Up  
**Type**: DevOps Task  
**Effort**: 4 Story Points (4h)  
**Priority**: 🔴 Critical (execution depends on this)  
**Assignee**: @DEVOPS  
**Dependency**: ARCH-001 ✅, GUARDIAN-003 ✅

---

## 📌 Objetivo
Inicializar Poetry em `wtnps-finadv`, adicionar 25 dependências (19 ativas + 6 dev), gerar `poetry.lock` validado, e garantir `pip install` limpo funcione.

---

## 📋 Ações

### Ação 1: Inicializar Poetry

```bash
cd wtnps-finadv

poetry init --no-interaction \
  --name wtnps-finadv \
  --description "WTNPS FinAdv - Algorithmic Trading Framework" \
  --author "evandro-godoy" \
  --python "^3.12"
```

**Validação**:
```bash
# Verificar pyproject.toml criado
cat pyproject.toml | head -20

# Verificar estrutura
grep -A 5 "\[tool.poetry\]" pyproject.toml
grep -A 5 "\[tool.poetry.dependencies\]" pyproject.toml
```

**Checklist**:
- [ ] `pyproject.toml` criado na raiz
- [ ] `[tool.poetry]` seção presente
- [ ] `[tool.poetry.dependencies]` seção presente
- [ ] Python constraint: `^3.12`
- [ ] Nenhuma dependência adicionada ainda

---

### Ação 2: Adicionar 19 Dependências Ativas

**Grupo 1: Data & Math** (pandas, numpy, scipy)
```bash
poetry add pandas numpy scipy
```

**Grupo 2: ML/AI** (tensorflow, keras, scikit-learn)
```bash
poetry add tensorflow keras scikit-learn
```

**Validação Grupo 2**: Keras + TensorFlow = não duplicar
```bash
grep "keras\|tensorflow" pyproject.toml
```

**Grupo 3: Trading/MT5**
```bash
poetry add python-metatrader5 pytz
```

**Grupo 4: Config & Validation**
```bash
poetry add pydantic pydantic-settings python-dotenv
```

**Grupo 5: Data Serialization**
```bash
poetry add joblib sqlalchemy
```

**Grupo 6: Web/GUI**
```bash
poetry add fastapi uvicorn websockets
```

**Grupo 7: Visualization**
```bash
poetry add plotly mplfinance bokeh
```

**Resumo Grupo 1-7**: 19 dependências ativas

**Validação Completa**:
```bash
# Verificar todas as 19 dependências adicionadas
poetry show --tree | head -30

# Contar dependências
grep -c "^[a-z]" < <(poetry show | awk '{print $1}')  # Should be >= 19
```

**Checklist**:
- [ ] pandas ✅
- [ ] numpy ✅
- [ ] scipy ✅
- [ ] tensorflow ✅
- [ ] keras ✅
- [ ] scikit-learn ✅
- [ ] python-metatrader5 ✅
- [ ] pytz ✅
- [ ] pydantic ✅
- [ ] pydantic-settings ✅
- [ ] python-dotenv ✅
- [ ] joblib ✅
- [ ] sqlalchemy ✅
- [ ] fastapi ✅
- [ ] uvicorn ✅
- [ ] websockets ✅
- [ ] plotly ✅
- [ ] mplfinance ✅
- [ ] bokeh ✅

---

### Ação 3: Adicionar 6 Dev Dependencies

```bash
poetry add --group dev \
  pytest \
  pytest-cov \
  pytest-mock \
  pytest-asyncio \
  black \
  flake8 \
  mypy \
  ipython

# Note: Total 8 dev, reorganizar se necessário
```

**Validação**:
```bash
# Verificar dev group
grep -A 15 "\[tool.poetry.group.dev.dependencies\]" pyproject.toml
```

**Checklist**:
- [ ] pytest ✅
- [ ] pytest-cov ✅
- [ ] pytest-mock ✅
- [ ] pytest-asyncio ✅
- [ ] black ✅
- [ ] flake8 ✅
- [ ] mypy ✅
- [ ] ipython ✅

---

### Ação 4: Verificar Estrutura pyproject.toml

```bash
# Validar estrutura completa
cat > /tmp/validate_pyproject.py << 'EOF'
import toml

with open('pyproject.toml', 'r') as f:
    config = toml.load(f)

# Verificar seções obrigatórias
sections = [
    ('tool.poetry', 'Metadata'),
    ('tool.poetry.dependencies', 'Dependencies'),
    ('tool.poetry.group.dev.dependencies', 'Dev Dependencies'),
]

for section, label in sections:
    parts = section.split('.')
    obj = config
    for part in parts:
        obj = obj.get(part, {})
    if obj:
        print(f"✓ {label} found")
    else:
        print(f"✗ {label} MISSING")

# Verificar Python version
python_ver = config.get('tool', {}).get('poetry', {}).get('python', 'NOT SET')
print(f"\nPython version constraint: {python_ver}")
if python_ver == '^3.12':
    print("✓ Python ^3.12 OK")
else:
    print("✗ Python version incorrect")
EOF

poetry run python /tmp/validate_pyproject.py
```

**Saída Esperada**:
```
✓ Metadata found
✓ Dependencies found
✓ Dev Dependencies found

Python version constraint: ^3.12
✓ Python ^3.12 OK
```

**Checklist**:
- [ ] `[tool.poetry]` present
- [ ] `[tool.poetry.dependencies]` present com 19 packages
- [ ] `[tool.poetry.group.dev.dependencies]` present com 8 packages
- [ ] Python = `^3.12`
- [ ] Nenhuma seção duplicada

---

### Ação 5: Gerar poetry.lock

```bash
# Lock without updating (use exact versions from add)
poetry lock --no-update

# Verificar lock criado
ls -lh poetry.lock
```

**Validação**:
```bash
# Contar packages no lock
grep "^name = " poetry.lock | wc -l  # Should be >= 50+ (transitive deps)

# Verificar tamanho (deve ser > 100 KB)
du -h poetry.lock
```

**Checklist**:
- [ ] `poetry.lock` criado
- [ ] Size > 100 KB
- [ ] Contains >= 50 packages (direct + transitive)
- [ ] Nenhum erro de dependency conflict
- [ ] Nenhum warning de incompatibility

---

### Ação 6: Teste de Install Limpo (Fresh Venv)

**Criar venv isolado**:
```bash
# Linux/Mac
python3.12 -m venv /tmp/test_wtnps_venv
source /tmp/test_wtnps_venv/bin/activate

# Windows PowerShell
python -m venv C:\tmp\test_wtnps_venv
C:\tmp\test_wtnps_venv\Scripts\Activate.ps1
```

**Instalar no venv limpo**:
```bash
cd wtnps-finadv
poetry install

# Verificar install
poetry show | head -20
```

**Teste de Imports Críticos**:
```bash
# Test cada package importante
python -c "import pandas; print('✓ pandas')"
python -c "import numpy; print('✓ numpy')"
python -c "import tensorflow; print('✓ tensorflow')"
python -c "import keras; print('✓ keras')"
python -c "import sklearn; print('✓ scikit-learn')"
python -c "import MetaTrader5; print('✓ MetaTrader5')"
python -c "from pydantic import BaseSettings; print('✓ pydantic')"
python -c "import fastapi; print('✓ fastapi')"
python -c "import pytest; print('✓ pytest')"
python -c "import black; print('✓ black')"
```

**Esperado**: Todos retornam `✓`

**Checklist**:
- [ ] Install completa sem erro
- [ ] Todos os 19 packages instalados
- [ ] Todos os 8 dev packages instalados
- [ ] Imports críticos funcionam
- [ ] Nenhum `ModuleNotFoundError`

---

### Ação 7: Validar Testes Descobertos

```bash
cd wtnps-finadv

# Descobrir testes
poetry run pytest --collect-only tests/ -q

# Contar
poetry run pytest --collect-only tests/ | grep "test session starts" -A 5
```

**Esperado**:
```
test session starts
collected 10 items  # ou similar
```

**Checklist**:
- [ ] >= 10 testes descobertos
- [ ] Nenhum erro de import
- [ ] Nenhum `ModuleNotFoundError`

---

### Ação 8: Executar Smoke Test

```bash
# Run all tests
poetry run pytest tests/ -v --tb=short

# Run com coverage
poetry run pytest tests/ --cov=src --cov-report=term-missing
```

**Checklist**:
- [ ] >= 90% testes passam
- [ ] Cobertura > 70%
- [ ] Nenhum erro de dependência

---

### Ação 9: Documentar pyproject.toml

**Adicionar comentários e pytest config**:

```toml
[tool.poetry]
name = "wtnps-finadv"
version = "0.1.0"
description = "WTNPS FinAdv - Algorithmic Trading Framework"
authors = ["evandro-godoy <evandro@example.com>"]
readme = "README.md"
python = "^3.12"

[tool.poetry.dependencies]
# Core data & math
pandas = "^2.0"
numpy = "^1.24"
scipy = "^1.10"

# ML & Neural Networks
tensorflow = "^2.14"
keras = "^2.14"
scikit-learn = "^1.3"

# Trading & Data
python-metatrader5 = "^5.0"
pytz = "^2024.1"

# Configuration
pydantic = "^2.0"
pydantic-settings = "^2.0"
python-dotenv = "^1.0"

# Serialization
joblib = "^1.3"
sqlalchemy = "^2.0"

# Web Framework & Async
fastapi = "^0.104"
uvicorn = "^0.24"
websockets = "^12.0"

# Visualization
plotly = "^5.17"
mplfinance = "^0.12"
bokeh = "^3.3"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4"
pytest-cov = "^4.1"
pytest-mock = "^3.12"
pytest-asyncio = "^0.21"
black = "^23.11"
flake8 = "^6.1"
mypy = "^1.7"
ipython = "^8.17"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "--strict-markers"

[tool.black]
line-length = 100
target-version = ['py312']

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

**Checklist**:
- [ ] Todas as 19 dependências listadas com versões
- [ ] Todas as 8 dev dependências listadas com versões
- [ ] `[tool.pytest.ini_options]` configurado
- [ ] `[tool.black]` configurado (opcional)
- [ ] `[tool.mypy]` configurado (opcional)

---

## 🎯 Critério de Aceite (DoD)

- ✅ `pyproject.toml` criado com Python ^3.12
- ✅ 19 dependências ativas adicionadas (all listed above)
- ✅ 8 dev dependencies adicionadas
- ✅ `poetry.lock` gerado sem conflicts
- ✅ Fresh install completa com sucesso
- ✅ Todos os 27 packages instalados corretamente
- ✅ Imports críticos (pandas, tensorflow, keras, MT5, etc) funcionam
- ✅ pytest descobre >= 10 testes
- ✅ >= 90% testes passam
- ✅ Cobertura > 70%
- ✅ Nenhum erro de dependência ou versionamento

---

## 🔗 Dependencies

- ✅ ARCH-001 (Setup Infraestrutura)
- ✅ GUARDIAN-003 (Code migrado)

## ➡️ Blocks

- Nenhum (final task)

---

## ⚠️ Riscos

| Risk | Probability | Mitigation |
|------|-------------|-----------|
| TensorFlow version incompatibility | Medium | Use `poetry update` se conflict, test fresh install |
| MT5 library not available on Linux | Medium | Document: MT5 só em Windows, mock em CI |
| Transitive dependency conflict | Low | `poetry lock --no-update`, resolver manualmente |
| Missing python 3.12 | Low | Specify python version em error message, update docs |

---

## 📝 Notas

- **Poetry vs pip**: Poetry = melhor versionamento, determinístico (lock file)
- **Python 3.12**: LTS até 2028, performance +5-10%
- **Dev group**: Separado de production = `poetry install` sem dev packages funciona
- **Transitive deps**: poetry resolve automaticamente 50+ packages (diretos + indiretos)
