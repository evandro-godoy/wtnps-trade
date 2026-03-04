# [FULLSTACK] Slice 1 — Simplificar monitor.js para contrato WS estrito (Dumb UI)

**Assignee:** @Fullstack  
**Labels:** `frontend`, `fullstack`, `monitor`, `websocket`, `javascript`, `priority:high`, `slice-1`, `newapp`  
**Milestone sugerido:** Slice 1 — Fundação do Monitor em Tempo Real

> **Instrução de integração (obrigatória):** Todos os commits e Pull Requests desta tarefa devem ter como alvo a branch `feature/monitor-slice-1` e **NÃO** a `main`.

---

## 📋 Contexto
Com a adoção de contrato estrito no backend (Pydantic), o `monitor.js` não deve mais conter lógica de fallback, classificação ou normalização de payload.

A UI deve confiar no payload WS como fonte final e apenas renderizar.

---

## 🎯 Objetivo
Refatorar `monitor.js` para remover complexidade defensiva e deixar as rotinas de renderização diretas, com mínima transformação de dados.

---

## 📁 Arquivos-alvo
- `newapp/static/js/monitor.js`
- `newapp/templates/monitor.html` (somente se precisar ajustar bindings)

---

## 🔧 Requisitos obrigatórios

### Requisito 1 — Remover fallback/classificação local
- [ ] Remover lógicas de fallback e classificação como `classifySeverity`, `toNumberOrNull` (ou equivalentes).
- [ ] Remover parse defensivo que duplique responsabilidade do backend.

### Requisito 2 — Renderização direta e simples
- [ ] Deixar `appendEventRow` e `updateMonitorCard` o mais diretas possível.
- [ ] Consumir payload WS confiando cegamente no contrato backend.
- [ ] Manter somente validações mínimas de integridade para evitar quebra fatal de DOM.

---

## ✅ Critérios de aceite
- [ ] `monitor.js` sem funções de fallback/classificação que pertencem ao backend.
- [ ] Renderização de eventos e card ocorre com payload canônico sem transformação complexa.
- [ ] Sem regressão visual/funcional no monitor realtime.

---

## 🧪 Validação manual mínima
- [ ] Conectar monitor e confirmar atualização contínua de rows/cards.
- [ ] Console do navegador sem erros de parsing de payload.
- [ ] Conferir que funções removidas não são mais referenciadas.

---

## 🔗 Dependências
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_CONTRATO_WS_PYDANTIC_STRICT.md`

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md` (Frontend casca burra + Strict Data Contracts)
- `.memory-bank/activeContext.md`
