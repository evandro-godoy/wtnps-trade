# 📋 PLANO FASE 3.1: VIRTUAL SCROLL PARA TABELAS

## Objetivo
Implementar virtual scrolling nas tabelas de predições (ML Signals e Technical Analysis) para:
- ✅ Renderizar apenas linhas visíveis (viewport)
- ✅ Suportar 1000+ linhas sem perda de performance
- ✅ Manter funcionalidade de search/filter
- ✅ Preservar styling e interações (hover, colors)

---

## Estrutura Atual vs Proposta

### ❌ Problema Atual
- Renderiza TODAS as linhas no DOM (50+ rows atualmente, pode crescer)
- Scroll suave mas DOM cresce linearly com dados
- Performance degrada em 500+ linhas

### ✅ Solução Proposta: Virtual Scroll
- Renderiza apenas **~20 linhas visíveis por viewport**
- Resto fica em "virtual space" (simulado pelo scrollbar)
- Atualiza dinamicamente ao rolar
- Suporta 10.000+ linhas sem lag

---

## Implementação

### Abordagem: Custom Virtual Scroll (Vanilla JS)

**Por que não usar biblioteca?**
- Sem dependência extra (leve)
- Controle total sobre performance
- Integra perfeitamente com código existente
- Apenas ~150 linhas de JS

**Como funciona:**
1. Container tem `height: 400px` + `overflow: auto`
2. Conteúdo tem "phantom" spacers (top + bottom) para simular altura total
3. Ao rolar, calcula qual range de rows renderizar
4. Atualiza DOM apenas com rows visíveis
5. Mantém scroll position natural

---

## Arquivos a Modificar

### 1. `newapp/static/css/style.css`
Adicionar classe para container com virtual scroll fixo

### 2. `newapp/templates/charts_clean.html`
- Adicionar `data-virtual-scroll` attribute na tabela
- Criar classe JavaScript `VirtualScroll` para gerenciar
- Refatorar `loadPredictions()` para usar virtual scroll

### 3. `newapp/static/js/virtual-scroll.js` (NOVO)
Classe `VirtualScroll` com:
- `constructor(container, rowHeight, bufferSize)`
- `setData(rows)`
- `render()`
- `onScroll()` handler

---

## Estimativa

- Criação do arquivo `virtual-scroll.js`: 20 min
- Modificações CSS: 10 min
- Integração em `charts_clean.html`: 20 min
- Testes: 10 min
- **Total: ~60 min**

---

## Sucesso Criteria

✅ Renderiza 50 linhas sem lag  
✅ Rola suavemente para 500+ linhas  
✅ Sticky header permanece no topo  
✅ Sem mudanças visuais (aparência igual)  
✅ Hover e cores funcionam  
✅ Search/filter ainda funciona (se implementado)  

---

## Próximas Fases

Após 3.1 completa:
- **Fase 3.2:** Split.js para drag resize
- **Fase 3.3:** Testes finais + documentação
