# Reorganização da Estrutura do NewApp

## Resumo da Migração

A estrutura de diretórios do `newapp` foi reorganizada para seguir o mesmo padrão arquitetural do projeto principal `wtnps-trade`.

## Estrutura Anterior

```
newapp/
├── __init__.py
├── main.py
├── config.py              # ❌ Raiz do projeto
├── plotting.py
├── test_provider.py       # ❌ Raiz do projeto
├── test_analyzer.py       # ❌ Raiz do projeto
├── data/                  # ❌ Nome inconsistente
│   ├── __init__.py
│   └── provider.py
├── analysis/              # ❌ Fora de src/
│   ├── __init__.py
│   └── context_analyzer.py
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
└── templates/
    └── index.html
```

## Estrutura Atual

```
newapp/
├── __init__.py            # ✅ Exports centralizados
├── main.py                # ✅ FastAPI entry point
├── plotting.py            # ✅ Bokeh charts
├── README.md
├── configs/               # ✅ Configurações isoladas
│   ├── __init__.py
│   └── config.py
├── src/                   # ✅ Código-fonte organizado
│   ├── __init__.py
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── context_analyzer.py
│   └── data_handler/      # ✅ Nome consistente com projeto raiz
│       ├── __init__.py
│       └── provider.py
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
├── templates/
│   └── index.html
└── tests/                 # ✅ Testes isolados
    ├── __init__.py
    ├── test_provider.py
    └── test_analyzer.py
```

## Mudanças de Imports

### Antes
```python
from newapp.config import DEFAULT_SYMBOL
from newapp.data.provider import get_default_provider
from newapp.analysis.context_analyzer import analyze_market_context
```

### Depois
```python
from newapp.configs.config import DEFAULT_SYMBOL
from newapp.src.data_handler.provider import get_default_provider
from newapp.src.analysis.context_analyzer import analyze_market_context
```

### Via __init__.py (Recomendado)
```python
# Imports diretos através do package
from newapp import (
    get_default_provider,
    analyze_market_context,
    DEFAULT_SYMBOL,
    DEFAULT_TIMEFRAME,
    HybridProvider,
    MarketContextAnalyzer,
)
```

## Arquivos Atualizados

### Código-fonte
- ✅ `newapp/__init__.py` - Exports atualizados
- ✅ `newapp/main.py` - Imports de config, provider, analyzer
- ✅ `newapp/plotting.py` - Sem alterações necessárias

### Configuração
- ✅ `configs/config.py` - Movido de raiz
- ✅ `configs/__init__.py` - Criado

### Source Code
- ✅ `src/__init__.py` - Criado
- ✅ `src/data_handler/provider.py` - Movido de `data/`
- ✅ `src/data_handler/__init__.py` - Movido de `data/`
- ✅ `src/analysis/context_analyzer.py` - Movido de `analysis/`
- ✅ `src/analysis/__init__.py` - Movido de `analysis/`

### Testes
- ✅ `tests/test_provider.py` - Movido + sys.path adicionado
- ✅ `tests/test_analyzer.py` - Movido + sys.path adicionado
- ✅ `tests/__init__.py` - Criado

### Documentação
- ✅ `README.md` - Todos os imports atualizados

## Diretórios Removidos

- ❌ `data/` → Renomeado para `src/data_handler/`
- ❌ `analysis/` → Movido para `src/analysis/`

## Vantagens da Nova Estrutura

1. **Consistência**: Mesma arquitetura do projeto raiz (`wtnps-trade`)
2. **Organização**: Separação clara entre código, configs e testes
3. **Escalabilidade**: Fácil adicionar novos módulos em `src/`
4. **Nomenclatura**: `data_handler` alinhado com projeto principal
5. **Isolamento**: Testes e configurações em diretórios dedicados

## Execução

### Servidor Web
```powershell
poetry run python -m newapp.main
# Acesse: http://localhost:8100
```

### Testes
```powershell
# Do diretório raiz do projeto
poetry run python newapp/tests/test_provider.py
poetry run python newapp/tests/test_analyzer.py
```

### Import Direto
```python
# Importações via package principal
from newapp import get_default_provider, DEFAULT_SYMBOL

# Ou imports específicos
from newapp.src.data_handler.provider import HybridProvider
from newapp.configs.config import MAX_LIMIT
```

## Status

✅ **Migração Completa**
- Estrutura de diretórios criada
- Arquivos movidos
- Imports atualizados em todos os arquivos
- Documentação atualizada
- Servidor testado e funcionando
- Porta 8100 ativa e respondendo

## Data da Migração

22 de Novembro de 2025
