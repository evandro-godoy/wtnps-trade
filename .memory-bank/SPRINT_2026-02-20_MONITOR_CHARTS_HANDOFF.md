# Sprint Handoff — Monitor + Charts Integration

**Data:** 2026-02-20  
**Responsável de Orquestração:** Architect  
**Status:** Issues preparadas para execução por agentes especializados

---

## Objetivo da Sprint
Resolver integração de negócio entre monitor realtime e interface:
1. Corrigir módulo de Análise Técnica no Charts.
2. Garantir first tick imediato ao iniciar monitor.
3. Unificar saída de ML + Análise Técnica antes do envio ao frontend.

---

## Decisões Arquiteturais
- Manter monólito FastAPI em `newapp/`.
- Manter comunicação via instâncias diretas + background tasks + WebSocket.
- Não introduzir EventBus, microservices ou brokers.
- Consolidar contrato de payload no backend como fonte única de verdade.

---

## Contrato de payload alvo
Campos mandatórios:
- `timestamp`, `ticker`, `timeframe`
- `ohlcv`
- `indicators`
- `analysis`
- `ml`
- `decision`

Compatibilidade legada pode existir como adapter de rota, não como contrato principal.

---

## Handoffs emitidos
- `ISSUES/ISSUE_BACKENDQUANT_UNIFICACAO_ML_ANALISE_FIRST_TICK.md`
- `ISSUES/ISSUE_FULLSTACK_CHARTS_ANALISE_E_MONITOR_WS.md`
- `ISSUES/ISSUE_GUARDIAN_TESTES_PAYLOAD_COMBINADO.md`

---

## Dependências entre agentes
- BackendQuant entrega contrato canônico e first tick.
- Fullstack adapta consumo frontend para contrato canônico.
- Guardian valida contrato + realtime + regressão.

---

## Critério de conclusão da Sprint
- Monitor envia first tick sem espera de novo candle.
- Charts exibe análise técnica sem erro de parsing.
- Payload combinado validado por testes QA.
