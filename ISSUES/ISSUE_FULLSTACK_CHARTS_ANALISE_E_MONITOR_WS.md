# [FULLSTACK] Corrigir Análise Técnica no Charts e consumo WS no Monitor

**Assignee:** @Fullstack  
**Labels:** `frontend`, `fullstack`, `charts`, `monitor`, `websocket`, `integration`, `priority:high`  
**Milestone sugerido:** Sprint Integração Monitor/Charts

---

## 📋 Contexto
A UI apresenta quebra de contrato entre o que consome e o que o backend retorna:
- Em `charts.html`, o JS espera `data.indicators`, enquanto `/api/analysis` retorna `analysis`.
- Em `monitor.html/monitor.js`, o card não reflete imediatamente a primeira atualização quando o monitor inicia.

---

## 🎯 Objetivo
Ajustar a camada frontend para consumir corretamente o contrato backend atual/canônico e refletir updates do monitor em tempo real (incluindo first tick).

---

## 📁 Arquivos-alvo
- `newapp/templates/charts.html`
- `newapp/static/js/app.js`
- `newapp/templates/monitor.html`
- `newapp/static/js/monitor.js`
- `newapp/templates/charts_clean.html` (somente se necessário para contrato comum)

---

## 🔧 Tarefas
- [ ] Corrigir parser da seção "Análise Técnica Rápida" em `charts.html` para o schema real do endpoint (`analysis`).
- [ ] Ajustar `app.js` para renderizar campos existentes (`trend`, `trend_strength`, `rsi`, `support`, `resistance`, `pattern`, etc.).
- [ ] Remover dependência de campos inexistentes (`analysis.trend.direction`, `moving_averages.*`) ou mapear fallback consistente.
- [ ] Em `monitor.js`, suportar mensagem inicial de snapshot + mensagens incrementais de tick com mesmo payload base.
- [ ] Garantir atualização visual imediata do card após clique em Play quando chegar first tick.
- [ ] Garantir resiliência: render não quebra se algum subcampo opcional vier ausente.

---

## ✅ Critérios de aceite
- [ ] `/charts` exibe análise técnica sem erro no console.
- [ ] `/monitor` atualiza card e log na primeira emissão do backend.
- [ ] WS permanece conectado e continua recebendo ticks seguintes.
- [ ] Nenhuma regressão em botões Play/Stop e estados visuais.

---

## 🧪 Validação manual mínima
- [ ] Abrir `/charts` e validar módulo de análise preenchido.
- [ ] Abrir `/monitor`, clicar Play e observar atualização <2s.
- [ ] Conferir console sem exceptions de `undefined`.

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md` (comunicação via WebSocket)
- `.memory-bank/activeContext.md`
- `.memory-bank/SPRINT_2026-02-20_MONITOR_CHARTS_HANDOFF.md`
