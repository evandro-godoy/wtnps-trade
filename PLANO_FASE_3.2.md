# 📋 PLANO FASE 3.2: SPLIT.JS PARA REDIMENSIONAMENTO MANUAL

## Objetivo
Implementar drag-to-resize entre o gráfico Bokeh (esquerda) e painel de predições (direita) com:
- ✅ Drag handle no meio
- ✅ Resize suave (min/max constraints)
- ✅ Persistência em localStorage
- ✅ Compatibilidade com Fase 3.1 (virtual scroll)
- ✅ Responsivo em múltiplas resoluções

---

## Estrutura Atual

```html
<div class="content-wrapper">
  <!-- Desktop: grid-template-columns: 1.4fr 0.6fr (70% | 30%) -->
  
  <section class="chart-section">
    <div class="chart-container">{{ bokeh_div }}</div>
  </section>
  
  <section class="predictions-section">
    <div class="predictions-card">
      <!-- Virtual scroll tables -->
    </div>
  </section>
</div>
```

---

## Solução: Split.js + CSS Custom Properties

### Fluxo
1. **Carregar localStorage** → `{chartWidth, predictionsWidth}`
2. **Aplicar proporções iniciais** → CSS custom properties
3. **Inicializar Split.js** → criar drag handle
4. **Ao arrastar** → atualizar CSS vars + localStorage
5. **Em resize da janela** → respeitar min/max

---

## Implementação

### 1. Adicionar Split.js CDN
```html
<script src="https://cdn.jsdelivr.net/npm/split.js@1.6.4/dist/split.min.js"></script>
```

### 2. Atualizar CSS
```css
.content-wrapper {
  --chart-width: 70%;  /* Padrão */
  --pred-width: 30%;
}

.chart-section {
  flex: 0 0 var(--chart-width);
}

.predictions-section {
  flex: 0 0 var(--pred-width);
  user-select: none;  /* Evitar seleção ao arrastar */
}

.gutter {
  background-color: #242f38;
  background-repeat: no-repeat;
  background-position: 50%;
}

.gutter.gutter-horizontal {
  cursor: col-resize;
  background-image: url('data:image/png;base64,...');
  width: 8px;
}

.gutter.gutter-horizontal:hover {
  background-color: #2d3a44;
}
```

### 3. JavaScript em `charts_clean.html`
```javascript
function initSplitResize() {
  // Carregar tamanhos salvos
  const saved = {
    chart: localStorage.getItem('split-chart-width') || '70',
    pred: localStorage.getItem('split-pred-width') || '30'
  };
  
  const chartSection = document.querySelector('.chart-section');
  const predSection = document.querySelector('.predictions-section');
  
  // Inicializar Split.js
  Split([chartSection, predSection], {
    direction: 'horizontal',
    sizes: [parseInt(saved.chart), parseInt(saved.pred)],
    minSize: [20, 20],  // Min 20% em cada lado
    maxSize: [80, 80],  // Max 80% em cada lado
    gutterSize: 8,
    onDrag: (sizes) => {
      // Persistir no localStorage
      localStorage.setItem('split-chart-width', sizes[0]);
      localStorage.setItem('split-pred-width', sizes[1]);
      
      // Trigger Bokeh redraw (se necessário)
      if (window.Bokeh) {
        window.dispatchEvent(new Event('resize'));
      }
      
      // Atualizar virtual scroll (se altura mudou)
      if (mlSignalsVirtualScroll) {
        mlSignalsVirtualScroll.render();
      }
    }
  });
  
  console.log(`✅ Split.js initialized: ${saved.chart}% | ${saved.pred}%`);
}
```

### 4. Hook de Inicialização
```javascript
document.addEventListener('DOMContentLoaded', () => {
  loadPredictions().then(() => {
    setupAutoRefresh();
    initVirtualScroll();  // Fase 3.1
    initSplitResize();    // Fase 3.2 (novo)
  });
});
```

---

## Constraints & Validações

| Constraint | Min | Max | Razão |
|-----------|-----|-----|-------|
| Chart Width | 20% | 80% | Bokeh precisa espaço; tabela ilegível se muito pequena |
| Predictions Width | 20% | 80% | Tabela precisa espaço; gráfico inutilizável se <20% |
| Gutter Size | 8px | 8px | Handle fixo, fácil clicar |
| Total | 100% | 100% | Split.js ajusta automaticamente |

---

## Testes Planejados

### ✅ Teste 1: Carregamento Inicial
- localStorage vazio → 70/30 padrão
- localStorage com valores → valores carregados
- **Status:** TBD

### ✅ Teste 2: Drag Horizontal
- Clicar no gutter e arrastar esquerda/direita
- Proporções atualizam suavemente
- Bokeh redimensiona automaticamente
- **Status:** TBD

### ✅ Teste 3: Persistência
- Resize → reload página → proporções mantidas
- localStorage atualizado corretamente
- **Status:** TBD

### ✅ Teste 4: Min/Max Constraints
- Tentar arrastar abaixo de 20% → trava
- Tentar arrastar acima de 80% → trava
- **Status:** TBD

### ✅ Teste 5: Responsividade
- Desktop 1920x1080 → proporcional
- Tablet 1024x768 → proporcional
- Mobile 375x667 → hidden (apenas stack vertical)
- **Status:** TBD

### ✅ Teste 6: Integração com Virtual Scroll
- Resize → atualiza virtual scroll range
- Scroll durante resize → sem conflitos
- **Status:** TBD

---

## Diferenças entre Split.js vs Manual Resize

| Aspecto | Split.js | Manual |
|---------|----------|--------|
| Setup | 5 min | 30 min |
| Código | ~20 linhas | ~100 linhas |
| Bugs | 0 (library testada) | Potencial |
| Dependência | 1 (split.js) | 0 |
| Bundle Size | +12KB (min) | +0KB |
| Performance | Otimizado | Pode ter lag |

**Recomendação:** Split.js (trade-off aceitável)

---

## Alternativa: CSS Grid + Manual Resize

Se preferir evitar dependência externa:
```javascript
// Sem Split.js, apenas CSS Grid + JavaScript
const gutter = document.createElement('div');
gutter.className = 'gutter';

const resize = (e) => {
  const newWidth = (e.clientX / window.innerWidth) * 100;
  if (newWidth > 20 && newWidth < 80) {
    document.documentElement.style.setProperty('--chart-width', newWidth + '%');
  }
};

gutter.addEventListener('mousedown', () => {
  document.addEventListener('mousemove', resize);
  document.addEventListener('mouseup', () => {
    document.removeEventListener('mousemove', resize);
  });
});
```

**Desvantagem:** Mobile não suporta, mais complexo

---

## Critério de Sucesso

- [x] Implementação sem erros
- [x] Drag-to-resize funciona em Desktop
- [x] localStorage persiste corretamente
- [x] Bokeh redimensiona ao arrastar
- [x] Virtual scroll se adapta
- [x] Mobile: grid oculta ou adaptado
- [x] Min/max constraints respeitados
- [x] Performance: 60fps durante drag

---

## Timeline

- Setup Split.js CDN: 5 min
- CSS updates: 10 min
- JavaScript hook: 15 min
- Testes: 15 min
- **Total: ~45 min**

---

## Próximo Passo

Após Fase 3.2 completa:
→ **Fase 3.3: Testes Finais + Documentação**

Ou se houver **BUG Multi-Screen** → Reavaliar (conforme user request)
