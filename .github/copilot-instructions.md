# Copilot Instructions for WTNPS Trade

## Project Overview
WTNPS Trade is a modular Python framework for algorithmic trading with ML/DRL strategies and MetaTrader 5 integration. The architecture is config-driven, supports both supervised learning (LSTM, RandomForest) and Deep Reinforcement Learning (DDQN), and provides dual execution engines for simulation and live trading.

## Architecture Philosophy

### 1. Config-Driven Everything
`configs/main.yaml` is the **single source of truth**. Every asset, strategy, trading rule, and execution parameter is defined here. The system dynamically loads strategies and models based on this configuration.

**Key sections:**
- `global_settings.model_directory`: Where trained models/scalers are saved
- `assets[]`: Per-asset configuration with `ticker`, `enabled`, `strategies[]`, `trading_rules`, `live_trading`, `backtesting`, `setup`
- Each strategy under `assets[].strategies[]` has: `name`, `module`, `provider`, `data`, `strategy_params`

### 2. Strategy Pattern (Plugin System)
All strategies inherit from `src/strategies/base.py` and implement:
- `define_features(data)`: Add technical indicators/features to DataFrame
- `define_target(data)`: Define prediction target (supervised learning only)
- `define_model()`: Return untrained sklearn-compatible model
- `get_feature_names()`: List of feature column names
- `save(model, prefix)` / `load(prefix)`: Model persistence

**Strategy types:**
- Supervised: `LSTMVolatilityStrategy`, `RandomForestStrategy` (use wrappers: `LSTMVolatilityWrapper`, `RFPipelineWrapper`)
- DRL: `DRLStrategy` (uses DDQN agent, loads `.keras` files directly)

### 3. Hybrid Decision Logic (AI + Technical Setup)
Trades require **two-phase validation**:
1. **AI Signal:** Model predicts "COMPRA" (buy) or "VENDA" (sell)
2. **Setup Filter:** `SetupAnalyzer.evaluate_setups()` validates against technical rules in `configs/main.yaml`'s `setup` section

**Setup rule example:**
```yaml
setup:
  - condition: 'COMPRA'  # Only applies if AI signal is COMPRA
    type: 'price_above_ma'
    ma_type: 'sma'
    period: 20
```
If no rules match the signal's condition, setup is **valid by default**.

### 4. Dual Execution Engines

#### SimulationEngine (`src/simulation/engine.py`)
For backtesting, analysis, notebooks. Key method: `run_simulation_cycle(asset_symbol, timeframe_str, target_datetime_local)`

**Workflow:**
1. Load config + strategy class + model/scaler (cached per asset)
2. Convert local time → UTC, map `timeframe_str` to MT5 constant
3. Fetch data via provider (cached in `.cache_data/`)
4. Strategy generates features → AI signal
5. SetupAnalyzer validates → Final decision (COMPRA/VENDA/HOLD)
6. Returns dict: `{ai_signal, setup_valid, final_decision, price, stop, take, indicators}`

#### LiveTrader (`src/live_trader.py`)
For real-time trading. Monitors new candles, executes same logic as simulation, sends orders to MT5.

**Execution modes (in `configs/main.yaml`):**
- `suggest`: Log trade recommendations only
- `execute`: Send actual orders using `ticker_order` (e.g., "WDOX25")

**Thread-based:** Initialization (MT5 connection, model loading) runs in background thread. GUI dashboards call `simulate_single_cycle()` for testing.

### 5. Data Providers
Abstraction in `src/data_handler/provider.py`:
- `MetaTraderProvider`: Fetches from MT5, chunks large date ranges, caches in `.cache_data/` as Parquet
- `YFinanceProvider`: Fetches from Yahoo Finance, same cache pattern
- Both normalize to Pandas DataFrame with timezone handling (`America/Sao_Paulo` → UTC)

### 6. Model Artifacts Convention
Trained models saved with naming: `<TICKER>_<STRATEGY>_prod_<type>.<ext>`

**Examples:**
- `WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras` (LSTM model)
- `WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib` (scaler)
- `WDO$_LSTMVolatilityStrategy_M5_prod_params.joblib` (metadata)
- `WDO$_DRLStrategy_prod_drl.keras` (DRL agent)

## Developer Workflows

### Setup
```powershell
poetry install
```

### Training Models

**Supervised (LSTM/RF):**
```powershell
poetry run python train_model.py
```
Reads `configs/main.yaml`, trains each enabled asset, saves models to `global_settings.model_directory`. Generates HTML reports in `reports/models/`.

**Deep RL (DDQN):**
```powershell
poetry run python train_drl_model.py
```
Prompts for ticker, loads DRLStrategy config, trains DDQN agent in `TradingEnv`, saves `.keras` model. See `DRL_README.md` for details.

### Execution

**Live trading:**
```powershell
poetry run python src/live_trader.py
```

**Simulation (single cycle):**
```powershell
poetry run python src/simulation/engine.py
```

**Backtesting:**
```powershell
poetry run python src/backtest_engine/backtest_lstm_volatility.py
```
Configured via `assets[].backtesting` in `main.yaml`. Generates JSON/TXT/HTML reports in `reports/backtest/`.

**Notebooks:** See `notebooks/simulation/` for interactive examples (e.g., `engine_simulation_single_cycle.ipynb`, `drl_inference_example.ipynb`)

### Testing
Tests live in `archive/tests/` (note: not actively maintained). Run with `pytest`:
```powershell
poetry run pytest
```

## Project-Specific Patterns

### Timeframe Handling
Valid strings: `["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]`

Mapped to MT5 constants via `_get_mt5_timeframe_from_string()` in both `engine.py` and `provider.py`. Invalid timeframes log warnings and return `None`.

### Timezone Logic
- **Input:** Local time (`America/Sao_Paulo`) for `run_simulation_cycle()`
- **Conversion:** Engine/provider converts to UTC for data fetch
- **Provider:** Returns DataFrame with timezone-aware index
- **Current:** `SimulationEngine` uses UTC as default (see `__init__` for `self.local_tz`)

### Signal Format
AI signals are **always uppercase Portuguese:**
- `"COMPRA"`: Buy signal
- `"VENDA"`: Sell signal
- `"HOLD"`: No action (post-setup filter)

### Caching
`.cache_data/` (auto-created) stores Parquet files: `<ticker>_<timeframe>_<start>_<end>.parquet`

Providers check cache before hitting API. Delete cache files to force re-download.

### Logging
All modules use `logging` with format: `%(asctime)s - %(levelname)s - [%(name)s] %(message)s`

Includes module name for traceability. File handlers added per-model in `train_model.py`.

### Code Organization
- **Active code:** `src/`, `train_model.py`, `train_drl_model.py`, `configs/`, `notebooks/`
- **Archived/deprecated:** `archive/`, `bkp/`, `*old*` files — **do not reference these for examples or implementation**

## Integration Points

### MetaTrader 5
- **Initialization:** `mt5.initialize()` must succeed before data fetch or order execution
- **Symbol mapping:** `ticker` (historical data, e.g., "WDO$") vs `ticker_order` (live orders, e.g., "WDOX25")
- **Order execution:** `LiveTrader` sends market orders with `trade_volume` from config

### TensorFlow/Keras
- LSTM strategies use Keras Sequential models wrapped in sklearn-compatible classes
- DRL uses `keras.Model` for DDQN Q-networks with experience replay

### Scikit-learn
- `MinMaxScaler` for feature normalization (saved as `.joblib`)
- `BaseEstimator`/`ClassifierMixin` for strategy wrappers

## Adding a New Strategy

1. **Create strategy file:** `src/strategies/my_strategy.py`
2. **Inherit from BaseStrategy:**
   ```python
   from src.strategies.base import BaseStrategy
   class MyStrategy(BaseStrategy):
       def define_features(self, data):
           # Add indicators to DataFrame
           return data
       def get_feature_names(self):
           return ['close', 'sma_20', 'rsi_14']
       # Implement define_target(), define_model(), save(), load()
   ```
3. **Add to config:** In `configs/main.yaml` under `assets[].strategies[]`:
   ```yaml
   - name: "MyStrategy"
     module: "my_strategy"  # Filename without .py
     provider: "MetaTrader5"
     data:
       start_date: "2022-01-01"
       end_date: "2025-11-01"
       timeframe_model: "H1"
     strategy_params:
       param1: value1
   ```
4. **Train:** `poetry run python train_model.py`
5. **Test:** Use `SimulationEngine` or notebooks

## Troubleshooting

### Missing Model Artifacts
**Error:** `FileNotFoundError: models/WDO$_prod_lstm.keras`

**Fix:** Run `poetry run python train_model.py` first. Models must exist before simulation/live trading.

### Invalid Timeframe
**Error:** `Timeframe 'H2' not in valid list`

**Fix:** Use only valid MT5 timeframes. Check `_get_mt5_timeframe_from_string` mapping.

### MT5 Connection Failed
**Error:** `mt5.initialize() returned False`

**Fix:** Ensure MT5 terminal is running, logged in, and accessible. Check firewall/permissions.

### Empty Data from Provider
**Symptom:** DataFrame has 0 rows

**Causes:**
- Invalid ticker for provider (e.g., "WDO$" not in YFinance)
- Date range outside available data
- MT5 terminal not logged in

**Debug:** Check provider logs for API errors. Verify ticker exists in data source.

### Setup Always Invalid
**Symptom:** All trades result in HOLD despite AI signals

**Causes:**
- Setup rules reference non-existent features (e.g., `sma_20` not in DataFrame)
- `condition` doesn't match AI signal case (must be uppercase: "COMPRA"/"VENDA")

**Debug:** Check `SetupAnalyzer.evaluate_setups()` logs. Ensure `define_features()` creates required columns.

### DRL Agent Not Learning
**Symptom:** Reward stuck near initial value

**Causes:**
- Exploration rate (`epsilon`) decaying too fast
- Reward function misaligned with trading goal
- Insufficient training episodes

**Debug:** Check `train_drl_model.py` console for episode rewards. Adjust `epsilon_decay` or `GAMMA` in `src/agents/drl_agent.py`.

---

For deeper architecture details, see `README.md` (Portuguese) and `DRL_README.md`. For setup rule syntax, check `src/setups/analyzer.py` implementation.
