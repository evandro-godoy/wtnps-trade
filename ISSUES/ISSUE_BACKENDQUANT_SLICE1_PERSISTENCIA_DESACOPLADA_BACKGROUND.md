# [BACKENDQUANT] Slice 1 — Persistência Desacoplada em Background no RealtimeMarketMonitor

**Assignee:** @BackendQuant  
**Labels:** `backend`, `quant`, `realtime`, `database`, `websocket`, `fastapi`, `priority:high`, `slice-1`, `newapp`  
**Milestone sugerido:** Slice 1 — Fundação do Monitor em Tempo Real

> **Instrução de integração (obrigatória):** Todos os commits e Pull Requests desta tarefa devem ter como alvo a branch `feature/monitor-slice-1` e **NÃO** a `main`.

---

## 📋 Contexto
No módulo `newapp`, o caminho crítico de tempo real deve priorizar latência de entrega via WebSocket. A gravação de candle/predição em SQLite/Postgres é I/O bloqueante e não pode atrasar o fluxo de emissão do monitor.

A estratégia oficial para o Slice 1 é **Persistência Desacoplada (Eventual Consistency)** com processamento em background.

---

## 🎯 Objetivo
Refatorar `monitor_engine.py` para que broadcast WS e persistência no `AssetsRatesRepository` sejam independentes, garantindo que `_process_new_candle` não espere o commit de banco.

---

## 📁 Arquivos-alvo
- `newapp/src/live/monitor_engine.py`
- `newapp/src/database/repository.py` (apenas integração/uso)
- `newapp/src/services/monitor_runtime.py` (se aplicável)
- `newapp/tests/` (testes de latência e independência do fluxo)

---

## 🔧 Requisitos obrigatórios

### Requisito 1 — Independência entre WS e persistência
- [ ] O método de envio via WebSocket e o método de gravação no `AssetsRatesRepository` devem ser executados de forma independente.
- [ ] Falha na gravação não pode impedir emissão de evento para clientes WS.

### Requisito 2 — Persistência em background
- [ ] Utilizar `asyncio.create_task()` ou estrutura de fila/background task para persistência.
- [ ] Garantir que o tempo de resposta de `_process_new_candle` não inclua tempo de commit de banco.
- [ ] Preservar estabilidade do Event Loop e das conexões WebSocket durante picos de I/O.

---

## 🛠️ Tarefas técnicas sugeridas
- [ ] Implementar pipeline `enqueue -> worker persist` com `asyncio.Queue` (ou alternativa equivalente).
- [ ] Garantir ordem temporal por `ticker+timeframe` no worker de persistência.
- [ ] Adicionar logs estruturados: `persist_enqueue`, `persist_success`, `persist_failure`, `persist_retry`.
- [ ] Definir política de retry/timeout sem bloquear stream realtime.
- [ ] Garantir dreno controlado de tarefas pendentes no shutdown.

---

## ✅ Critérios de aceite
- [ ] `_process_new_candle` finaliza sem aguardar commit no banco.
- [ ] WebSocket continua emitindo mesmo com lentidão/erro transitório de banco.
- [ ] Persistência ocorre em background com evidência de fila/task ativa.
- [ ] Testes cobrindo independência entre broadcast e persistência, incluindo cenário de falha de write.

---

## 📊 Estimativa
- **Story Points:** 8
- **Horas:** 10h–14h
- **Prioridade:** 🔴 ALTA

---

## 🔗 Dependências cruzadas (Slice 1)
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_MONITOR_ALWAYS_ON_SINGLETON.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_LAZY_LOADING_ML_CACHE.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_CONTRATO_WS_PYDANTIC_STRICT.md`
- `ISSUES/ISSUE_GUARDIAN_SLICE1_MASTER_TESTES_REALTIME.md`
- `ISSUES/ISSUE_ARCHITECT_EPIC_SLICE1_INTEGRACAO_SHARED_BRANCH.md`

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md` (seção Eventual Consistency / Background Persistence)
- `.memory-bank/activeContext.md` (estratégia de banco definida no Slice 1)
