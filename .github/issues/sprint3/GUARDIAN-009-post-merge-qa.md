---
name: GUARDIAN Task
about: Post-merge integrity sweep
title: "[GUARDIAN] Post-merge integrity sweep"
labels: "agent:guardian, domain:qa, sprint-3"
assignees: ""
---

## Objective
Clean up post-merge inconsistencies and validate imports/tests after provider migration.

## Context & Files
- Target: tests/unit/test_lstm_inference.py
- Related: src/live/monitor_engine.py, src/api/main.py, src/main.py

## Technical Scope
1. Update tests to use mt5_provider where applicable.
2. Verify imports: RealTimeMonitor, TradingSystem, FastAPI app.
3. Remove or flag dead/backup files if safe.

## Dependencies / Blockers
- Execute after ARCH-005, FULLSTACK-006, QUANT-007, DEVOPS-008.

## Definition of Done
- pytest runs without import errors (mock MT5 if needed).
- Core imports succeed without ModuleNotFoundError.
