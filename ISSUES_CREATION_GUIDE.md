# 📋 Guia de Criação de Issues - Sprint 3 WTNPS Trade

**Data:** 2026-02-18  
**Repositório:** evandro-godoy/wtnps-trade  
**Branch base:** main

---

## 🎯 Issues a Criar

### Issue #1: 🔧 DEVOPS - CI/CD & Infraestrutura Validation

**Título:** `[DEVOPS] CI/CD Pipeline Validation & Stabilization - Sprint 3`

**Labels:** `infrastructure`, `ci/cd`, `priority:high`

**Assignee:** DEVOPS agent

**Milestone:** Sprint 3 - Phase 3.3

**Descrição:**
```markdown
## 📋 Escopo
Validar CI na `main`, prevenir regressões e garantir pipeline estável durante Fase 3.3.

## 🎯 Tarefas
- [ ] Verificar CI status na `main` (último workflow green?)
- [ ] Registrar logs e warnings recorrentes
- [ ] Validar workflow .github/workflows/ (pytest, lint, type-check)
- [ ] Propor ajustes de robustez (cache, timeouts, deps pinning)
- [ ] Estabelecer monitoramento contínuo
- [ ] Alertar squad em caso de regressão

## ✅ Critérios de Aceitação
- CI confirmado green na `main`
- Logs e warnings documentados
- Pipeline hardening implementado (se necessário)
- Monitoramento ativo estabelecido

## 📁 Arquivos Relevantes
- `.github/workflows/` - workflow configurations
- `pyproject.toml` - dependencies
- `tests/` - test discovery

## ⏱️ Prazo
1-2 dias

## 🔗 Referências
- Prompt: `.github/prompts/plan-devopsCI.prompt.md`
- Copilot Instructions: `.github/copilot-instructions.md`
```

---

### Issue #2: 🏛️ ARCHITECT - BUG Multi-Screen Analysis & Design

**Título:** `[ARCHITECT] Bokeh Multi-Screen Bug Analysis & Phase 4 Design`

**Labels:** `architecture`, `bug`, `phase-4`, `design`

**Assignee:** ARCHITECT agent

**Milestone:** Sprint 3 - Phase 3.3

**Descrição:**
```markdown
## 📋 Escopo
Analisar BUG_BOKEH_RESIZE_MULTI_SCREEN.md (4 soluções), escolher padrão robusto, desenhar arquitetura extensível para Fase 4.

## 🎯 Tarefas
- [ ] Analisar 4 soluções propostas no BUG doc
- [ ] Criar matriz comparativa (Complexity, Performance, Maintainability, Browser Support, Testability)
- [ ] Escolher melhor padrão (recomendação: ResizeObserver)
- [ ] Desenhar arquitetura com pseudocódigo
- [ ] Propor EventBus ou Plugin pattern para extensibilidade
- [ ] Documentar roadmap integração Fase 4
- [ ] Definir owner e timeline Fase 4 (1-2 dias, FULLSTACK lead)

## ✅ Critérios de Aceitação
- Matriz comparativa 4x5 completa
- Padrão escolhido documentado com pseudocódigo
- EventBus/Plugin design especificado
- Roadmap Fase 4 claro
- Análise de risco/mitigação

## 📁 Arquivos Relevantes
- `ISSUES/BUG_BOKEH_RESIZE_MULTI_SCREEN.md` - bug analysis
- `newapp/templates/charts_clean.html` - template target
- `newapp/static/js/` - JS integration point
- `.github/copilot-instructions.md` - architectural patterns

## ⏱️ Prazo
1-2 dias

## 🔗 Referências
- Prompt: `.github/prompts/plan-architectBugAnalysis.prompt.md`
- Status Fase 4: DEFERRED (design only, não implementar)
```

---

### Issue #3: 💻 FULLSTACK - Phase 3.3 Testing & Performance

**Título:** `[FULLSTACK] Phase 3.3 - Execute 15 Tests & Performance Validation`

**Labels:** `testing`, `frontend`, `performance`, `phase-3.3`

**Assignee:** FULLSTACK agent

**Milestone:** Sprint 3 - Phase 3.3

**Descrição:**
```markdown
## 📋 Escopo
Executar 15 testes funcionais Fase 3.3, validar performance (60fps), responsividade, localStorage e cross-browser.

## 🎯 Tarefas
### Setup
- [ ] Atualizar branch `main`
- [ ] Start newapp (poetry install + python main.py)
- [ ] Abrir DevTools (Performance, Network, Console)

### Testes (15 total)
- [ ] Virtual Scroll - 100 linhas render
- [ ] Virtual Scroll - 1000 linhas @ 60fps
- [ ] Virtual Scroll - DOM mutations < 100/sec
- [ ] Drag-to-resize funciona
- [ ] Split.js constraints (20%-80%)
- [ ] localStorage persistence (reload test)
- [ ] Responsividade Desktop (1920x1080)
- [ ] Responsividade Tablet (768x1024)
- [ ] Responsividade Mobile (375x667)
- [ ] Bokeh charts responsive
- [ ] Cross-browser Chrome ✅
- [ ] Cross-browser Firefox ✅
- [ ] Cross-browser Safari ✅
- [ ] Cross-browser Edge ✅
- [ ] Bundle size < 500KB

### Performance Benchmarking
- [ ] FPS average ≥ 60 durante scroll
- [ ] First load < 3s
- [ ] Bundle analyzer rodado

### Documentação
- [ ] 5-6 screenshots key moments
- [ ] Relatório em FASE_3.3_TESTES_RESULTADOS_FINAL.md

## ✅ Critérios de Aceitação
- 15/15 testes executados (pass)
- 60fps benchmark validado
- Cross-browser matrix 4/4
- Screenshots capturados
- Relatório final completo

## 📁 Arquivos Relevantes
- `FASE_3.3_CHECKLIST.md` - test cases
- `newapp/main.py` - app entry point
- `newapp/templates/charts_clean.html` - UI target
- `newapp/static/js/` - JS modules

## ⏱️ Prazo
2-3 dias

## 🔗 Referências
- Prompt: `.github/prompts/plan-fullstackPhase3.3.prompt.md`
- NÃO depende de DEVOPS CI (paralelo)
```

---

### Issue #4: 📊 QUANT - ML Strategies Validation

**Título:** `[QUANT] ML Strategies & Configs Validation - LSTM WDO$/WIN$`

**Labels:** `machine-learning`, `testing`, `validation`, `quant`

**Assignee:** QUANT agent

**Milestone:** Sprint 3 - Phase 3.3

**Descrição:**
```markdown
## 📋 Escopo
Validar LSTM strategies (WDO$, WIN$), configs/main.yaml, data providers (MT5/YFinance), model artifacts e integration test.

## 🎯 Tarefas
### Config Validation
- [ ] Parse configs/main.yaml (YAML válido?)
- [ ] Verificar campos obrigatórios (assets, strategy, provider, data, trading_rules)
- [ ] Validar valores (timeframes, datas, regras)
- [ ] Gerar config_validation_report.txt

### Model Artifacts
- [ ] Listar models/ directory (pattern: *_prod_*)
- [ ] Carregar WDO$ model (keras + scaler + params)
- [ ] Carregar WIN$ model (keras + scaler + params)
- [ ] Verificar integridade files (size > 0, data recente)
- [ ] Gerar model_artifacts_report.txt

### Strategy Execution
- [ ] Test WDO$ LSTMVolatilityStrategy.get_signal()
- [ ] Test WIN$ LSTMVolatilityStrategy.get_signal()
- [ ] Validar output (COMPRA/VENDA/HOLD)
- [ ] Gerar strategy_signal_test.txt

### Data Provider
- [ ] MT5: verificar terminal running (Windows)
- [ ] MT5: tentar conectar e obter candles
- [ ] YFinance: fallback test
- [ ] Gerar provider_connectivity_report.txt

### Integration Test
- [ ] Rodar simulação 1-dia completa
- [ ] Validar P&L razoável (não-explode)
- [ ] Registrar performance

### Relatório Final
- [ ] Consolidar em QUANT_Phase3.3_ML_Validation_Report.md

## ✅ Critérios de Aceitação
- configs/main.yaml validado ✅
- Model artifacts carregam sem erro ✅
- 2 strategies (WDO$, WIN$) retornam signals válidos ✅
- Provider connectivity report ✅
- 1-day sim test completo ✅
- Relatório técnico gerado ✅

## 📁 Arquivos Relevantes
- `configs/main.yaml` - main config
- `models/` - Keras/scaler/params artifacts
- `src/strategies/lstm_volatility.py` - strategy class
- `src/data_handler/provider.py` - data providers
- `src/simulation/engine.py` - simulation engine

## ⏱️ Prazo
2-3 dias

## 🔗 Referências
- Prompt: `.github/prompts/plan-quantMLValidation.prompt.md`
- NÃO depende de DEVOPS CI (paralelo)
```

---

### Issue #5: 📋 PLAN - Roadmap Phases 4-10 & Sprint Planning

**Título:** `[PLAN] Structure Roadmap Phases 4-10 + Sprint Velocity & Milestones`

**Labels:** `planning`, `roadmap`, `epic`, `sprint`

**Assignee:** PLAN agent

**Milestone:** Sprint 3 - Phase 3.3

**Descrição:**
```markdown
## 📋 Escopo
Consolidar outputs 3 workstreams, estruturar épicos Fases 4-10, definir velocidade sprint, criar roadmap living doc.

## 🎯 Tarefas
### Consolidar Inputs
- [ ] Aguardar DEVOPS (CI status)
- [ ] Aguardar ARCHITECT (BUG design + Fase 4 roadmap)
- [ ] Aguardar FULLSTACK (15 test results)
- [ ] Aguardar QUANT (ML validation report)
- [ ] Aguardar GUARDIAN (QA audit + risk matrix)
- [ ] Criar Workstream Summary (2-3 linhas por item)

### Estruturar Épicos Fases 4-10
- [ ] Fase 4: BUG Fix Multi-Screen (1-2 dias, stories + points)
- [ ] Fase 5: Backend Persistence (3-4 dias)
- [ ] Fase 6: Mobile Optimization (2-3 dias)
- [ ] Fase 7: Real-time Updates (2-3 dias)
- [ ] Fase 8: Advanced Trading Features (4-5 dias)
- [ ] Fase 9: ML Improvements (5-7 dias)
- [ ] Fase 10: Documentation & Release (2-3 dias)

### Velocidade Sprint
- [ ] Calcular velocity histórica (Fases 3.1/3.2)
- [ ] Aplicar velocity a Fases 4-10
- [ ] Gerar timeline (4 sprints)

### Living Document
- [ ] Criar Roadmap_Phases_4-10.md (root/)
- [ ] Épicos + stories + points
- [ ] Sprint velocity + timeline
- [ ] Risk matrix por fase
- [ ] Update criteria checklist

### Sprint 1 Board
- [ ] Decompor Fases 4+5 em tasks
- [ ] Priorizar backlog

## ✅ Critérios de Aceitação
- Workstream summary completo ✅
- 7 épicos (Fases 4-10) estruturados ✅
- Sprint velocity calculado ✅
- Roadmap_Phases_4-10.md criado ✅
- Sprint 1 board pronto ✅
- Risk matrix incluída ✅

## 📁 Arquivos Relevantes
- `FASE_3.3_CHECKLIST.md` - current phase
- `RESUMO_GERAL_FASES_1_3.2.md` - historical context
- Outputs de DEVOPS, ARCHITECT, FULLSTACK, QUANT, GUARDIAN

## ⏱️ Prazo
2-3 dias (aguarda inputs)

## 🔗 Referências
- Prompt: `.github/prompts/plan-planRoadmapPhases.prompt.md`
- DEPENDE de: DEVOPS, ARCHITECT, FULLSTACK, QUANT, GUARDIAN
```

---

### Issue #6: 🛡️ GUARDIAN - QA Audit & Compliance Check

**Título:** `[GUARDIAN] QA Audit Phases 1-3.2 + Risk Matrix Phases 4-10`

**Labels:** `qa`, `audit`, `compliance`, `security`, `risk`

**Assignee:** GUARDIAN agent

**Milestone:** Sprint 3 - Phase 3.3

**Descrição:**
```markdown
## 📋 Escopo
Auditar cobertura testes Fases 1-3.2, compliance check vs copilot-instructions.md, security/performance audit, risk matrix Fases 4-10.

## 🎯 Tarefas
### Auditoria Testes Fase 1-3.2
- [ ] Fase 1: Análise Estrutural (3/3 tests)
- [ ] Fase 2: CSS Grid Responsivo (3/3 tests)
- [ ] Fase 3.1: Virtual Scroll (4/4 tests)
- [ ] Fase 3.2: Split.js Drag-to-Resize (5/5 tests)
- [ ] Cross-cutting (2/4 - a11y missing)
- [ ] Gerar coverage_audit_phases_1_3.2.md

### Compliance Check
- [ ] Verificar conventions (signals, model naming, timeframes, timezones)
- [ ] Verificar architecture patterns (config-driven, plugin, providers, threads)
- [ ] Code quality (type hints, docs, error handling, logging)
- [ ] Gerar compliance_check.md

### Security Audit
- [ ] XSS Prevention (template escaping, sanitization)
- [ ] CSRF Protection (tokens, middleware)
- [ ] SQL Injection (parameterized queries)
- [ ] Dependency vulnerabilities (poetry show --outdated)
- [ ] Gerar security_audit.md

### Performance Audit
- [ ] Current performance (Virtual Scroll 60fps, Bokeh <500ms)
- [ ] Projected load Fases 4-10 (DB +100-200ms, WS +50ms, etc.)
- [ ] Bottleneck analysis
- [ ] Scalability recommendations
- [ ] Gerar performance_scalability_audit.md

### Risk Matrix Fases 4-10
- [ ] 9-item risk matrix (por fase)
- [ ] Scores: Probability, Impact, Mitigation
- [ ] Priority ranking

### Accessibility Audit
- [ ] WCAG 2.1 basics (labels, keyboard nav, contrast)
- [ ] Recommendations

### Consolidação
- [ ] Gerar QA_Audit_Report_Phase_3.3.md

## ✅ Critérios de Aceitação
- Coverage audit 15/15 tests ✅
- Compliance matrix ≥90% ✅
- Security findings (no critical) ✅
- Performance assessment ✅
- Risk matrix Fases 4-10 ✅
- a11y findings ✅
- QA_Audit_Report_Phase_3.3.md completo ✅

## 📁 Arquivos Relevantes
- `FASE_3.3_CHECKLIST.md` - test reference
- `.github/copilot-instructions.md` - compliance standards
- `pyproject.toml` - dependencies
- `newapp/` - codebase target
- Outputs de FULLSTACK (test results)

## ⏱️ Prazo
2-3 dias

## 🔗 Referências
- Prompt: `.github/prompts/plan-guardianQAaudit.prompt.md`
- DEPENDE de: FULLSTACK (test results)
```

---

### Issue #7: 🔄 MIGRATION - Consolidate newapp & Legacy Code

**Título:** `[MIGRATION] Consolidate newapp & Legacy Code - Unified Architecture`

**Labels:** `migration`, `refactoring`, `architecture`, `consolidation`

**Assignee:** PLAN/ARCHITECT agents

**Milestone:** Sprint 4 - Migration

**Descrição:**
```markdown
## 📋 Escopo
Padronizar ambiente, unificar configs, consolidar data layer (providers/DB), centralizar strategies/models e migrar execução (simulação/backtest/live) para pilha web/DB-first.

## 🎯 Tarefas
### Step 1: Padronizar Ambiente & Deps
- [ ] Confirmar Python 3.12+ e Poetry
- [ ] Rodar poetry check e poetry install (root + newapp)
- [ ] Mapear dependências MT5 (terminal, conexão, módulos)
- [ ] Validar drivers/DB (SQLite, SQL Server)
- [ ] Conferir variáveis de ambiente e paths
- [ ] Registrar gaps de deps entre root/newapp

### Step 2: Unificar Configs
- [ ] Ampliar newapp/configs/main.yaml com seções live/backtest/setup
- [ ] Espelhar configs/main.yaml em newapp
- [ ] Ajustar loaders em newapp/configs/config.py
- [ ] Decidir: um único config ou adaptadores?

### Step 3: Consolidar Data Layer
- [ ] Tornar newapp/src/data_handler/hybrid_loader.py o provider padrão
- [ ] Adaptar consumidores legados (simulação/live/backtest)
- [ ] Usar loader/repos de newapp/src/database

### Step 4: Centralizar Estratégias/Modelos
- [ ] Centralizar LSTMVolatilityStrategy em newapp/src/strategies/
- [ ] Reexportar para flows legados
- [ ] Alinhar paths de modelos (train_model.py vs newapp/train_model.py)

### Step 5: Migrar Execução
- [ ] Portar simulação (src/simulation/engine.py → newapp)
- [ ] Portar backtest (src/backtest_engine/ → newapp/src/backtest/)
- [ ] Integrar WebSocket/UI em newapp/main.py

### Step 6: Revisão de Duplicidades
- [ ] Code review (root vs newapp)
- [ ] Remover/deprecar versões legadas
- [ ] Atualizar testes em newapp/tests

## ✅ Critérios de Aceitação
- Ambiente padronizado (Python, Poetry, MT5, DB) ✅
- Config único ou adaptador unificado ✅
- Data layer consolidado ✅
- Strategies/models centralizados ✅
- Execução migrada para newapp ✅
- Duplicidades removidas ✅

## 📁 Arquivos Relevantes
- `pyproject.toml` vs `newapp/pyproject.toml`
- `configs/main.yaml` vs `newapp/configs/main.yaml`
- `src/data_handler/` vs `newapp/src/data_handler/`
- `src/strategies/` vs `newapp/src/strategies/`
- `train_model.py` vs `newapp/train_model.py`

## ⏱️ Prazo
5-7 dias

## 🔗 Referências
- Prompt: `.github/prompts/plan-wtnpsTradeMigration.prompt.md`
- Align with: newapp/MIGRATION.md, newapp/ARCHITECTURE.md
```

---

## 📝 Instruções para Criação no GitHub

### Passo 1: Acesse o repositório
```
https://github.com/evandro-godoy/wtnps-trade/issues/new
```

### Passo 2: Para cada issue acima:
1. Copie o **Título**
2. Cole na descrição o conteúdo markdown completo
3. Adicione as **Labels** especificadas
4. Defina o **Milestone**: "Sprint 3 - Phase 3.3" (ou "Sprint 4 - Migration" para Issue #7)
5. Atribua ao **Assignee** correspondente (se aplicável)
6. Clique em **Submit new issue**

### Passo 3: Dependências entre Issues
Após criar todas, adicione comentários linkando dependências:

**Issue #5 (PLAN)** comentar:
```markdown
Depende de:
- #1 (DEVOPS)
- #2 (ARCHITECT)
- #3 (FULLSTACK)
- #4 (QUANT)  
- #6 (GUARDIAN)
```

**Issue #6 (GUARDIAN)** comentar:
```markdown
Depende de:
- #3 (FULLSTACK) - test results input
```

---

## 🚀 Próximos Passos

1. ✅ Criar todas as 7 issues
2. ✅ Atribuir agents/owners
3. ✅ Marcar dependências
4. ✅ Iniciar workstreams paralelos:
   - **WS1:** Issues #1 (DEVOPS) + #2 (ARCHITECT) - 1-2 dias
   - **WS2:** Issues #3 (FULLSTACK) + #4 (QUANT) - 2-3 dias
   - **WS3:** Issues #5 (PLAN) + #6 (GUARDIAN) - 2-3 dias (aguarda WS1+WS2)
   - **Migration:** Issue #7 - Sprint 4 (após Phase 3.3)

---

**Pronto! Issues criadas = Sprint 3 iniciado 🚀**
