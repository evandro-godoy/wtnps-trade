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

**Arquivo:** `0_Master_Orchestration_Prompt.md`  
**Agent:** 🎯 PLAN (Orchestrator)  
**Escopo:** Sincronismo de 3 workstreams + consolidação final  
**Prazo:** 2-3 dias (aguarda inputs)

**Responsabilidades:**
- Coordena 6 agents em paralelo
- Monitora dependências entre workstreams
- Validação de critérios consolidados
- Sincroniza merge PR + release

**Inputs recebidos de:** DEVOPS, ARCHITECT, FULLSTACK, QUANT, GUARDIAN  
**Outputs fornecidos para:** Consolidação final + PR ready

---

## 🔄 Workstream 1: Infraestrutura & CI (1-2 dias)

### 🔧 **Prompt 1: DEVOPS - CI/CD & Infraestrutura**

**Arquivo:** `1_Devops_CI_Infrastructure.md`  
**Agent:** 🔧 DEVOPS  
**Escopo:** Resolver CI failure + Validar pipeline GitHub Actions  
**Prazo:** 1-2 dias  
**Status:** 🔴 BLOQUEADOR (CI falha no PR #2)

**3 Tarefas principais:**
1. **Investigar CI failure** → Root cause documentation
2. **Fix + Validate locally** → Commit em PR branch
3. **GitHub Actions rerun** → CI verde ✅

**Deliverables:**
- ✅ Root cause document
- ✅ Fix commited
- ✅ CI green no PR
- ✅ PR comment aprovação

**Depende de:** Nenhum (paralelo)  
**Fornece input para:** PLAN (consolidação), FULLSTACK (não bloqueador)

---

### 🏛️ **Prompt 2: ARCHITECT - BUG Analysis & Design**

**Arquivo:** `2_Architect_Bug_Analysis.md`  
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

**Arquivo:** `3_Fullstack_Phase3.3_Testing.md`  
**Agent:** 💻 FULLSTACK  
**Escopo:** Executar 12 testes fase 3.3 + performance benchmarking  
**Prazo:** 2-3 dias  
**Status:** 🟢 PRONTO (não depende DEVOPS CI)

**6 Tarefas principais:**
1. **Setup teste local** → Ambiente pronto
2. **Executar 12 testes** → Manual validation (checklist)
3. **Performance benchmarking** → 60fps target
4. **Responsividade** → 3 breakpoints (desktop/tablet/mobile)
5. **localStorage persistence** → State reload test
6. **Cross-browser** → Chrome, Firefox, Safari, Edge

**Deliverables:**
- ✅ 12/12 testes executados
- ✅ 60fps benchmark validado
- ✅ 5-6 screenshots key moments
- ✅ Relatório FASE_3.3_TESTES_RESULTADOS_FINAL.md
- ✅ Cross-browser matrix (4/4 browsers)

**Depende de:** Nenhum (CI não bloqueador)  
**Fornece input para:** GUARDIAN (QA audit), PLAN (consolidação)

---

### 📊 **Prompt 4: QUANT - ML Validation**

**Arquivo:** `4_Quant_ML_Validation.md`  
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

**Arquivo:** `5_Plan_Roadmap_Phases4-10.md`  
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

**Arquivo:** `6_Guardian_QA_Audit.md`  
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
| **WS2** (Tests+ML) | 2-3 dias | 🟢 Pronto | 12 tests ✅, ML valid ✅ |
| **WS3** (Planning+QA) | 2-3 dias | 🟡 Aguarda | Roadmap ✅, Risk matrix ✅ |
| **Consolidação** | 1 dia | 🟡 Após WS | PR ready ✅ |
| **TOTAL** | **3-4 dias** | 🟡 Em curso | Fase 3.3 COMPLETE ✅ |

---

## 📖 Read Order by Role

**👨‍💼 Para Gestores / PMs:**
1. [0_Master_Orchestration_Prompt.md](0_Master_Orchestration_Prompt.md) (overview)
2. [5_Plan_Roadmap_Phases4-10.md](5_Plan_Roadmap_Phases4-10.md) (roadmap)
3. [6_Guardian_QA_Audit.md](6_Guardian_QA_Audit.md) (risk matrix)

**👨‍💻 Para Engineers:**
1. Seu prompt específico (ex: [3_Fullstack_Phase3.3_Testing.md](3_Fullstack_Phase3.3_Testing.md))
2. [0_Master_Orchestration_Prompt.md](0_Master_Orchestration_Prompt.md) (dependencies)

**🏗️ Para Arquitetura:**
1. [2_Architect_Bug_Analysis.md](2_Architect_Bug_Analysis.md) (design)
2. [0_Master_Orchestration_Prompt.md](0_Master_Orchestration_Prompt.md) (sync)
3. [5_Plan_Roadmap_Phases4-10.md](5_Plan_Roadmap_Phases4-10.md) (phase 4 impact)

---

## ✅ Critérios de Sucesso

- [ ] CI verde (DEVOPS)
- [ ] 12/12 testes passando (FULLSTACK)
- [ ] ML strategies validadas (QUANT)
- [ ] BUG design aprovado (ARCHITECT)
- [ ] Roadmap Fases 4-10 (PLAN)
- [ ] QA audit + risk matrix (GUARDIAN)
- [ ] PR #2 ready merge
- [ ] Fase 3.3 COMPLETE ✅

---

## 📞 Quick Reference - Contacts & Escalation

| Problema | Agent | Arquivo |
|----------|-------|---------|
| ❌ CI falha? | DEVOPS | `1_Devops_CI_Infrastructure.md` |
| 🐛 BUG multi-screen? | ARCHITECT | `2_Architect_Bug_Analysis.md` |
| 🧪 Testes não passam? | FULLSTACK | `3_Fullstack_Phase3.3_Testing.md` |
| ⚙️ ML strategy fails? | QUANT | `4_Quant_ML_Validation.md` |
| 📋 Roadmap priority? | PLAN | `5_Plan_Roadmap_Phases4-10.md` |
| 🛡️ Risk concerns? | GUARDIAN | `6_Guardian_QA_Audit.md` |
| 🎯 Sync issue? | MESTRE | `0_Master_Orchestration_Prompt.md` |

---

## 📁 Estrutura Local Recomendada

```
.github/prompts/
├── INDEX_Prompts.md (este arquivo)
├── 0_Master_Orchestration_Prompt.md
├── 1_Devops_CI_Infrastructure.md
├── 2_Architect_Bug_Analysis.md
├── 3_Fullstack_Phase3.3_Testing.md
├── 4_Quant_ML_Validation.md
├── 5_Plan_Roadmap_Phases4-10.md
└── 6_Guardian_QA_Audit.md
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
