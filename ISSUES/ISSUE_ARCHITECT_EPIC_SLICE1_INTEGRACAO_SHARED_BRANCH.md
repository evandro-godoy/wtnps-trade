# [ARCHITECT][EPIC] Slice 1 — Integração Final na Shared Branch `feature/monitor-slice-1`

**Assignee:** @Architect  
**Labels:** `architect`, `epic`, `integration`, `slice-1`, `newapp`, `priority:high`  
**Milestone sugerido:** Slice 1 — Fundação do Monitor em Tempo Real

> **Instrução de integração (obrigatória):** Todos os commits e Pull Requests desta tarefa devem ter como alvo a branch `feature/monitor-slice-1` e **NÃO** a `main`.

---

## 🎯 Objetivo
Orquestrar e validar a integração completa do Slice 1 após entrega dos agentes BackendQuant, Fullstack e Guardian na branch compartilhada.

O merge para `main` ocorrerá somente após validação ponta a ponta e aprovação arquitetural final.

---

## 📂 Contexto & Escopo
A branch `feature/monitor-slice-1` concentra as entregas da Fundação do Monitor em Tempo Real:
- Realtime Always-On + Singleton
- Lazy Loading de ML + cache
- Persistência desacoplada em background
- Contrato WS estrito com Pydantic
- Frontend monitor como "casca burra"
- Suíte de testes Guardian consolidada

---

## 🔗 PRs e Issues dependentes

### BackendQuant
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_MONITOR_ALWAYS_ON_SINGLETON.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_LAZY_LOADING_ML_CACHE.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_PERSISTENCIA_DESACOPLADA_BACKGROUND.md`
- `ISSUES/ISSUE_BACKENDQUANT_SLICE1_CONTRATO_WS_PYDANTIC_STRICT.md`

### Fullstack
- `ISSUES/ISSUE_FULLSTACK_SLICE1_BASE_TEMPLATE_MONITOR_PASSIVO_WS.md`
- `ISSUES/ISSUE_FULLSTACK_SLICE1_MONITOR_JS_CONTRATO_WS_DUMB_UI.md`

### Guardian
- `ISSUES/ISSUE_GUARDIAN_SLICE1_MASTER_TESTES_REALTIME.md`

---

## 🧪 Checklist de validação ponta a ponta (Architect)
- [ ] Confirmar que todos os PRs do Slice 1 apontam para `feature/monitor-slice-1`.
- [ ] Validar integração backend/frontend no monitor realtime (sem regressão funcional).
- [ ] Validar contrato canônico WS com payload Pydantic UI-ready.
- [ ] Validar que fluxo Always-On não depende de ação manual da UI.
- [ ] Validar que persistência em background não bloqueia caminho crítico de broadcast.
- [ ] Consolidar resultado dos testes Guardian (go/no-go).

---

## 📦 Definition of Done (DoD)
- [ ] Todas as tarefas do Slice 1 integradas na `feature/monitor-slice-1`.
- [ ] Validação arquitetural ponta a ponta concluída e documentada.
- [ ] Decisão explícita de promoção para `main` registrada.
- [ ] Apenas após aprovação da Epic: abrir PR de `feature/monitor-slice-1` para `main`.

---

## 📤 Entregável esperado
Relatório arquitetural final contendo:
- Estado de integração por agente
- Riscos residuais e mitigação
- Resultado da validação E2E
- Recomendação final de merge para `main`

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md` (Shared Feature Branch + padrões do Slice 1)
- `.memory-bank/activeContext.md`
