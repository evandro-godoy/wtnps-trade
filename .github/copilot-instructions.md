# Copilot Instructions for WTNPS Trade

## Big Picture
- Config-driven trading framework. The single source of truth is [configs/main.yaml](configs/main.yaml); engines dynamically load strategies, models, and rules from this file.
- Two execution paths share the same core logic: [src/simulation/engine.py](src/simulation/engine.py) for point-in-time simulation and [src/live_trader.py](src/live_trader.py) for real-time MT5 trading.
- Hybrid decision flow is mandatory: ML signal ("COMPRA"/"VENDA") then setup validation in [src/setups/analyzer.py](src/setups/analyzer.py). If no setup rule matches the signal, the setup is valid by default.
- Strategy plugin pattern: each strategy inherits from [src/strategies/base.py](src/strategies/base.py) and implements `define_features`, `define_target` (supervised only), `define_model`, `get_feature_names`, `save`/`load`.
- Providers in [src/data_handler/provider.py](src/data_handler/provider.py) are MT5/YFinance with `.cache_data/` Parquet caching; MT5 is Windows-only and must be running.

## Key Conventions
- AI signals are uppercase Portuguese: `COMPRA`, `VENDA`, `HOLD`.
- Model artifacts follow `<TICKER>_<STRATEGY>_<TIMEFRAME>_prod_<type>.*` in `global_settings.model_directory` (fallback to `models/`). Example: `WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras`.
- Timeframes are limited to `M1/M5/M15/M30/H1/H4/D1/W1/MN1`; invalid values warn and return `None`.
- Timezone: simulation inputs are local (America/Sao_Paulo) and converted to UTC for providers.
- Ignore deprecated code under `archive/`, `bkp/`, and `*old*` when adding features.

## Developer Workflows (Poetry)
- Install deps: `poetry install` (MT5 terminal must be running for live data).
- Train supervised models: `poetry run python train_model.py` (writes models + scalers + reports).
- Train DRL: `poetry run python train_drl_model.py` (interactive ticker selection).
- Run live trading: `poetry run python src/live_trader.py` (respects `execution_mode: suggest|execute`).
- Run simulation engine: `poetry run python src/simulation/engine.py`.
- Monitor GUI: `poetry run python run_monitor_gui.py` (see [src/gui/README.md](src/gui/README.md)).
- Real-time monitor CLI: `poetry run python run_monitor.py` (see [src/live/README.md](src/live/README.md)).

## Web App (newapp)
- `newapp/` is a FastAPI web interface with its own provider stack and DB layer; entry point is [newapp/main.py](newapp/main.py).
- Hybrid provider chain: MT5 -> cache -> synthetic (see [newapp/src/data_handler/provider.py](newapp/src/data_handler/provider.py)).
- SQL Server integration uses env vars from [newapp/sql/README.md](newapp/sql/README.md); DB-first reads then provider fallback.

## Patterns to Preserve
- Strategy loading is dynamic via module name in YAML; see `_load_asset_resources()` in engines.
- Feature engineering feeds both ML and setup rules; missing feature columns should warn once, not crash.
- Thread separation in GUI/monitor: UI main thread + background worker with `queue.Queue`.

## Where to Look
- System overview: [README.md](README.md) and [DRL_README.md](DRL_README.md).
- LSTM pipeline example: [src/strategies/lstm_volatility.py](src/strategies/lstm_volatility.py).
- Live monitor flow: [src/live/monitor_engine.py](src/live/monitor_engine.py).
