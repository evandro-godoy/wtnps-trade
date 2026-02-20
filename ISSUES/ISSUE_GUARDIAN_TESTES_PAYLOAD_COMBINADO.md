# [GUARDIAN] Validar payload combinado (ML + Análise Técnica) e first tick

**Assignee:** @Guardian  
**Labels:** `qa`, `testing`, `guardian`, `websocket`, `contract`, `phase-1`, `priority:high`  
**Milestone sugerido:** Sprint Integração Monitor/Charts

---

## 📋 Contexto
Após unificação do pipeline backend e ajustes frontend, precisamos validar contrato, comportamento realtime e ausência de regressão funcional.

---

## 🎯 Objetivo
Executar bateria de testes para garantir:
1. Contrato combinado consistente.
2. Emissão de first tick ao iniciar monitor.
3. Compatibilidade UI e estabilidade em fluxo contínuo.

---

## 📁 Escopo de validação
- `newapp/src/live/monitor_engine.py`
- `newapp/src/services/monitor_runtime.py`
- `newapp/src/api/routers/monitor.py`
- `newapp/static/js/monitor.js`
- `newapp/static/js/app.js`
- `newapp/tests/` (novos testes e smoke)

---

## 🧪 Plano de testes
- [ ] **Contract test (API/WS):** validar presença e tipos de `ohlcv`, `indicators`, `analysis`, `ml`, `decision`.
- [ ] **First tick test:** iniciar monitor e confirmar primeira mensagem em até 2s.
- [ ] **No-duplicate test:** garantir que first tick não duplica com próximo ciclo.
- [ ] **Continuous stream test:** validar sequência temporal e estabilidade de 3+ mensagens.
- [ ] **Charts compatibility test:** `/api/analysis` + frontend sem erro de parsing.
- [ ] **Regression smoke:** start/stop/status monitor + `/api/monitor-predictions`.

---

## ✅ Critérios de aceite
- [ ] Todos os testes novos passando.
- [ ] Sem regressões nos smoke tests críticos da Fase 1.
- [ ] Evidências anexadas: logs, payload samples, tempos de resposta.
- [ ] Relatório final com riscos residuais (se houver).

---

## 📤 Entregável esperado
Relatório QA consolidado com:
- Matriz de casos (Pass/Fail)
- Evidências (capturas/logs)
- Recomendação de go/no-go para merge

---

## 🔗 Referências
- `newapp/tests/tmp_phase1_smoke_runner.py`
- `.memory-bank/systemPatterns.md`
- `.memory-bank/SPRINT_2026-02-20_MONITOR_CHARTS_HANDOFF.md`
