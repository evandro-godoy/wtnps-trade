# [FULLSTACK] Monitor analítico em Grid (sem candlestick) com payload unificado

**Assignee:** @Fullstack  
**Labels:** `frontend`, `fullstack`, `monitor`, `websocket`, `ux`, `priority:high`  
**Milestone sugerido:** Sprint atual

---

## 📋 Contexto
A diretriz de negócio/UX foi atualizada: a view Monitor deve ser exclusivamente analítica e equalizada ao destaque informacional do legado (sinais ML + análise técnica + decisão), sem gráfico candlestick.

Referências:
- `.memory-bank/activeContext.md`
- `src/gui/monitor_ui.py`
- `newapp/templates/monitor.html`
- `newapp/static/js/monitor.js`

---

## 🎯 Objetivo
Refatorar o Monitor para um layout Grid analítico que consuma o payload WS canônico recém-unificado pelo BackendQuant, removendo qualquer dependência de visualização candlestick nesta tela e preservando a semântica visual operacional do legado.

---

## 📁 Escopo fechado (arquivos-alvo)
- `newapp/templates/monitor.html`
- `newapp/static/js/monitor.js`
- `newapp/static/css/style.css` (somente se necessário para estilo compartilhado)

---

## 🧱 Contrato de dados obrigatório (BackendQuant)
Consumir diretamente os blocos:
- `timestamp`, `ticker`, `timeframe`
- `ml`
- `decision`
- `analysis`
- `indicators`
- `ohlcv` (apenas para resumo numérico; não para chart)

Campos adicionais esperados para render semântica:
- `severity`: `ALERT|INFO|TICK` (ou derivado localmente por `ml.probability`)
- `decision.signal_valid`: `true|false`
- `decision.validation_reason`: `string`

---

## 🔧 Tarefas
- [ ] Remover do Monitor qualquer estrutura de chart/candlestick (UI e JS).
- [ ] Implementar layout com CSS Grid para leitura rápida por ativo/timeframe.
- [ ] Criar 4 blocos analíticos explícitos: `ml`, `decision`, `analysis`, `indicators`.
- [ ] Manter card de resumo com status, close, variação e timestamp.
- [ ] Atualizar `monitor.js` para render incremental por chave `ticker+timeframe`.
- [ ] Garantir fallback robusto para campos ausentes (`N/A`, sem exceptions).
- [ ] Manter controles Play/Stop e estados visuais ativo/inativo.
- [ ] Preservar log/tabela de eventos recentes com limite de itens (rolling).

### 🎨 Regras visuais obrigatórias (equivalência com legado)
- [ ] Implementar mapeamento de categoria por threshold legado (comparador estrito):
	- `ALERT` quando `ml.probability > 0.65`
	- `INFO` quando `ml.probability > 0.55` e não ALERT
	- `TICK` caso contrário
- [ ] Respeitar semântica de cor do legado:
	- `ALERT`: fundo `#fff3cd`, texto `#856404`
	- `INFO`: fundo `#d1ecf1`, texto `#0c5460`
	- `TICK`: fundo `#ffffff`, texto `#6c757d`
- [ ] Incluir ícones por categoria:
	- `ALERT`: `🚨`
	- `INFO`: `📊`
	- `TICK`: neutro (sem ícone crítico)
- [ ] Incluir estado visual de validação no bloco `decision`:
	- `signal_valid=true` -> badge/label `VALIDADO` com ícone `✅`
	- `signal_valid=false` -> badge/label `NÃO VALIDADO` com ícone `⚠️`
- [ ] Exibir `decision.validation_reason` quando `signal_valid=false`.

### 🧩 Classes CSS sugeridas (obrigatório mapear semanticamente)
- [ ] `alert-high` para `ALERT` (`probability > 0.65`)
- [ ] `alert-medium` para `INFO` (`0.55 < probability <= 0.65`)
- [ ] `alert-low` para `TICK` (`probability <= 0.55`)
- [ ] `decision-valid` e `decision-blocked` para estado de validação

---

## ✅ Critérios de aceite
- [ ] Monitor abre sem qualquer candlestick.
- [ ] Primeira mensagem recebida já preenche o Grid analítico.
- [ ] Campos `ml`/`decision`/`analysis`/`indicators` renderizam sem `undefined` no console.
- [ ] Decisão (validada/bloqueada) fica visualmente destacada.
- [ ] Play/Stop continuam funcionais sem regressão.
- [ ] Conexão WS resiliente com reconexão e atualização contínua.
- [ ] Cores/ícones de severidade no Grid refletem exatamente as faixas do legado (`>0.65`, `>0.55`, restante).
- [ ] Casos de borda confirmados: `0.65` não usa `alert-high`; `0.55` não usa `alert-medium`.

---

## 🧪 Validação manual mínima
- [ ] Subir app e abrir `/monitor`.
- [ ] Iniciar `WDO$ M5` e `WIN$ M5`.
- [ ] Verificar atualização em tempo real dos 4 blocos.
- [ ] Confirmar ausência de erros JS no console após 5+ mensagens WS.
- [ ] Simular valores de probabilidade (`0.54`, `0.56`, `0.66`) e validar classes/cores/ícones esperados.
- [ ] Simular `decision.signal_valid=false` e confirmar exibição de `NÃO VALIDADO` + `validation_reason`.

---

## ⚠️ Restrições
- Não introduzir frameworks SPA.
- Não alterar arquitetura monolítica.
- Não criar EventBus/broker.
- Não alterar contrato canônico definido pelo BackendQuant.
