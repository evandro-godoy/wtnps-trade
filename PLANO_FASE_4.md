# 🚀 FASE 4: Otimização Multi-Screen e Zoom

**Data Início:** 2026-01-31  
**Status:** 🟡 EM PLANEJAMENTO  
**Objetivo:** Resolver sobreposição do Bokeh em segunda tela e zoom do navegador  
**Duração Estimada:** 2-3 horas  
**Prioridade:** Alta (afeta traders com múltiplos monitores)

---

## 📋 CONTEXTO

### Problema Identificado
O gráfico Bokeh em `/charts-clean` apresenta sobreposição com a tabela de predições quando:
1. Janela do navegador é movida para **segunda tela** com resolução/DPI diferente
2. **Zoom do navegador** é ajustado (Ctrl++ ou Ctrl+-)

### Status Atual
- ✅ **Funciona perfeitamente:** Desktop Full HD em tela primária
- ❌ **Falha:** Multi-screen e zoom do navegador
- 📄 **Documentado:** `ISSUES/BUG_BOKEH_RESIZE_MULTI_SCREEN.md`

### Causa Raiz
1. `ResizeObserver` não detecta mudanças de DPI/zoom do navegador
2. Bokeh `sizing_mode='stretch_width'` calcula largura com base no viewport inicial
3. CSS Grid perde sincronização após mudança de contexto visual

---

## 🎯 OBJETIVOS DA FASE 4

### Objetivo Principal
✅ **Eliminar sobreposição** do gráfico Bokeh em qualquer cenário de tela/zoom

### Objetivos Específicos
1. Implementar **MutationObserver** para detectar mudanças de estilo Bokeh
2. Adicionar **Event Listeners** para zoom do navegador (visualViewport)
3. Criar **mecanismo de recalculo forçado** do layout Bokeh
4. Validar em **múltiplas resoluções e DPIs**
5. Manter **performance 60fps** após implementação

---

## 🛠️ SOLUÇÃO ESCOLHIDA

### Abordagem: MutationObserver + Visual Viewport API

**Por que esta solução?**
- ✅ Mínima mudança no código existente
- ✅ Não quebra arquitetura atual
- ✅ Funciona com Bokeh 3.8.1
- ✅ Testável incrementalmente
- ✅ Performance overhead aceitável (~5ms)

**Alternativas Descartadas:**
- ❌ Solução 1 (`sizing_mode='fixed'`): Perde responsividade
- ❌ Solução 3 (Bokeh Server): Mudança arquitetural grande
- ❌ Solução 4 (Plotly.js): Migração completa de biblioteca

---

## 📝 TAREFAS TÉCNICAS

### Tarefa 4.1: Implementar MutationObserver
**Tempo Estimado:** 45 minutos  
**Arquivo:** `newapp/templates/charts_clean.html`

**Passos:**
1. Criar função `initBokehMutationObserver()`
2. Observar mudanças no atributo `style` do container Bokeh
3. Detectar mudanças de `width` ou `height`
4. Trigger recalculo do Split.js e Bokeh layout
5. Adicionar debounce de 100ms para evitar loops

**Código esperado:**
```javascript
function initBokehMutationObserver() {
  const bokehRoot = document.querySelector('.bk-root');
  if (!bokehRoot) return;

  const observer = new MutationObserver(debounce((mutations) => {
    mutations.forEach(mutation => {
      if (mutation.attributeName === 'style') {
        // Recalcular layout
        window.dispatchEvent(new Event('resize'));
        
        // Re-render virtual scroll se necessário
        if (window.mlSignalsVirtualScroll) {
          window.mlSignalsVirtualScroll.render();
        }
      }
    });
  }, 100));

  observer.observe(bokehRoot, {
    attributes: true,
    attributeFilter: ['style']
  });

  console.log('✅ MutationObserver initialized for Bokeh');
}
```

---

### Tarefa 4.2: Adicionar Visual Viewport API Listener
**Tempo Estimado:** 30 minutos  
**Arquivo:** `newapp/templates/charts_clean.html`

**Passos:**
1. Detectar eventos de zoom via `visualViewport`
2. Calcular escala atual vs escala anterior
3. Trigger re-render de Bokeh quando escala muda
4. Atualizar proporções do Split.js

**Código esperado:**
```javascript
function initZoomDetection() {
  if (!window.visualViewport) {
    console.warn('⚠️ VisualViewport API not supported');
    return;
  }

  let previousScale = window.visualViewport.scale;

  window.visualViewport.addEventListener('resize', debounce(() => {
    const currentScale = window.visualViewport.scale;
    
    if (Math.abs(currentScale - previousScale) > 0.01) {
      console.log(`🔍 Zoom detected: ${previousScale.toFixed(2)} → ${currentScale.toFixed(2)}`);
      
      // Force Bokeh re-layout
      if (window.Bokeh) {
        const bokehDoc = window.Bokeh.documents?.[0];
        if (bokehDoc) {
          bokehDoc.resize();
        }
      }
      
      previousScale = currentScale;
    }
  }, 150));

  console.log('✅ Zoom detection initialized');
}
```

---

### Tarefa 4.3: Implementar Force Re-layout para Bokeh
**Tempo Estimado:** 30 minutos  
**Arquivo:** `newapp/templates/charts_clean.html`

**Passos:**
1. Criar função `forceBokehRelayout()`
2. Invalidar cache de dimensões do Bokeh
3. Re-calcular gridplot dimensions
4. Dispatch resize event para componentes

**Código esperado:**
```javascript
function forceBokehRelayout() {
  if (!window.Bokeh) {
    console.warn('⚠️ Bokeh not loaded');
    return;
  }

  const bokehDoc = window.Bokeh.documents?.[0];
  if (!bokehDoc) return;

  // Get current container dimensions
  const chartArea = document.getElementById('chart-area');
  const newWidth = chartArea.clientWidth;
  const newHeight = chartArea.clientHeight;

  console.log(`📐 Force relayout: ${newWidth}x${newHeight}`);

  // Force Bokeh to recalculate
  bokehDoc.resize();
  
  // Trigger browser resize event
  window.dispatchEvent(new Event('resize'));
}
```

---

### Tarefa 4.4: Integrar com Sistema Existente
**Tempo Estimado:** 30 minutos  
**Arquivos:** `newapp/templates/charts_clean.html`, `newapp/static/js/virtual-scroll.js`

**Passos:**
1. Chamar `initBokehMutationObserver()` após Bokeh carregar
2. Chamar `initZoomDetection()` no `DOMContentLoaded`
3. Integrar `forceBokehRelayout()` com Split.js `onDrag` callback
4. Testar compatibilidade com Virtual Scroll

**Modificações no código existente:**
```javascript
// Em charts_clean.html, após inicialização do Bokeh
document.addEventListener('DOMContentLoaded', () => {
  // ... código existente ...
  
  // NOVO: Inicializar observadores
  initBokehMutationObserver();
  initZoomDetection();
  
  // Integrar com Split.js
  if (window.Split) {
    const splitInstance = Split(/* ... existente ... */, {
      onDrag: (sizes) => {
        // ... código existente ...
        forceBokehRelayout(); // NOVO
      }
    });
  }
});
```

---

### Tarefa 4.5: Adicionar Debounce Helper
**Tempo Estimado:** 15 minutos  
**Arquivo:** `newapp/templates/charts_clean.html`

**Código esperado:**
```javascript
/**
 * Debounce function - prevents function from being called too frequently
 * @param {Function} func - Function to debounce
 * @param {number} wait - Milliseconds to wait
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
```

---

## 🧪 PLANO DE TESTES

### Teste 4.1: Multi-Screen com Mesma Resolução
**Ambiente:** 2 monitores Full HD (1920x1080)

1. Abrir `/charts-clean` na tela primária
2. ✅ Verificar layout 70/30 correto
3. Mover janela para segunda tela
4. ✅ **ESPERADO:** Layout mantém proporção, sem overlaps
5. Voltar para tela primária
6. ✅ **ESPERADO:** Layout continua correto

**Critério de Sucesso:** Nenhuma sobreposição em ambas as telas

---

### Teste 4.2: Multi-Screen com DPI Diferente
**Ambiente:** Monitor 1 (100% scale) + Monitor 2 (150% scale)

1. Abrir `/charts-clean` em monitor 1 (100%)
2. Mover para monitor 2 (150% DPI)
3. ✅ **ESPERADO:** Bokeh recalcula dimensões, sem overlaps
4. Console log: `🔍 Zoom detected: 1.00 → 1.50`

**Critério de Sucesso:** MutationObserver detecta mudança e re-renderiza

---

### Teste 4.3: Zoom Navegador (Ctrl++ / Ctrl+-)
**Ambiente:** Desktop Full HD

1. Abrir `/charts-clean` com zoom 100%
2. Pressionar **Ctrl++** 3 vezes (zoom 150%)
3. ✅ **ESPERADO:** Layout adapta, sem overlaps
4. Console: `🔍 Zoom detected: 1.00 → 1.50`
5. Pressionar **Ctrl+-** 3 vezes (voltar 100%)
6. ✅ **ESPERADO:** Layout volta ao normal

**Critério de Sucesso:** Bokeh redimensiona em cada mudança de zoom

---

### Teste 4.4: Performance com Observers
**Ambiente:** Desktop Full HD

1. Abrir DevTools → Performance
2. Iniciar gravação
3. Drag gutter 10 vezes (esquerda/direita)
4. Zoom navegador 5 vezes
5. Parar gravação
6. ✅ **ESPERADO:** FPS > 55, nenhum long task >50ms

**Critério de Sucesso:** Overhead dos observers < 10ms por evento

---

### Teste 4.5: Compatibilidade Cross-Browser
**Ambientes:** Chrome, Firefox, Edge

1. Testar MutationObserver em cada navegador
2. Testar Visual Viewport API (pode não ter suporte em Firefox antigo)
3. ✅ **ESPERADO:** Graceful degradation se API não disponível

**Critério de Sucesso:** Sem erros no console, funciona em 90%+ dos browsers

---

## 📊 CRITÉRIO DE SUCESSO FASE 4

Para marcar como **COMPLETA**, todos os itens abaixo devem ser ✅:

- [ ] MutationObserver implementado e funcional
- [ ] Visual Viewport API integrada
- [ ] Force re-layout implementado
- [ ] Debounce helper adicionado
- [ ] Integração com Split.js e Virtual Scroll
- [ ] Teste 4.1: Multi-screen mesma resolução **PASSOU**
- [ ] Teste 4.2: Multi-screen DPI diferente **PASSOU**
- [ ] Teste 4.3: Zoom navegador **PASSOU**
- [ ] Teste 4.4: Performance < 10ms overhead **PASSOU**
- [ ] Teste 4.5: Cross-browser 90%+ **PASSOU**
- [ ] Console sem erros críticos
- [ ] Documentação atualizada

---

## 📂 ARQUIVOS AFETADOS

### Modificados
```
newapp/templates/charts_clean.html    [+150 linhas JS]
  - initBokehMutationObserver()
  - initZoomDetection()
  - forceBokehRelayout()
  - debounce()
  - Integração com Split.js
```

### Novos (opcional)
```
newapp/static/js/bokeh-resize-fix.js   [Se preferir arquivo separado]
```

---

## ⚠️ RISCOS E MITIGAÇÕES

### Risco 1: Performance Degradation
**Probabilidade:** Média  
**Impacto:** Alto (pode causar lag)  
**Mitigação:** 
- Usar debounce de 100-150ms
- Limitar observação apenas ao Bokeh root
- Testar com profiler antes de deploy

### Risco 2: Loop Infinito de Observers
**Probabilidade:** Baixa  
**Impacto:** Crítico (trava navegador)  
**Mitigação:**
- Adicionar flag `isResizing` para prevenir re-entrada
- Limitar número de callbacks por segundo (max 10)

### Risco 3: Visual Viewport API Não Suportada
**Probabilidade:** Média (Firefox < 90)  
**Impacto:** Baixo (zoom não funcionará)  
**Mitigação:**
- Detecção de feature: `if (!window.visualViewport) { console.warn(...) }`
- Fallback: MutationObserver continua funcionando

### Risco 4: Bokeh API Interna Muda
**Probabilidade:** Baixa  
**Impacto:** Médio  
**Mitigação:**
- Usar apenas APIs públicas de `Bokeh.documents`
- Adicionar validações: `if (!bokehDoc) return;`

---

## 🔄 ROLLBACK PLAN

Se implementação causar problemas críticos:

1. **Desabilitar Observers:**
   ```javascript
   // Comentar chamadas:
   // initBokehMutationObserver(); 
   // initZoomDetection();
   ```

2. **Remover Force Re-layout do Split.js:**
   ```javascript
   onDrag: (sizes) => {
     // ... código existente ...
     // forceBokehRelayout(); // COMENTAR
   }
   ```

3. **Reverter para estado Fase 3.3:**
   ```bash
   git diff HEAD~1 newapp/templates/charts_clean.html
   git checkout HEAD~1 -- newapp/templates/charts_clean.html
   ```

---

## 📝 DOCUMENTAÇÃO A ATUALIZAR

Após conclusão da Fase 4:

### 1. Atualizar `BUG_BOKEH_RESIZE_MULTI_SCREEN.md`
```markdown
## Status
✅ **RESOLVIDO** - Fase 4 (2026-01-31)

## Solução Implementada
- MutationObserver para detectar mudanças de estilo
- Visual Viewport API para zoom do navegador
- Force re-layout integrado com Split.js

## Validação
- ✅ Testado em multi-screen
- ✅ Testado com zoom navegador
- ✅ Performance mantida (60fps)
```

### 2. Atualizar `RESUMO_GERAL_FASES_1_3.2.md`
Renomear para `RESUMO_GERAL_FASES_1_4.md` e adicionar:
```markdown
## ✅ Fase 4: Otimização Multi-Screen
- Implementou MutationObserver
- Adicionou Visual Viewport API
- Resolveu bug de sobreposição
- **Duração:** X horas | **Status:** Completa
```

### 3. Criar `FASE_4_STATUS.md`
Sumário técnico similar aos documentos de fases anteriores

---

## 🎯 PRÓXIMOS PASSOS APÓS FASE 4

### Se Fase 4 for bem-sucedida:
- ✅ Issue `BUG_BOKEH_RESIZE_MULTI_SCREEN.md` pode ser fechada
- ✅ UI está 100% funcional em todos os cenários
- ✅ Preparar para Fase 5 (Backend Persistence)

### Se Fase 4 falhar:
- ⚠️ Reavaliar Solução 3 (Bokeh Server)
- ⚠️ Considerar Solução 4 (Migração para Plotly.js)
- ⚠️ Documentar como limitação conhecida e workaround

---

## 💡 NOTAS TÉCNICAS

### MutationObserver Performance
- **Overhead típico:** 3-8ms por mutation
- **Debounce recomendado:** 100-150ms
- **Browser support:** 98%+ (IE11+)

### Visual Viewport API
- **Browser support:** 90%+ (Chrome 61+, Firefox 91+, Safari 13+)
- **Fallback necessário:** Firefox < 91
- **Performance:** Negligível (<1ms)

### Bokeh.documents API
- **Estável desde:** Bokeh 2.x
- **Método usado:** `bokehDoc.resize()`
- **Alternativa:** `window.dispatchEvent(new Event('resize'))`

---

## ✅ SIGN-OFF CHECKLIST

Antes de marcar Fase 4 como completa:

- [ ] Code review interno feito
- [ ] Todos os 5 testes passaram
- [ ] Performance validada (<10ms overhead)
- [ ] Documentação atualizada
- [ ] Issue original atualizada
- [ ] Commit com mensagem descritiva
- [ ] Branch pronto para merge (se aprovado)

---

**Fase 4 Estimativa Total:** 2-3 horas  
**Prioridade:** Alta (afeta UX de traders multi-monitor)  
**Status:** 🟡 Aguardando início da implementação

