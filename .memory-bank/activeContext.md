# Active Context: WTNPS-TRADE

## 🎯 Objetivo Atual (O que estamos construindo agora?)
Estamos na fase de estabilização do módulo de monitoramento de mercado em fatias verticais (**Vertical Slicing**).

### Status Atual de Slices (Atualizado em 2026-03-04)
* **Slice 1 (Fundação):** encerrado e integrado.
* **Slice 2 (Motor de Regras):** encerrado e integrado com sucesso.
* **Slice 3 (Controlo de Fluxo e Frequência):** iniciado.

### Sprint Ativa (2026-03-04) — Slice 3: Controlo de Fluxo e Frequência
Objetivo desta sprint: permitir que cada cliente WebSocket escolha a densidade de atualização (`tick`, `close`, `hybrid`) sem alterar o throughput do motor singleton.

### Fluxo de integração definido (Git) para o Slice 3
* **Modelo:** Shared Feature Branch para coordenação multiagente.
* **Branch oficial do slice:** `feature/monitor-slice-3-frequency` (baseada em `main`).
* **Regra ativa:** todos os PRs do Slice 3 devem apontar exclusivamente para `feature/monitor-slice-3-frequency`.
* **Gate de merge:** promoção para `main` apenas após validação ponta a ponta do Architect.

### Status do Slice 1 (Fundação)
**Concluído em arquitetura e pronto para execução técnica.**

### Fluxo de integração definido (Git)
* **Modelo:** Shared Feature Branch para coordenação multiagente no Slice 1.
* **Branch oficial do slice:** `feature/monitor-slice-1` (baseada em `main`).
* **Regra ativa:** nenhum PR desta fase deve apontar para `main`; todos devem apontar para `feature/monitor-slice-1`.
* **Gate de merge:** promoção para `main` somente após validação ponta a ponta do Architect.

O foco imediato da equipe é o **Slice 1: Fundação do Monitor em Tempo Real**, com três pilares estruturantes:
1. **Backend Always-On:** `RealtimeMarketMonitor` como singleton centralizado, inicializado no `lifespan` do FastAPI para os ativos principais (`WDO$` e `WIN$`).
2. **WebSocket passivo no frontend:** clientes apenas consomem e exibem stream, sem acionar start/stop do motor central.
3. **Template Inheritance no Jinja2:** adoção de `base.html` para eliminar duplicação de layout (ex.: sidebar) entre `monitor.html` e `charts.html`.

### Progresso de definições arquiteturais do Slice 1
As definições-base da fundação foram expandidas e agora incluem também a estratégia de inferência ML:
* **Lazy Loading de modelos/scalers:** artefatos `.keras` e `.joblib` são carregados sob demanda no primeiro candle com predição.
* **Cache em memória:** após o primeiro load, modelos permanecem em cache por ativo/estratégia/timeframe.
* **Proteção do Event Loop:** carregamento pesado de TensorFlow/Keras/Joblib deve ocorrer em thread separada (`asyncio.to_thread`) para não bloquear API nem WebSockets.
* **Persistência desacoplada (Eventual Consistency):** envio via WebSocket é prioritário; gravação em banco ocorre em background assíncrono (queue/task), sem bloquear `_process_new_candle`.
* **Contrato estrito WS com Pydantic:** payload é validado/serializado no backend com schema canônico (`MonitorPayload`) e formato pronto para UI.

### Estratégia de Testes definida para Slice 1 (realtime)
O fluxo de testes automatizados do `RealtimeMarketMonitor` foi definido e congelado para esta fase:
* **Padrão:** Replay Engine com banco de dados usando Injeção de Dependência (DI) da fonte de candles.
* **Fonte de teste:** tabelas históricas do banco do projeto (Assets/Rates) em SQLite/SQL Server/Postgres.
* **Regra de ouro:** o comportamento de produção do MT5 **não pode** ser alterado; em `pytest`, o MT5 não deve ser invocado.
* **Meta:** validar o loop de negócio e o payload canônico de eventos sem depender de terminal MetaTrader no CI.

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
* Executar implementação do `MonitorPayload` (Pydantic) no backend WS e remover regras de fallback/formatação do frontend.
* Concluir refactors já definidos no Slice 1: singleton always-on, lazy loading ML, persistência desacoplada e suíte de testes Guardian.
* Consolidar validação de contrato canônico entre backend, WS e testes automatizados.

## 🧭 Sprint Ativa (2026-03-04) — Slice 1: Fundação do Monitor em Tempo Real
O recorte atual foi definido como fundação arquitetural para os próximos slices:

1. **@BackendQuant** — motor realtime always-on + singleton por ativo/timeframe + broadcast desacoplado da UI.
2. **@Fullstack** — base template compartilhado (Jinja2 inheritance) + monitor frontend passivo ao WS.
3. **@Guardian** — testes de singleton e continuidade de emissão de eventos WS.

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
