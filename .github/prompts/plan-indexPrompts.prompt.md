# 📑 INDEX - Prompts Sprint 3 WTNPS Trade

**Data:** 2026-02-18  
**Status:** 7 Prompts estruturados + Índice de navegação  
**Versão:** 1.0

---

## 🎯 Visão Geral

Este índice é seu **mapa de navegação** dos 7 prompts de orquestração para Sprint 3. Cada prompt é autossuficiente mas conectado via dependências mapeadas abaixo.

**Estrutura:** 3 workstreams paralelos (1-2 dias cada) → Consolidação central

---

## 📊 Mapa de Prompts

### 🏆 **Prompt 0: Mestre (Orquestrador Central)**

**Arquivo:** `plan-masterOrchestration.prompt.md`  
**Agent:** 🎯 PLAN (Orchestrator)  
**Escopo:** Sincronismo de 3 workstreams + consolidação final  
**Prazo:** 2-3 dias (aguarda inputs)

**Responsabilidades:**
- Coordena 6 agents em paralelo
- Monitora dependências entre workstreams
- Validação de critérios consolidados
- Sincroniza estabilizacao da `main` + release

**Inputs recebidos de:** DEVOPS, ARCHITECT, FULLSTACK, QUANT, GUARDIAN  
**Outputs fornecidos para:** Consolidação final + main estavel

---

## 🔄 Workstream 1: Infraestrutura & CI (1-2 dias)

### 🔧 **Prompt 1: DEVOPS - CI/CD & Infraestrutura**

**Arquivo:** `plan-devopsCI.prompt.md`  
**Agent:** 🔧 DEVOPS  
**Escopo:** Validar CI na `main` + Monitorar pipeline GitHub Actions  
**Prazo:** 1-2 dias  
**Status:** 🟢 CI green na `main`

**3 Tarefas principais:**
1. **Verificar CI na main** → Status e evidencias
2. **Hardening do pipeline** → Ajustes preventivos
3. **Monitoramento continuo** → Alertas de regressao

**Deliverables:**
- ✅ Registro do status atual
- ✅ Pipeline estabilizado
- ✅ CI green na `main`
- ✅ Alerta rapido em regressao

**Depende de:** Nenhum (paralelo)  
**Fornece input para:** PLAN (consolidação), FULLSTACK (não bloqueador)

---

### 🏛️ **Prompt 2: ARCHITECT - BUG Analysis & Design**

**Arquivo:** `plan-architectBugAnalysis.prompt.md`  
**Agent:** 🏛️ ARCHITECT  
**Escopo:** Analisar BUG multi-screen Bokeh + Desenhar padrão Fase 4  
**Prazo:** 1-2 dias  
**Status:** 🟡 DEFERRED (implementação Fase 4)

**4 Tarefas principais:**
1. **Análise 4 soluções** → Matriz comparativa trade-offs
2. **Desenhar padrão escolhido** → Pseudocódigo + estrutura
3. **Padrão extensível** → EventBus ou plugin design
4. **Roadmap Fase 4** → Timeline + owners

**Deliverables:**
- ✅ Matriz 4 soluções (trade-offs)
- ✅ Padrão arquitetural escolhido (ResizeObserver recom.)
- ✅ EventBus / Plugin design
- ✅ Fase 4 roadmap claro (1-2 dias, FULLSTACK lead)

**Depende de:** Nenhum (paralelo)  
**Fornece input para:** PLAN (roadmap Fase 4), FULLSTACK (design reference)

---

## 🎨 Workstream 2: Testes & Validação (2-3 dias)

### 💻 **Prompt 3: FULLSTACK - Phase 3.3 Testing**

**Arquivo:** `plan-fullstackPhase3.3.prompt.md`  
**Agent:** 💻 FULLSTACK  
**Escopo:** Executar 15 testes fase 3.3 + performance benchmarking  
**Prazo:** 2-3 dias  
**Status:** 🟢 PRONTO (não depende DEVOPS CI)

**6 Tarefas principais:**
1. **Setup teste local** → Ambiente pronto
2. **Executar 15 testes** → Manual validation (checklist)
3. **Performance benchmarking** → 60fps target
4. **Responsividade** → 3 breakpoints (desktop/tablet/mobile)
5. **localStorage persistence** → State reload test
6. **Cross-browser** → Chrome, Firefox, Safari, Edge

**Deliverables:**
- ✅ 15/15 testes executados
- ✅ 60fps benchmark validado
- ✅ 5-6 screenshots key moments
- ✅ Relatório FASE_3.3_TESTES_RESULTADOS_FINAL.md
- ✅ Cross-browser matrix (4/4 browsers)

**Depende de:** Nenhum (CI não bloqueador)  
**Fornece input para:** GUARDIAN (QA audit), PLAN (consolidação)

---

### 📊 **Prompt 4: QUANT - ML Validation**

**Arquivo:** `plan-quantMLValidation.prompt.md`  
**Agent:** 📊 QUANT  
**Escopo:** Validar LSTM strategies + Configs + Data providers  
**Prazo:** 2-3 dias  
**Status:** 🟢 PRONTO (paralelo com FULLSTACK)

**6 Tarefas principais:**
1. **Validar configs** → YAML parse + fields check
2. **Model artifacts** → Keras/scaler/params load test
3. **Strategy execution** → get_signal() returns valid output
4. **Data providers** → MT5 e/ou YFinance accessible
5. **Integration test** → 1-day simulation run
6. **Technical report** → Consolidar todos testes

**Deliverables:**
- ✅ configs/main.yaml validado
- ✅ Model artifacts carregam sem erro
- ✅ 2 strategies (WDO$, WIN$) executam signals válidos
- ✅ Provider connectivity report
- ✅ 1-day sim test PnL reasonable
- ✅ QUANT_Phase3.3_ML_Validation_Report.md

**Depende de:** Nenhum (paralelo)  
**Fornece input para:** PLAN (consolidação), GUARDIAN (QA context)

---

## 📋 Workstream 3: Planning & QA (2-3 dias)

### 📋 **Prompt 5: PLAN - Roadmap Phases 4-10**

**Arquivo:** `plan-planRoadmapPhases.prompt.md`  
**Agent:** 📋 PLAN  
**Escopo:** Estruturar épicos + velocidade sprint + milestones  
**Prazo:** 2-3 dias (aguarda ARCHITECT + FULLSTACK + QUANT)  
**Status:** 🟡 AGUARDANDO INPUTS

**6 Tarefas principais:**
1. **Consolidar workstreams** → Receber outputs WS1+WS2+GUARDIAN
2. **Estruturar épicos Fases 4-10** → 7 fases com stories + points
3. **Definir velocidade sprint** → Story points/dia × timeline
4. **Create living doc** → Roadmap_Phases_4-10.md em root/
5. **Sincronizar outputs** → Reflet CI status, BUG design, test results
6. **Sprint 1 board** → Decompor Fases 4+5 em tasks

**Deliverables:**
- ✅ 7 épicos (Fases 4-10) com stories + points
- ✅ Sprint velocity calculado
- ✅ 4-sprint timeline
- ✅ Roadmap_Phases_4-10.md (living document)
- ✅ Sprint 1 board pronto
- ✅ Risk matrix por fase

**Depende de:** DEVOPS, ARCHITECT, FULLSTACK, QUANT, GUARDIAN  
**Fornece input para:** Mestre (consolidação), implementação Sprint 1

---

### 🛡️ **Prompt 6: GUARDIAN - QA Audit & Compliance**

**Arquivo:** `plan-guardianQAaudit.prompt.md`  
**Agent:** 🛡️ GUARDIAN  
**Escopo:** Auditar testes Fases 1-3.2 + Risk matrix Fases 4-10  
**Prazo:** 2-3 dias  
**Status:** 🟡 EM PARALELO

**7 Tarefas principais:**
1. **Auditoria testes** → Coverage Fases 1-3.2 (15/15 críticos)
2. **Compliance check** → vs copilot-instructions.md
3. **Security audit** → XSS, CSRF, SQL injection
4. **Performance audit** → Pode escalar?
5. **Risk matrix** → 9-item matrix Fases 4-10
6. **Accessibility audit** → WCAG 2.1 basics
7. **Consolidação** → QA_Audit_Report_Phase_3.3.md

**Deliverables:**
- ✅ Coverage audit (15/15 tests)
- ✅ Compliance matrix (90%+)
- ✅ Security findings (no critical)
- ✅ Performance assessment
- ✅ Risk matrix Fases 4-10
- ✅ a11y findings
- ✅ QA_Audit_Report_Phase_3.3.md

**Depende de:** FULLSTACK (test results)  
**Fornece input para:** PLAN (risk matrix), Mestre (QA sign-off)

---

## 🔗 Mapa de Dependências

```
              ┌──────────────────────┐
              │  MESTRE (Central)    │
              │ Aguarda todos 6 →    │
              │ Consolida            │
              └──────────────────────┘
                      ↑
         ┌────────────┼────────────┐
         │            │            │
    WS1: CI+Design  WS2: Tests  WS3: QA+Plan
    (1-2 dias)    (2-3 dias)   (2-3 dias)
         │            │            │
    ┌────┴────┐  ┌────┴────┐  ┌───┴─────┐
    │DEVOPS   │  │FULLSTACK│  │PLAN     │
    │ARCHITECT│  │QUANT    │  │GUARDIAN │
    └─────────┘  └─────────┘  └─────────┘

Sincronismo:
✅ WS1 não bloqueia WS2 (paralelo)
✅ WS2 não bloqueia WS3 (paralelo)
⏳ WS3 (PLAN) aguarda outputs WS1+WS2
```

---

## ⏱️ Timeline

| Workstream | Prazo | Status | Deliverables |
|-----------|-------|--------|-------------|
| **WS1** (CI+Design) | 1-2 dias | 🟢 Pronto | CI ✅, BUG design ✅ |
| **WS2** (Tests+ML) | 2-3 dias | 🟢 Pronto | 15 tests ✅, ML valid ✅ |
| **WS3** (Planning+QA) | 2-3 dias | 🟡 Aguarda | Roadmap ✅, Risk matrix ✅ |
| **Consolidação** | 1 dia | 🟡 Após WS | main estavel ✅ |
| **TOTAL** | **3-4 dias** | 🟡 Em curso | Fase 3.3 COMPLETE ✅ |

---

## 📖 Read Order by Role

**👨‍💼 Para Gestores / PMs:**
1. [plan-masterOrchestration.prompt.md](plan-masterOrchestration.prompt.md) (overview)
2. [plan-planRoadmapPhases.prompt.md](plan-planRoadmapPhases.prompt.md) (roadmap)
3. [plan-guardianQAaudit.prompt.md](plan-guardianQAaudit.prompt.md) (risk matrix)

**👨‍💻 Para Engineers:**
1. Seu prompt específico (ex: [plan-fullstackPhase3.3.prompt.md](plan-fullstackPhase3.3.prompt.md))
2. [plan-masterOrchestration.prompt.md](plan-masterOrchestration.prompt.md) (dependencies)

**🏗️ Para Arquitetura:**
1. [plan-architectBugAnalysis.prompt.md](plan-architectBugAnalysis.prompt.md) (design)
2. [plan-masterOrchestration.prompt.md](plan-masterOrchestration.prompt.md) (sync)
3. [plan-planRoadmapPhases.prompt.md](plan-planRoadmapPhases.prompt.md) (phase 4 impact)

---

## ✅ Critérios de Sucesso

- [ ] CI verde na `main` (DEVOPS)
- [ ] 15/15 testes passando (FULLSTACK)
- [ ] ML strategies validadas (QUANT)
- [ ] BUG design aprovado (ARCHITECT)
- [ ] Roadmap Fases 4-10 (PLAN)
- [ ] QA audit + risk matrix (GUARDIAN)
- [ ] main estavel para continuidade
- [ ] Fase 3.3 COMPLETE ✅

---

## 📞 Quick Reference - Contacts & Escalation

| Problema | Agent | Arquivo |
|----------|-------|---------|
| ❌ CI falha? | DEVOPS | `plan-devopsCI.prompt.md` |
| 🐛 BUG multi-screen? | ARCHITECT | `plan-architectBugAnalysis.prompt.md` |
| 🧪 Testes não passam? | FULLSTACK | `plan-fullstackPhase3.3.prompt.md` |
| ⚙️ ML strategy fails? | QUANT | `plan-quantMLValidation.prompt.md` |
| 📋 Roadmap priority? | PLAN | `plan-planRoadmapPhases.prompt.md` |
| 🛡️ Risk concerns? | GUARDIAN | `plan-guardianQAaudit.prompt.md` |
| 🎯 Sync issue? | MESTRE | `plan-masterOrchestration.prompt.md` |

---

## 📁 Estrutura Local Recomendada

```
.github/prompts/
├── INDEX_Prompts.md (este arquivo)
├── plan-masterOrchestration.prompt.md
├── plan-devopsCI.prompt.md
├── plan-architectBugAnalysis.prompt.md
├── plan-fullstackPhase3.3.prompt.md
├── plan-quantMLValidation.prompt.md
├── plan-planRoadmapPhases.prompt.md
└── plan-guardianQAaudit.prompt.md
```

**Salve todos os 8 arquivos** (7 prompts + INDEX) nesta pasta.

---

## 🚀 Próximos Passos

1. ✅ Refine cada prompt conforme necessário (já estão em untitled)
2. ✅ Salve os 8 arquivos em `.github/prompts/`
3. ✅ Commit: `git add .github/prompts/ && git commit -m "feat: Sprint 3 prompts + INDEX"`
4. ✅ Compartilhe com cada agent
5. ✅ Comece execução (workstreams paralelos!)

---

**Pronto para começar? Abra seu prompt específico!**
