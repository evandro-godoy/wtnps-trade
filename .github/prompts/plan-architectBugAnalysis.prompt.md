# 🏛️ Prompt ARCHITECT - Análise BUG & Padrão Extensível

**Agent:** ARCHITECT  
**Escopo:** BUG multi-screen Bokeh + Roadmap Solução  
**Prazo:** 1-2 dias  
**Status:** Deferred (Fase 4 candidate)

---

## 📋 Missão

Analisar BUG_BOKEH_RESIZE_MULTI_SCREEN.md (4 soluções propostas), escolher pattern mais robusto, desenhar arquitetura extensível para Fase 4. Não implementar agora; desenhar e validar com PLAN para roadmap.

---

## 🎯 Tarefas Específicas

### Task 1: Análise das 4 Soluções Propostas
**Objetivo:** Avaliar trade-offs, escolher melhor padrão  
**Entrada:** [ISSUES/BUG_BOKEH_RESIZE_MULTI_SCREEN.md](../../ISSUES/BUG_BOKEH_RESIZE_MULTI_SCREEN.md)  
**Saída:** Decisão documentada + matriz comparativa

**Passo a passo:**
1. Ler completo BUG_BOKEH_RESIZE_MULTI_SCREEN.md
2. Para cada das 4 soluções, avaliar:
   - **Complexity:** Linhas de código, dependências novas?
   - **Performance:** Impacto renderização/DOM?
   - **Maintainability:** Código claro para próximos devs?
   - **Browser Support:** Todos navegadores modernos?
   - **Testability:** Fácil testar automaticamente?

3. Criar matrix 4x5 comparativa

**Exemplo esperado:**

| Solução | Complexity | Perf | Maintain | Browser | Test |
|---------|-----------|------|----------|---------|------|
| 1: MutationObserver | Medium | Good | ✅ | All | ✅ |
| 2: ResizeObserver | Low | Best | ✅ | Modern | ✅ |
| 3: CSS fix | Low | Best | ⚠️ | Iffy | Hard |
| 4: iFrame wrapper | High | Poor | ❌ | All | ❌ |

### Task 2: Desenhar Padrão Escolhido
**Objetivo:** Especificar arquitetura de correção  
**Entrada:** Matriz + análise de trade-offs  
**Saída:** Design doc com pseudocódigo/structure

**Passo a passo:**
1. Escolher melhor solução (recomendação: ResizeObserver para modern browsers)
2. Desenhar estrutura:
   - Onde hook no código (newapp/templates/charts_clean.html? newapp/static/js)?
   - Quais files alterar (CSS, JS, HTML)?
   - Integração com Virtual Scroll já existente?
   - Integração com Split.js drag?

3. Pseudocódigo/estrutura:
   ```
   ResizeObserver Pattern (recomendado):
   - newapp/static/js/bokeh-observer.js (novo)
     - Inicialize ResizeObserver when Bokeh chart DOM mounted
     - On resize: recalculate grid constraints, trigger Bokeh.resize()
     - Fallback: MutationObserver se ResizeObserver unavailable
   
   - newapp/templates/charts_clean.html
     - Add data-bokeh-chart="true" to container
     - Import bokeh-observer.js after virtual-scroll.js
   
   - Integration:
     - Virtual Scroll notify ResizeObserver on scroll events? YES
     - Split.js notify on drag? YES (hook to splitInstance.on('drag'))
   ```

### Task 3: Padrão Extensível & Coupling
**Objetivo:** Garantir que solução BUG não quebra Phases 4-10  
**Entrada:** Desenho + [copilot-instructions.md](../../.github/copilot-instructions.md)  
**Saída:** EventBus design ou padrão plugin

**Passo a passo:**
1. Verificar: solução BUG pode ser plugin isolado?
   - Não deve modificar Virtual Scroll core
   - Não deve modificar Split.js core
   - Deve ser desativável/testável isoladamente

2. Propor padrão:
   ```
   Option A: EventBus Central
   - newapp/src/events/EventEmitter.ts
   - Virtual Scroll emits "scroll:end"
   - Split.js emits "panel:resized"
   - Bokeh Observer listens, reacts independently
   
   Option B: Plugin Registry
   - newapp/static/js/plugins/registry.js
   - registerPlugin('bokeh-resize-handler', handler)
   - Plugins notified on core events
   ```

3. RECOMENDAR EventBus (menos coupling)

### Task 4: Roadmap Integração Fase 4
**Objetivo:** Documentar quando + como implementar  
**Entrada:** Padrão escolhido + PLAN roadmap  
**Saída:** Integração spec para Fase 4

**Passo a passo:**
1. Providenciar timing:
   - Fase 3.3: Testes finais (não toca BUG)
   - Fase 4: BUG fix + EventBus (1-2 dias)
   - Fase 5+: Novos features aprimorando EventBus

2. Definir owner Fase 4:
   - ARCHITECT: Design aprovado
   - FULLSTACK: Implementa ResizeObserver + hooks
   - GUARDIAN: Testa cross-browser (Chrome, Safari, Firefox, Edge)

3. Risco/Mitigation:
   - **Risk:** ResizeObserver change performance
   - **Mitigation:** Benchmark antes/depois, throttle resize events
   - **Test:** Fase 4 includes performance suite

---

## 🏗️ Padrões Arquiteturais a Preservar

Ref: [.github/copilot-instructions.md](../../.github/copilot-instructions.md)

- ✅ Config-driven framework (configs/main.yaml)
- ✅ Plugin pattern (strategies herdam de base.py)
- ✅ Provider abstraction (MT5/YFinance interchangeable)
- ✅ Thread separation (GUI main + worker queues)

**BUG fix deve respeitar estes padrões** → EventBus reúsa padrão Agent-based.

---

## 🔄 Dependências

| Agente | Tarefa | Impacto |
|--------|--------|---------|
| PLAN | Roadmap Fases 4-10 | Sincroniza com BUG timeline |
| FULLSTACK | Fase 3.3 Testing | Independente (paralelo) |
| GUARDIAN | QA Audit | Independente (paralelo) |

**ARCHITECT → PLAN:** Fornecer design + recomendação integração Fase 4 para roadmap.

---

## ✅ Critérios de Aceitação

- [ ] Matriz comparativa 4 soluções (trade-offs claros)
- [ ] Padrão arquitetural escolhido (com justificativa)
- [ ] Pseudocódigo/estrutura desenhada (onde alterar, o que adicionar)
- [ ] EventBus (ou plugin) pattern proposto (acoplamento baixo)
- [ ] Roadmap Fase 4 claro (timeline, owner, risks)
- [ ] Design doc salvos em [ISSUES/](../../ISSUES/) ou PR comment

---

## 📌 Referências

- BUG: [ISSUES/BUG_BOKEH_RESIZE_MULTI_SCREEN.md](../../ISSUES/BUG_BOKEH_RESIZE_MULTI_SCREEN.md)
- Architecture: [newapp/ARCHITECTURE.md](../../newapp/ARCHITECTURE.md)
- Copilot Instructions: [.github/copilot-instructions.md](../../.github/copilot-instructions.md)
- Mestre: `plan-masterOrchestration.prompt.md`

---

**Próximo:** ARCHITECT fornece output → PLAN integra em Roadmap Fases 4-10. Não bloqueado por outro agent.
