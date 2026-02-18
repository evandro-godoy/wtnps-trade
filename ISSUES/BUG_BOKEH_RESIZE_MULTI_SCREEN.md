# 🐛 BUG: Bokeh Chart Sobreposição em Segunda Tela e Zoom do Navegador

## Descrição

O gráfico Bokeh gerado em `/charts-clean` apresenta **sobreposição com a tabela de predições** quando:
1. A janela do navegador é movida para uma **segunda tela/monitor** com resolução diferente
2. O **zoom do navegador** é ajustado (Ctrl++ ou Ctrl+-)

Embora o layout funcione corretamente em **Desktop Full HD na tela primária**, o componente falha em se redimensionar dinamicamente quando há mudanças de DPI, zoom ou dimensões físicas da tela.

---

## Informações de Ambiente

- **Navegadores afetados:** Chrome, Edge (todos baseados em Chromium)
- **Versão do Bokeh:** 3.8.1
- **FastAPI/Python:** Python 3.12+, Poetry
- **Branch:** `main`
- **Arquivo afetado:** `newapp/templates/charts_clean.html`, `newapp/plotting.py`, `newapp/static/css/style.css`

---

## Passos para Reproduzir

### Caso 1: Segunda Tela
1. Abrir http://localhost:8000/charts-clean em navegador na **tela primária**
2. Layout exibe corretamente com grid 70% (gráfico) | 30% (predições)
3. **Mover janela do navegador para segunda tela** (ou monitor com DPI/resolução diferente)
4. ❌ **Resultado:** Gráfico Bokeh sobrepõe a tabela de predições
5. ✅ **Esperado:** Layout mantém proporção 70/30, sem overlaps

### Caso 2: Zoom do Navegador
1. Abrir http://localhost:8000/charts-clean
2. Pressionar **Ctrl++** (aumentar zoom) ou **Ctrl+-** (diminuir zoom) várias vezes
3. ❌ **Resultado:** 
   - Gráfico não se adapta ao novo tamanho efetivo
   - Tabela é empurrada para baixo ou fica sobreposta
   - Scrollbars horizontais indesejados aparecem
4. ✅ **Esperado:** Layout se reajusta fluidamente sem sobreposição

---

## Comportamento Observado

### ❌ **Comportamento Atual**
```
┌─────────────────────────────────────────────┐
│ Sidebar │  BOKEH CHART                      │
│         │  [████████████████████]            │
│         │                                    │
│         │  [████████ PRED GRID ████]  ← Overlap!
│         │                                    │
└─────────────────────────────────────────────┘
```

### ✅ **Comportamento Esperado**
```
┌─────────────────────────────────────────────┐
│ Sidebar │ BOKEH  │ PRED                     │
│         │ CHART  │ GRID                     │
│         │        │ ┌──────────────────┐     │
│         │ (70%)  │ │ Data | Tipo | ... │     │
│         │        │ │ ──── | ──── | ──── │     │
│         │        │ │ Scroll Area     │     │
│         │        │ └──────────────────┘     │
│         │        │ (30%)                    │
└─────────────────────────────────────────────┘
```

---

## Análise Técnica

### Causa Raiz Identificada

1. **ResizeObserver não funciona corretamente com Bokeh 3.8.1**
   - `ResizeObserver` detecta mudança de tamanho, mas Bokeh não processa corretamente
   - Documento Bokeh não recebe trigger de re-render

2. **CSS Grid com `sizing_mode='stretch_width'` do Bokeh entra em conflito**
   - `sizing_mode='stretch_width'` calcula largura com base no **viewport inicial**
   - Mudanças de DPI/zoom não invalidam este cálculo
   - Layout CSS Grid perde sincronização

3. **Ausência de `min-height: 0` em `.bk-pane-manager`**
   - Bokeh gridplot não respeita constrangimentos de altura
   - Componentes transbordão o container pai

4. **Zoom do navegador não ativa resize events CSS**
   - `ResizeObserver` não dispara ao usar Ctrl++ 
   - Apenas redimensionamento da janela ativa observer

---

## Impacto

- 🔴 **Severidade:** Média (afeta Multi-Monitor)
- 🟡 **Frequência:** Alto (ocorre toda vez que move para outra tela ou ajusta zoom)
- 🟡 **Escopo:** Apenas `/charts-clean` (outras páginas não afetadas)
- 🟢 **Usuários impactados:** Traders com setup multi-monitor (muito comum em trading)

---

## Possíveis Soluções

### Solução 1: Usar `sizing_mode='fixed'` + JavaScript Manual
```python
# Em newapp/plotting.py
fig_candle = figure(
    sizing_mode='fixed',  # Trocar de 'stretch_width'
    width=800,  # Dinâmico via JS
    height=350,
    ...
)
```

**Prós:** Controle total via JavaScript  
**Contras:** Mais código JS, menos automático

---

### Solução 2: Usar MutationObserver em vez de ResizeObserver
```javascript
const observer = new MutationObserver((mutations) => {
  // Detectar mudanças no DOM do Bokeh
  // Recalcular proporcionalidade
});

observer.observe(chartContainer, {
  attributes: true,
  attributeFilter: ['style']
});
```

**Prós:** Mais confiável com Bokeh  
**Contras:** Menos padrão, pode ter overhead

---

### Solução 3: Usar Bokeh Server ao invés de Static Components
```python
# Usar bokeh serve em vez de components()
# Permite gerenciamento automático de re-renders
```

**Prós:** Suporte nativo ao resize  
**Contras:** Mudança arquitetural significativa, requer WebSocket

---

### Solução 4: Usar Canvas/SVG com Plotly.js
```python
# Migrar de Bokeh para Plotly
# Plotly tem melhor suporte a responsive design
```

**Prós:** Melhor responsividade nativa  
**Contras:** Migração de todo código gráfico

---

## Recomendação para Curto Prazo

**Bloquear/Documentar a limitação:**
- Adicionar aviso na interface: "Para melhor experiência multi-monitor, mantenha a página em uma única tela"
- Desabilitar zoom (meta tag viewport)
- Documentar como workaround

---

## Recomendação para Longo Prazo

**Solução 2 (MutationObserver)** parece mais viável:
- Mínimas mudanças no código atual
- Não quebra arquitetura existente
- Funciona com Bokeh 3.8.1
- Testável incrementalmente

---

## Links Relacionados

- Bokeh Issue: https://github.com/bokeh/bokeh/issues (search: `sizing_mode resize`)
- ResizeObserver MDN: https://developer.mozilla.org/en-US/docs/Web/API/ResizeObserver
- Bokeh Components: https://docs.bokeh.org/en/latest/docs/user_guide/embed/components.html

---

## Arquivos Afetados

```
newapp/
├── plotting.py              # Figuras Bokeh com sizing_mode='stretch_width'
├── templates/
│   └── charts_clean.html    # ResizeObserver script
└── static/css/
    └── style.css            # CSS Grid com constraints
```

---

## Checklist para Correção

- [ ] Investigar por que ResizeObserver não funciona com Bokeh
- [ ] Testar MutationObserver como alternativa
- [ ] Validar em múltiplos navegadores (Chrome, Firefox, Safari)
- [ ] Testar com múltiplos monitores de diferentes DPIs
- [ ] Testar com zoom 50%, 100%, 150%, 200%
- [ ] Adicionar testes automatizados (Playwright/Selenium)
- [ ] Documentar workaround para usuários
- [ ] Considerar migração para Plotly.js se problema persistir

---

## Prioridade

🟡 **Média** - Funciona bem em modo comum (Desktop) mas quebra em cenários avançados (multi-monitor)

---

## Notas Adicionais

- Problema identificado em Fase 2 do desenvolvimento de Interface Responsiva
- Desktop Full HD (1920x1080) funciona perfeitamente
- Tablet (1024x768) funciona perfeitamente
- Mobile (<768px) não testado (problema específico de re-sizing)

---

## Última Atualização

**Data:** 2026-01-30  
**Por:** Evandro Godoy / GitHub Copilot  
**Status:** ⏳ Aberto - Aguardando Investigação
