---
name: ARCHITECT Task
about: Core refactor for monitor/provider alignment
title: "[ARCHITECT] Migrate MonitorEngine to mt5_provider"
labels: "agent:architect, domain:core, sprint-3"
assignees: ""
---

## Objective
Migrate RealTimeMonitor to use config-driven mt5_provider and align OHLC column handling without breaking LSTM inference or UI callbacks.

## Context & Files
- Target: src/live/monitor_engine.py
- Related: src/data_handler/mt5_provider.py, src/core/config.py, src/main, configs/main.yaml

## Technical Scope
1. Replace provider import to src.data_handler.mt5_provider.MetaTraderProvider.
2. Use timeframe string for provider calls (no MT5 constants).
3. Normalize OHLCV handling so strategy + analyzer still work.
4. Replace legacy provider connection methods with mt5_provider equivalents (add is_connected/close_connection if needed).
5. Rename src/main to src/main.py and verify imports.
6. Fix model_directory path in configs/main.yaml (relative models/).

## Dependencies / Blockers
- None (can be implemented without UI changes).

## Definition of Done
- MonitorEngine uses mt5_provider without runtime errors.
- LSTM inference runs with correct OHLCV columns.
- configs/main.yaml uses model_directory: "models".
- src/main.py exists and can be imported.
