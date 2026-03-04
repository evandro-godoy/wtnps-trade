# [GUARDIAN] Slice 1 — Testes de Singleton por Ativo + Emissão Contínua WebSocket

> **Status:** SUBSTITUÍDA por `ISSUES/ISSUE_GUARDIAN_SLICE1_MASTER_TESTES_REALTIME.md`.
> 
> Esta issue foi consolidada na issue master para evitar sobreposição de escopo.
> Não executar este escopo de forma isolada.

**Assignee:** @Guardian  
**Labels:** `qa`, `testing`, `guardian`, `websocket`, `realtime`, `priority:high`, `slice-1`  
**Milestone sugerido:** Slice 1 — Fundação do Monitor em Tempo Real

> **Instrução de integração (obrigatória):** Todos os commits e Pull Requests desta tarefa devem ter como alvo a branch `feature/monitor-slice-1` e **NÃO** a `main`.

---

## 📋 Contexto
Com a adoção do modelo Always-On no backend, precisamos de validação formal para evitar regressões críticas: múltiplas instâncias de monitor por ativo e interrupções silenciosas no stream WS.

---

## 🎯 Objetivo
Criar testes automatizados e de integração que comprovem:
1. O runtime mantém **uma única instância** de monitor por ativo/timeframe (Singleton).
2. O endpoint WebSocket emite eventos continuamente a partir do motor centralizado.
3. Reconexão de cliente não cria novo motor.

---

## 📁 Escopo de validação
- `newapp/src/live/monitor_engine.py`
- `newapp/src/api/lifespan.py`
- `newapp/src/api/websockets/monitor_ws.py`
- `newapp/src/services/monitor_runtime.py` (se aplicável)
- `newapp/tests/` (novos testes unitários/integração)

---

## 🧪 Plano de testes
- [ ] **Singleton Registry Test:** ao pedir monitor repetidamente para mesmo `ticker+timeframe`, retorna mesma instância.
- [ ] **Startup Bootstrap Test:** no startup, `WDO$` e `WIN$` são registrados uma vez cada.
- [ ] **No Duplicate on Reconnect Test:** reconectar WS não incrementa contagem de instâncias.
- [ ] **Continuous WS Stream Test:** cliente recebe sequência contínua de mensagens por janela de tempo definida.
- [ ] **Liveness/Heartbeat Test (se aplicável):** confirmar que monitor não entra em estado morto sem erro explícito.

---

## ✅ Critérios de aceite
- [ ] Testes de singleton e stream adicionados em `newapp/tests/` com execução reproduzível.
- [ ] Evidência de que há 1 instância por ativo/timeframe, sem race-condition básica.
- [ ] Endpoint WS apresenta emissões contínuas sob carga leve (mínimo 1 cliente conectado).
- [ ] Relatório de QA com resultado dos casos (Pass/Fail), logs e riscos residuais.

---

## 📤 Entregável esperado
Relatório Guardian contendo:
- Matriz de casos de teste
- Evidências (logs/outputs)
- Recomendação de merge para conclusão do Slice 1

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md` (Singleton/Always-On)
- `.memory-bank/activeContext.md` (Slice 1 Fundação)
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_MONITOR_ALWAYS_ON_SINGLETON.md`
- `ISSUES/ISSUE_FULLSTACK_SLICE1_BASE_TEMPLATE_MONITOR_PASSIVO_WS.md`
