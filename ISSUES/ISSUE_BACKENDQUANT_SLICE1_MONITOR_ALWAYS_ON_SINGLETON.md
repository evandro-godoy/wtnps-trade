# [BACKENDQUANT] Slice 1 — RealtimeMarketMonitor Always-On (Singleton) + WS Broadcast Centralizado

**Assignee:** @BackendQuant  
**Labels:** `backend`, `quant`, `realtime`, `websocket`, `monitor`, `priority:high`, `slice-1`, `newapp` 
**Milestone sugerido:** Slice 1 — Fundação do Monitor em Tempo Real

> **Instrução de integração (obrigatória):** Todos os commits e Pull Requests desta tarefa devem ter como alvo a branch `feature/monitor-slice-1` e **NÃO** a `main`.

---

## 📋 Contexto
No Slice 1, o monitor em tempo real precisa deixar de depender de ação manual da UI para existir. A arquitetura alvo define um motor centralizado **Always-On**, com **instância única por ativo**, inicializado no `lifespan` do FastAPI.

A UI e o endpoint WS devem apenas consumir/broadcast do motor centralizado, sem iniciar/parar engine por clique de usuário.

---

## 🎯 Objetivo
Refatorar o fluxo backend para que:
1. `RealtimeMarketMonitor` seja singleton por ativo/timeframe (`WDO$` e `WIN$` no bootstrap).
2. O motor seja inicializado no `lifespan` do FastAPI e execute em background de forma contínua.
3. `monitor_ws.py` atue somente como camada de broadcast/stream para clientes conectados.
4. A decisão/validação seja desacoplada do sinal ML via **Strategy Pattern** (Decision Block).

---

## 📁 Arquivos-alvo
- `newapp/src/live/monitor_engine.py`
- `newapp/src/api/lifespan.py`
- `newapp/src/api/websockets/monitor_ws.py`
- `newapp/src/services/monitor_runtime.py` (se aplicável)
- `newapp/src/analysis/context_analyzer.py` (integração da validação)
- `newapp/src/.../decision_*` (novo módulo Strategy para bloco `decision`, se necessário)

---

## 🔧 Tarefas
- [ ] Implementar registro central de monitores (singleton por chave `ticker+timeframe`) com proteção contra dupla inicialização.
- [ ] Inicializar monitores principais (`WDO$`, `WIN$`) durante startup no `lifespan`.
- [ ] Garantir execução em background sem bloquear thread principal do FastAPI.
- [ ] Remover dependência de start/stop do motor por eventos de UI no fluxo padrão.
- [ ] Refatorar `monitor_ws.py` para consumir stream já existente e somente fazer broadcast para conexões ativas.
- [ ] Definir interface Strategy para `Decision Block` (ex.: `DecisionValidationStrategy`) e conectar no pipeline após inferência ML.
- [ ] Implementar estratégia default de validação preservando regras atuais (RSI/pattern) sem acoplamento ao código de inferência.
- [ ] Garantir shutdown limpo no lifespan (encerrar tasks/threads corretamente).

---

## ✅ Critérios de aceite
- [ ] Existe apenas **1 instância** de monitor por ativo/timeframe em runtime.
- [ ] Em startup da aplicação, monitores de `WDO$` e `WIN$` sobem automaticamente.
- [ ] Reconexões WebSocket não criam nova instância do motor.
- [ ] `monitor_ws.py` não contém lógica de controle de ciclo de vida do motor.
- [ ] Bloco `decision` é produzido via Strategy (interface + implementação default), desacoplado da etapa de sinal ML.
- [ ] Fluxo contínuo de emissão mantém estabilidade sem bloquear API/WS.

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md` (Singleton/Always-On e comunicação WS)
- `.memory-bank/activeContext.md` (Slice 1 Fundação)
- `newapp/ARCHITECTURE.md`

---

## 🔗 Dependências cruzadas (Slice 1)
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_LAZY_LOADING_ML_CACHE.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_PERSISTENCIA_DESACOPLADA_BACKGROUND.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_CONTRATO_WS_PYDANTIC_STRICT.md`
- `ISSUES/ISSUE_GUARDIAN_SLICE1_MASTER_TESTES_REALTIME.md`
- `ISSUES/ISSUE_ARCHITECT_EPIC_SLICE1_INTEGRACAO_SHARED_BRANCH.md`
