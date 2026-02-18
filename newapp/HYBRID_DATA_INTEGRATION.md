# Integração Híbrida de Dados (Database-First Strategy)

## Visão Geral

Sistema implementado que **prioriza o banco de dados** para carregar gráficos, com fallback automático para providers externos quando há gaps (dados faltantes). Persiste novos dados **em background** sem bloquear a renderização.

## Componentes

### 1. Hybrid Data Loader (`newapp/src/data_handler/hybrid_data_loader.py`)

**Funções principais:**
- `get_hybrid_candles(db, symbol, timeframe_str, limit, background_tasks)` - Versão assíncrona (FastAPI)
- `get_hybrid_candles_sync(db, symbol, timeframe_str, limit)` - Versão síncrona (fallback)

**Fluxo de execução:**
```
1. Query AssetsRates (DB) → últimos N candles
2. Detecta gap: compara última vela do DB com tempo esperado
   - Gap < 2 candles → retorna dados do DB (fresh)
   - Gap ≥ 2 candles → busca do provider
3. Provider fetch (MT5 → Cache → Synthetic)
4. Retorna dados IMEDIATAMENTE (DB + novos)
5. Persiste novos candles em BACKGROUND (não bloqueia)
```

**Características técnicas:**
- Thread-safe (singleton providers)
- Timezone-aware (UTC normalization)
- Deduplicação automática (remove duplicatas por timestamp)
- Logging detalhado para troubleshooting

### 2. Endpoints Atualizados

**main.py:**
- `/charts` - Gráficos interativos
- `/api/ohlc` - Dados OHLCV JSON
- `/api/analysis` - Análise técnica
- `/api/combined` - OHLC + análise
- `/dashboard` - Dashboard (deprecated)

**main_clean.py:**
- `/charts-clean` - Gráficos clean UI
- `/api/monitor-predictions` - Predições do monitor

**Todos agora usam:**
```python
df = get_hybrid_candles(db, symbol, timeframe, limit, background_tasks)
```

### 3. Persistência Assíncrona

**FastAPI BackgroundTasks (preferencial):**
```python
background_tasks.add_task(
    AssetsRatesRepository.save_rates_dataframe,
    db, df_new, symbol, timeframe_int, timeframe_str, False
)
```

**Vantagens:**
- Não bloqueia resposta HTTP
- Executa após enviar response
- Sem overhead de asyncio.create_task

**Fallback (asyncio task):**
- Usado quando BackgroundTasks não disponível
- Cria task na event loop

**Último fallback (sync):**
- Executa de forma síncrona se não há event loop
- Usado apenas em `get_hybrid_candles_sync()`

## Detecção de Gap

**Lógica:**
```python
expected_latest = round_down_to_timeframe(datetime.now(UTC))
latest_db = df_db.index[-1]
gap_seconds = expected_latest - latest_db

if gap_seconds > (timeframe_seconds * 2):
    # Buscar do provider
```

**Tolerância:** 2 candles
- M5: 10 minutos
- H1: 2 horas
- D1: 2 dias

## Comportamento por Cenário

### 1. Database Vazio
```
DB: [] → Provider fetch → Persiste tudo → Retorna
```

### 2. Database Fresh (< 2 candles gap)
```
DB: [data] → Verifica freshness → Retorna DB → Sem persist
```

### 3. Database Stale (≥ 2 candles gap)
```
DB: [old_data] → Provider fetch [new_data] → 
Retorna [old_data + new_data] → Persiste [new_data]
```

### 4. Provider Falha
```
DB: [old_data] → Provider erro → Retorna [old_data] → Log warning
```

## Performance

**Latência esperada:**
- **DB hit (fresh):** ~50-100ms (query SQLite)
- **DB + Provider:** ~200-500ms (MT5 fetch) + background persist
- **Synthetic fallback:** ~50-150ms (geração in-memory)

**Background persist:**
- Não impacta tempo de resposta HTTP
- SQLite com WAL mode (concurrent reads durante write)
- Sem deadlocks (single writer via BackgroundTasks)

## Testes

### Teste Unitário (`newapp/tests/test_hybrid_loader.py`)
```bash
poetry run pytest newapp/tests/test_hybrid_loader.py -v
```

**Cobertura:**
- Conversão de timeframe
- Cálculo de expected latest time
- Cenários: DB vazio, fresh, gap, fallback
- Persistência assíncrona vs síncrona

### Verificação de Integração (`verify_hybrid_integration.py`)
```bash
poetry run python newapp/tests/verify_hybrid_integration.py
```

**Valida:**
1. Query database (estado atual)
2. Hybrid loader execution
3. Persistência de novos dados
4. Freshness dos dados

**Output esperado:**
```
✅ Hybrid loader: WORKING
✅ Database query: WORKING
✅ Provider fallback: WORKING
✅ Data persistence: WORKING
📊 Total candles: 100
🔄 New candles added: X
```

## Troubleshooting

### Gráfico não carrega
1. Verificar logs: `tail -f logs/app.log`
2. Checar conexão MT5: `mt5.terminal_info()`
3. Validar database: `poetry run python newapp/tests/verify_hybrid_integration.py`

### Dados desatualizados
- Mercado fechado → Normal (última vela = fechamento)
- Gap detection threshold muito alto → Ajustar em `hybrid_data_loader.py`
- Provider offline → Usar cache ou synthetic

### Database lock
- WAL mode ativo? → Verificar `PRAGMA journal_mode;`
- Background task duplicado? → Não deve ocorrer (BackgroundTasks é serial)
- Conexão não fechada? → Verificar `finally: db.close()`

## Melhorias Futuras

1. **Cache em memória (Redis):** Para dados muito frequentes
2. **Streaming updates (WebSocket):** Para gráficos real-time
3. **Compression:** Parquet com snappy para cache
4. **Particionamento:** Separar DB por período (mensais)
5. **Metrics:** Prometheus para latency tracking

## Arquivos Modificados

```
newapp/src/data_handler/
├── hybrid_data_loader.py      # NEW - Lógica híbrida
└── provider.py                 # Existing - Providers MT5/Cache/Synthetic

newapp/
├── main.py                     # MODIFIED - Endpoints com hybrid loader
└── main_clean.py               # MODIFIED - Clean UI com hybrid loader

newapp/tests/
├── test_hybrid_loader.py       # NEW - Testes unitários
└── verify_hybrid_integration.py # NEW - Verificação end-to-end
```

## Referências

- **SQLAlchemy Sessions:** https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- **FastAPI BackgroundTasks:** https://fastapi.tiangolo.com/tutorial/background-tasks/
- **Pandas timezone handling:** https://pandas.pydata.org/docs/user_guide/timeseries.html#time-zone-handling
