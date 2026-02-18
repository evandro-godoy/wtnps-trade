# Migration Analysis: Root → NewApp
## WTNPS Trade Consolidation Report

**Date**: 2026-02-18  
**Analyst**: Plan Agent  
**Scope**: Evaluate duplications between root and newapp/, propose consolidation plan  
**Timeline**: 5-7 days (estimated)

---

## Executive Summary

The WTNPS Trade project currently maintains **two parallel execution stacks**:
1. **Root (`src/`)**: Legacy desktop-focused codebase with Tkinter GUI, direct MT5/YFinance providers, and CLI-based execution
2. **NewApp (`newapp/`)**: Modern web-based architecture with FastAPI, DB-first hybrid data layer, and REST API exposure

**Key Finding**: ~60% of core logic is duplicated with architectural divergence. NewApp represents the target architecture (DB-first, web-enabled, better separation of concerns), while root contains broader strategy coverage and proven live trading infrastructure.

**Recommendation**: Consolidate on newapp architecture, migrate missing components from root, and establish single source of truth for configs and strategies.

---

## 1. Duplication Analysis

### 1.1 Configuration Files

| Aspect | Root | NewApp | Status |
|--------|------|--------|--------|
| Main Config | [configs/main.yaml](configs/main.yaml) | [newapp/configs/main.yaml](newapp/configs/main.yaml) | **99% Duplicate** |
| Lines | 159 | 159 | Identical structure |
| Differences | `end_date: "2025-11-19"` | `end_date: "2025-12-31"` | Minor date drift |
| Loader | Direct YAML load in engines | [newapp/configs/config.py](newapp/configs/config.py) | Different loaders |

**Impact**: Two configs require synchronized updates, risk of divergence.

**Recommendation**: 
- **Step 2**: Unify on `newapp/configs/main.yaml` as single source of truth
- Create symlink or import wrapper from root to newapp config
- Extend newapp config loader to handle all legacy sections

---

### 1.2 Strategies Layer

| Strategy | Root (`src/strategies/`) | NewApp (`newapp/src/strategies/`) | Duplication |
|----------|--------------------------|-----------------------------------|-------------|
| `base.py` | ✅ BaseStrategy interface | ✅ BaseStrategy interface | **100%** |
| `lstm_volatility.py` | ✅ 274 lines, LSTMVolatilityStrategy | ✅ 281 lines, LSTMVolatilityStrategy | **~95%** |
| `lstm.py` | ✅ Generic LSTM | ❌ Missing | - |
| `drl_strategy.py` | ✅ DRL Agent (PPO/A2C) | ❌ Missing | - |
| `random_forest.py` | ✅ RandomForest classifier | ❌ Missing | - |
| `sentiment_lstm.py` | ✅ NLP + LSTM | ❌ Missing | - |
| `sentiment_random_forest.py` | ✅ NLP + RF | ❌ Missing | - |

**Findings**:
- `LSTMVolatilityStrategy` is nearly identical (same classes, methods, logic)
- Root has **5 additional strategies** not present in newapp
- Both use same base class contract (`define_features`, `define_target`, `define_model`, etc.)

**Recommendation**:
- **Step 4**: Centralize all strategies in `newapp/src/strategies/`
- Port missing strategies (DRL, RF, Sentiment) from root → newapp
- Create single import point for backward compatibility in root

---

### 1.3 Data Handler Layer

| Component | Root | NewApp | Architecture |
|-----------|------|--------|--------------|
| **Provider** | [src/data_handler/provider.py](src/data_handler/provider.py) | [newapp/src/data_handler/provider.py](newapp/src/data_handler/provider.py) | Different implementations |
| MT5 Support | Direct MT5 calls | MetaTraderProvider class | Abstracted |
| YFinance Support | Direct yfinance calls | ❌ Not exposed | - |
| Cache Layer | Parquet files in `.cache_data/` | CacheProvider + Parquet | Formalized |
| DB Integration | ❌ None | ✅ DB-first via [hybrid_data_loader.py](newapp/src/data_handler/hybrid_data_loader.py) | **Major Gap** |
| Hybrid Chain | ❌ None | ✅ MT5 → DB → Cache → Synthetic | **Major Gap** |
| Historical Reader | ❌ None | ✅ [historical_reader.py](newapp/src/data_handler/historical_reader.py) | **Major Gap** |

**Findings**:
- **NewApp is superior**: DB-first, thread-safe singleton, cascading providers
- Root provider is simpler but lacks DB integration and formalized abstractions
- Both use same `.cache_data/` directory (potential conflict)

**Recommendation**:
- **Step 3**: Adopt `newapp/src/data_handler/` as canonical data layer
- Migrate root consumers (simulation, live_trader, backtest) to use HybridProvider
- Deprecate root provider after validation

---

### 1.4 Training Scripts

| Aspect | Root ([train_model.py](train_model.py)) | NewApp ([newapp/train_model.py](newapp/train_model.py)) | Delta |
|--------|------------------------------------------|----------------------------------------------------------|-------|
| Data Source | `src.data_handler.provider` | `hybrid_data_loader.get_default_provider()` | Different providers |
| DB Integration | ❌ None | ✅ TrainingRunRepository, SQLAlchemy | **Major** |
| Model Registry | File-based (models/) | DB + file-based | **Major** |
| Reporting | HTML only | HTML + JSON + DB records | Enhanced |
| Config Loader | Direct YAML | [newapp/configs/config.py](newapp/configs/config.py) | Abstracted |

**Findings**:
- Root version is production-proven but DB-unaware
- NewApp version tracks training runs in DB, enables versioning and audit trail
- Both write to same `models/` directory (shared resource)

**Recommendation**:
- **Step 4**: Consolidate on newapp training script
- Add backward compat wrapper in root that delegates to newapp
- Migrate training history to DB

---

### 1.5 Execution Engines

| Engine | Root | NewApp | Status |
|--------|------|--------|--------|
| **Live Trading** | [src/live_trader.py](src/live_trader.py) | [newapp/src/live/monitor_engine.py](newapp/src/live/monitor_engine.py) | Parallel |
| **Simulation** | [src/simulation/engine.py](src/simulation/engine.py) | ❌ Missing | **Gap in newapp** |
| **Backtest** | [src/backtest_engine/](src/backtest_engine/) | [newapp/src/backtest/stream_engine.py](newapp/src/backtest/stream_engine.py) | Different implementations |
| **GUI** | Tkinter ([run_monitor_gui.py](run_monitor_gui.py)) | FastAPI + Bokeh ([newapp/main.py](newapp/main.py)) | Platform shift |

**Findings**:
- Root has proven live trader with MT5 order execution
- NewApp has WebSocket-based monitor but lacks point-in-time simulation engine
- Backtest engines differ significantly in approach

**Recommendation**:
- **Step 5**: Port simulation engine to newapp while preserving live_trader logic
- Integrate live_trader as API endpoint in FastAPI
- Maintain GUI options (web + desktop) during transition

---

### 1.6 Database Layer

| Component | Root | NewApp | Gap |
|-----------|------|--------|-----|
| **ORM Models** | ❌ None | ✅ [newapp/src/database/models.py](newapp/src/database/models.py) | **Critical** |
| **Repositories** | ❌ None | ✅ [newapp/src/database/repository.py](newapp/src/database/repository.py) | **Critical** |
| **Session Mgmt** | ❌ None | ✅ [newapp/src/database/db.py](newapp/src/database/db.py) | **Critical** |
| **Ingestion** | ❌ None | ✅ [newapp/src/database/ingest_historical.py](newapp/src/database/ingest_historical.py) | **Critical** |
| **SQLite Local** | ❌ None | ✅ `wtnps_trade.db` | Available |
| **SQL Server** | ❌ None | ✅ Optional via env vars | Available |

**Findings**:
- **NewApp has full DB infrastructure**, root has none
- This is the largest architectural gap
- DB enables:
  - Training run versioning
  - Historical data caching
  - Audit trails
  - Multi-user support

**Recommendation**:
- **Step 3**: Make DB layer mandatory for all flows
- Backfill historical data from cache to DB
- Integrate DB repositories into legacy engines

---

### 1.7 Dependencies ([pyproject.toml](pyproject.toml))

| Category | Root Usage | NewApp Usage | Status |
|----------|------------|--------------|--------|
| **Poetry** | Single project root | Same lockfile | ✅ Unified |
| **FastAPI** | ❌ Not used | ✅ Core framework | NewApp only |
| **Tkinter** | ✅ Desktop GUI | ❌ Not used | Root only |
| **TensorFlow** | ✅ DRL + LSTM | ✅ LSTM | Shared |
| **SQLAlchemy** | ❌ Not used | ✅ ORM | NewApp only |
| **Bokeh** | ✅ GUI charts | ✅ Web charts | Shared |
| **MetaTrader5** | ✅ Required | ✅ Optional (provider) | Shared |

**Findings**:
- Single pyproject.toml covers both, but feature usage differs
- No dependency conflicts detected
- Optional dependencies opportunity: group by execution mode

**Recommendation**:
- **Step 1**: Define dependency groups in pyproject.toml:
  - `[tool.poetry.extras]` for web-only (fastapi, sqlalchemy)
  - `[tool.poetry.extras]` for desktop-only (tkinter)
  - Keep core ML deps (tensorflow, sklearn) as base

---

## 2. Gap Analysis

### Critical Gaps in NewApp
1. ❌ **Simulation Engine**: Root has point-in-time simulator, newapp lacks it
2. ❌ **DRL Strategies**: Root has DRL (PPO, A2C agents), newapp missing
3. ❌ **Sentiment Strategies**: Root has NLP-based strategies, newapp missing
4. ❌ **Desktop GUI**: Root has proven Tkinter GUI with threading, newapp is web-only

### Critical Gaps in Root
1. ❌ **Database Layer**: No ORM, repos, or persistence beyond files
2. ❌ **Web API**: No REST endpoints, no remote access
3. ❌ **Hybrid Data Loader**: No DB-first cascading provider
4. ❌ **Training Versioning**: No ML experiment tracking

---

## 3. Migration Plan (6 Steps)

### Step 1: Padronizar Ambiente e Dependências
**Duration**: 1 day  
**Complexity**: Low

**Tasks**:
- [x] Verify Python 3.12+ and Poetry installed
- [ ] Run `poetry check` and `poetry install` in root
- [ ] Define dependency groups in pyproject.toml:
  ```toml
  [tool.poetry.extras]
  web = ["fastapi", "uvicorn", "sqlalchemy", "pyodbc"]
  desktop = ["tkcalendar"]
  drl = ["tensorflow>=2.20.0"]
  ```
- [ ] Document MT5 requirements (Windows, terminal running, login)
- [ ] Test DB connections (SQLite local + optional SQL Server)
- [ ] Align cache/models/reports paths between root and newapp
- [ ] Create `.env.example` with all required environment variables

**Deliverables**:
- Updated [pyproject.toml](pyproject.toml) with dependency groups
- Environment setup documentation
- Validated dependencies across both stacks

**Risks**:
- MT5 terminal connection failures → Mitigate with provider fallback to Cache/Synthetic
- SQL Server optional dependency issues → Keep SQLite as default

---

### Step 2: Unificar Configuração
**Duration**: 1 day  
**Complexity**: Low

**Tasks**:
- [ ] Expand [newapp/configs/main.yaml](newapp/configs/main.yaml) with all sections from [configs/main.yaml](configs/main.yaml)
- [ ] Add sections for:
  - Simulation parameters (point-in-time mode)
  - GUI settings (monitor refresh rate, display options)
  - DRL training hyperparameters
- [ ] Update [newapp/configs/config.py](newapp/configs/config.py) to handle all legacy config keys
- [ ] Create config migration utility to validate schema
- [ ] Update root engines to import config from newapp:
  ```python
  # src/simulation/engine.py
  from newapp.configs.config import get_config
  ```
- [ ] Add config versioning and validation (JSON schema or Pydantic)
- [ ] Document config structure in [newapp/README.md](newapp/README.md)

**Deliverables**:
- Single unified config in newapp/configs/
- Config loader supporting all legacy flows
- Validation schema and tests

**Risks**:
- Breaking changes to existing deployments → Mitigate with config version field and backward compat layer

---

### Step 3: Consolidar Data Layer
**Duration**: 1.5 days  
**Complexity**: Medium-High

**Tasks**:
- [ ] Make [newapp/src/data_handler/hybrid_data_loader.py](newapp/src/data_handler/hybrid_data_loader.py) the default provider
- [ ] Migrate root consumers:
  - [ ] [src/simulation/engine.py](src/simulation/engine.py) → use HybridProvider
  - [ ] [src/live_trader.py](src/live_trader.py) → use HybridProvider
  - [ ] [src/backtest_engine/](src/backtest_engine/) → use HybridProvider
  - [ ] [train_model.py](train_model.py) → use HybridProvider
- [ ] Establish provider priority chain: `MT5 → DB → Cache → Synthetic`
- [ ] Implement DB backfill:
  - [ ] Scan `.cache_data/` for existing Parquet files
  - [ ] Ingest to DB via [newapp/src/database/ingest_historical.py](newapp/src/database/ingest_historical.py)
  - [ ] Validate DB vs Cache consistency
- [ ] Add YFinance support to newapp provider (currently missing)
- [ ] Create provider adapter in root for backward compatibility:
  ```python
  # src/data_handler/provider.py (legacy wrapper)
  from newapp.src.data_handler.hybrid_data_loader import get_default_provider
  get_provider = get_default_provider  # Alias
  ```
- [ ] Update all imports across root to use new provider
- [ ] Test with MT5 offline (should fallback gracefully)

**Deliverables**:
- All execution flows using HybridProvider
- DB populated with historical data
- Deprecated root provider marked for removal

**Risks**:
- MT5 threading issues in live trader → Carefully test thread safety
- DB write performance bottlenecks → Add async writes and bulk inserts
- Cache vs DB data consistency → Implement checksums and validation

---

### Step 4: Centralizar Estratégias e Modelos
**Duration**: 1.5 days  
**Complexity**: Medium

**Tasks**:
- [ ] Port missing strategies to newapp:
  - [ ] Copy [src/strategies/drl_strategy.py](src/strategies/drl_strategy.py) → [newapp/src/strategies/drl_strategy.py](newapp/src/strategies/drl_strategy.py)
  - [ ] Copy [src/strategies/random_forest.py](src/strategies/random_forest.py) → newapp
  - [ ] Copy [src/strategies/sentiment_lstm.py](src/strategies/sentiment_lstm.py) → newapp
  - [ ] Copy [src/strategies/sentiment_random_forest.py](src/strategies/sentiment_random_forest.py) → newapp
- [ ] Consolidate `LSTMVolatilityStrategy`:
  - [ ] Compare [src/strategies/lstm_volatility.py](src/strategies/lstm_volatility.py) vs [newapp/src/strategies/lstm_volatility.py](newapp/src/strategies/lstm_volatility.py)
  - [ ] Merge differences (if any) into newapp version
  - [ ] Delete root version
- [ ] Update root strategy imports to re-export from newapp:
  ```python
  # src/strategies/lstm_volatility.py
  from newapp.src.strategies.lstm_volatility import LSTMVolatilityStrategy
  __all__ = ['LSTMVolatilityStrategy']
  ```
- [ ] Consolidate training scripts:
  - [ ] Merge [train_model.py](train_model.py) logic into [newapp/train_model.py](newapp/train_model.py)
  - [ ] Add CLI wrapper in root: `poetry run python -m newapp.train_model`
- [ ] Align model artifact paths:
  - [ ] Ensure both use `global_settings.model_directory` from unified config
  - [ ] Validate naming convention: `<TICKER>_<STRATEGY>_<TIMEFRAME>_prod_<type>.*`
- [ ] Update [newapp/src/ml/predictor.py](newapp/src/ml/predictor.py) to load all strategy types
- [ ] Add model registry in DB:
  - [ ] TrainingRun table tracks model metadata
  - [ ] Link models to assets and strategies

**Deliverables**:
- All strategies in `newapp/src/strategies/`
- Single training script with DB versioning
- Model registry in database
- Root imports aliased to newapp

**Risks**:
- DRL environment compatibility issues → Test thoroughly with PPO/A2C agents
- Model file path conflicts → Use DB as source of truth for active model
- Breaking changes to model loading → Add version detection and migration

---

### Step 5: Migrar Execução
**Duration**: 2 days  
**Complexity**: High

**Tasks**:
- [ ] Port simulation engine to newapp:
  - [ ] Create [newapp/src/simulation/engine.py](newapp/src/simulation/engine.py)
  - [ ] Copy logic from [src/simulation/engine.py](src/simulation/engine.py)
  - [ ] Adapt to use HybridProvider and DB repositories
  - [ ] Preserve point-in-time replay functionality
- [ ] Integrate backtest engines:
  - [ ] Compare [src/backtest_engine/](src/backtest_engine/) vs [newapp/src/backtest/](newapp/src/backtest/)
  - [ ] Merge capabilities into newapp unified backtest
  - [ ] Add streaming backtest API endpoint
- [ ] Consolidate live trader:
  - [ ] Move [src/live_trader.py](src/live_trader.py) → [newapp/src/live/live_trader.py](newapp/src/live/live_trader.py)
  - [ ] Integrate with [newapp/src/live/monitor_engine.py](newapp/src/live/monitor_engine.py)
  - [ ] Add FastAPI endpoints:
    - `POST /api/live/start` - Start live trading session
    - `GET /api/live/status` - Get current positions/orders
    - `POST /api/live/stop` - Stop live trading
- [ ] Migrate GUIs:
  - [ ] Keep Tkinter GUI ([run_monitor_gui.py](run_monitor_gui.py)) as standalone desktop option
  - [ ] Enhance web UI in [newapp/templates/](newapp/templates/) with live trading controls
  - [ ] Add WebSocket real-time updates for positions
- [ ] Update execution entry points:
  - [ ] `poetry run python -m newapp.main` (web server)
  - [ ] `poetry run python run_monitor_gui.py` (desktop)
  - [ ] `poetry run python -m newapp.src.simulation.engine` (simulation)
  - [ ] `poetry run python -m newapp.src.live.live_trader` (live CLI)

**Deliverables**:
- Simulation engine in newapp
- Unified backtest API
- Live trading integrated with web interface
- Dual GUI support (web + desktop)

**Risks**:
- MT5 order execution bugs during migration → Extensive testing in demo account
- WebSocket threading conflicts → Use async/await properly in FastAPI
- Legacy GUI users resistance → Maintain desktop option indefinitely

---

### Step 6: Revisão de Duplicidades e Limpeza
**Duration**: 1 day  
**Complexity**: Low-Medium

**Tasks**:
- [ ] Code review: compare all root vs newapp paired modules
- [ ] Identify remaining duplications:
  ```bash
  # Use diff tool
  diff -r src/ newapp/src/ > duplication_report.txt
  ```
- [ ] Deprecate legacy modules:
  - [ ] Add deprecation warnings to root modules
  - [ ] Update all root imports to use newapp equivalents
- [ ] Remove obsolete files:
  - [ ] Delete [src/data_handler/provider.py](src/data_handler/provider.py) (replaced by hybrid loader)
  - [ ] Move [archive/](archive/) legacy code to separate repo or delete
  - [ ] Clean [bkp/](bkp/) and `*old*` files
- [ ] Update tests:
  - [ ] Port tests from [tests/](tests/) to [newapp/tests/](newapp/tests/)
  - [ ] Ensure coverage for all migrated flows
  - [ ] Run full test suite: `poetry run pytest newapp/tests/ -v`
- [ ] Update documentation:
  - [ ] Rewrite [README.md](README.md) to reflect newapp-first architecture
  - [ ] Update all phase documents (FASE_*.md) with new structure
  - [ ] Add migration guide for users/developers
- [ ] Final validation:
  - [ ] Train model end-to-end: `poetry run python -m newapp.train_model`
  - [ ] Run backtest: `poetry run python -m newapp.src.backtest.stream_engine`
  - [ ] Run simulation: `poetry run python -m newapp.src.simulation.engine`
  - [ ] Start web server: `poetry run python newapp/main.py`
  - [ ] Test desktop GUI: `poetry run python run_monitor_gui.py`

**Deliverables**:
- Deduplicated codebase
- Archived legacy code
- Full test coverage in newapp
- Updated documentation

**Risks**:
- Accidental deletion of production code → Use git branches and thorough review
- Broken imports after cleanup → Automated import checker in CI
- Documentation lag → Update docs as part of each step, not just Step 6

---

## 4. Timeline Estimate

| Step | Duration | Dependencies | Risk Level |
|------|----------|--------------|------------|
| 1. Padronizar Ambiente | 1 day | None | Low |
| 2. Unificar Configs | 1 day | Step 1 | Low |
| 3. Consolidar Data Layer | 1.5 days | Step 2 | High |
| 4. Centralizar Estratégias | 1.5 days | Step 3 | Medium |
| 5. Migrar Execução | 2 days | Steps 3, 4 | High |
| 6. Revisão e Limpeza | 1 day | Step 5 | Medium |
| **Total** | **8 days** | Sequential | **Medium-High** |

**Critical Path**: Steps 3 → 4 → 5 (data layer → strategies → execution)

**Recommended Timeline**: **5-7 business days** with 1 developer, assuming:
- No major bugs discovered during migration
- DB infrastructure already tested
- MT5 environment stable

**Accelerators**:
- Parallelize Steps 1-2 (can be done simultaneously)
- Use automated testing to catch regressions early
- Maintain rollback branches for each step

---

## 5. Risks and Mitigations

### High-Risk Areas

#### 5.1 MT5 Connection Stability
**Risk**: MT5 terminal crashes or connection drops during live migration  
**Impact**: Trading interruption, data loss  
**Mitigation**:
- Test with demo account first (WDOX25 demo)
- Implement robust reconnection logic in provider
- Maintain file-based cache as fallback
- Monitor MT5 health via API heartbeat

#### 5.2 Database Migration Failures
**Risk**: Historical data ingestion errors, schema conflicts  
**Impact**: Incomplete data in DB, backtest failures  
**Mitigation**:
- Validate all Parquet files before ingestion
- Use transactions for bulk inserts (rollback on error)
- Keep original cache files intact
- Add data integrity checks (row counts, date ranges)

#### 5.3 Model Compatibility
**Risk**: Models trained in root don't load in newapp  
**Impact**: Need to retrain all models  
**Mitigation**:
- Test model loading early in Step 4
- Use same TensorFlow/Keras versions
- Add model version metadata
- Implement model migration tool if needed

#### 5.4 Live Trading Execution Bugs
**Risk**: Order placement errors after migration  
**Impact**: Financial loss, incorrect positions  
**Mitigation**:
- Extensive testing in `execution_mode: "suggest"` mode
- Manual review of suggested orders before enabling `"execute"`
- Start with minimal trade_volume (1 contract)
- Add order validation and sanity checks

#### 5.5 Config Breaking Changes
**Risk**: Unified config breaks existing deployments  
**Impact**: System downtime  
**Mitigation**:
- Add config version field
- Implement backward compatibility layer
- Validate config on startup with clear error messages
- Document migration path in CHANGELOG

---

### Medium-Risk Areas

#### 5.6 Import Path Changes
**Risk**: Breaking imports after restructuring  
**Impact**: Runtime errors, failed imports  
**Mitigation**:
- Use aliasing wrappers in root modules
- Add `__all__` exports for clarity
- Run static analysis (`mypy`, `ruff`) before each commit

#### 5.7 Threading/Async Conflicts
**Risk**: Race conditions when mixing Tkinter, FastAPI, and MT5 threads  
**Impact**: Deadlocks, UI freezes  
**Mitigation**:
- Use proper thread synchronization (locks, queues)
- Avoid shared state between GUI and API
- Test concurrent scenarios (GUI + web server)

#### 5.8 Dependency Conflicts
**Risk**: Poetry lock issues with new dependency groups  
**Impact**: Installation failures  
**Mitigation**:
- Run `poetry lock --no-update` after changes
- Test install in clean environment
- Pin critical dependencies (TensorFlow, MT5)

---

## 6. Success Criteria

Migration is complete when:
- [ ] All execution flows (train, backtest, simulate, live) run from newapp
- [ ] DB contains all historical data with indicators
- [ ] All 7 strategies (LSTM, DRL, RF, Sentiment) available in newapp
- [ ] Web UI and desktop GUI both functional
- [ ] No duplicated code between root and newapp (except deprecation wrappers)
- [ ] Test suite passes: `poetry run pytest newapp/tests/ -v --cov=newapp`
- [ ] Documentation updated: README, architecture diagrams, user guides
- [ ] Live trading validated in demo account for 1 week
- [ ] Root modules marked as deprecated with clear migration path

---

## 7. Post-Migration Governance

### Code Organization
```
wtnps-trade/
├── newapp/                    # Primary codebase
│   ├── src/                   # All core logic
│   ├── configs/               # Single source of truth
│   └── tests/                 # Comprehensive test suite
├── src/                       # Deprecated (aliased to newapp)
├── configs/                   # Deprecated (symlinked to newapp)
├── models/                    # Shared model artifacts
├── .cache_data/               # Shared cache (sync to DB)
└── pyproject.toml             # Unified dependencies
```

### Development Rules
1. **New features**: Implement in newapp only
2. **Bug fixes**: Fix in newapp, propagate to root if still in use
3. **Config changes**: Update newapp/configs/main.yaml only
4. **Testing**: All new code requires tests in newapp/tests/
5. **Documentation**: Keep [newapp/README.md](newapp/README.md) up-to-date

### Deprecation Timeline
- **Day 0-30**: Both stacks operational, newapp preferred
- **Day 30-60**: Root modules emit deprecation warnings
- **Day 60+**: Root modules disabled (import fails with migration guide)
- **Day 90**: Root modules archived to separate branch

---

## 8. Main Duplications Summary

### Critical Duplications (Require Immediate Action)
1. **configs/main.yaml ↔ newapp/configs/main.yaml**: 99% identical, 159 lines each
2. **src/strategies/lstm_volatility.py ↔ newapp/src/strategies/lstm_volatility.py**: ~95% identical, core trading strategy
3. **train_model.py ↔ newapp/train_model.py**: Similar structure, different data sources

### Architectural Duplications (Different Implementations)
4. **src/data_handler/provider.py ↔ newapp/src/data_handler/**: Legacy vs modern provider
5. **src/backtest_engine/ ↔ newapp/src/backtest/**: CLI vs web-based backtest

### Functional Gaps (Not Duplications)
6. **Root-only**: DRL strategies, sentiment strategies, simulation engine, Tkinter GUI
7. **NewApp-only**: Database layer, FastAPI, hybrid loader, REST API

---

## 9. Estimated Complexity

**Overall Complexity**: **MEDIUM-HIGH**

**Breakdown**:
- **Low Complexity** (30%):
  - Environment setup (Step 1)
  - Config unification (Step 2)
  - Code cleanup (Step 6)

- **Medium Complexity** (40%):
  - Strategy consolidation (Step 4)
  - Documentation updates

- **High Complexity** (30%):
  - Data layer migration (Step 3) - requires DB backfill, provider refactoring
  - Execution engine migration (Step 5) - touches live trading, requires extensive testing

**Why Medium-High**:
- ✅ Clear separation between root and newapp (minimal entanglement)
- ✅ NewApp already has target architecture in place
- ✅ Single dependency file (no split environments)
- ⚠️ DB migration requires careful validation
- ⚠️ Live trading changes carry financial risk
- ⚠️ Multiple execution flows to migrate (train, backtest, simulate, live)

---

## 10. Recommended Next Steps

1. **Immediate** (Today):
   - Get approval on migration plan
   - Create feature branch: `git checkout -b migration/root-to-newapp`
   - Backup current production models and configs

2. **Week 1** (Days 1-3):
   - Execute Steps 1-2 (environment + config)
   - Begin Step 3 (data layer migration)

3. **Week 2** (Days 4-6):
   - Complete Step 3 (data layer)
   - Execute Step 4 (strategies)
   - Begin Step 5 (execution engines)

4. **Week 2** (Days 7-8):
   - Complete Step 5 (execution engines)
   - Execute Step 6 (cleanup)

5. **Week 3** (Validation):
   - Run full test suite
   - Demo account validation
   - Documentation review
   - Production deployment planning

---

## Appendix A: File-by-File Comparison

### Configs
| Root Path | NewApp Path | Similarity | Action |
|-----------|-------------|------------|--------|
| configs/main.yaml | newapp/configs/main.yaml | 99% | Merge → newapp |
| configs/placeholder.txt | - | - | Delete |
| - | newapp/configs/config.py | - | Keep (loader) |

### Strategies
| Root Path | NewApp Path | Similarity | Action |
|-----------|-------------|------------|--------|
| src/strategies/base.py | newapp/src/strategies/base.py | 100% | Keep newapp |
| src/strategies/lstm_volatility.py | newapp/src/strategies/lstm_volatility.py | 95% | Merge → newapp |
| src/strategies/drl_strategy.py | - | - | Port → newapp |
| src/strategies/lstm.py | - | - | Port → newapp |
| src/strategies/random_forest.py | - | - | Port → newapp |
| src/strategies/sentiment_lstm.py | - | - | Port → newapp |
| src/strategies/sentiment_random_forest.py | - | - | Port → newapp |

### Data Handlers
| Root Path | NewApp Path | Similarity | Action |
|-----------|-------------|------------|--------|
| src/data_handler/provider.py | newapp/src/data_handler/provider.py | 30% | Deprecate root |
| - | newapp/src/data_handler/hybrid_data_loader.py | - | Keep (target) |
| - | newapp/src/data_handler/historical_reader.py | - | Keep |

### Training
| Root Path | NewApp Path | Similarity | Action |
|-----------|-------------|------------|--------|
| train_model.py | newapp/train_model.py | 60% | Merge → newapp |
| train_drl_model.py | - | - | Port → newapp |

### Execution
| Root Path | NewApp Path | Similarity | Action |
|-----------|-------------|------------|--------|
| src/live_trader.py | newapp/src/live/monitor_engine.py | 40% | Merge → newapp |
| src/simulation/engine.py | - | - | Port → newapp |
| src/backtest_engine/ | newapp/src/backtest/ | 30% | Merge → newapp |

---

## Appendix B: Environment Variables Reference

**Current**:
- `WTNPS_HOST` (newapp only)
- `WTNPS_PORT` (newapp only)

**Proposed After Migration**:
```bash
# Data Provider
MT5_PATH="C:/Program Files/MetaTrader 5/terminal64.exe"
MT5_LOGIN=12345678
MT5_PASSWORD=secret
MT5_SERVER="Server-Demo"

# Database
DATABASE_URL="sqlite:///wtnps_trade.db"  # or "mssql+pyodbc://..."
ENABLE_DB_CACHE=true

# Web Server
WTNPS_HOST=0.0.0.0
WTNPS_PORT=8000

# Paths
MODEL_DIR="c:/projects/wtnps-trade/models"
CACHE_DIR="c:/projects/wtnps-trade/.cache_data"
REPORTS_DIR="c:/projects/reports"

# Execution
EXECUTION_MODE=suggest  # or "execute"
LOG_LEVEL=INFO
```

---

**End of Report**

---

## Quick Reference

- **Main Duplications**: Configs (99%), LSTMVolatilityStrategy (95%), training scripts (60%)
- **Complexity**: Medium-High (DB migration + live trading risks)
- **Timeline**: 5-7 days (8 days with buffer)
- **Critical Path**: Data Layer (Step 3) → Strategies (Step 4) → Execution (Step 5)
- **Highest Risk**: Live trading migration (Step 5)
- **Biggest Gap**: NewApp missing simulation engine, root missing DB layer

