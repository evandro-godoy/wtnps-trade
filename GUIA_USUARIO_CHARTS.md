# 📖 GUIA DO USUÁRIO - Interface de Gráficos

**Versão:** 1.2.0  
**Data:** 2026-01-30

---

## 🎯 Visão Geral

A interface de gráficos permite visualizar análises de mercado em tempo real com:
- **Gráficos Bokeh** interativos (candlestick + volume + RSI)
- **Tabelas inteligentes** com predições ML e análise técnica
- **Drag-to-resize** para customizar seu layout
- **Performance otimizada** para 1000+ predições

---

## 🎮 Como Usar

### 1. Acessar a Interface
```
http://localhost:8000/charts-clean
```

### 2. Entender o Layout

**Desktop:**
```
┌─────────────────────────────┐
│ Gráfico (70%)  │ Predições  │
│ Candlestick    │ (30%)      │
│ + Volume       │ • ML Signals
│ + RSI          │ • Analysis
└─────────────────────────────┘
```

### 3. Customizar Proporções

**Arrastar o separador:**
1. Passe o mouse sobre a linha cinzenta no meio
2. Cursor muda para ⟷ (col-resize)
3. Arraste esquerda/direita
4. Suas preferências são **salvas automaticamente**

**Exemplos:**
- 50/50 split: Espaço igual para gráfico e tabelas
- 80/20 split: Foco no gráfico
- 60/40 split: Equilíbrio

---

## 📊 Entendendo os Dados

### Aba: Sinais ML
Predições de Inteligência Artificial em tempo real

| Coluna | Significado |
|--------|------------|
| **Data/Hora** | Timestamp da predição |
| **Tipo** | COMPRA (verde) ou VENDA (vermelho) |
| **Direção** | CALL (↑) ou PUT (↓) |
| **Preço** | Preço do ativo no momento |
| **Prob. ML (%)** | Confiança da predição (0-100%) |
| **Status** | ✅ Válido ou ⚠️ Inválido |
| **Mensagem** | Detalhes adicionais |

**Cores:**
- 🟢 Verde: Sinal de COMPRA (bullish)
- 🔴 Vermelho: Sinal de VENDA (bearish)

### Aba: Análise Técnica
Análise de indicadores e padrões

| Coluna | Significado |
|--------|------------|
| **Tendência** | ALTA (▲), BAIXA (▼), LATERAL (⬌) |
| **RSI 14** | Índice de Força Relativa (30=sobrev., 70=sobcomprado) |
| **EMA20** | Média Móvel Exponencial (20 períodos) |
| **SMA20** | Média Móvel Simples (20 períodos) |
| **SMA50** | Média Móvel Simples (50 períodos) |
| **Padrão** | Padrão de candela identificado |
| **Suporte/Resistência** | Níveis técnicos |

---

## 🔧 Recursos Avançados

### Scroll em Tabelas
- Suave mesmo com 1000+ linhas
- Renderização otimizada (virtual scroll)
- Sem lag ou travamento

### Clear Logs
- Botão 🗑️ Limpar (top right)
- Reseta histórico de predições
- Ideal para começar análise nova

### Auto-refresh
- Atualiza predições a cada 5 segundos
- Apenas durante horário de mercado
- Sincronizado com novos candles

### Market Status
- 🟢 **Live**: Mercado aberto, dados em tempo real
- 🔴 **Closed**: Mercado fechado, sem updates

---

## 📱 Resoluções Suportadas

### Desktop Full HD (1920x1080+) ✅
- Layout optimal
- Todos os recursos funcionam
- Drag-to-resize ativo

### Tablet Landscape (1024x768) ✅
- Grid adapta para 60/40
- Componentes reescalam
- Drag-to-resize ativo

### Mobile Portrait (375x667) ✅
- Stack vertical (100% width)
- Gráfico em cima, tabelas abaixo
- Scroll vertical
- Drag-to-resize **desativado** (por design)

---

## ⚡ Performance

- **Scroll:** Suave 60fps
- **Drag:** Responsivo <100ms
- **Carregamento:** <2 segundos
- **Memória:** ~50MB (otimizado)

---

## 🐛 Troubleshooting

### Problema: Tabelas muito lentas
**Solução:** 
- Clique "Limpar" para resetar histórico
- Feche e reabra se necessário

### Problema: Gutter não aparece
**Solução:**
- Recarregue a página (Ctrl+R)
- Verifique se tela > 1200px largura

### Problema: localStorage não salva
**Solução:**
- Verifique se browser não está em "private mode"
- Limpe cache (Ctrl+Shift+Delete)

### Problema: Gráfico corta
**Solução:**
- Maximize a janela do navegador
- Evite zoom do navegador (Ctrl+0 para resetar)

---

## 💾 Seus Dados

**O que é salvo:**
- Proporções do layout (localStorage)
- Histórico de predições (sessão)

**O que NÃO é salvo:**
- Dados após fechar navegador
- Preferências entre máquinas diferentes

---

## ❓ FAQ

**P: Posso usar em duas telas?**
A: Desktop sim, mas pode ter sobreposição em 2ª tela (bug conhecido).

**P: Funciona no meu celular?**
A: Sim! Modo mobile com stack vertical.

**P: Perdeu meu layout customizado!**
A: Limpe cache do navegador ou restaure localStorage.

**P: Como atualizo dados manualmente?**
A: Clique 🔄 "Sincronizar" (top right).

**P: Posso exportar dados?**
A: Não no momento (roadmap futuro).

---

## 📞 Suporte

Para bugs ou sugestões:
1. Abra DevTools (F12)
2. Verifique console para erros
3. Capture screenshot
4. Reporte na issue tracker

---

**v1.2.0 - Pronta para uso** ✅
