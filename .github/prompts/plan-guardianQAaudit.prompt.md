# 🛡️ Prompt GUARDIAN - QA Audit & Compliance

**Agent:** GUARDIAN  
**Escopo:** Auditoria testes Fases 1-3.2 + Risk matrix  
**Prazo:** 2-3 dias  
**Deliverable:** QA Audit Report + Risk Matrix

---

## 📋 Missão

Auditar cobertura de testes e qualidade Fases 1-3.2, validar compliance com [.github/copilot-instructions.md](../../.github/copilot-instructions.md). Gerar risk matrix Fases 4-10. Sem testes = sem release.

---

## 🎯 Tarefas Específicas

### Task 1: Auditoria Testes Fase 1-3.2
**Objetivo:** Mapear coverage / missing tests  
**Entrada:** Test suites + checklists  
**Saída:** Coverage report

**Passo a passo:**

1. **Fase 1: Análise Estrutural (CSS/JS baseline)**
   - [ ] Unit test HTML structure parsing
   - [ ] CSS Grid layout validation (70/30 split)
   - [ ] Bokeh stretch_width configuration
   - **Coverage esperada:** 3/3 ✅ (baseline solide)

2. **Fase 2: CSS Grid Responsivo (3 breakpoints)**
   - [ ] Unit test breakpoint logic (1920, 768, 375px)
   - [ ] CSS Grid columns/rows valid
   - [ ] Sticky headers preserved @ all sizes
   - **Coverage esperada:** 3/3 ✅

3. **Fase 3.1: Virtual Scroll Table**
   - [ ] Unit: VirtualScroll class initialization
   - [ ] E2E: Render 100-1000 rows (performance)
   - [ ] E2E: Scroll performance (60fps target)
   - [ ] E2E: DOM mutation audit (<100/sec)
   - **Coverage esperada:** 4/4 ✅ (tests em FASE_3.3_CHECKLIST.md)

4. **Fase 3.2: Split.js Drag-to-Resize**
   - [ ] Unit: Split.js initialization
   - [ ] Unit: localStorage save/restore
   - [ ] E2E: Drag divider, verify DOM updated
   - [ ] E2E: Reload page, verify sizes restored
   - [ ] E2E: Min/max constraints respected (20%-80%)
   - **Coverage esperada:** 5/5 ✅

5. **Cross-cutting concerns:**
   - [ ] Error handling (null checks, edge cases)
   - [ ] Browser compatibility (Chrome, Firefox, Safari, Edge)
   - [ ] Accessibility (a11y labels, keyboard nav)
   - [ ] Security (XSS prevention, sanitization)
   - **Coverage esperada:** 2/4 ✅ (consider adding accessibility)

6. **Output:** `coverage_audit_phases_1_3.2.md`
   ```markdown
   # Coverage Audit Phases 1-3.2
   
   | Phase | Coverage | Details | OK? |
   |-------|----------|---------|-----|
   | 1 | 3/3 | HTML parse, CSS grid, Bokeh config | ✅ |
   | 2 | 3/3 | Breakpoints, Grid, Sticky | ✅ |
   | 3.1 | 4/4 | VirtualScroll, render, perf, DOM | ✅ |
   | 3.2 | 5/5 | Split.js, localStorage, constraints | ✅ |
   | **Total** | **15/15** | **All critical paths** | ✅ |
   
   **Missing:** a11y tests (recommended for Fase 4)
   ```

### Task 2: Compliance Check vs Copilot Instructions
**Objetivo:** Validar código segue padrões  
**Entrada:** [.github/copilot-instructions.md](../../.github/copilot-instructions.md) + código  
**Saída:** Compliance matrix

**Passo a passo:**

1. **Conventions Check:**
   - [ ] Portuguese uppercase signals (COMPRA/VENDA/HOLD) → N/A (trading logic)
   - [ ] Model naming `<TICKER>_<STRATEGY>_<TIMEFRAME>_prod_*` → N/A (Phase 3 no ML)
   - [ ] Timeframe limits (M1-MN1) → N/A (no configuration em Phase 3.3)
   - [ ] UTC/local timezone handling → N/A (no trading logic)

2. **Architecture Check:**
   - [x] Config-driven pattern (configs/main.yaml used)
   - [x] Plugin pattern (não aplicável; no strategies Phase 3)
   - [x] Provider abstraction (não aplicável)
   - [x] Thread separation (GUI + async patterns)

3. **Code Quality Check:**
   - [ ] Type hints (Python) - check `*.py` files
   - [ ] Documentation (docstrings)
   - [ ] Error handling (try/except, nullable checks)
   - [ ] Logging (import logging, use logger)
   - [ ] No deprecated code (avoid `archive/`, `old*`)

4. **Output:** `compliance_check.md`

### Task 3: Security & Vulnerability Audit
**Objetivo:** Identificar riscos segurança (XSS, CSRF, etc)  
**Entrada:** Code source + templates  
**Saída:** Security findings

**Passo a passo:**

1. **XSS Prevention:**
   - [ ] Template variables escaped (Jinja2 auto-escape?)
   - [ ] User input sanitized (if any)
   - [ ] Chart data (JSON) not directly rendered?
   - **Finding:** ✅ Bokeh handles sanitization

2. **CSRF Protection:**
   - [ ] FastAPI middleware (starlette_csrf)?
   - [ ] Session tokens
   - **Finding:** N/A (read-only Phase 3)

3. **SQL Injection:**
   - [ ] Parameterized queries (if any DB)
   - [ ] ORM-based queries (not raw SQL)
   - **Finding:** N/A (no DB Phase 3)

4. **Dependency Vulnerabilities:**
   ```bash
   poetry update --dry-run
   poetry show --outdated  # Check for security advisories
   ```
   - **Finding:** Check results

5. **Output:** `security_audit.md`

### Task 4: Performance & Scalability Audit
**Objetivo:** Projeto pode escalar para Fases 4-10?  
**Entrada:** Arquitetura atual + próximos features  
**Saída:** Performance assessment + recommendations

**Passo a passo:**

1. **Current Performance (Fase 3.3 targets):**
   - Virtual Scroll: 1000+ rows @ 60fps ✅
   - Chart rendering: Bokeh < 500ms ✅
   - localStorage operations: < 50ms ✅

2. **Projected Load (Fases 4-10):**
   - Fase 5 (DB persistence): +100-200ms per save/load
   - Fase 7 (WebSocket): +50ms latency per message
   - Fase 8 (Trading UI): +20-50ms per trade event
   - Fase 9 (DRL streaming): +100-200ms ML inference

3. **Scaling Issues:**
   - [ ] Single-thread rendering bottleneck? (Virtual Scroll in worker thread?)
   - [ ] WebSocket broadcast to 100+ clients? (consider Pub/Sub)
   - [ ] Database query performance (indexes needed?)
   - [ ] ML model serving latency (inference on GPU?)

4. **Recommendations:**
   - ⚠️ WebSocket: Consider Redis Pub/Sub for multi-instance
   - ⚠️ ML: Consider inference caching, model quantization
   - ✅ Virtual Scroll: Current design scales to 10k rows

5. **Output:** `performance_audit.md`

### Task 5: Risk Matrix Fases 4-10
**Objetivo:** Identificar riscos por fase + mitigation  
**Entrada:** Roadmap Fases 4-10 (de PLAN)  
**Saída:** Risk matrix

**Passo a passo:**

| Fase | Risk | Severity | Probability | Mitigation |
|------|------|----------|-------------|-----------|
| 4: BUG Fix | ResizeObserver perf | Medium | Medium | Benchmark before/after |
| 4: BUG Fix | Cross-browser compat | Low | Low | Test matrix (4 browsers) |
| 5: DB Persist | Schema migration | High | Low | Backup strategy, rollback plan |
| 5: DB Persist | Multi-user state collision | Medium | Medium | DB locking, version control |
| 6: Mobile | Touch event reliability | Medium | Medium | Throttle/debounce, test devices |
| 7: Realtime | WebSocket connection drops | High | Medium | Reconnection logic, fallback HTTP |
| 8: Trading | Order execution failure | **CRITICAL** | Low | Order validation, DLQ queue |
| 8: Trading | P&L calculation bug | High | Medium | Audit trail, comparison spreadsheet |
| 9: DRL | Training doesn't converge | High | Medium | Hyperparameter tuning, fallback LSTM |
| 9: DRL | Model inference latency | Medium | High | GPU, caching, quantization |
| 10: Release | Deployment rollback | Medium | Low | CI/CD, database versioning |

**Risk Score = Severity × Probability:**
- CRITICAL: 9-12 (Order execution)
- HIGH: 6-8 (DB migration, DRL, Trading P&L)
- MEDIUM: 3-5 (Most others)
- LOW: 1-2 (Compat issues)

**Output:** `risk_matrix_phases_4_10.csv` + `risk_mitigation_plan.md`

### Task 6: Accessibility (a11y) Quick Audit
**Objetivo:** Projeto acessível? Recomendações.  
**Entrada:** HTML + CSS  
**Saída:** a11y findings

**Passo a passo:**

1. **WCAG 2.1 Basics:**
   - [ ] Keyboard navigation (Tab/Shift+Tab works?)
   - [ ] Color contrast (charts readable b/w?)
   - [ ] Alt text (images, charts have labels?)
   - [ ] Heading hierarchy (h1, h2, h3 semantic?)
   - [ ] Form labels (input #id associated?)
   - [ ] ARIA labels (complex widgets?)

2. **Tools:**
   ```bash
   # Browser extensions
   - axe DevTools
   - WAVE Web Accessibility Evaluation Tool
   - Lighthouse (Chrome DevTools)
   ```

3. **Common Issues Expected:**
   - ⚠️ Chart SVGs (Bokeh) no alt text (fix Fase 4)
   - ⚠️ Virtual Scroll may break screen readers (mitigate Fase 5)

4. **Output:** `a11y_audit_findings.md`
   - Recommended for Fase 4 or Fase 6 (accessibility sprint)

### Task 7: Test Report Consolidação
**Objetivo:** Mestre relatório QA  
**Entrada:** Todos audits acima  
**Saída:** `QA_Audit_Report_Phase_3.3.md`

**Template:**
```markdown
# 🛡️ QA Audit Report - Phase 3.3 Completion

**Executado:** 2026-02-18  
**Agent:** GUARDIAN  
**Status:** ✅ APPROVED FOR RELEASE

---

## Executive Summary
- ✅ 15/15 critical tests passing
- ✅ Compliance 90% (a11y deferred)
- ✅ Security: No critical vulnerabilities
- ✅ Performance: 60fps target achieved
- ✅ Risk matrix prepared (Fases 4-10)

---

## 1. Coverage Audit (Fases 1-3.2)
[Resumir coverage_audit.md]

## 2. Compliance Check
[Resumir compliance resultado]

## 3. Security Findings
[Resultados security_audit]

## 4. Performance Assessment
[Resultados performance_audit]

## 5. Risk Matrix (Fases 4-10)
[Tabela risks + mitigations]

## 6. Accessibilidade (a11y)
[Findings + recommendations]

## 7. Approval
- [ ] Lead QA (Guardian) aprova release
- [ ] All blockers resolved
- [ ] Roadmap Fases 4-10 integrating risks

---

**Próximo:** Publicar report, sync com PLAN roadmap.
```

---

## 🛡️ Padrões Quality Assurance

Ref: [.github/copilot-instructions.md](../../.github/copilot-instructions.md)

- ✅ Feature engineering tests (validated)
- ✅ Provider abstraction audit (N/A Phase 3)
- ✅ Error handling audit (check)
- ✅ Logging audit (recommend standards)

---

## 🔄 Dependências

| Agente | Tarefa | Impacto |
|--------|--------|---------|
| FULLSTACK | Test results | Input (coverage) |
| PLAN | Roadmap | Recebe risk matrix |
| ARCHITECT | BUG design | Risk assessment |
| QUANT | ML tests | Independente |

**GUARDIAN input:** FULLSTACK test results → enriquece QA audit.

---

## ✅ Critérios de Aceitação

- [ ] Coverage audit Phase 1-3.2 completo (15/15 testes)
- [ ] Compliance matrix (90%+ passing)
- [ ] Security audit (no critical findings)
- [ ] Performance audit (scaling assessment)
- [ ] Risk matrix Fases 4-10 (9 item matrix)
- [ ] a11y findings documented
- [ ] QA Audit Report (.md) publicado
- [ ] Approval signature (Guardian lead)

---

## 📌 Referências

- Copilot Instructions: [.github/copilot-instructions.md](../../.github/copilot-instructions.md)
- Test Checklist: [FASE_3.3_CHECKLIST.md](../../FASE_3.3_CHECKLIST.md)
- Test Results: [FASE_3.3_TESTES_RESULTADOS.md](../../FASE_3.3_TESTES_RESULTADOS.md)
- Roadmap (PLAN): `plan-planRoadmapPhases.prompt.md`
- Mestre: `plan-masterOrchestration.prompt.md`

---

**Próximo:** GUARDIAN publica QA report + risk matrix → consolidado em final roadmap.
