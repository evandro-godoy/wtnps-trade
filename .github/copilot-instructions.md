# Copilot Instructions for WTNPS Trade

## Project Overview
WTNPS Trade is a modular Python framework for algorithmic trading with ML/DRL strategies and MetaTrader 5 integration. The architecture is config-driven, supports both supervised learning (LSTM, RandomForest) and Deep Reinforcement Learning (DDQN), and provides dual execution engines for simulation and live trading.

**Tech Stack:** Python 3.12+, Poetry, MetaTrader5, TensorFlow/Keras, scikit-learn, pandas/numpy
**Key Directories:** `src/` (active code), `configs/` (YAML config), `models/` (trained artifacts), `notebooks/` (analysis), `archive/` (deprecated - **ignore for examples**)

## Architecture Philosophy

### 1. Config-Driven Everything
`configs/main.yaml` is the **single source of truth**. Every asset, strategy, trading rule, and execution parameter is defined here. The system dynamically loads strategies and models based on this configuration.

**Key sections:**
- `global_settings.model_directory`: Where trained models/scalers are saved (fallback default: 'models')
- `assets[]`: Per-asset configuration with `ticker`, `enabled`, `strategies[]`, `trading_rules`, `live_trading`, `backtesting`, `setup`
- Each strategy under `assets[].strategies[]` has: `name`, `module`, `provider`, `data`, `strategy_params`
- Note: Code may reference `models_directory` due to legacy naming; use `model_directory` in YAML configs

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

### Environment Setup
```powershell
poetry install
```
**First-time setup:** Ensure MetaTrader 5 terminal is installed and running before data operations.

### Training Models

**Supervised Learning (LSTM/RandomForest):**
```powershell
poetry run python train_model.py
```
- Reads `configs/main.yaml`, processes each enabled asset
- Downloads data via `MetaTraderProvider` or `YFinanceProvider` (auto-cached in `.cache_data/`)
- Saves models to `global_settings.model_directory` with naming: `<TICKER>_<STRATEGY>_<TIMEFRAME>_prod_<type>.<ext>`
- Generates HTML/JSON reports in `reports/models/` with metrics, confusion matrices, feature stats

**Deep Reinforcement Learning (DDQN):**
```powershell
poetry run python train_drl_model.py
```
- Interactive prompt for ticker selection
- Trains DDQN agent in `TradingEnv` (see `DRL_README.md`)
- Saves `.keras` model: `<TICKER>_DRLStrategy_prod_drl.keras`
- Outputs episode rewards to console for monitoring convergence

### Execution Modes

**Live Trading (Real-time):**
```powershell
poetry run python src/live_trader.py
```
- Monitors new candles, executes AI+Setup decision logic
- Modes (in `configs/main.yaml`): `suggest` (logs only) or `execute` (sends MT5 orders)
- Uses `ticker_order` for live trades (e.g., "WDOX25"), `ticker` for data (e.g., "WDO$")
- Thread-based: Init in background, main loop monitors candle closes

**GUI Dashboards:**
```powershell
# Monitor with real-time alerts (live or replay mode)
poetry run python run_monitor_gui.py --mode live
poetry run python run_monitor_gui.py --mode replay --ticker WDO$ --date 2025-11-20 --speed 2.0

# LiveTrader testing dashboard
poetry run python src/gui/live_trader_dashboard.py

# Simulation engine testing
poetry run python src/gui/dashboard.py
```

**Simulation (Point-in-time analysis):**
```powershell
poetry run python src/simulation/engine.py
```
- Entry point: `SimulationEngine.run_simulation_cycle(asset_symbol, timeframe_str, target_datetime_local)`
- Returns dict: `{ai_signal, setup_valid, final_decision, price, stop, take, indicators}`
- Used by notebooks (see `notebooks/simulation/`) and dashboards

**Backtesting:**
```powershell
poetry run python src/backtest_engine/backtest_lstm_volatility.py
```
- Configured via `assets[].backtesting` in `main.yaml`
- Simulates trades with Stop Loss/Take Profit tracking
- Generates JSON/TXT/HTML reports in `reports/backtest/`

### Testing
Tests in `archive/tests/` (not actively maintained). Run with:
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
`.cache_data/` (auto-created) stores Parquet files: `<provider>_<ticker>_<timeframe>_<start>_<end>.parquet`

**Examples:**
- `MT5_WDO_M5_20220101_20251119.parquet` (MetaTrader5 data)
- `YF_AAPL_1d_2022-01-01_2025-11-01.parquet` (Yahoo Finance)

Providers check cache before API calls. Delete cache files to force fresh download. Chunking handles large date ranges (183-day chunks for MT5).

### Logging
All modules use `logging` with format: `%(asctime)s - %(levelname)s - [%(name)s] %(message)s`

Includes module name for traceability. File handlers added per-model in `train_model.py`. Log levels:
- `INFO`: Normal operations, model training progress
- `WARNING`: Invalid timeframes, missing features (logged once)
- `ERROR`: Provider failures, model loading errors
- `CRITICAL`: Config not found, MT5 initialization failure

### GUI Architecture
All dashboards built with **tkinter**, follow thread separation pattern:
- **Main thread:** GUI rendering (responsive)
- **Background thread:** Engine/LiveTrader operations (blocking I/O)
- **Communication:** `queue.Queue` for thread-safe data passing

**Key files:**
- `src/gui/monitor_ui.py`: Real-time monitor with live/replay modes
- `src/gui/live_trader_dashboard.py`: LiveTrader testing interface
- `src/gui/dashboard.py`: SimulationEngine testing
- `src/gui/chart_widget.py`: Reusable candlestick chart component (mplfinance)

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
   import pandas as pd
   
   class MyStrategy(BaseStrategy):
       def define_features(self, data: pd.DataFrame) -> pd.DataFrame:
           """Add technical indicators to DataFrame."""
           data['sma_20'] = data['close'].rolling(window=20).mean()
           data['rsi_14'] = self._calculate_rsi(data['close'], 14)
           return data.dropna()
       
       def define_target(self, data: pd.DataFrame) -> pd.Series:
           """Define binary classification target."""
           # Example: predict if next close > current close
           return (data['close'].shift(-1) > data['close']).astype(int)
       
       def get_feature_names(self) -> list[str]:
           return ['close', 'sma_20', 'rsi_14', 'volume']
       
       def define_model(self):
           """Return sklearn-compatible model wrapper."""
           from sklearn.ensemble import RandomForestClassifier
           return RandomForestClassifier(n_estimators=100)
       
       def save(self, model, model_path_prefix: str):
           """Delegate to model wrapper's save method."""
           model.save(model_path_prefix)
       
       @classmethod
       def load(cls, model_path_prefix: str):
           """Load trained model from disk."""
           import joblib
           return joblib.load(f"{model_path_prefix}_model.joblib")
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
       lookback: 50
       feature_threshold: 0.7
   ```

4. **Train:** `poetry run python train_model.py` (processes all enabled assets)
5. **Test:** Use `SimulationEngine` in notebook or `run_monitor_gui.py` for live validation

## Common Code Patterns & Developer Tips

### Strategy Loading in Engines
Both `SimulationEngine` and `LiveTrader` use identical patterns to load strategies:
1. Get asset config from YAML via `config['assets'][i]`
2. Extract strategy name and module: `strategy_config['name']`, `strategy_config['module']`
3. Dynamically import: `importlib.import_module(f"src.strategies.{module_name}")`
4. Instantiate strategy class: `strategy_class = getattr(module, class_name); strategy = strategy_class()`
5. Load trained model: `strategy_class.load(model_path_prefix)` (classmethod)

**Reference:** See `_load_asset_resources()` in [src/simulation/engine.py](src/simulation/engine.py#L100-L150) and `_load_asset_resources()` in [src/live_trader.py](src/live_trader.py#L100-L160)

### Data Pipeline for Feature Engineering
1. Raw data (OHLCV) → `define_features()` adds technical indicators → DataFrame with all columns
2. Strategy.get_feature_names() specifies which columns to use for ML model input
3. Features are normalized via `MinMaxScaler` (saved as `.joblib` file)
4. For supervised learning: `define_target()` creates binary classification target (1 or 0)
5. Sequences are created for LSTM: `create_sequences(X, y, lookback=108)` yields 3D arrays `(samples, timesteps, features)`

**Reference:** [src/strategies/lstm_volatility.py](src/strategies/lstm_volatility.py#L25-L80) - see `create_sequences()` function

### Model Artifact Loading Pattern
**Problem:** Code tries `models_directory` but config has `model_directory`
**Solution:** Use `.get('model_directory', 'models')` with fallback. Both `train_model.py`, `SimulationEngine`, and `LiveTrader` apply this pattern.

Naming format: `{TICKER}_{STRATEGY_CLASS_NAME}_{TIMEFRAME}_prod_` prefix
- LSTM: suffix `_lstm.keras` (Keras native format)
- Scaler: suffix `_scaler.joblib` (scikit-learn format)
- Params: suffix `_params.joblib` (metadata dictionary)

### Thread Safety in LiveTrader
- Initialization runs in background thread (`_initialize_resources()`)
- Main thread waits for `is_trader_initialized` flag before executing trades
- Lock (`_lock`) protects shared state: `asset_resources`, `last_candle_time`, `current_state`, `mt5_provider`
- GUI updates use `callback()` function passed via constructor

**Key methods:**
- `_start_initialization_thread()`: Launches daemon thread
- `_initialize_mt5()`: Wrapped in `with self._lock:`
- `_load_asset_resources()`: Wrapped in `with self._lock:`

### SetupAnalyzer Logic
- Evaluates setup rules only if a matching `condition` exists in config
- **Default behavior:** If no rule matches the AI signal's condition, setup is **VALID** (not INVALID)
- Rules check DataFrame columns created by `define_features()` - missing columns log warnings once
- Returns dict: `{valid: bool, setup_used: str or None, details: dict}`

**Reference:** [src/setups/analyzer.py](src/setups/analyzer.py)

### Testing a New Feature
Use the **SimulationEngine** entry point for isolated testing:
```python
from src.simulation.engine import SimulationEngine
engine = SimulationEngine('configs/main.yaml')
result = engine.run_simulation_cycle(
    asset_symbol='WDO$', 
    timeframe_str='M5',
    target_datetime_local=pd.Timestamp('2025-11-20 10:00:00')  # UTC or local based on config
)
# result: {ai_signal, setup_valid, final_decision, price, stop, take, indicators}
```

## Troubleshooting

### YAML Config Keys Mismatch
**Issue:** Code references `models_directory` but config defines `model_directory`
**Root Cause:** Legacy naming inconsistency; the code uses `.get('model_directory', 'models')` as fallback
**Status:** Works as-is; just use `model_directory` in YAML (don't use `models_directory`)

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
