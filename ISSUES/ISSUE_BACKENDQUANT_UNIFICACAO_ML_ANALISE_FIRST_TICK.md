# [BACKENDQUANT] Unificar pipeline ML + Análise Técnica e corrigir first tick do Monitor

**Assignee:** @BackendQuant  
**Labels:** `backend`, `quant`, `prediction`, `websocket`, `monitor`, `priority:high`, `phase-1`  
**Milestone sugerido:** Sprint Integração Monitor/Charts

---

## 📋 Contexto
A aplicação está estável em infraestrutura/persistência, porém há divergência de contrato e fluxo no pipeline de predição realtime.

### Problemas observados
1. O monitor realtime não emite atualização imediata ao clicar **Play** (aguarda próximo candle M5).
2. O payload realtime não está totalmente unificado com a análise técnica/validação usada no pipeline legado.
3. Há inconsistências de contrato no loop do `RealtimeMarketMonitor`.

---

## 🎯 Objetivo
Criar **um pipeline canônico backend** que combine:
- Sinal ML
- Análise técnica (`MarketContextAnalyzer`)
- Validação de sinal (`signal_valid` + `validation_reason`)

Esse payload combinado deve alimentar **tanto** o WebSocket `/ws/monitor` quanto o endpoint `/api/monitor-predictions`.

---

## 📁 Arquivos-alvo
- `newapp/src/live/monitor_engine.py`
- `newapp/src/services/prediction_service.py` (ou novo serviço canônico em `newapp/src/services/`)
- `newapp/src/services/monitor_runtime.py`
- `newapp/src/api/routers/monitor.py`
- `newapp/src/analysis/context_analyzer.py` (consumo/integração, sem quebrar contrato atual)

---

## 🔧 Tarefas
- [ ] Corrigir chamadas do provider no loop realtime para contrato oficial (`ticker`, `timeframe`, `count`) em todo o ciclo async/sync.
- [ ] Ajustar `RealtimeMarketMonitor._process_new_candle()` para tratar `analyze()` como `dict`, não `DataFrame`.
- [ ] Implementar emissão **imediata de first tick** após `_warm_up()`:
  - Processar última vela fechada do buffer.
  - Disparar callback/broadcast inicial (`snapshot` ou equivalente).
  - Evitar duplicata no próximo ciclo (controle por timestamp processado).
- [ ] Unificar estrutura de payload para monitor realtime e `/api/monitor-predictions`.
- [ ] Incluir bloco `decision` no payload com `signal_valid` e `validation_reason`.
- [ ] Manter arquitetura monolítica (FastAPI + tasks + WebSocket), sem EventBus.

---

## 🧱 Contrato de payload alvo (canônico)
```json
{
  "timestamp": "ISO8601",
  "ticker": "WDO$",
  "timeframe": "M5",
  "ohlcv": {"open": 0, "high": 0, "low": 0, "close": 0, "volume": 0},
  "indicators": {"ema_9": 0, "ema_20": 0, "sma_20": 0, "sma_50": 0, "rsi_14": 0},
  "analysis": {"trend": "ALTA|BAIXA|LATERAL", "trend_strength": "FORTE|MODERADA|FRACA", "support": 0, "resistance": 0, "pattern": "...", "rsi_condition": "..."},
  "ml": {"signal": "COMPRA|VENDA|HOLD", "direction": "CALL|PUT", "probability": 0.0},
  "decision": {"signal_valid": true, "validation_reason": "..."}
}
```

---

## ✅ Critérios de aceite
- [ ] Ao clicar Play, a UI recebe primeiro update em até 2s (sem esperar candle seguinte).
- [ ] `/ws/monitor` e `/api/monitor-predictions` usam o mesmo contrato base.
- [ ] `signal_valid` e `validation_reason` presentes quando aplicável.
- [ ] Sem bloqueio do thread principal do FastAPI.
- [ ] Sem regressão em start/stop/status de monitor.

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md` (seções 5 e 7)
- `.memory-bank/activeContext.md`
- `.memory-bank/SPRINT_2026-02-20_MONITOR_CHARTS_HANDOFF.md`
