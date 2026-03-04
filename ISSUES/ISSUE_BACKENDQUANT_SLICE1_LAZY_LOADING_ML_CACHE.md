# [BACKENDQUANT] Slice 1 — Lazy Loading + Cache em Memória para Inferência ML no FastAPI

**Assignee:** @BackendQuant  
**Labels:** `backend`, `quant`, `ml`, `realtime`, `fastapi`, `priority:high`, `slice-1`, `newapp`  
**Milestone sugerido:** Slice 1 — Fundação do Monitor em Tempo Real

> **Instrução de integração (obrigatória):** Todos os commits e Pull Requests desta tarefa devem ter como alvo a branch `feature/monitor-slice-1` e **NÃO** a `main`.

---

## 📋 Contexto
No monitor realtime do `newapp`, o carregamento de artefatos ML (`.keras` e `.joblib`) não deve ocorrer no startup (`lifespan`) da API. Esse preload pode bloquear a subida do servidor e degradar conexões WebSocket.

A estratégia oficial para o Slice 1 é **Lazy Loading com cache em memória**.

---

## 🎯 Objetivo
Refatorar a camada de predição (ex.: `prediction_engine.py` ou adaptação do legado) para carregar modelo/scaler sob demanda no primeiro uso e manter cache para inferências subsequentes rápidas, sem bloquear o Event Loop do FastAPI.

---

## 📁 Arquivos-alvo
- `newapp/src/services/prediction_engine.py` (ou arquivo equivalente de inferência)
- `newapp/src/live/monitor_engine.py` (integração com chamada assíncrona de predição)
- `newapp/src/strategies/lstm_volatility.py` (se necessário para separar load/predict)
- `newapp/tests/` (testes de lazy loading + não bloqueio básico)

---

## 🔧 Requisitos obrigatórios

### Requisito 1 — Verificação explícita de lazy loading
- [ ] Implementar verificação no fluxo de inferência: `if model is None: load_model()`.
- [ ] Aplicar a mesma abordagem para scaler/parâmetros (`if scaler is None: load_scaler()`).
- [ ] Após o primeiro load, manter os artefatos em cache de memória por chave de ativo/estratégia/timeframe.

### Requisito 2 — Carregamento em thread separada
- [ ] Garantir que a rotina de load bloqueante (TensorFlow/Keras/Joblib) rode em thread separada (`asyncio.to_thread` ou equivalente).
- [ ] Evitar bloqueio do Event Loop principal do FastAPI durante o primeiro carregamento.
- [ ] Preservar estabilidade de conexões WebSocket durante o processo de load.

---

## 🛠️ Tarefas técnicas sugeridas
- [ ] Criar componente/facade de cache de artefatos ML com estado interno (`model`, `scaler`, `params`).
- [ ] Adicionar proteção de concorrência (single-flight/lock) para evitar carregamento duplicado simultâneo.
- [ ] Definir logs estruturados para estados: `cache_miss`, `loading_started`, `loading_finished`, `loading_failed`, `cache_hit`.
- [ ] Garantir tratamento de exceção sem derrubar processo FastAPI (fallback/erro controlado no payload).

---

## ✅ Critérios de aceite
- [ ] API sobe sem carregar modelos no `lifespan`.
- [ ] Primeira predição dispara lazy loading e conclui com sucesso.
- [ ] Predições subsequentes utilizam cache (sem recarregar artefatos).
- [ ] Carregamento pesado não bloqueia Event Loop nem interrompe WebSockets ativos.
- [ ] Testes cobrindo `cache miss` + `cache hit` + erro de load controlado.

---

## 📊 Estimativa
- **Story Points:** 8
- **Horas:** 10h–14h
- **Prioridade:** 🔴 ALTA

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md` (seção ML Lazy Loading + cache)
- `.memory-bank/activeContext.md` (progresso do Slice 1)
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_MONITOR_ALWAYS_ON_SINGLETON.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_PERSISTENCIA_DESACOPLADA_BACKGROUND.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_CONTRATO_WS_PYDANTIC_STRICT.md`
- `ISSUES/ISSUE_GUARDIAN_SLICE1_MASTER_TESTES_REALTIME.md`

---

## 🔗 Dependências cruzadas (Slice 1)
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_MONITOR_ALWAYS_ON_SINGLETON.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_PERSISTENCIA_DESACOPLADA_BACKGROUND.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_CONTRATO_WS_PYDANTIC_STRICT.md`
- `ISSUES/ISSUE_GUARDIAN_SLICE1_MASTER_TESTES_REALTIME.md`
- `ISSUES/ISSUE_ARCHITECT_EPIC_SLICE1_INTEGRACAO_SHARED_BRANCH.md`
