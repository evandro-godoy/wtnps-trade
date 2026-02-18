# NewApp Architecture Documentation

> Estado: Em Desenvolvimento. Este documento descreve a arquitetura planejada e o estado atual desta worktree “limpa”: sem duplicações; apenas objetos já implementados e recursos core permanecem válidos. As demais seções representam a visão futura/migrada.

**Version:** 1.0.0  
**Last Updated:** 2025-11-27  
**Status:** Em Desenvolvimento

## Overview

NewApp is the **next-generation web-based trading platform** for WTNPS Trade, designed as a modern, cloud-ready alternative to the legacy desktop framework. It follows clean architecture principles with clear separation of concerns, robust path resolution, and database-first data persistence.

## Objetos Implementados (Worktree Atual)
- **Web API + UI:** `newapp/main.py`, `main_clean.py`. Detalhe técnico: FastAPI app com rotas `GET /home`, `GET /charts`, `GET /monitor`, `GET /backtest`, REST `GET /api/ohlc`, `GET /api/analysis`, `GET /api/combined`, `POST /api/backtest/run`, `GET /api/backtest/run/{run_id}` e WebSockets `ws/monitor`, `ws/backtest`. Integrações: `HybridProvider`, `hybrid_data_loader` (database-first), `MarketContextAnalyzer`, SQLAlchemy `get_db`, `templates/` e `static/` com Bokeh (`newapp/plotting.py`). BackgroundTasks para persistência assíncrona.
- **Hybrid Data Loader (Database-First):** `newapp/src/data_handler/hybrid_data_loader.py`. Detalhe técnico: Estratégia DB-first com gap detection; fluxo: (1) query AssetsRates, (2) detecta gaps (> 2 candles), (3) fallback MT5 → Cache → Synthetic, (4) retorna imediatamente (DB+novos), (5) persiste em background via FastAPI BackgroundTasks (não bloqueia). Timezone-aware, thread-safe, deduplicação automática. Integrações: endpoints `/charts`, `/api/ohlc`, `AssetsRatesRepository`, providers. Ver `HYBRID_DATA_INTEGRATION.md`.
- **Provedores de Dados (HybridProvider):** `newapp/src/data_handler/provider.py`. Detalhe técnico: singleton thread-safe; cascata MT5 → Cache → Synthetic; cache Parquet em `newapp/.cache_data`; APIs `get_data`/`get_latest_candles`. Integrações: `hybrid_data_loader`, rotas `/api/*` e páginas de gráficos; MT5 (opcional), leitura/escrita de Parquet.
- **Análise Técnica:** `newapp/src/analysis/context_analyzer.py`. Detalhe técnico: `MarketContextAnalyzer` e helpers; saída com tendência + força, RSI, suportes/resistências, MAs e padrões. Integrações: `/api/analysis`, `MarketAnalysisRepository.save_analysis`, enriquecimento de indicadores em `AssetsRatesRepository`.
- **Banco de Dados (ORM/Repos):** `newapp/src/database/db.py`, `models.py`, `repository.py`. Tabelas: `OHLCVData`, `TechnicalIndicators`, `MarketAnalysis`, `DataProviderLog`, `AssetsRates`, `BacktestRun`, `BacktestTrade`. Detalhe técnico: SQLite com WAL mode (concurrent reads), path resolution via `get_db()`, suporte para SQL Server (prod). Integrações: endpoints (`get_db`), `hybrid_data_loader` (query + async persist), backtest (`BacktestRunRepository`, `BacktestTradeRepository`).
- **Backtesting Engine:** `newapp/src/backtest/engine.py`. Detalhe técnico: execução síncrona e streaming; sinais por EMA9×SMA20 com fallback para ML LSTM (artefatos em `../models/` quando disponíveis). Integrações: WebSocket `/ws/backtest` e APIs `/api/backtest/*`, persistência via repositórios.
- **Configuração e Paths:** `newapp/configs/config.py`. Constantes: `APP_ROOT`, `PROJECT_ROOT`, `STATIC_DIR`, `TEMPLATES_DIR`, `CACHE_DIR`, `MODELS_DIR`. Nota: path resolution via config (não via `newapp.src.utils.paths`). Integrações: app, providers, templates, logging.
- **Templates/Estático/Plotting:** `templates/`, `static/`, `newapp/plotting.py` (Bokeh). Integrações: páginas HTML e geração de gráfico de candles.
- **Testes (parciais):** `newapp/tests/` (ex.: `test_provider.py`, `test_database.py`, `test_context_analyzer.py`, `test_bokeh_chart.py`, `test_backtest_stream.py`, `test_hybrid_loader.py`, `verify_hybrid_integration.py`). Integrações: providers, ORM, análise, backtest e hybrid loader.
- **Recursos Compartilhados:** `models/` (raiz, artefatos LSTM/DRL), `wtnps_trade.db` (SQLite na raiz). Observação: o provider usa `newapp/.cache_data`; unificação com `.cache_data` na raiz é desejável em ciclo futuro.

## Technology Stack

- **Backend:** FastAPI (async REST API)
- **Frontend:** HTML/CSS/JS with Jinja2 templates, Bokeh charts
- **Database:** SQLAlchemy ORM (SQLite dev / SQL Server prod)
- **Data Providers:** Singleton pattern with cascading fallback (MT5 → Cache → Synthetic)
- **ML/AI:** TensorFlow/Keras (LSTM), scikit-learn integration
- **Analysis:** Independent technical analysis engine
- **Deployment:** Docker-ready, cloud-native

## Folder Structure

```
newapp/
├── main.py                    # FastAPI application entry point
├── main_clean.py              # Alternative clean version
├── calculate_indicators.py    # Standalone indicator calculator
├── plotting.py                # Bokeh chart generation
│
├── configs/                   # Configuration module
│   ├── config.py              # Centralized settings (env vars)
│   └── ...
│
├── src/                       # Source code (domain-driven)
│   ├── analysis/              # Technical analysis engine
│   │   └── context_analyzer.py
│   ├── backtest/              # Backtesting module
│   │   └── engine.py
│   ├── data_handler/          # Data abstraction (providers)
│   │   ├── provider.py
│   │   └── historical_reader.py
│   ├── database/              # SQLAlchemy ORM & repository
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   └── ...
│   ├── live/                  # Live trading (future)
│   └── utils/                 # Shared utilities
│       ├── indicators.py      # Technical indicators
│       └── paths.py           # Path resolution helpers
│
├── static/                    # Frontend assets (CSS, JS)
├── templates/                 # Jinja2 HTML templates
├── tests/                     # Test suite
├── sql/                       # Database scripts
├── notebooks/                 # Jupyter analysis notebooks
└── .cache_data/               # Parquet cache (shared with root)
```

## Relationship with Root-Level Files

NewApp operates in a **hybrid architecture** alongside legacy code during the migration period.

### Shared Resources (Root Level)

NewApp **shares** these resources with legacy `src/` code:

#### 1. Models Directory: `../models/`
- Contains trained LSTM/DRL models (`.keras`, `.joblib`, `.pkl`)
- **Access via:** `from newapp.src.utils.paths import get_models_dir`
- **Single source of truth** - no duplication

**Example:**
```python
from newapp.src.utils.paths import get_models_dir

models_dir = get_models_dir()
lstm_model = models_dir / "WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras"
```

#### 2. Database: `../wtnps_trade.db`
- SQLite database at repository root
- **Access via:** `from newapp.src.utils.paths import get_database_path`
- Environment variable: `WTNPS_SQLITE_PATH` (optional, auto-detected)

**Example:**
```python
from newapp.src.utils.paths import get_database_path

db_path = get_database_path()
engine = create_engine(f"sqlite:///{db_path}")
```

#### 3. Cache: `../.cache_data/`
- Parquet files for historical data (MT5, YFinance)
- **Access via:** `from newapp.src.utils.paths import get_cache_dir`
- Shared to avoid duplicate downloads
- Auto-regenerates if deleted

#### 4. Project Config: `../pyproject.toml`
- Poetry dependency management
- Python 3.12+ requirement
- Shared across all modules

### Independent Resources

NewApp has its **own**:

#### 1. Configuration: `newapp/configs/config.py`
- Environment variable based settings
- Independent from legacy `configs/main.yaml`
- Web-specific configuration (ports, API keys, etc.)

#### 2. Code Architecture: `newapp/src/`
- Repository pattern (vs legacy plugin pattern)
- Async-first design (FastAPI)
- Database-driven (vs config-driven)

#### 3. Tests: `newapp/tests/`
- Separate test suite
- Focused on web API functionality
- Independent test database fixtures

### Legacy Resources (Reference Only)

Located in **`src/`** (root level, **NOT** archived):

- ⚠️ **IMPORTANT:** `src/` is **LEGACY ACTIVE CODE** still used by:
  - `train_model.py` - Model training
  - `train_drl_model.py` - DRL agent training  
  - `run_monitor.py` - CLI monitor
  - `run_monitor_gui.py` - GUI monitor

- Desktop GUI code (Tkinter - 7 modules)
- Simulation engines (point-in-time analysis)
- Strategy plugin system
- Setup filters (technical rule validation)

**Migration Status:** Legacy code will be gradually migrated to newapp in future cycles. Do NOT archive `src/` until all entry points are migrated.

## Path Resolution System

NewApp uses a **robust path resolution system** that works across different execution contexts (CLI, web server, tests, Docker).

### Resolution Order

For all shared resources (models, database, cache):

1. **Environment Variable** (highest priority)
   - `WTNPS_MODELS_PATH` - Absolute path to models directory
   - `WTNPS_SQLITE_PATH` - Absolute path to database file
   - `WTNPS_CACHE_PATH` - Absolute path to cache directory

2. **Repository Root Detection** (automatic)
   - Searches upward for `pyproject.toml`
   - Resolves to `<repo_root>/models`, `<repo_root>/wtnps_trade.db`, etc.

3. **Relative Fallback** (last resort)
   - Uses relative paths from current working directory
   - Logs warning for troubleshooting

### Usage Examples

```python
from newapp.src.utils.paths import (
    get_models_dir,
    get_database_path,
    get_cache_dir,
    get_repository_root,
)

# Models
models_dir = get_models_dir()
lstm_path = models_dir / "WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras"

# Database
db_path = get_database_path()
# Works from: CLI, web server, tests, notebooks, Docker

# Cache
cache_dir = get_cache_dir()
parquet_file = cache_dir / "MT5_WDO_M5_20220101_20251119.parquet"

# Repository root (for custom paths)
repo_root = get_repository_root()
config_file = repo_root / "configs" / "main.yaml"
```

### Environment Variable Configuration

```bash
# Optional - auto-detected if not set
export WTNPS_MODELS_PATH=/absolute/path/to/models
export WTNPS_SQLITE_PATH=/absolute/path/to/wtnps_trade.db
export WTNPS_CACHE_PATH=/absolute/path/to/.cache_data

# Database backend selection
export WTNPS_DB_BACKEND=sqlite  # or "sqlserver"

# Web server
export UVICORN_PORT=8100
```

## Entry Points

### Development Server
```powershell
cd newapp
poetry run uvicorn main:app --reload --port 8100
```

### Production
```powershell
poetry run uvicorn newapp.main:app --host 0.0.0.0 --port 8100 --workers 4
```

### Alternative Entry Points
```powershell
# Clean version (minimal UI)
poetry run uvicorn newapp.main_clean:app --reload --port 8100

# Standalone indicator calculation
poetry run python newapp/calculate_indicators.py
```

## API Endpoints

### Web Pages
- `GET /` - Home page (dashboard)
- `GET /home` - Home with sidebar navigation
- `GET /charts` - Interactive candlestick charts
- `GET /monitor` - Real-time monitor interface
- `GET /backtest` - Backtesting interface

### REST API
- `GET /api/ohlc` - OHLCV data (JSON)
  - Params: `symbol`, `timeframe`, `limit`
- `GET /api/analysis` - Technical analysis (JSON)
  - Params: `symbol`, `timeframe`, `limit`
- `GET /api/ohlc-with-analysis` - Combined data (JSON)
  - Params: `symbol`, `timeframe`, `limit`

See `INTERFACE_README.md` for detailed API documentation.

## Database Schema

See `src/database/models.py` for ORM definitions:

### Main Tables
- **`assets_rates`** - OHLCV + technical indicators (main table)
  - Columns: `symbol`, `timeframe`, `timestamp`, OHLC, volume, indicators
  - Single table strategy for performance
  - Immutable OHLC, enrichable indicators

### Future Tables (Planned)
- `ohlcv_data` - Raw price data (normalized)
- `technical_indicators` - Computed indicators (separate)
- `market_analysis` - Analysis results cache
- `backtest_run` / `backtest_trade` - Backtesting records

**Strategy:** Start with single table (`AssetsRates`), normalize later if needed.

## Design Patterns

### Repository Pattern
All database access through repositories in `src/database/repository.py`:

```python
from newapp.src.database.repository import AssetsRatesRepository
from newapp.src.database.db import get_session

with get_session() as session:
    repo = AssetsRatesRepository(session)
    rates = repo.get_ohlcv_range(symbol, timeframe, start, end)
```

### Singleton Providers
Data providers use singleton pattern with caching:

```python
from newapp import get_default_provider

provider = get_default_provider()  # Returns cached instance
data = provider.get_ohlcv(symbol, timeframe, limit)
```

**Provider types:**
- `MetaTraderProvider` - Fetches from MT5 terminal
- `CachedDataProvider` - Reads from Parquet cache
- `SyntheticDataProvider` - Generates fake data for testing
- `HybridProvider` - Cascading fallback (MT5 → Cache → Synthetic)

### Service Layer
Business logic separated from API layer:

```python
from newapp import analyze_market_context

# Pure function - no side effects
analysis = analyze_market_context(data)
```

## Migration from Legacy

### Completed (2025-11-22)
- ✅ Folder structure reorganization
- ✅ Centralized configuration
- ✅ Database integration (SQLite)
- ✅ Web UI (home, charts, monitor)
- ✅ Technical analysis engine
- ✅ Data provider abstraction

### Completed (2025-11-27)
- ✅ Robust path resolution system
- ✅ Eliminated `newapp/models/` duplication
- ✅ Archived utility scripts to `archive/scripts/`
- ✅ Architecture documentation

### In Progress
- 🔄 Backtesting engine (basic implementation done)
- 🔄 Live trading integration

### Planned (Future Cycles)
- ⏳ **Cycle 2:** Migrate strategy plugin system to newapp
- ⏳ **Cycle 3:** Migrate model training scripts
- ⏳ **Cycle 4:** Migrate DRL agents and environments
- ⏳ **Cycle 5:** Deprecate legacy CLI tools, create web equivalents
- ⏳ **Cycle 6:** Migrate Tkinter GUIs to web dashboards
- ⏳ **Cycle 7:** Archive `src/` directory (when fully migrated)

### Migration Principles
1. **No Breaking Changes** - Legacy code continues working
2. **Gradual Replacement** - Migrate features in small increments
3. **Dual Operation** - Both systems coexist during transition
4. **Shared Resources** - Models, database, cache remain shared
5. **Documentation First** - Document before changing

## Development Workflow

### Adding New Features

1. **Create module** in appropriate `src/` subdirectory
2. **Define models** in `src/database/models.py` if needed
3. **Create repository** in `src/database/repository.py` for data access
4. **Add API endpoint** in `main.py`
5. **Create template** in `templates/` for web UI
6. **Write tests** in `tests/`
7. **Update documentation** (this file, README.md)

### Testing

```powershell
# Run all tests
poetry run pytest newapp/tests/ -v

# Run specific test
poetry run pytest newapp/tests/test_provider.py::test_hybrid_provider -v

# Coverage report
poetry run pytest --cov=newapp/src --cov-report=html

# Test with different database backends
WTNPS_DB_BACKEND=sqlite poetry run pytest newapp/tests/test_database.py
```

### Database Migrations

Currently using **direct ORM changes** (no Alembic yet).

To rebuild database:
```powershell
cd newapp/src/database
poetry run python setup_database.py
```

To verify database integrity:
```powershell
poetry run python newapp/src/database/_verify_before.py
# ... make changes ...
poetry run python newapp/src/database/_verify_after.py
```

## Performance Considerations

### Trading Systems Require Low Latency

1. **Database Queries**
   - Index on `(symbol, timeframe, timestamp)` for fast lookups
   - Single table strategy avoids JOINs
   - Repository pattern allows query optimization

2. **Data Providers**
   - Cache Parquet files to avoid repeated API calls
   - Singleton pattern prevents redundant initialization
   - MT5 chunking for large date ranges (183-day max)

3. **Model Loading**
   - Lazy loading - models loaded on first use
   - Cache loaded models in memory (engine lifecycle)
   - Path resolution cached to avoid filesystem searches

4. **API Responses**
   - FastAPI async for non-blocking I/O
   - Limit query results (default 5000 candles max)
   - Consider Redis cache for frequently accessed data (future)

## Security Considerations

1. **API Keys** - Never hardcode, use environment variables
2. **Database Credentials** - Windows Authentication preferred
3. **File Paths** - Validate user inputs, prevent path traversal
4. **Model Loading** - Verify file signatures before loading
5. **Trading Execution** - Require explicit confirmation for live orders

## Documentation

### NewApp-Specific
- **README.md** - Architecture overview, quick start
- **ARCHITECTURE.md** - This file (detailed architecture)
- **MIGRATION.md** - Migration history (Nov 2025 reorganization)
- **INTERFACE_README.md** - Web UI implementation guide
- **databaseplan.prompt.md** - Database strategy

### Database
- **src/database/DATABASE_BACKEND.md** - Backend choice rationale
- **src/database/SWITCH_TO_SQLSERVER.md** - SQL Server migration guide

### Root-Level (Project-Wide)
- **README.md** - Main project documentation (Portuguese)
- **DRL_README.md** - Deep Reinforcement Learning guide
- **CONTEXT_ANALYZER_README.md** - Technical analysis module
- **IMPLEMENTATION_PLAN.md** - Overall roadmap
- **.github/copilot-instructions.md** - AI assistant context

## Support & Troubleshooting

### Common Issues

**Issue:** `FileNotFoundError: models/WDO$_prod_lstm.keras`  
**Solution:** Ensure models are trained (`poetry run python train_model.py`) or set `WTNPS_MODELS_PATH` environment variable.

**Issue:** `OperationalError: no such table: assets_rates`  
**Solution:** Initialize database (`poetry run python newapp/src/database/setup_database.py`)

**Issue:** Path resolution fails in Docker  
**Solution:** Set absolute paths via environment variables (`WTNPS_MODELS_PATH`, `WTNPS_SQLITE_PATH`)

**Issue:** Import errors from legacy `src/`  
**Solution:** Ensure you're importing from `newapp.src.*`, not `src.*`

### Getting Help

- Legacy code reference: Check `src/` directory (active legacy code)
- Archived utilities: See `archive/scripts/` for old inspection tools
- Project-wide docs: See root `README.md` and `.github/copilot-instructions.md`

---

**Last Reviewed:** 2025-11-27  
**Next Review:** After Cycle 2 completion (strategy migration)
