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

## Regra de consolidação (legado obrigatório na Sprint)

### Thresholds estritos de severidade
- `ALERT` quando `ml.probability > 0.65`
- `INFO` quando `ml.probability > 0.55` e não `ALERT`
- `TICK` nos demais casos (`<= 0.55`)

Regras de borda obrigatórias:
- `0.65` não é `ALERT`
- `0.55` não é `INFO`

### Trava técnica no bloco `decision`
Antes de emitir no WebSocket, o backend deve validar o sinal ML contra contexto técnico:
- Bloquear `COMPRA/CALL` se `rsi_condition == SOBRECOMPRADO`
- Bloquear `VENDA/PUT` se `rsi_condition == SOBREVENDIDO`
- Bloquear `COMPRA/CALL` se `pattern == REJEICAO_ALTA`
- Bloquear `VENDA/PUT` se `pattern == REJEICAO_BAIXA`

No fluxo realtime atual, tendência é contexto e não bloqueio por padrão (`require_trend_alignment=False`).

Campos mínimos no `decision`:
- `signal_valid`
- `validation_reason`
- status equivalente a `VALIDADO`/`NÃO VALIDADO`

### Semântica visual (equivalência com legado)
- `ALERT`: fundo `#fff3cd`, texto `#856404`, ícone `🚨`
- `INFO`: fundo `#d1ecf1`, texto `#0c5460`, ícone `📊`
- `TICK`: fundo `#ffffff`, texto `#6c757d`
- Validação: `✅` para válido e `⚠️` para não validado

---

## Handoffs emitidos
- `ISSUES/ISSUE_BACKENDQUANT_UNIFICACAO_ML_ANALISE_FIRST_TICK.md`
- `ISSUES/ISSUE_FULLSTACK_CHARTS_ANALISE_E_MONITOR_WS.md`
- `ISSUES/ISSUE_FULLSTACK_MONITOR_GRID_ANALITICO_SEM_CANDLESTICK.md` *(referência cruzada da diretriz UX mais recente para Monitor Grid analítico)*
- `ISSUES/ISSUE_GUARDIAN_TESTES_PAYLOAD_COMBINADO.md`

## Execução em paralelo
- @Fullstack está atuando em paralelo na issue `ISSUES/ISSUE_FULLSTACK_MONITOR_GRID_ANALITICO_SEM_CANDLESTICK.md` enquanto os demais handoffs seguem seu fluxo de validação e integração.

---

## Dependências entre agentes
- BackendQuant entrega contrato canônico e first tick.
- Fullstack adapta consumo frontend para contrato canônico.
- Guardian valida contrato + realtime + regressão.

---

## Critério de conclusão da Sprint
- Monitor envia first tick sem espera de novo candle.
- Charts exibe análise técnica sem erro de parsing.
- Monitor Grid aplica severidade/cores/ícones conforme thresholds estritos do legado.
- Payload inclui `decision` com bloqueio técnico aplicado antes do broadcast.
- Payload combinado validado por testes QA.
