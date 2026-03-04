# [GUARDIAN] Slice 1 — Suíte de Testes do RealtimeMarketMonitor com Replay DB (sem MT5)

> **Status:** SUBSTITUÍDA por `ISSUES/ISSUE_GUARDIAN_SLICE1_MASTER_TESTES_REALTIME.md`.
> 
> Esta issue foi consolidada na issue master para evitar sobreposição de escopo.
> Não executar este escopo de forma isolada.

**Assignee:** @Guardian  
**Labels:** `qa`, `testing`, `guardian`, `realtime`, `monitor`, `slice-1`, `priority:high`, `newapp`  
**Milestone sugerido:** Slice 1 — Fundação do Monitor em Tempo Real

> **Instrução de integração (obrigatória):** Todos os commits e Pull Requests desta tarefa devem ter como alvo a branch `feature/monitor-slice-1` e **NÃO** a `main`.

---

## 📋 Contexto
A estratégia de testes do Slice 1 foi definida: validar o `RealtimeMarketMonitor` em CI usando **Replay Engine com banco de dados**, sem depender de MetaTrader 5.

⚠️ **Regra de Ouro:** o comportamento de produção do MT5 (`mt5.initialize()`, abertura do terminal, etc.) **não pode ser alterado**. O isolamento deve ocorrer apenas por injeção de provider no contexto de teste.

---

## 🎯 Objetivo
Criar a suíte automatizada do monitor realtime cobrindo fluxo de processamento e emissão de eventos canônicos, com fonte de dados vinda das tabelas existentes do banco (Assets/Rates), sem invocar MT5 no `pytest`.

---

## 📁 Arquivos-alvo
- `newapp/tests/` (novos testes unitários/integração)
- `newapp/src/live/monitor_engine.py` (pontos de injeção, se já expostos)
- `newapp/src/database/repository.py` (uso do acesso a dados existente)
- `newapp/src/api/websockets/monitor_ws.py` (contrato de emissão)

---

## 🧪 Requisitos obrigatórios

### Requisito 1 — Injeção de provider histórico do banco
- [ ] Instanciar o monitor com provider falso/replay injetado por DI.
- [ ] Provider de replay deve consumir candles diretamente do banco do projeto (tabelas de Assets/Rates pré-existentes).
- [ ] Cenário de teste não deve depender de MT5 local.

### Requisito 2 — Processamento + emissão canônica
- [ ] Validar que o monitor processa candles vindos do replay DB.
- [ ] Validar emissão de eventos para fila/callback do WebSocket no formato canônico mínimo:
  - `ohlcv`
  - `indicators`
  - `ml`
- [ ] Verificar coerência temporal e sequência de mensagens (ordem dos candles).

### Requisito 3 — MT5 não invocado no pytest
- [ ] Garantir por teste (spy/mock/patch) que `mt5.initialize()` não é chamado.
- [ ] Garantir que nenhum caminho de abertura de terminal MT5 é executado durante a suíte.
- [ ] Documentar no relatório de QA a evidência de isolamento do MT5.

---

## ✅ Critérios de aceite
- [ ] Suíte executa em CI sem MetaTrader instalado/aberto.
- [ ] Testes passam consumindo dados de replay via banco do projeto.
- [ ] Payloads emitidos pelo monitor preservam contrato canônico esperado pelo WS.
- [ ] Evidência explícita de não invocação de `mt5.initialize()` durante `pytest`.
- [ ] Relatório final com casos, logs e riscos residuais.

---

## 📤 Entregável esperado
Relatório Guardian contendo:
- Matriz de casos (Pass/Fail)
- Evidências de payload emitido
- Evidências de isolamento MT5
- Recomendação de merge para conclusão do Slice 1

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md` (seção de testes realtime por DI/replay)
- `.memory-bank/activeContext.md` (fluxo de testes do Slice 1 definido)
- `ISSUES/ISSUE_GUARDIAN_SLICE1_TESTES_SINGLETON_E_STREAM_WS.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_MONITOR_ALWAYS_ON_SINGLETON.md`
