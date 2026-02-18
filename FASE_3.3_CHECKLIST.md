# 🚀 PRÓXIMAS AÇÕES - FASE 3.3 INICIANDO

**Status Atual:** Fases 1-3.2 ✅ COMPLETAS  
**Próximo:** Fase 3.3 (Testes Finais + Documentação)  
**Duração Estimada:** 60-90 minutos

---

## 📋 Checklist Fase 3.3

### Seção 1: Testes Funcionais

- [ ] **Teste 1: Tela Primária (Desktop Full HD)**
  - Carregue `/charts-clean` em 1920x1080
  - Verifique: Gráfico + tabelas visíveis, sem overlaps
  - Teste: Scrolle tabelas (virtual scroll), arrastar gutter (split.js)
  - **Esperado:** Funcionamento perfeito, 60fps

- [ ] **Teste 2: Segunda Tela (se disponível)**
  - Mova navegador para segunda tela
  - **Esperado:** Layout mantém proporção OU documenta BUG multi-screen
  - **Atual:** BUG já documentado em issue

- [ ] **Teste 3: Zoom Navegador**
  - Pressione Ctrl++ (aumentar zoom)
  - Pressione Ctrl+- (diminuir zoom)
  - **Esperado:** Layout se adapta OU documenta comportamento
  - **Atual:** BUG conhecido, pode ativar issue resolution

- [ ] **Teste 4: Responsividade Tablet**
  - Simulе 1024x768 (F12 → Device toolbar)
  - **Esperado:** Grid 60/40, componentes visíveis
  - Teste drag-to-resize (se tela > 1200px lógico)

- [ ] **Teste 5: Responsividade Mobile**
  - Simule 375x667 (móbile portrait)
  - **Esperado:** Stack vertical, sem overlaps
  - **Esperado:** Split.js desativado (<1200px)

### Seção 2: Performance & Profiling

- [ ] **Perfil Chrome DevTools**
  - Abra `/charts-clean`
  - DevTools → Performance → Record
  - Scrolle tabelas 5 segundos
  - Drag gutter por 5 segundos
  - **Esperado:** Frame rate 60fps, FCP <2s

- [ ] **Memory Usage**
  - DevTools → Memory
  - Take heap snapshot
  - **Esperado:** DOM ~500-800 nodes (não crescer linearly)

- [ ] **Performance Timing**
  - DevTools → Network
  - Recarregue página
  - **Esperado:** `/charts-clean` <1s, JS <500ms

### Seção 3: Navegadores Múltiplos

- [ ] **Chrome/Chromium** ✅ Assume funciona
- [ ] **Firefox** (se disponível)
  - **Testar:** Gutter visual, drag, localStorage
- [ ] **Safari** (se disponível)
  - **Testar:** Compatibilidade split.js

### Seção 4: Casos Extremos

- [ ] **Histórico Grande (100+ predições)**
  - Virtual scroll render apenas ~15 visíveis
  - Scroll suave mesmo com 1000 linhas

- [ ] **Múltiplas Abas**
  - Alterne entre "ML Signals" e "Technical Analysis"
  - Virtual scroll persiste ou reseta corretamente

- [ ] **Clear Logs**
  - Clique "Limpar" button
  - Histórico zera, tabelas ficam vazias
  - Virtual scroll reseta

- [ ] **Reload Durante Auto-refresh**
  - Deixe página rodando com auto-refresh por 30s
  - Pressione F5 ou Ctrl+R
  - **Esperado:** localStorage persiste (verificar tamanho gutter)

---

## 📸 Documentação de Screenshots

Para cada teste, considere capturar:

```
📁 screenshots/
├── 01_desktop_full_hd.png           (1920x1080, gráfico + tabelas)
├── 02_tablet_landscape.png          (1024x768, grid 60/40)
├── 03_mobile_portrait.png           (375x667, stack vertical)
├── 04_gutter_default.png            (close-up gutter)
├── 05_gutter_dragging.png           (gutter mid-drag)
├── 06_gutter_50_50.png              (proporção 50/50 após drag)
├── 07_virtual_scroll_smooth.png     (100+ linhas, scroll suave)
├── 08_localStorage_saved.png        (DevTools → Application → localStorage)
└── 09_performance_profile.png       (Chrome DevTools FPS graph)
```

---

## 🔧 Troubleshooting Rápido

### ❌ Split.js não aparece
- Verificar: `Split` global no console
- Verificar: CDN carregou (Network tab)
- Solução: Hard refresh (Ctrl+Shift+R)

### ❌ Gutter não ativa
- Verificar: Classe `.gutter-horizontal` aplicada
- Verificar: Cursor muda para col-resize
- Solução: `document.querySelector('.gutter')`

### ❌ Virtual scroll não funciona
- Verificar: `window.PredictionVirtualScroll` existe
- Verificar: `mlSignalsVirtualScroll` não null
- Console: `mlSignalsVirtualScroll.getVisibleRange()`

### ❌ localStorage não persiste
- Verificar: App não em modo "private browsing"
- Verificar: localStorage não desativado
- Console: `localStorage.getItem('split-chart-width')`

### ❌ Bokeh não redimensiona ao drag
- Verificar: `window.dispatchEvent(new Event('resize'))` sendo chamado
- Verificar: Bokeh loaded (window.Bokeh existe)
- Solução: Verificar split.js onDrag callback

---

## 📝 Documentação Recomendada

Após testes passarem, criar:

### 1. **USER_GUIDE.md**
```markdown
# Como Usar a Interface de Gráficos

## Customizar Layout
1. Arraste o separador entre gráfico e predições
2. Mude de 20% a 80% cada lado
3. Suas preferências são salvas automaticamente

## Tabelas com Muitas Linhas
- Scroll suave mesmo com 1000+ predições
- Apenas linhas visíveis são renderizadas
- Clique "Limpar" para resetar histórico

## Resoluções Suportadas
- ✅ Desktop Full HD (1920x1080+)
- ✅ Tablet Landscape (1024x768)
- ✅ Mobile Portrait (375x667)
```

### 2. **ARCHITECTURE_SUMMARY.md**
```markdown
# Arquitetura UI - Fase 3.2

## Componentes
- **Grid Layout:** CSS Grid 2-coluna responsivo
- **Virtual Scroll:** Vanilla JS, renderiza apenas visíveis
- **Drag-to-Resize:** Split.js + localStorage

## Performance
- DOM: ~15 nodes (vs 50+ antes)
- Scroll: 60fps
- Memory: ~40% redução

## Browsers Suportados
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
```

### 3. **CHANGELOG.md** (adicionar à existente)
```markdown
## [v1.2.0] - 2026-01-30

### Added
- Virtual Scroll para tabelas (Fase 3.1)
- Drag-to-resize com Split.js (Fase 3.2)
- CSS Grid responsivo (Fase 2)
- localStorage para preferências

### Fixed
- Overlaps em Tablet/Mobile (resolvido)

### Known Issues
- Bokeh não redimensiona em 2ª tela/zoom (deferred)
```

---

## ✅ Critério de Sucesso Fase 3.3

Para marcar como **COMPLETA**:

- ✅ Todos os 15 testes acima PASSARAM
- ✅ Nenhum erro no console
- ✅ Performance: 60fps em todos os cenários
- ✅ Documentação criada
- ✅ Screenshots capturadas
- ✅ Changelog atualizado
- ✅ Issue multi-screen: Reavaliar ou MANTER como deferred

---

## 🎯 Se Encontrar BUG Multi-Screen em Testes

Conforme user request: "em caso de repetição do bug... reavaliamos"

**Opções:**
1. ✅ **Documentar mais detalhes** (já feito em issue)
2. 🔧 **Implementar MutationObserver** (Solução 2 do issue) - 30 min
3. ⏸️ **Manter como deferred** (para depois)

---

## 📞 Próxima Ação

Após completar Fase 3.3:

1. Atualizar `RESUMO_GERAL_FASES_1_3.2.md` com resultados finais
2. Decidir se continua com Fase 4+ ou finaliza release
3. Confirmar `main` estavel apos os testes

---

**Fase 3.3 Estimado:** 60-90 minutos  
**Próximo Milestone:** UI Completo & Documentado ✅
