# Active Context: WTNPS-TRADE

## 🎯 Objetivo Atual (O que estamos construindo agora?)
Estamos na fase de consolidação do "Monólito Funcional". O foco imediato é finalizar a integração entre o backend FastAPI (orquestrando o `MonitorEngine` e WebSockets) e duas visões de frontend claramente separadas: Charts e Monitor.

A meta é ter uma aplicação executável via VS Code, ponta a ponta, que:
1. Conecte no MetaTrader 5 e carregue dados híbridos (Parquet + Live).
2. Processe indicadores e inferência ML (modelos Keras) em background.
3. Exiba dados em tempo real sem travar o navegador, respeitando o propósito de cada visão.

### Decisão Arquitetural de Frontend (Sprint Atual)
* **Separação explícita de responsabilidades:**
	* **Charts View:** responsável por visualização gráfica (candlestick/plotagem).
	* **Monitor View:** responsável por leitura analítica rápida em **Grid** (cards/tabelas) com dados consolidados de `ml`, `decision`, `analysis` e `indicators`.
* **Novo escopo do Monitor:** não renderizar candlestick/Plotly; priorizar interpretação de sinal e validação operacional.
* **Contrato de dados mantido:** o Monitor continua consumindo payload unificado via WebSocket, sem alterar o loop do `MonitorEngine`.

### Regra Estrita de Consolidação de Sinais (Legado)
* **Classificação por probabilidade (comparador estrito):**
	* `ALERT` quando `ml.probability > 0.65`.
	* `INFO` quando `ml.probability > 0.55` e não `ALERT`.
	* `TICK` nos demais casos (`<= 0.55`).
* **Bordas obrigatórias:** `0.65` não é `ALERT`; `0.55` não é `INFO`.
* **Trava de contexto técnico no bloco `decision`:**
	* Bloquear `COMPRA/CALL` se `rsi_condition == SOBRECOMPRADO`.
	* Bloquear `VENDA/PUT` se `rsi_condition == SOBREVENDIDO`.
	* Bloquear `COMPRA/CALL` se `pattern == REJEICAO_ALTA`.
	* Bloquear `VENDA/PUT` se `pattern == REJEICAO_BAIXA`.
* **Alinhamento de tendência:** no realtime atual, tendência contextualiza; não bloqueia por padrão (`require_trend_alignment=False`).
* **Semântica de decisão no payload:** sempre expor `decision.signal_valid`, `decision.validation_reason` e status equivalente a `VALIDADO`/`NÃO VALIDADO`.
* **Semântica visual (equivalência com legado):**
	* `ALERT`: fundo `#fff3cd`, texto `#856404`, ícone `🚨`.
	* `INFO`: fundo `#d1ecf1`, texto `#0c5460`, ícone `📊`.
	* `TICK`: fundo `#ffffff`, texto `#6c757d`.
	* `decision.signal_valid=true`: destaque com `✅`; `false`: destaque com `⚠️`.

## 🚧 Tarefas Imediatas
* Centralizar e estabilizar as rotas no `newapp/src/api/main.py`.
* Garantir que o `WebSocketManager` envie corretamente os payloads JSON contendo as barras e indicadores (ex: SMA 21, SMA 200, EMA 9).
* Ajustar o frontend de forma segmentada:
	* Charts (`live_chart.js` / `charts_clean.html`) para visualização gráfica.
	* Monitor (`monitor.html` / `monitor.js`) para grid analítico sem chart.
* Ajustar os agentes de IA na IDE para que utilizem estritamente este Memory Bank e parem de propor refatorações arquiteturais prematuras (ex: EventBus puro).

## 🧭 Sprint Ativa (2026-02-20) — Monitor + Charts Integration
O foco imediato foi decomposto em 3 handoffs especializados com labels e escopo fechado:

1. **@BackendQuant** — unificação do pipeline de predição (ML + análise técnica) e correção de first tick no monitor realtime.
2. **@Fullstack** — correção do parser/render da análise técnica no Charts e ajuste de consumo WebSocket no Monitor.
3. **@Guardian** — validação de contrato do payload combinado e regressão funcional.

Artefatos oficiais desta sprint:
- `ISSUES/ISSUE_BACKENDQUANT_UNIFICACAO_ML_ANALISE_FIRST_TICK.md`
- `ISSUES/ISSUE_FULLSTACK_CHARTS_ANALISE_E_MONITOR_WS.md`
- `ISSUES/ISSUE_FULLSTACK_MONITOR_GRID_ANALITICO_SEM_CANDLESTICK.md`
- `ISSUES/ISSUE_GUARDIAN_TESTES_PAYLOAD_COMBINADO.md`
- `.memory-bank/SPRINT_2026-02-20_MONITOR_CHARTS_HANDOFF.md`

## ⚠️ Decisões Recentes e Restrições Ativas
* **ABANDONADA TEMPORARIAMENTE:** A migração completa para o padrão "Canonical Layout" e arquitetura estrita orientada a eventos (`EventBus`).
* **FOCO EXCLUSIVO:** A pasta `newapp/` e seus subdiretórios representam o código-fonte principal no momento.
* **REGRA CRÍTICA:** Não introduzir complexidade desnecessária. Faça funcionar de forma fluida primeiro.## ?? UI/UX Visual Density & Formatting Guidelines
### Contexto do Problema (Sprint 2026-02-20)
A UI nova (
ewapp/templates/monitor.html) apresenta densidade visual insuficiente em compara??o com a UI legada (src/gui/monitor_ui.py):
- **Legado:** ~20?25 eventos simult?neos vis?veis (Treeview com 2 tabs).
- **Novo:** ~8 itens vis?veis (Grid com 4 cards compactos).
**Decis?o:** Implementar tabela densa com 25+ linhas vis?veis, sticky header, resumo cards horizontal (60px), e formata??o rigorosa (2 casas decimais, larguras fixas).
### Estrutura de Layout Aprovada
\\\
???????????????????????????????????????????????????
? STICKY HEADER (50px)                            ?
? Status: 5 monitores | Last: 15:30:42 | Eventos: 237
???????????????????????????????????????????????????
? RESUMO HORIZONTAL (3 cards, 60px)              ?
? [?? ML Signals: 156] [?? Decision: 23] [?? Ind: 4]
???????????????????????????????????????????????????
? TABELA DENSA (25+ rows, max-h 500px, scroll)   ?
? TIME    ? TICKER ? TYPE ? PRICE ? PROB ? SINAL ? STATUS
? 15:30:42? WDO\$   ? ??   ? 95.60 ? 72.00?COMPRA ? ?
? 15:30:35? WIN\$   ? ??   ? 27.53 ? 62.50?VENDA  ? ??
? ...     ?        ?      ?       ?      ?       ?
???????????????????????????????????????????????????
\\\
### Especifica??es de Coluna
| Coluna | Largura | Formato | Alinhamento | Exemplo |
|--------|---------|---------|-------------|---------|
| TIME | 70px | HH:MM:SS (2 dig.) | right | 15:30:42 |
| TICKER | 65px | Symbol | center | WDO\$ |
| TYPE | 60px | Severity Icon | center | ?? |
| PRICE | 90px | 2 decimais | right | 95.60 |
| PROB | 70px | 2 decimais + % | right | 72.00 |
| SIGNAL | 80px | COMPRA/VENDA/HOLD | center | COMPRA |
| STATUS | 75px | Icon + state | center | ? / ?? |
**Total:** ~510px (acomoda telas 1024+ com margem esquerda).
### Mapeamento de Cores (Severity por Evento)
| Categoria | ?cone | Background | Text | Regra |
|-----------|-------|------------|------|-------|
| ALERT | ?? | #fff3cd | #856404 | prob > 0.65 |
| INFO | ?? | #d1ecf1 | #0c5460 | 0.55 < prob ? 0.65 |
| TICK | ? | #ffffff | #6c757d | prob ? 0.55 |
### Status (Coluna)
| Status | ?cone | Condi??o |
|--------|-------|----------|
| VALID | ? | decision.signal_valid == true |
| BLOCKED | ?? | decision.signal_valid == false |
### Requisitos Formata??o
1. Time: HH:MM:SS com 2 d?gitos
2. Pre?o: 2 casas decimais
3. Probabilidade: 2 casas decimais + %
4. Signal: UPPERCASE (COMPRA/VENDA/HOLD)
5. Altura linha: 32px
6. Font-size: 12px
7. Header sticky com top: 0
### Implementa??o
Ver: ISSUES/ISSUE_FULLSTACK_MONITOR_UI_DENSITY_IMPROVEMENT.md
`
