---
name: QUANT Task
about: LSTM adapter alignment with MT5 provider output
title: "[QUANT] Consolidate LSTM adapter OHLC handling"
labels: "agent:quant, domain:strategy, sprint-3"
assignees: ""
---

## Objective
Ensure LSTM adapter consumes MT5 data consistently and produces signals without column mismatches.

## Context & Files
- Target: src/modules/strategy/lstm_adapter.py
- Related: src/strategies/lstm_volatility.py, src/events.py
- New tests: tests/unit/test_lstm_adapter.py

## Technical Scope
1. Normalize OHLCV columns so adapter works with MT5 provider data.
2. Validate lookback alignment with model input shape.
3. Add a unit test using synthetic MarketDataEvent inputs.
4. Keep event bus publishing intact.

## Dependencies / Blockers
- Depends on ARCH-005 column normalization approach.

## Definition of Done
- Adapter emits SignalEvent with valid confidence for synthetic input.
- Test suite passes for test_lstm_adapter.py.
