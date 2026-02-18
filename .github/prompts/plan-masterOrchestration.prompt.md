# 🎯 Prompt Mestre - Orquestração Sprint 3 WTNPS Trade

**Data:** 2026-02-18  
**Status:** Distribuição Multi-Agente (1-3 dias)  
**Objetivo:** Completar Fase 3.3 + Validar CI na `main` + Planejar Fases 4-10

---

## 📋 Contexto Executivo

O projeto **WTNPS Trade** está em **80% de conclusão** (Fases 1-3.2 ✅):
- ✅ Layout responsivo com CSS Grid
- ✅ Virtual scroll (1000+ linhas @ 60fps)
- ✅ Drag-to-resize com Split.js + localStorage
- ⚠️ 1 BUG conhecido: Bokeh sobrepõe em 2ª tela (deferred)
- ✅ CI green na `main`

**Entrega esperada:** 3 workstreams em paralelo → Consolidação central → Sync dependências

---

## 🎨 Distribuição de Responsabilidades

### Workstream 1: Infraestrutura & CI
**Leads:** DEVOPS + ARCHITECT  
**Deadline:** 1-2 dias  
**Deliverables:** CI ✅, BUG roadmap ✅

**Tarefas:**
1. **DEVOPS** → `plan-devopsCI.prompt.md`
   - Verificar CI na `main` e monitorar regressões
   - Manter pipeline estável durante a Fase 3.3
   
2. **ARCHITECT** → `plan-architectBugAnalysis.prompt.md`
   - Analisar 4 soluções BUG_BOKEH_RESIZE_MULTI_SCREEN.md
   - Desenhar padrão persistível, roadmap Fase 4

---

### Workstream 2: Testes & Conclusão Fase 3.3
**Leads:** FULLSTACK + QUANT  
**Deadline:** 2-3 dias  
**Deliverables:** 15/15 testes ✅, relatório ML ✅

**Tarefas:**
1. **FULLSTACK** → `plan-fullstackPhase3.3.prompt.md`
   - Executar 15 testes FASE_3.3_CHECKLIST.md
   - Validar performance, responsividade, localStorage
   
2. **QUANT** → `plan-quantMLValidation.prompt.md`
   - Testar LSTM strategies (WDO$, WIN$)
   - Validar configs/main.yaml, gerar relatório

---

### Workstream 3: Planning & QA
**Leads:** PLAN + GUARDIAN  
**Deadline:** 2-3 dias  
**Deliverables:** Roadmap Fases 4-10 ✅, Audit ✅

**Tarefas:**
1. **PLAN** → `plan-planRoadmapPhases.prompt.md`
   - Estruturar épicos, backlogs, story points
   - Definir velocidade sprint, milestones
   
2. **GUARDIAN** → `plan-guardianQAaudit.prompt.md`
   - Auditar cobertura testes Fases 1-3.2
   - Matriz de risco, compliance check

---

## 🔗 Dependências & Sincronismo

| De | Para | Tipo | Impacto |
|----|------|------|---------|
| DEVOPS CI | FULLSTACK Testes | Bloqueante? | Não (paralelo) |
| DEVOPS CI | main estavel | Bloqueante | SIM |
| DEVOPS CI | PLAN Roadmap | Info | Sim (context) |
| ARCHITECT Bug | PLAN Roadmap | Design | Sim (Phase 4) |
| FULLSTACK Tests | GUARDIAN Audit | Input | Sim (resultados) |

**Orquestração:** PLAN aguarda DEVOPS + ARCHITECT base → sincroniza Roadmap Fases 4-10 com BUG fix priority

---

## 📁 Arquivos Críticos Referenciados

- **Configs:** [configs/main.yaml](../../configs/main.yaml)
- **Status Atual:** [FASE_3.3_CHECKLIST.md](../../FASE_3.3_CHECKLIST.md)
- **Testes:** [FASE_3.3_TESTES_RESULTADOS.md](../../FASE_3.3_TESTES_RESULTADOS.md)
- **BUG:** [ISSUES/BUG_BOKEH_RESIZE_MULTI_SCREEN.md](../../ISSUES/BUG_BOKEH_RESIZE_MULTI_SCREEN.md)
- **Branch:** `main`

---

## ✅ Critérios de Conclusão Mestre

- [ ] CI green na `main` (DEVOPS)
- [ ] 15/15 testes executados (FULLSTACK)
- [ ] LSTM ML validado (QUANT)
- [ ] Roadmap Fases 4-10 estruturado (PLAN)
- [ ] QA Audit completo (GUARDIAN)
- [ ] BUG Analysis + roadmap Fase 4 (ARCHITECT)
- [ ] Prompts atualizados em .github/prompts (Mestre)
- [ ] main estavel para continuidade (Consolidação)

---

## 📞 Contato & Escalação

- Bloqueador? → Escale para ARCHITECT (design) ou DEVOPS (infra)
- Precisa contexto? → Ref: [RESUMO_GERAL_FASES_1_3.2.md](../../RESUMO_GERAL_FASES_1_3.2.md)
- Questão ML? → QUANT com [configs/main.yaml](../../configs/main.yaml)

---

**Próximo:** Cada agente executa seu prompt especializado. Mestre reconsolidar na conclusão.
