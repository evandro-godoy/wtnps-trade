# 📋 FASE 4: TAREFAS PENDENTES E PRÓXIMAS AÇÕES

**Data:** 2026-01-31  
**Status Implementação:** ✅ **COMPLETA**  
**Status Testes:** ⏳ **PENDENTE**

---

## ✅ TAREFAS COMPLETADAS

### Implementação (100%)
- [x] ✅ Função `debounce()` implementada
- [x] ✅ Função `forceBokehRelayout()` implementada
- [x] ✅ `initBokehMutationObserver()` implementada
- [x] ✅ `initZoomDetection()` implementada
- [x] ✅ Integração com Split.js
- [x] ✅ Sequência de inicialização atualizada
- [x] ✅ Error handling adicionado
- [x] ✅ Graceful degradation implementada
- [x] ✅ Console logs para debugging

### Documentação (100%)
- [x] ✅ `PLANO_FASE_4.md` criado
- [x] ✅ `FASE_4_STATUS.md` criado
- [x] ✅ `RESUMO_GERAL_FASES_1_4.md` criado
- [x] ✅ Issue `BUG_BOKEH_RESIZE_MULTI_SCREEN.md` atualizada
- [x] ✅ Código comentado e documentado

---

## ⏳ TAREFAS PENDENTES

### 1. Git Operations (Manual)
**Status:** ⏳ Aguardando execução manual

Devido a problema com PowerShell 6+, execute manualmente:

```bash
# 1. Verificar status
git status

# 2. Adicionar arquivos modificados
git add newapp/templates/charts_clean.html
git add ISSUES/BUG_BOKEH_RESIZE_MULTI_SCREEN.md
git add FASE_4_STATUS.md
git add PLANO_FASE_4.md
git add RESUMO_GERAL_FASES_1_4.md
git add FASE_4_TAREFAS_PENDENTES.md

# 3. Commit
git commit -m "feat(ui): Implement Phase 4 - Multi-screen and zoom fixes

- Add MutationObserver to detect Bokeh DOM changes
- Integrate Visual Viewport API for zoom detection  
- Implement forceBokehRelayout() for dimension recalculation
- Add debounce utility for performance optimization
- Update Split.js integration with new relayout function
- Add graceful degradation for older browsers
- Create comprehensive documentation

Resolves: Multi-screen overlay issue
Phase: 4 of 10
Status: Implementation complete, awaiting tests"

# 4. Push (se necessário)
git push origin feature/newapp-ui
```

---

### 2. Testes Fase 4 (Requer Ambiente Multi-Screen)
**Status:** ⏳ Aguardando ambiente de teste

#### Teste 4.1: Multi-Screen com Mesma Resolução
**Ambiente:** 2 monitores Full HD (1920x1080)

```bash
# Passos:
1. Abrir http://localhost:8000/charts-clean na tela primária
2. Verificar layout 70/30 correto
3. Mover janela para segunda tela
4. Verificar: Layout mantém proporção, sem overlaps
5. Console: Verificar log "🔄 Bokeh style mutation detected"
```

**Critério de Sucesso:** ✅ Nenhuma sobreposição em ambas as telas

---

#### Teste 4.2: Multi-Screen com DPI Diferente
**Ambiente:** Monitor 1 (100% scale) + Monitor 2 (150% scale)

```bash
# Passos:
1. Abrir /charts-clean em monitor 1 (100%)
2. Mover para monitor 2 (150% DPI)
3. Verificar: Bokeh recalcula dimensões, sem overlaps
4. Console: "🔄 Bokeh style mutation detected"
```

**Critério de Sucesso:** ✅ MutationObserver detecta mudança e re-renderiza

---

#### Teste 4.3: Zoom Navegador (Ctrl++/Ctrl+-)
**Ambiente:** Desktop Full HD, qualquer navegador

```bash
# Passos:
1. Abrir /charts-clean com zoom 100%
2. Pressionar Ctrl++ 3 vezes (zoom 150%)
3. Verificar: Layout adapta, sem overlaps
4. Console: "🔍 Zoom detected: 1.00x → 1.50x"
5. Pressionar Ctrl+- 3 vezes (voltar 100%)
6. Verificar: Layout volta ao normal
```

**Critério de Sucesso:** ✅ Bokeh redimensiona em cada mudança de zoom

---

#### Teste 4.4: Performance com Observers
**Ambiente:** Desktop Full HD, Chrome DevTools

```bash
# Passos:
1. Abrir DevTools → Performance
2. Iniciar gravação
3. Drag gutter 10 vezes (esquerda/direita)
4. Zoom navegador 5 vezes (Ctrl++ e Ctrl+-)
5. Parar gravação
6. Analisar: FPS, long tasks, frame rate
```

**Critério de Sucesso:** ✅ FPS > 55, nenhum long task > 50ms

---

#### Teste 4.5: Cross-Browser
**Ambiente:** Chrome, Firefox, Edge (Safari se disponível)

```bash
# Passos para cada navegador:
1. Abrir /charts-clean
2. Testar drag-to-resize
3. Testar zoom (Ctrl++)
4. Mover entre telas (se multi-monitor)
5. Console: Verificar logs e erros
```

**Critério de Sucesso:** ✅ Funciona em 90%+ browsers, sem erros críticos

**Notas:**
- Firefox < 91: Visual Viewport API não suportada (esperado)
- Safari: Testar ambos MutationObserver e Visual Viewport

---

### 3. Servidor Local para Testes
**Status:** ⏳ Aguardando inicialização

Para testar, o servidor FastAPI precisa estar rodando:

```bash
# Opção 1: Com Poetry
cd newapp
poetry run uvicorn main_clean:app --reload --host 0.0.0.0 --port 8000

# Opção 2: Com Python direto
cd newapp
python -m uvicorn main_clean:app --reload --host 0.0.0.0 --port 8000

# Verificar:
# http://localhost:8000/charts-clean
```

---

### 4. Validação de Código
**Status:** ⏳ Aguardando validação

```bash
# Verificar sintaxe JavaScript (se ESLint disponível)
eslint newapp/templates/charts_clean.html

# Ou validar manualmente:
# 1. Abrir /charts-clean no navegador
# 2. Console: Verificar erros JavaScript
# 3. Console: Verificar logs de inicialização:
#    - "✅ MutationObserver initialized for Bokeh"
#    - "✅ Zoom detection initialized"
#    - "✅ Split.js initialized"
```

---

## 📊 CHECKLIST DE CONCLUSÃO FASE 4

### Implementação
- [x] Código implementado
- [x] Error handling
- [x] Graceful degradation
- [x] Console logs
- [x] Documentação criada

### Git (Pendente)
- [ ] Commit realizado
- [ ] Push para origin (se necessário)

### Testes (Pendente)
- [ ] Teste 4.1: Multi-screen mesma resolução
- [ ] Teste 4.2: Multi-screen DPI diferente
- [ ] Teste 4.3: Zoom navegador
- [ ] Teste 4.4: Performance
- [ ] Teste 4.5: Cross-browser

### Após Testes Passarem
- [ ] Atualizar `FASE_4_STATUS.md` com resultados
- [ ] Atualizar `BUG_BOKEH_RESIZE_MULTI_SCREEN.md` (status: ✅ RESOLVIDO)
- [ ] Criar `FASE_4_TESTES_RESULTADOS.md`
- [ ] Decidir próximos passos (Fase 5 ou outras melhorias)

---

## 🎯 PRÓXIMA FASE

### Se Testes Passarem (Cenário Ideal)
**Fase 5: Backend Persistence**
- Salvar preferências de layout no backend
- Sincronização entre dispositivos
- Histórico de predições persistente
- Autenticação de usuários (se necessário)

**Estimativa:** 2-3 dias

### Se Testes Falharem (Cenário Alternativo)
**Reavaliação de Soluções:**
- Tentar ajustes nos observers (debounce, thresholds)
- Considerar Solução 3 (Bokeh Server com WebSocket)
- Considerar Solução 4 (Migração para Plotly.js)
- Documentar como limitação conhecida

---

## 📞 INSTRUÇÕES PARA USUÁRIO

### Para Executar Testes:
1. ✅ Certifique-se de que o servidor está rodando
2. ✅ Tenha ambiente multi-monitor disponível (ideal)
3. ✅ Use Chrome DevTools para performance profiling
4. ✅ Execute testes 4.1-4.5 sequencialmente
5. ✅ Documente resultados em `FASE_4_TESTES_RESULTADOS.md`

### Para Commit Manual:
1. ✅ Execute comandos Git listados na seção 1 acima
2. ✅ Verifique com `git status` antes de push
3. ✅ Push apenas após testes básicos (console sem erros)

### Para Prosseguir para Fase 5:
1. ✅ Complete todos os testes Fase 4
2. ✅ Atualize documentação com resultados
3. ✅ Feche issue do bug multi-screen
4. ✅ Solicite início da Fase 5

---

## 💡 NOTAS IMPORTANTES

### Limitações Conhecidas
- **PowerShell 6+:** Não disponível no ambiente (usar comandos Git manualmente)
- **Ambiente Multi-Screen:** Necessário para testes 4.1 e 4.2
- **Visual Viewport API:** Firefox < 91 não suportado (esperado)

### Workarounds Disponíveis
- Git: Usar Git Bash ou Command Prompt do Windows
- Testes: Simulador de múltiplas telas (Windows + P) se necessário
- Zoom: Testar apenas com Ctrl++ (mais comum que multi-screen)

---

**Status Geral:** ✅ **IMPLEMENTAÇÃO COMPLETA, AGUARDANDO TESTES**  
**Próxima Ação:** Executar comandos Git manualmente e iniciar testes

