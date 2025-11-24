# NewApp - WTNPS Trade Web Interface

## Overview
`newapp` é a interface web moderna do WTNPS Trade, construída com **FastAPI** para substituir a interface desktop (Tkinter). Fornece acesso via API REST aos dados de mercado e estratégias de trading com suporte para deployments cloud e local.

## Arquitetura

### Estrutura de Diretórios
```
newapp/
├── __init__.py
├── main.py                    # FastAPI application entry point
├── plotting.py                # Bokeh chart generation
├── README.md
├── configs/
│   ├── __init__.py
│   └── config.py              # Centralized configuration
├── src/
│   ├── __init__.py
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── context_analyzer.py # Technical analysis engine
│   ├── data_handler/
│   │   ├── __init__.py
│   │   ├── provider.py        # Data provider abstraction layer
│   │   └── historical_reader.py # DB-first historical data reader
│   ├── database/
│   │   ├── __init__.py
│   │   ├── db.py              # SQLAlchemy engine & session management
│   │   ├── models.py          # ORM models (AssetsRates, etc.)
│   │   ├── repository.py      # Data access layer with repositories
│   │   ├── ingest_historical.py # Historical data ingestion script
│   │   └── enrich_assets_rates_indicators.py # Indicator enrichment
│   └── utils/
│       ├── __init__.py
│       └── indicators.py      # Centralized technical indicators
├── static/
│   ├── css/
│   │   └── style.css          # Application styles
│   └── js/
│       └── app.js             # Frontend logic
├── templates/
│   └── index.html             # Main dashboard template
└── tests/
    ├── __init__.py
    ├── test_provider.py       # Data provider test suite
    └── test_analyzer.py       # Market analyzer test suite
```

### Componentes Principais

#### 1. Data Provider (`src/data_handler/provider.py`)
Sistema de abstração de dados com padrão **Singleton** e **Factory**:

**Providers Disponíveis:**
- **`MetaTraderProvider`**: Conexão direta com MT5 (Windows-only)
- **`CacheProvider`**: Leitura de arquivos Parquet cacheados
- **`SyntheticProvider`**: Geração de dados sintéticos para testes
- **`HybridProvider`**: Cascata inteligente (MT5 → Cache → Synthetic)

**Características:**
- Thread-safe para requisições concorrentes
- Cache automático em `.cache_data/`
- Chunked downloads para grandes volumes de dados
- Timezone-aware (UTC por padrão)

**Uso:**
```python
from newapp.src.data_handler.provider import get_default_provider

provider = get_default_provider()  # HybridProvider singleton
df = provider.get_latest_candles('WDO$', 'M5', 500)
```

#### 2. Configuration (`configs/config.py`)
Centraliza todas as configurações da aplicação:

**Variáveis de Ambiente Suportadas:**
- `WTNPS_HOST`: Host do servidor (padrão: `0.0.0.0`)
- `WTNPS_PORT`: Porta do servidor (padrão: `8100`)
- `WTNPS_RELOAD`: Auto-reload em dev (padrão: `true`)
- `WTNPS_LOG_LEVEL`: Nível de log (padrão: `INFO`)
- `WTNPS_ENABLE_MT5`: Habilita MetaTrader5 (padrão: `true`)

**Constantes:**
```python
from newapp.configs.config import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, MAX_LIMIT

print(DEFAULT_SYMBOL)      # "WDO$"
print(DEFAULT_TIMEFRAME)   # "M5"
print(MAX_LIMIT)           # 5000
```

#### 3. Market Context Analyzer (`analysis/context_analyzer.py`)
Motor de análise técnica independente para contexto de mercado:

**Análises Fornecidas:**
- **Tendência:** Direção (ALTA/BAIXA/LATERAL) e força (FORTE/MODERADA/FRACA)
- **Momentum:** RSI com classificação (SOBRECOMPRADO/SOBREVENDIDO/NEUTRO)
- **Níveis:** Suporte e resistência dinâmicos
- **Price Action:** Padrões de vela (BARRA_FORTE, REJEIÇÃO, etc.)
- **Médias Móveis:** EMA(9), SMA(20), SMA(50)

**Características:**
✅ Validação de sinais ML contra contexto técnico  
✅ Parâmetros configuráveis (períodos, thresholds)  
✅ Thread-safe para uso web  
✅ Análise completa em single call  

**Uso:**
```python
from newapp.src.analysis.context_analyzer import analyze_market_context

# Quick analysis
context = analyze_market_context(df)
print(f"Trend: {context['trend']}, RSI: {context['rsi']}")

# Advanced usage with custom parameters
from newapp.src.analysis.context_analyzer import MarketContextAnalyzer

analyzer = MarketContextAnalyzer(
    ema_fast=9,
    sma_slow=50,
    rsi_period=14
)
context = analyzer.analyze(df)

# Validate ML signal
valid, reason = analyzer.validate_signal('COMPRA', context, require_trend_alignment=True)
```

#### 4. Main Application (`main.py` - Refatorado)
Aplicação FastAPI com endpoints REST:

**Endpoints:**
- `GET /` - Dashboard HTML principal
- `GET /api/ohlc` - Dados OHLCV em JSON
  - Query params: `symbol`, `timeframe`, `limit`
  - Exemplo: `/api/ohlc?symbol=WDO$&timeframe=H1&limit=1000`
- `GET /api/analysis` - Análise técnica de contexto
  - Query params: `symbol`, `timeframe`, `limit`
  - Exemplo: `/api/analysis?symbol=WDO$&timeframe=M5&limit=500`
- `GET /api/combined` - OHLC + Análise em single request
  - Query params: `symbol`, `timeframe`, `limit`
  - Exemplo: `/api/combined?symbol=WDO$&timeframe=M5&limit=500`

**Response Schema - OHLC (JSON):**
```json
{
  "symbol": "WDO$",
  "timeframe": "M5",
  "count": 500,
  "latest": {
    "time": "2025-11-22T14:30:00+00:00",
    "open": 100500.0,
    "high": 100550.0,
    "low": 100480.0,
    "close": 100520.0,
    "volume": 1234
  },
  "data": [...]
}
```

**Response Schema - Analysis (JSON):**
```json
{
  "symbol": "WDO$",
  "timeframe": "M5",
  "candles_analyzed": 500,
  "timestamp": "2025-11-22T18:25:00+00:00",
  "analysis": {
    "trend": "ALTA",
    "trend_strength": "FRACA",
    "rsi": 59.52,
    "rsi_condition": "NEUTRO",
    "support": 5406.50,
    "resistance": 5419.50,
    "distance_to_support": 0.18,
    "distance_to_resistance": 0.06,
    "pattern": "NEUTRO",
    "ema_fast": 5414.11,
    "sma_fast": 5413.68,
    "sma_slow": 5412.53,
    "current_price": 5416.50
  }
}
```

**Response Schema - Combined (JSON):**
```json
{
  "symbol": "WDO$",
  "timeframe": "M5",
  "count": 500,
  "timestamp": "2025-11-22T18:25:00+00:00",
  "latest": { "time": "...", "open": 5416.0, ... },
  "ohlc": [...],
  "analysis": { "trend": "ALTA", ... }
}
```

## Execução

### Desenvolvimento Local (Windows com MT5)
```powershell
# Ativar ambiente Poetry
poetry shell

# Executar aplicação
poetry run python -m newapp.main

# Ou usando uvicorn diretamente
poetry run uvicorn newapp.main:app --reload --port 8100
```

### Desenvolvimento Cloud (sem MT5)
```bash
# Define variável de ambiente para desabilitar MT5
export WTNPS_ENABLE_MT5=false

# Executar com dados sintéticos
poetry run python -m newapp.main
```

### Produção
```powershell
# Usando uvicorn com workers
poetry run uvicorn newapp.main:app --host 0.0.0.0 --port 8100 --workers 4
```

Acesse: `http://localhost:8100`

## Integração com Sistema Existente

### Módulo de Indicadores Centralizados (`src/utils/indicators.py`)

**Novo desde v0.2.0** - Consolidação de cálculos técnicos duplicados.

Todas as funções de cálculo de indicadores (EMA, SMA, RSI) foram centralizadas para:
- ✅ Eliminar duplicação de código (~100 linhas)
- ✅ Garantir consistência nos cálculos
- ✅ Facilitar testes unitários
- ✅ Permitir fácil adição de novos indicadores

**Funções Disponíveis:**
```python
from newapp.src.utils.indicators import (
    calculate_ema,      # EMA individual
    calculate_sma,      # SMA individual
    calculate_rsi,      # RSI individual
    add_basic_indicators,           # Enriquecimento completo
    enrich_indicators_from_close,   # Wrapper legado (EMA9, SMA20/50/200)
    compute_indicator_dict,         # Retorna dict de Series
)
```

**Uso nos Módulos:**
- `ingest_historical.py` → Usa `enrich_indicators_from_close()`
- `repository.py` → Usa `compute_indicator_dict()` para bulk updates
- `context_analyzer.py` → Delega cálculos individuais mantendo lógica de análise
- `enrich_assets_rates_indicators.py` → Usa `compute_indicator_dict()`

**Exemplo:**
```python
import pandas as pd
from newapp.src.utils.indicators import add_basic_indicators

df = pd.DataFrame({'close': [100, 102, 101, 103, 105]})
df = add_basic_indicators(df, ema_periods=[9], sma_periods=[20, 50, 200])
# Adiciona colunas: ema_9, sma_20, sma_50, sma_200
```

### Diferenças vs `src/data_handler/provider.py`

| Aspecto | `src/` (Original) | `newapp/` (Novo) |
|---------|-------------------|------------------|
| **Objetivo** | Desktop app (Tkinter) | Web app (FastAPI) |
| **Concorrência** | Single-threaded | Thread-safe (Singleton) |
| **Fallback** | Manual | Automático (HybridProvider) |
| **Cloud Support** | Não (requer MT5) | Sim (Synthetic fallback) |
| **Imports** | `import MetaTrader5` | Conditional import |
| **Indicadores** | Duplicados em cada módulo | Centralizados em `utils/indicators.py` |

### Compatibilidade de Dados
Ambos os sistemas:
- Usam o mesmo diretório de cache (`.cache_data/`)
- Formato Parquet compatível
- Schema OHLCV idêntico
- **Novidade:** Base histórica SQLite (`wtnps_trade.db`) para dados imutáveis
- Timezone UTC

**Compartilhamento de Cache:**
```python
# Script antigo (src/)
from src.data_handler.provider import MetaTraderProvider
provider = MetaTraderProvider()
df = provider.get_data('WDO$', '2025-01-01', '2025-11-22', mt5.TIMEFRAME_M5)
# Cache salvo em: .cache_data/MT5_WDO_M5_20250101_20251122.parquet

# NewApp pode ler o mesmo cache
from newapp.src.data_handler.provider import CacheProvider
cache = CacheProvider()
df_cached = cache.get_latest_candles('WDO$', 'M5', 500)  # Usa cache do script antigo
```

## Migrações Futuras

### Roadmap de Features
1. **WebSocket para dados real-time** (substituir polling)
2. **Autenticação/Autorização** (JWT tokens)
3. **Dashboard interativo** (Vue.js/React)
4. **Endpoints de estratégias ML** (carregar modelos treinados)
5. **API de backtesting** (executar via REST)

### Migração Desktop → Web
Para migrar funcionalidades de `src/gui/`:

1. **Identificar lógica de negócio** (separar de UI Tkinter)
2. **Criar endpoint FastAPI** correspondente
3. **Adaptar para async/await** se necessário
4. **Implementar frontend** (HTML/JS ou framework moderno)

**Exemplo - Monitor GUI:**
```python
# Antes (src/gui/monitor_ui.py)
class MonitorUI:
    def fetch_data(self):
        df = provider.get_latest_candles(...)
        self.update_chart(df)  # Tkinter canvas

# Depois (newapp/main.py)
@router.get('/api/monitor/latest')
async def get_monitor_data():
    df = data_provider.get_latest_candles(...)
    return df.to_dict('records')  # JSON para frontend
```

## Troubleshooting

### Erro: `ModuleNotFoundError: No module named 'MetaTrader5'`
**Causa:** MT5 não instalado (ambiente cloud/Linux)

**Solução:**
```powershell
# Desabilitar MT5 provider
$env:WTNPS_ENABLE_MT5="false"
poetry run python -m newapp.main
```

### Erro: `FileNotFoundError: [Errno 2] No such file or directory: '.cache_data'`
**Causa:** Diretório de cache não existe

**Solução:**
```python
# Executar validação de config (automático no import)
from newapp.configs.config import validate_config
validate_config()  # Cria diretórios necessários
```

### Dados sintéticos sempre retornados
**Causa:** MT5 desconectado + cache vazio

**Debug:**
```python
from newapp.src.data_handler.provider import MetaTraderProvider

mt5_provider = MetaTraderProvider()
print(mt5_provider.is_connected())  # False?

# Verificar cache
from newapp.configs.config import CACHE_DIR
print(list(CACHE_DIR.glob('*.parquet')))  # Vazio?
```

**Solução:** Conectar MT5 terminal ou popular cache com `train_model.py`

### Performance lenta em grandes datasets
**Causa:** Chunked downloads não otimizados

**Otimização:**
```python
# Ajustar tamanho de chunk (padrão: 183 dias)
from newapp.src.data_handler.provider import MetaTraderProvider

provider = MetaTraderProvider()
# Modificar _download_rates_in_chunks(chunk_size_days=90)
```

## Testes

### Unit Tests
```powershell
# Test data provider
$env:PYTHONPATH="c:\projects\wtnps-trade"
poetry run python newapp/test_provider.py

# Test market analyzer
$env:PYTHONPATH="c:\projects\wtnps-trade"
poetry run python newapp/test_analyzer.py

# Run all tests via pytest (future)
poetry run pytest tests/newapp/ -v
```

### Test Coverage

**Provider Tests (`test_provider.py`):**
- ✅ SyntheticProvider: Geração de dados aleatórios
- ✅ CacheProvider: Leitura de Parquet files
- ✅ MetaTraderProvider: Conexão MT5 e fetch
- ✅ HybridProvider: Fallback chain (MT5 → Cache → Synthetic)
- ✅ Singleton pattern validation

**Analyzer Tests (`test_analyzer.py`):**
- ✅ MarketContextAnalyzer: Análise técnica completa
- ✅ Signal Validation: Validação de sinais ML
- ✅ Convenience Function: `analyze_market_context()`
- ✅ Edge Cases: DataFrame vazio, dados insuficientes, parâmetros customizados

### Integration Tests
```python
# tests/newapp/test_provider_integration.py
import pytest
from newapp.src.data_handler.provider import HybridProvider

@pytest.fixture
def provider():
    return HybridProvider()

def test_fallback_chain(provider):
    df = provider.get_latest_candles('INVALID_SYMBOL', 'M5', 10)
    assert len(df) == 10  # Synthetic fallback
```

### Manual Testing
```bash
# Test OHLC endpoint
curl http://localhost:8100/api/ohlc?limit=10

# Test analysis endpoint
curl http://localhost:8100/api/analysis?symbol=WDO$&timeframe=M5&limit=500

# Test combined endpoint
curl http://localhost:8100/api/combined?limit=100

# Check provider/analyzer status (TODO: implement health endpoint)
curl http://localhost:8100/api/health
```

## Comparação: Análise Antiga vs Nova

### Diferenças vs `src/analysis/context_analyzer.py`

| Aspecto | `src/` (Original) | `newapp/` (Novo) |
|---------|-------------------|------------------|
| **Objetivo** | Desktop app (integrado com SimulationEngine) | Web app (API REST independente) |
| **Imports** | `from src.utils.logger` | Logging standalone |
| **Dependências** | Acoplado com `src/` modules | Autocontido (zero deps `src/`) |
| **Type Hints** | Parcial | Completo (`from __future__ import annotations`) |
| **Docstrings** | Português | Inglês (padrão API) |
| **Signal Format** | 'CALL'/'PUT' | 'COMPRA'/'VENDA' (normalizado internamente) |
| **Thread Safety** | N/A (single-thread) | Considerado (web concurrency) |

### Compatibilidade de Análise
Ambos os sistemas:
- Usam os mesmos algoritmos (EMA, SMA, RSI, S/R)
- Retornam dicionários compatíveis
- Suportam validação de sinais
- Períodos padrão idênticos (EMA9, SMA20/50, RSI14)

**Migração de Código:**
```python
# Antes (src/)
from src.analysis.context_analyzer import MarketContextAnalyzer
from src.data_handler.provider import MetaTraderProvider

provider = MetaTraderProvider()
df = provider.get_latest_candles('WDO$', mt5.TIMEFRAME_M5, 500)
analyzer = MarketContextAnalyzer()
context = analyzer.analyze(df)

# Depois (newapp/)
from newapp.src.data_handler.provider import get_default_provider
from newapp.src.analysis.context_analyzer import analyze_market_context

provider = get_default_provider()  # HybridProvider
df = provider.get_latest_candles('WDO$', 'M5', 500)
context = analyze_market_context(df)  # Mesma estrutura de retorno
```

## Manual Testing
```bash
# Test API endpoints
curl http://localhost:8100/api/ohlc?limit=10

# Check provider status
curl http://localhost:8100/api/health  # TODO: implement
```

## Segurança

### CORS Configuration
```python
# Para permitir frontend externo
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://seu-frontend.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### Rate Limiting
```python
# Instalar: poetry add slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/ohlc")
@limiter.limit("10/minute")
async def api_ohlc(...):
    ...
```

## Deployment Cloud

### Docker
```dockerfile
# Dockerfile (na raiz do projeto)
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

COPY newapp/ ./newapp/
COPY src/utils/ ./src/utils/  # Dependência logger

ENV WTNPS_ENABLE_MT5=false
ENV WTNPS_HOST=0.0.0.0
ENV WTNPS_PORT=8100

CMD ["poetry", "run", "uvicorn", "newapp.main:app", "--host", "0.0.0.0"]
```

### Kubernetes
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wtnps-trade-web
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: web
        image: wtnps-trade:latest
        env:
        - name: WTNPS_ENABLE_SYNTHETIC
          value: "true"
        ports:
        - containerPort: 8100
```

## Contribuindo

### Adicionando Novo Provider
```python
# newapp/data/provider.py
class MyCustomProvider(BaseDataProvider):
    def get_data(self, ticker, start_date, end_date, timeframe):
        # Implementar lógica de fetch
        return pd.DataFrame(...)
    
    def get_latest_candles(self, ticker, timeframe, count):
        return pd.DataFrame(...)

# Registrar no factory
def get_provider(provider_type: str):
    if provider_type == 'custom':
        return MyCustomProvider()
    ...
```

### Code Style
- **Type hints** obrigatórios
- **Docstrings** (Google Style) para funções públicas
- **Logging** ao invés de `print()`
- **Async/await** para operações I/O bound

---

**Versão:** 0.2.0  
**Última Atualização:** 2025-11-22  
**Mantenedores:** Equipe WTNPS Trade
