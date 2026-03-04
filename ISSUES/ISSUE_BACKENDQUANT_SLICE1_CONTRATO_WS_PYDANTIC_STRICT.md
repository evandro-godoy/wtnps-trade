# [BACKENDQUANT] Slice 1 — Contrato Estrito WebSocket com Pydantic (MonitorPayload)

**Assignee:** @BackendQuant  
**Labels:** `backend`, `quant`, `realtime`, `websocket`, `pydantic`, `fastapi`, `priority:high`, `slice-1`, `newapp`  
**Milestone sugerido:** Slice 1 — Fundação do Monitor em Tempo Real

> **Instrução de integração (obrigatória):** Todos os commits e Pull Requests desta tarefa devem ter como alvo a branch `feature/monitor-slice-1` e **NÃO** a `main`.

---

## 📋 Contexto
No `newapp`, o frontend do monitor deve se tornar uma camada de renderização simples. Toda validação, normalização e serialização do payload WS deve acontecer no backend via contrato estrito.

A estratégia definida é **Strict Data Contracts com Pydantic**.

---

## 🎯 Objetivo
Criar os modelos Pydantic para o payload do monitor em tempo real e garantir que a mensagem enviada via WebSocket já esteja pronta para exibição (UI-ready), sem exigir fallback/parse defensivo no JS.

---

## 📁 Arquivos-alvo
- `newapp/src/api/websockets/monitor_ws.py`
- `newapp/src/live/monitor_engine.py`
- `newapp/src/services/` (camada de montagem/serialização do payload)
- `newapp/src/schemas/monitor_payload.py` (novo, sugerido)
- `newapp/tests/` (testes de contrato)

---

## 🔧 Requisitos obrigatórios

### Requisito 1 — Schema estrito MonitorPayload
- [ ] Criar `MonitorPayload` com estrutura canônica obrigatória:
  - `ohlcv`
  - `indicators`
  - `analysis`
  - `ml`
  - `decision`
- [ ] Validar tipos e coerência mínima antes de broadcast.
- [ ] Bloquear envio de payload fora do schema (com log de erro controlado).

### Requisito 2 — Formatação crítica no backend
- [ ] Tratar no backend (pré-serialização/model validators) formatações visuais críticas.
- [ ] Garantir que probabilidade não chegue nula para UI.
- [ ] Aplicar arredondamentos/base formatting necessários para renderização direta.
- [ ] Eliminar necessidade de helpers defensivos no JS (ex.: `toNumberOrNull`).

---

## 🛠️ Tarefas técnicas sugeridas
- [ ] Definir submodelos Pydantic (`OHLCV`, `Indicators`, `Analysis`, `ML`, `Decision`) e compor `MonitorPayload`.
- [ ] Centralizar montagem de payload em função única no backend (single source of truth).
- [ ] Incluir versão de contrato (`schema_version`) se aplicável para evolução incremental.
- [ ] Adicionar testes de serialização/validação com cenários de nulo, tipo inválido e payload completo.

---

## ✅ Critérios de aceite
- [ ] Todo broadcast WS usa instância validada de `MonitorPayload`.
- [ ] Frontend recebe dados prontos para exibição sem fallback numérico/classificação local.
- [ ] Falhas de validação não derrubam loop realtime nem conexão WS.
- [ ] Testes de contrato passando com cobertura de casos críticos.

---

## 📊 Estimativa
- **Story Points:** 8
- **Horas:** 10h–14h
- **Prioridade:** 🔴 ALTA

---

## 🔗 Dependências cruzadas (Slice 1)
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_MONITOR_ALWAYS_ON_SINGLETON.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_LAZY_LOADING_ML_CACHE.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_PERSISTENCIA_DESACOPLADA_BACKGROUND.md`
- `ISSUES/ISSUE_FULLSTACK_SLICE1_MONITOR_JS_CONTRATO_WS_DUMB_UI.md`
- `ISSUES/ISSUE_GUARDIAN_SLICE1_MASTER_TESTES_REALTIME.md`
- `ISSUES/ISSUE_ARCHITECT_EPIC_SLICE1_INTEGRACAO_SHARED_BRANCH.md`

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md` (Strict Data Contracts / Pydantic)
- `.memory-bank/activeContext.md` (Slice 1 concluído em arquitetura)
