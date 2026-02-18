# 💻 Prompt FULLSTACK - Execução Fase 3.3 Testes

**Agent:** FULLSTACK  
**Escopo:** 12 testes Phase 3.3 + Validação Performance  
**Prazo:** 2-3 dias  
**Deliverable:** 12/12 testes ✅ + Relatório

---

## 📋 Missão

Executar 12 testes funcionais Fase 3.3 conforme [FASE_3.3_CHECKLIST.md](../../FASE_3.3_CHECKLIST.md). Validar:
- ✅ Virtual Scroll (1000+ linhas @ 60fps)
- ✅ Drag-to-resize (Split.js + localStorage)
- ✅ Responsividade (Desktop/Tablet/Mobile)
- ✅ Performance Bokeh integration

**NÃO depende de DEVOPS CI** — roda paralelo.

---

## 🎯 Tarefas Específicas

### Task 1: Setup Teste Local
**Objetivo:** Ambiente pronto, browser aberto, console ready  
**Entrada:** [FASE_3.3_CHECKLIST.md](../../FASE_3.3_CHECKLIST.md)  
**Saída:** Ambiente validated, checklist aberto

**Passo a passo:**
1. Clonar/pull branch feature/newapp-ui:
   ```bash
   git checkout feature/newapp-ui
   git pull origin feature/newapp-ui
   ```

2. Start newapp:
   ```bash
   cd newapp
   poetry install
   poetry run python main.py
   ```

3. Abrir browser + DevTools:
   - Chrome/Edge: F12
   - Performance tab ready
   - Network throttle → "Slow 3G" para testes

### Task 2: Executar 12 Testes (Sem Pytest)
**Objetivo:** Validação manual + observação  
**Entrada:** 12 test cases  
**Saída:** Checklist completo (pass/fail + screenshot)

**Referência:** [FASE_3.3_CHECKLIST.md](../../FASE_3.3_CHECKLIST.md) deve listar todos 12.

**Padrão esperado:**
```
Teste 1: Virtual Scroll - Render 100 linhas
- Ação: Browse http://localhost:8000, scroll tabela
- Esperado: <50ms render time, <10 DOM mutations
- Pass/Fail: [ ]
- Screenshot: teste_1_virtualscroll.png

Teste 2: Virtual Scroll - Render 1000 linhas
- Ação: Load 1000 row dataset
- Esperado: 60fps, <3s first load
- Pass/Fail: [ ]
- Performance metric: ___

... (10 mais testes)
```

### Task 3: Performance Benchmarking
**Objetivo:** Validar 60fps target + bundle size  
**Entrada:** Chrome DevTools + bundle analyzer  
**Saída:** Benchmark report

**Passo a passo:**
1. **FPS Test:**
   - DevTools → Performance tab
   - Record 10s scroll + drag-to-resize
   - Verify: Average FPS ≥ 60
   - Screenshot: performance_timings.png

2. **Bundle Size:**
   ```bash
   cd newapp
   npm run build  # ou equivalente
   ls -lh static/js/
   ```
   - virtual-scroll.js: ~15KB (expected: +17KB from baseline)
   - total.js: verify < 500KB

3. **DOM Mutation Metrics:**
   - DevTools → Elements tab
   - Monitor: Mutations/sec during scroll
   - Expected: <100 mutations/sec (healthy)

### Task 4: Responsividade (3 breakpoints)
**Objetivo:** Validar layout em Desktop/Tablet/Mobile  
**Entrada:** Chrome DevTools device emulation  
**Saída:** 3 screenshots (desktop 1920x1080, tablet 768x1024, mobile 375x667)

**Passo a passo:**
1. Desktop (1920x1080):
   - [ ] 70/30 grid visible (charts left, table right)
   - [ ] Drag-to-resize works
   - [ ] Bokeh charts responsive
   - Screenshot: responsive_desktop.png

2. Tablet (768x1024):
   - [ ] 70/30 grid visible or stacked?
   - [ ] Drag-to-resize works/disabled?
   - [ ] Scroll smooth
   - Screenshot: responsive_tablet.png

3. Mobile (375x667):
   - [ ] Stacked layout (charts above table)
   - [ ] Drag disabled (design choice)
   - [ ] Virtual scroll works
   - Screenshot: responsive_mobile.png

### Task 5: localStorage Persistence
**Objetivo:** Drag position persists across reload  
**Entrada:** Browser localStorage  
**Saída:** Verification test

**Passo a passo:**
1. Drag panel divider to 60% (charts) / 40% (table)
2. Refresh page (Ctrl+R)
3. Verify: Grid still 60/40 (not reset to 50/50)
4. Check DevTools → Application → Local Storage
   - Key: "split-sizes" (ou similar)
   - Value: [0.6, 0.4] (ou JSON)
5. Pass: [ ] localStorage key exists and persists

### Task 6: Cross-Browser Compatibility
**Objetivo:** Funciona em Chrome, Firefox, Safari, Edge  
**Entrada:** Multiple browsers  
**Saída:** Compatibility matrix

**Passo a passo:**
1. Test em cada browser:
   - Chrome (latest)
   - Firefox (latest)
   - Safari (latest)
   - Edge (latest)

2. Cada browser: Teste #1-5 acima (resumido)

3. Matriz esperada:
   | Feature | Chrome | Firefox | Safari | Edge |
   |---------|--------|---------|--------|------|
   | Virtual Scroll | ✅ | ✅ | ✅ | ✅ |
   | Drag-to-resize | ✅ | ✅ | ✅ | ✅ |
   | localStorage | ✅ | ✅ | ✅ | ✅ |
   | Bokeh charts | ✅ | ✅ | ⚠️ | ✅ |

---

## 🧪 Automação (Pytest opcional)

Se desejar automação (playwright/puppeteer):
```bash
# Exemplo com Playwright
poetry add pytest-playwright
poetry run playwright install

# Teste exemplo
def test_virtual_scroll_performance():
    page = browser.new_page()
    page.goto("http://localhost:8000")
    # Medir FPS, verificar DOM mutations
```

Mas **foco em manual para agora** — relatório visual mais valioso que números.

---

## 📊 Relatório Final

Após completas os 12 testes, gerar **FASE_3.3_TESTES_RESULTADOS_FINAL.md** com:
- ✅ 12/12 test results (pass/fail)
- ✅ Performance metrics (FPS, load times)
- ✅ Screenshots (5-6 key moments)
- ✅ Cross-browser matrix
- ✅ Recomendações Fase 4 (se encontrar issues)

---

## 🔄 Dependências

| Agente | Tarefa | Impacto |
|--------|--------|---------|
| DEVOPS | CI green | **NÃO depende** (paralelo) |
| QUANT | ML validation | Independente (paralelo) |
| GUARDIAN | QA audit | Recebe outputs FULLSTACK |

**Não aguarde DEVOPS.** Comece testes agora se código feature/newapp-ui esteja pronto.

---

## ✅ Critérios de Aceitação

- [ ] 12/12 testes executados (manual validation)
- [ ] 60fps benchmark validado
- [ ] Responsividade (3 breakpoints) ✅
- [ ] Cross-browser matrix completa (4+ browsers)
- [ ] localStorage persistence ✅
- [ ] 5-6 screenshots key moments
- [ ] Relatório FASE_3.3_TESTES_RESULTADOS_FINAL.md
- [ ] Nenhum bloqueador crítico encontrado (bugs reportados < 3)

---

## 📌 Referências

- Checklist: [FASE_3.3_CHECKLIST.md](../../FASE_3.3_CHECKLIST.md)
- Resultados esperados: [FASE_3.3_TESTES_RESULTADOS.md](../../FASE_3.3_TESTES_RESULTADOS.md)
- Code: [newapp/templates/charts_clean.html](../../newapp/templates/charts_clean.html)
- Mestre: `plan-masterOrchestration.prompt.md`

---

**Próximo:** FULLSTACK fornece test results → GUARDIAN integra em QA Audit.
