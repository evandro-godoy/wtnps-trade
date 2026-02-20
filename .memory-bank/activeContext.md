# Active Context: WTNPS-TRADE

## 🎯 Objetivo Atual (O que estamos construindo agora?)
Estamos na fase de consolidação do "Monólito Funcional". O foco imediato é finalizar a integração entre o backend FastAPI (orquestrando o `MonitorEngine` e WebSockets) e a interface gráfica baseada em Jinja2 e Plotly (`charts_clean.html`). 

A meta é ter uma aplicação executável via VS Code, ponta a ponta, que:
1. Conecte no MetaTrader 5 e carregue dados híbridos (Parquet + Live).
2. Processe indicadores e inferência ML (modelos Keras) em background.
3. Exiba o gráfico de candlesticks atualizado em tempo real na tela do usuário, plotando também as médias móveis e sinais sem travar o navegador.

## 🚧 Tarefas Imediatas
* Centralizar e estabilizar as rotas no `newapp/src/api/main.py`.
* Garantir que o `WebSocketManager` envie corretamente os payloads JSON contendo as barras e indicadores (ex: SMA 21, SMA 200, EMA 9).
* Ajustar o frontend (`live_chart.js` / `charts_clean.html`) para consumir o WebSocket de forma performática.
* Ajustar os agentes de IA na IDE para que utilizem estritamente este Memory Bank e parem de propor refatorações arquiteturais prematuras (ex: EventBus puro).

## 🧭 Sprint Ativa (2026-02-20) — Monitor + Charts Integration
O foco imediato foi decomposto em 3 handoffs especializados com labels e escopo fechado:

1. **@BackendQuant** — unificação do pipeline de predição (ML + análise técnica) e correção de first tick no monitor realtime.
2. **@Fullstack** — correção do parser/render da análise técnica no Charts e ajuste de consumo WebSocket no Monitor.
3. **@Guardian** — validação de contrato do payload combinado e regressão funcional.

Artefatos oficiais desta sprint:
- `ISSUES/ISSUE_BACKENDQUANT_UNIFICACAO_ML_ANALISE_FIRST_TICK.md`
- `ISSUES/ISSUE_FULLSTACK_CHARTS_ANALISE_E_MONITOR_WS.md`
- `ISSUES/ISSUE_GUARDIAN_TESTES_PAYLOAD_COMBINADO.md`
- `.memory-bank/SPRINT_2026-02-20_MONITOR_CHARTS_HANDOFF.md`

## ⚠️ Decisões Recentes e Restrições Ativas
* **ABANDONADA TEMPORARIAMENTE:** A migração completa para o padrão "Canonical Layout" e arquitetura estrita orientada a eventos (`EventBus`).
* **FOCO EXCLUSIVO:** A pasta `newapp/` e seus subdiretórios representam o código-fonte principal no momento.
* **REGRA CRÍTICA:** Não introduzir complexidade desnecessária. Faça funcionar de forma fluida primeiro.