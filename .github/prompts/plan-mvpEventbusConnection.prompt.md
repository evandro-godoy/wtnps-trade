# Plan: Sprint 1 - MVP EventBus Connection

Establish event-driven bridge between legacy EventBus ([src/events.py](src/events.py), [src/live/lstm_volatility_adapter.py](src/live/lstm_volatility_adapter.py)) and NewApp FastAPI architecture ([newapp/main.py](newapp/main.py)), enabling real-time ML signal distribution via WebSocket and REST APIs.

## Steps

1. **Create EventBus Test Suite** — Add [tests/unit/test_event_bus.py](tests/unit/test_event_bus.py) with subscribe/publish, error handling, and thread-safety tests (coverage ≥80%)

2. **Build NewApp EventBus Bridge** — Create [newapp/src/adapters/event_bus_adapter.py](newapp/src/adapters/event_bus_adapter.py) as async-safe facade over legacy `EventBus`, converting newapp data to `MarketDataEvent`/`SignalEvent`/`OrderEvent`

3. **Integrate EventBus → WebSocket** — Extend [newapp/main.py](newapp/main.py) WebSocket manager to subscribe to `EventBus` and publish events to connected clients with event-type filtering

4. **Connect LSTM Adapter to FastAPI** — Add `POST /api/ml/lstm/predict` endpoint in [newapp/main.py](newapp/main.py) using [src/live/lstm_volatility_adapter.py](src/live/lstm_volatility_adapter.py), publishing signals to EventBus

5. **Create Integration Tests** — Add [tests/integration/test_eventbus_websocket_flow.py](tests/integration/test_eventbus_websocket_flow.py) verifying end-to-end: market data → EventBus → WebSocket delivery

6. **Update Sprint Documentation** — Create [newapp/EVENTBUS_INTEGRATION.md](newapp/EVENTBUS_INTEGRATION.md) with architecture diagrams, add `integration_task.md` template to [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/)

## Further Considerations

### 1. Async vs Thread Safety
**Problem:** Legacy EventBus uses `threading.Lock`. FastAPI is async-first.

**Options:**
- Wrap calls in `asyncio.to_thread()` (MVP approach)
- Reimplement EventBus as async-native in newapp

**Recommendation:** Start with `to_thread()` wrapper for MVP, evaluate performance in Sprint 2.

**Implementation Details:**
```python
# NewApp adapter wraps legacy EventBus calls
async def publish_event_async(event):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, event_bus.publish, event)
```

### 2. CI Python Version Mismatch
**Problem:** [.github/workflows/ci.yml](.github/workflows/ci.yml) uses Python 3.10 but [pyproject.toml](pyproject.toml) requires 3.12+.

**Fix:**
- Update CI workflow: `python-version: "3.12"`
- Verify all dependencies support 3.12
- Update CI conditional checks for version-specific features

**Scope:** Include in Sprint 1 (blocking issue for main branch)

### 3. Event Persistence (Database Logging)
**Problem:** Events are currently in-memory only. No audit trail.

**Options:**
- Add event logging to SQLite ([newapp/src/database/models.py](newapp/src/database/models.py))
- Create EventLog table with timestamp, event_type, payload, client_id

**Recommendation:** Defer to Sprint 2 unless critical for MVP compliance.

**Future Implementation:**
```python
class EventLog(Base):
    __tablename__ = "event_logs"
    id: int
    timestamp: datetime
    event_type: str
    payload: JSON
    client_id: Optional[str]
```

### 4. Model Preloading at Startup
**Problem:** First LSTM prediction takes 2-3s due to .keras model loading.

**Fix:**
- Add `@app.on_event("startup")` handler in [newapp/main.py](newapp/main.py)
- Pre-load models for all configured tickers
- Cache in memory (singleton pattern)

**Recommendation:** YES - Essential for responsive MVP.

**Implementation:**
```python
@app.on_event("startup")
async def preload_models():
    """Pre-load all trained LSTM models at startup"""
    config = load_config()
    for asset in config['assets']:
        ticker = asset['ticker']
        for strategy in asset['strategies']:
            if strategy['name'] == 'LSTMVolatilityStrategy':
                model_path = f"models/{ticker}_prod_lstm.keras"
                # Load and cache
                model_cache[ticker] = load_model(model_path)
```

## Risk Assessment

### High-Risk Items
1. **Async/Thread Boundary** — Legacy EventBus not thread-safe for FastAPI async loops
   - **Mitigation:** Wrap in `asyncio.to_thread()`
   - **Fallback:** Create async-only EventBus in newapp

2. **MT5 Terminal Dependency** — Live data requires Windows + MT5 running
   - **Mitigation:** Use cached data for testing
   - **Fallback:** Use synthetic/YFinance data

### Medium-Risk Items
3. **Model Loading Performance** — 2-3s cold load per model
   - **Mitigation:** Preload at startup
   - **Fallback:** Async model loading with progress callback

4. **WebSocket Client Management** — Memory leak if clients disconnect ungracefully
   - **Mitigation:** Implement heartbeat + cleanup on disconnect
   - **Fallback:** Manual cleanup interval

### Low-Risk Items
5. **CI Pipeline Mismatch** — Python version inconsistency
   - **Mitigation:** Update CI to 3.12
   - **Fallback:** Test locally with 3.12

## Definition of Done (DoD)

### Code Quality
- ✅ All new code passes mypy type checking
- ✅ No circular imports between legacy and newapp
- ✅ Thread-safe EventBus bridge (validated by tests)
- ✅ Proper error handling (no uncaught exceptions)
- ✅ Logging at INFO/DEBUG levels

### Testing
- ✅ Unit tests for EventBus (subscribe, publish, error handling)
- ✅ Unit tests for adapter (data conversion, signal generation)
- ✅ Integration tests for EventBus → WebSocket flow
- ✅ Test coverage ≥ 80%
- ✅ CI passes on Python 3.12

### Documentation
- ✅ [newapp/EVENTBUS_INTEGRATION.md](newapp/EVENTBUS_INTEGRATION.md) with architecture diagrams
- ✅ API docs in [newapp/main.py](newapp/main.py) (docstrings)
- ✅ [.github/ISSUE_TEMPLATE/integration_task.md](.github/ISSUE_TEMPLATE/integration_task.md) created
- ✅ README updated with "Event-Driven Architecture" section

### Integration
- ✅ Existing `/api/ohlc` endpoint still works
- ✅ Existing `/api/technical-analysis` endpoint still works
- ✅ New `/api/ml/lstm/predict` endpoint functional
- ✅ WebSocket clients receive EventBus events
- ✅ Backward compatible with legacy CLI tools

## Sprint Capacity Estimate

### Priority 1: EventBus Bridge (3-5 days)
- Task 1a: EventBus tests → 8h
- Task 1b: NewApp adapter → 12h
- Task 1c: WebSocket publisher → 8h
- Task 1d: Integration tests → 8h

**Subtotal:** 36h (4.5 days, 1 developer)

### Priority 2: LSTM Integration (2-3 days)
- Task 2a: Refactor LSTMAdapter → 6h
- Task 2b: LSTM service layer → 8h
- Task 2c: FastAPI endpoint → 4h
- Task 2d: Unit tests → 6h

**Subtotal:** 24h (3 days, 1 developer)

### Priority 3: Documentation (1 day)
- Task 3a: Architecture doc → 3h
- Task 3b: Issue templates → 2h
- Task 3c: README updates → 2h

**Subtotal:** 7h (1 day, 0.5 developers)

**Total Sprint Estimate:** 67h (~9 days, 1 FTE developer)
**Recommended Sprint Duration:** 2 weeks (allows for blockers, code review, integration testing)

## Success Criteria

### Quantitative
- ✅ EventBus test coverage ≥ 80%
- ✅ 0 failing CI tests
- ✅ LSTM prediction latency < 500ms (from request to WebSocket publish)
- ✅ WebSocket event delivery latency < 100ms (after EventBus publish)
- ✅ All 6 GitHub Issues closed with linked pull requests

### Qualitative
- ✅ Code passes architecture review (no circular imports)
- ✅ Team agrees EventBus bridge is production-ready
- ✅ Documentation is clear enough for onboarding new developer
- ✅ No "HACK" or "TODO" comments left behind
- ✅ Git history is clean (squashed commits, descriptive messages)

## Next Steps (After Sprint Planning Approval)

1. **Create GitHub Issues** from this plan using [.github/ISSUE_TEMPLATE/](integration_task.md) template
2. **Assign to Squad Members:**
   - QUANT: Task 2a (LSTM Refactor) + Task 2b (Service Layer)
   - ARCHITECT: Task 1a (Tests) + Task 1b (Adapter)
   - GUARDIAN: Task 1d (Integration Tests) + Task 2d (Unit Tests)
   - DEVOPS: Task 1c (WebSocket) + CI/CD fix
3. **Set Backlog Order:** Priority 1 → Priority 2 → Priority 3
4. **Kick-off:** Daily standup at 9am (async or sync TBD)
5. **Review Cadence:** Every 2 days or when tasks move to "In Review"
