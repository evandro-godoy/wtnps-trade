# [GUARDIAN][MASTER] Slice 1 — Suíte Unificada de Testes do RealtimeMarketMonitor (Singleton + Stream WS + Replay DB sem MT5)

**Assignee:** @Guardian  
**Labels:** `qa`, `testing`, `guardian`, `realtime`, `monitor`, `websocket`, `slice-1`, `priority:high`, `newapp`  
**Milestone sugerido:** Slice 1 — Fundação do Monitor em Tempo Real

> **Instrução de integração (obrigatória):** Todos os commits e Pull Requests desta tarefa devem ter como alvo a branch `feature/monitor-slice-1` e **NÃO** a `main`.

---

## 📋 Contexto
Esta issue consolida integralmente o escopo das issues Guardian do Slice 1 para eliminar sobreposição de execução.

Escopo consolidado:
1. Garantir padrão **Singleton/Always-On** por ativo/timeframe.
2. Validar **emissão contínua** no endpoint WebSocket a partir do motor centralizado.
3. Executar suíte com **Replay Engine via banco** por DI, garantindo que o MT5 não seja invocado no `pytest`.

⚠️ **Regra de Ouro:** o comportamento de produção do MT5 (`mt5.initialize()`, abertura do terminal etc.) permanece inalterado; o isolamento ocorre apenas em testes por provider injetado.

---

## 🎯 Objetivo
Criar a suíte automatizada completa do `RealtimeMarketMonitor` para validar ciclo de vida, processamento de candles históricos do banco e emissão do payload canônico no canal de callback/fila WebSocket, sem dependência de MetaTrader no CI.

---

## 📁 Arquivos-alvo
- `newapp/tests/` (novos testes unitários/integração)
- `newapp/src/live/monitor_engine.py`
- `newapp/src/api/lifespan.py`
- `newapp/src/api/websockets/monitor_ws.py`
- `newapp/src/services/monitor_runtime.py` (se aplicável)
- `newapp/src/database/repository.py` (reuso do acesso existente ao DB)

---

## 🧪 Plano de testes unificado

### A) Singleton e ciclo de vida Always-On
- [ ] **Singleton Registry Test:** mesma chave `ticker+timeframe` retorna a mesma instância.
- [ ] **Startup Bootstrap Test:** `WDO$` e `WIN$` sobem uma única vez no startup.
- [ ] **No Duplicate on Reconnect Test:** reconexão WS não cria nova instância.

### B) Replay via banco com DI (sem MT5)
- [ ] Instanciar monitor com provider replay/fake injetado por DI.
- [ ] Provider replay consome candles das tabelas de Assets/Rates já existentes no banco do projeto.
- [ ] Fluxo de teste não depende de MT5 local/terminal aberto.

### C) Processamento e emissão de eventos canônicos
- [ ] Validar processamento de candles vindos do replay DB.
- [ ] Validar emissão para callback/fila WS contendo, no mínimo:
  - `ohlcv`
  - `indicators`
  - `ml`
- [ ] Validar continuidade do stream (3+ mensagens), ordem temporal e liveness.

### D) Prova de isolamento do MT5 no pytest
- [ ] Garantir por spy/mock/patch que `mt5.initialize()` não é chamado.
- [ ] Garantir que nenhum caminho de abertura do terminal MT5 é executado.
- [ ] Evidenciar em relatório/log de testes o isolamento completo.

---

## ✅ Critérios de aceite
- [ ] Suíte executa em CI sem MetaTrader instalado/aberto.
- [ ] Evidência de 1 instância por ativo/timeframe (sem duplicação em reconnect WS).
- [ ] Stream WS contínuo e estável sob carga leve (mínimo 1 cliente).
- [ ] Payload emitido mantém contrato canônico esperado.
- [ ] Evidência explícita de que `mt5.initialize()` não foi invocado no `pytest`.
- [ ] Relatório final QA com matriz de casos, logs e riscos residuais.

---

## 📤 Entregável esperado
Relatório Guardian consolidado com:
- Matriz de casos (Pass/Fail)
- Evidências de payload e stream contínuo
- Evidências de singleton por ativo/timeframe
- Evidências de isolamento do MT5
- Recomendação de merge para conclusão do Slice 1

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md`
- `.memory-bank/activeContext.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_MONITOR_ALWAYS_ON_SINGLETON.md`
- `ISSUES/ISSUE_FULLSTACK_SLICE1_BASE_TEMPLATE_MONITOR_PASSIVO_WS.md`
