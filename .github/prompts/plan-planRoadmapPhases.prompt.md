# 📋 Prompt PLAN - Roadmap Fases 4-10 & Gestão Sprint

**Agent:** PLAN  
**Escopo:** Estruturar épicos, backlogs, velocidade sprint  
**Prazo:** 2-3 dias  
**Deliverable:** Roadmap_Phases_4-10.md + Sprint Planning

---

## 📋 Missão

Consolidar outputs dos 3 workstreams em roadmap estratégico Fases 4-10:
- Design BUG fix (ARCHITECT)
- Test results (FULLSTACK)
- ML validation (QUANT)
- QA audit (GUARDIAN)

Estruturar épicos, story points, velocidade sprint, milestones. Artefato final: 1 roadmap livingdoc + sprint boards.

---

## 🎯 Tarefas Específicas

### Task 1: Consolidar Inputs Workstreams
**Objetivo:** Receber outputs 3 agents, normalizar  
**Entrada:** 
- DEVOPS: CI ✅ ou não
- ARCHITECT: BUG design + timeline Fase 4
- FULLSTACK: 15 test results
- QUANT: ML validation report
- GUARDIAN: QA audit + risk matrix

**Saída:** Summary doc (2-3 linhas por item)

**Passo a passo:**
1. Aguardar todos 3 workstreams fornecerem outputs (2-3 dias)
2. Atualizar referencias de docs para `main` e reconciliar contagem de testes (15 itens)
3. Coletar em template:
   ```markdown
   ## Workstream Summary
   
   ### CI & Infrastructure (DEVOPS + ARCHITECT)
   - CI Status: ✅ [ou ❌ razão]
   - BUG Multi-Screen Design: ✅ ResizeObserver pattern escolhido
   - Recomendação Fase 4: 1-2 dias, FULLSTACK lead
   - Risk: [baixa]
   
   ### Testing (FULLSTACK + QUANT)
   - Testes 15/15: ✅ [ou N/15 com falhas]
   - Performance: 60fps ✅
   - ML validation: ✅ All signals valid
   - Cross-browser: 4/4 passing
   - Risk: [baixa]
   
   ### QA & Risk (GUARDIAN)
   - Cobertura tests: 85% (target 90%)
   - Critical bugs: 1 (BUG multi-screen, deferred)
   - Bloqueador merge: [SIM/NÃO]
   - Risk Score: [baixo/médio/alto]
   ```

### Task 2: Estruturar Épicos Fases 4-10
**Objetivo:** Quebrar roadmap em épicos executáveis  
**Entrada:** Outputs consolidados + contexto Fases 1-3.2  
**Saída:** Épicos estruturados (com features, story points)

**Passo a passo:**

Fases esperadas (ref: [RESUMO_GERAL_FASES_1_3.2.md](../../RESUMO_GERAL_FASES_1_3.2.md)):

```
Fase 4: BUG Fix Multi-Screen (1-2 dias)
├─ Epic: ResizeObserver integration
│  ├─ Story: Implement bokeh-observer.js (5 points)
│  ├─ Story: Hook EventBus to Split.js (3 points)
│  ├─ Story: Cross-browser test (Chrome/Firefox/Safari) (5 points)
│  └─ Story: Performance benchmark (3 points)
├─ Risk: ResizeObserver perf impact?
└─ Owner: FULLSTACK (ARCHITECT review)

Fase 5: Backend Persistence (3-4 dias)
├─ Epic: Save/Load chart state to DB
│  ├─ Story: PostgreSQL schema (chart_state table) (5 points)
│  ├─ Story: API endpoints GET/POST /api/chart-state (8 points)
│  ├─ Story: Frontend localStorage → API sync (5 points)
│  └─ Story: Multi-user state isolation (5 points)
├─ Risk: DB migration complexity?
└─ Owner: FULLSTACK + DEVOPS

Fase 6: Mobile Optimization (2-3 dias)
├─ Epic: Mobile-first layout + touch support
│  ├─ Story: CSS media queries <375px (3 points)
│  ├─ Story: Touch-drag support (5 points)
│  ├─ Story: Mobile chart interactions (5 points)
│  └─ Story: Performance (<3s load on 3G) (5 points)
├─ Risk: Touch reliability across devices?
└─ Owner: FULLSTACK + GUARDIAN

Fase 7: Real-time Updates (2-3 dias)
├─ Epic: WebSocket live data feed
│  ├─ Story: FastAPI WebSocket endpoint (5 points)
│  ├─ Story: Client WebSocket listener (3 points)
│  ├─ Story: Chart update stream (live candlesticks) (5 points)
│  └─ Story: Reconnection logic (3 points)
├─ Risk: Bandwidth/latency?
└─ Owner: FULLSTACK + QUANT

Fase 8: Advanced Trading Features (4-5 dias)
├─ Epic: Order management + live P&L
│  ├─ Story: Order entry form (8 points)
│  ├─ Story: Live P&L calculation (8 points)
│  ├─ Story: Position tracking dashboard (5 points)
│  └─ Story: Risk alerts (5 points)
├─ Risk: MT5 API complexity?
└─ Owner: QUANT + FULLSTACK

Fase 9: Machine Learning Improvements (5-7 dias)
├─ Epic: DRL + Ensemble strategies
│  ├─ Story: DRL agent training (target env) (8 points)
│  ├─ Story: Ensemble LSTM + DRL voting (8 points)
│  ├─ Story: Hyperparameter tuning framework (5 points)
│  └─ Story: Backtest ensemble vs single (5 points)
├─ Risk: Training time?
└─ Owner: QUANT + ARCHITECT

Fase 10: Documentation & Release (2-3 dias)
├─ Epic: Release v2.0 + user docs
│  ├─ Story: API documentation (swagger) (3 points)
│  ├─ Story: User guide (video + markdown) (5 points)
│  ├─ Story: Deployment guide (Docker) (5 points)
│  └─ Story: Release notes + changelog (3 points)
├─ Risk: Nenhum (low risk)
└─ Owner: DEVOPS + PLAN

```

### Task 3: Definir Velocidade Sprint
**Objetivo:** Story points/semana × Fases → Timeline  
**Entrada:** Épicos estruturados  
**Saída:** Sprint velocity + roadmap timeline

**Passo a passo:**

1. **Calcular velocidade histórica:**
   - Fase 3.1 (Virtual Scroll): 13 points em 1 dia = 13 points/dia
   - Fase 3.2 (Split.js): 11 points em 1 dia = 11 points/dia
   - **Velocity avg:** 12 points/dia = 60 points/semana (5 working days)

2. **Aplicar velocidade a Fases 4-10:**
   | Fase | Points | Dias | Owner |
   |------|--------|------|-------|
   | 4: BUG Multi-Screen | 16 | 2 | FULLSTACK + ARCHITECT |
   | 5: DB Persistence | 23 | 4 | FULLSTACK + DEVOPS |
   | 6: Mobile | 18 | 3 | FULLSTACK + GUARDIAN |
   | 7: Realtime | 16 | 3 | FULLSTACK + QUANT |
   | 8: Trading UI | 26 | 4 | QUANT + FULLSTACK |
   | 9: DRL Ensemble | 26 | 5 | QUANT + ARCHITECT |
   | 10: Release | 16 | 3 | DEVOPS + PLAN |

3. **Timeline sem parallelização (sequencial):**
   - Total: 141 points ÷ 60 points/week = **2.4 semanas** (serial)

4. **Timeline COM parallelização (3 teams):**
   - Team A (FULLSTACK + GUARDIAN): Fases 4, 6, 7 (16+18+16=50 points = 1 week)
   - Team B (QUANT + ARCHITECT): Fases 8, 9 (26+26=52 points = 1 week)
   - Team C (DEVOPS + PLAN): Fase 5, 10 (23+16=39 points = 1 week)
   - **Paralelo:** 1 semana simultânea (faster!)

5. **Recomendação:**
   - Sprint 1: Fases 4 + 5 (paralelo) → 1 semana
   - Sprint 2: Fases 6 + 8 (overlapping) → 1 semana
   - Sprint 3: Fases 7 + 9 (overlapping) → 1 semana
   - Sprint 4: Fase 10 (release) → 1 semana
   - **Total: 4 sprints = 4 semanas** (vs 2.4 sequencial!)

### Task 4: Criar Living Roadmap Document
**Objetivo:** Artefato central (versão única) roadmap Fases 4-10  
**Entrada:** Épicos + timeline + risk matrix  
**Saída:** `Roadmap_Phases_4-10.md` no root `/`

**Template:**
```markdown
# 🚀 WTNPS Trade - Roadmap Fases 4-10

**Versão:** 1.0  
**Atualizado:** 2026-02-18  
**Owner:** PLAN Agent  
**Status:** Draft (aprovando agora)

---

## Timeline Visual

\`\`\`
Sprint 1 [Sem 1]          Sprint 2 [Sem 2]         Sprint 3 [Sem 3]         Sprint 4 [Sem 4]
├─ Fase 4: BUG Fix       ├─ Fase 6: Mobile        ├─ Fase 7: Realtime      ├─ Fase 10: Release
├─ Fase 5: DB Persist    ├─ Fase 8: Trading UI    ├─ Fase 9: DRL
\`\`\`

---

## Fases Detalhadas

### Fase 4: BUG Fix Multi-Screen (1 semana)
**Owner:** FULLSTACK + ARCHITECT  
**Risk:** Baixa | **Bloqueador:** Não

**Épica:** ResizeObserver integration
- [x] Design finalizado (ARCHITECT)
- [ ] Implementation (FULLSTACK)
- [ ] Tests cross-browser
- [ ] Merge to main

[...detalhes...]

---

## Risk Matrix

| Fase | Risk | Mitigation |
|------|------|-----------|
| 4 | Perf degradation | Benchmark before/after |
| 5 | DB migration | Backup strategy ready |
| 9 | Training time | GPU allocation, time budget |

---

## Critérios de Conclusão Geral Roadmap

- [ ] Todas fases 4-10 planejadas (story level)
- [ ] Timeline validado (velocity-based)
- [ ] Risk matrix aprovada
- [ ] Owner designado (6 agents)
- [ ] Dependências mapeadas
- [ ] Documento publicado em root/
```

### Task 5: Sincronizar com Workstream Outputs
**Objetivo:** Roadmap reflete decisões = CI status, BUG design, test results  
**Entrada:** Consolidação Task 1  
**Saída:** Roadmap ajustado

**Passo a passo:**

1. **Se CI falhar (DEVOPS):**
   - Adicione Fase 4.0 "hotfix CI" antes BUG fix
   - Impacta timeline

2. **Se BUG design simples:**
   - Reduz Fase 4 points (16 → 12)
   - Timeline mais rápida

3. **Se tests falham:**
   - FULLSTACK gera issue list
   - Adiciona fixes como subtasks, impacta Sprint 1

4. **Se ML validation falha:**
   - QUANT propõe retraining
   - Fase 9 pode iniciar mais cedo ou mais tarde

**Aplicar ajustes automaticamente em roadmap.**

### Task 6: Preparar Sprint Board (Sprint 1)
**Objetivo:** Primeira sprint (Fases 4+5) decomposto em tasks executáveis  
**Entrada:** Épicos Fase 4 + Fase 5  
**Saída:** Sprint board Ready (Jira/GitHub Projects board)

**Passo a passo:**

1. Quebrar cada Epic em Stories:
   ```
   Epic: BUG Fix Multi-Screen
   ├─ Story 1: Implement bokeh-observer.js (5 points)
   │  ├─ Task: Create file newapp/static/js/bokeh-observer.js
   │  ├─ Task: Implement ResizeObserver listener
   │  ├─ Task: Add Bokeh.resize() callback
   │  └─ Acceptance: Observer listens to chart div
   ├─ Story 2: Hook to Split.js (3 points)
   │  ├─ Task: Import bokeh-observer in charts_clean.html
   │  ├─ Task: Add splitInstance.on('drag') → notify observer
   │  └─ Acceptance: Drag-to-resize updates Bokeh
   ```

2. Assign tasks a agents
3. Criar GitHub Issues ou Jira tickets

---

## 🛡️ Padrões Arquiteturais Preservados

Ref: [.github/copilot-instructions.md](../../.github/copilot-instructions.md)

- ✅ Config-driven (configs/main.yaml)
- ✅ Plugin pattern (strategies)
- ✅ Provider abstraction (MT5/YFinance)
- ✅ Thread separation (GUI + workers)

**Fases 4-10 respeitam padrões.**

---

## 🔄 Dependências Cross-Sprint

| Sprint | Bloqueador? | Depende de |
|--------|-------------|-----------|
| 1 (Fases 4+5) | Não | main estabilizada ✅ |
| 2 (Fases 6+8) | Fase 5 DB | Sprint 1 completo |
| 3 (Fases 7+9) | Fase 5 API | Sprint 1 API ready |
| 4 (Fase 10) | Releases | Sprints 1-3 ✅ |

**Verdade Acoplamento:** Sprint 2 aguarda Sprint 1 (DB persistence predecessora).

---

## ✅ Critérios de Aceitação

- [ ] 7 épicos estruturados (Fases 4-10)
- [ ] Stories decompostas com points (cada 3-8 points)
- [ ] Timeline validado (4 sprints paralelos)
- [ ] Risk matrix por fase
- [ ] Roadmap_Phases_4-10.md publicado em root/
- [ ] Sprint 1 board criado (pronto executar)
- [ ] Dependências mapeadas (cross-sprint awareness)
- [ ] Sincronizado com outputs DEVOPS/ARCHITECT/FULLSTACK/QUANT/GUARDIAN

---

## 📌 Referências

- Resumo Fases 1-3.2: [RESUMO_GERAL_FASES_1_3.2.md](../../RESUMO_GERAL_FASES_1_3.2.md)
- BUG Design (ARCHITECT): `plan-architectBugAnalysis.prompt.md`
- Test Results (FULLSTACK): `plan-fullstackPhase3.3.prompt.md`
- ML Report (QUANT): `plan-quantMLValidation.prompt.md`
- QA Audit (GUARDIAN): `plan-guardianQAaudit.prompt.md`
- Mestre: `plan-masterOrchestration.prompt.md`

---

**Próximo:** PLAN publica roadmap + Sprint 1 board. Trabalho implementa Sprint 1 em paralelo com Fase 5.
