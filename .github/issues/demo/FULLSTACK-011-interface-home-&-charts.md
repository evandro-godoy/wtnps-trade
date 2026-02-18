---
name: [FULLSTACK] Interface da Demo (Home & Charts)
about: Ajustar templates para cumprir os requisitos visuais estritos da demo.
title: "[UI] Implementar Home e Customizar Charts Clean (Médias)"
labels: fullstack, ui, frontend
assignees: fullstack-agent
---

**Contexto:**
A demo exige duas telas obrigatórias e uma configuração visual específica para o gráfico.

**Requisitos Visuais:**
1. **Home (`templates/home.html`):** Deve ter um menu lateral e um link claro para a interface de Charts.
2. **Charts (`templates/charts_clean.html`):**
   - Exibir gráfico de Candlestick.
   - Ativo: WDO$ (Padrão).
   - Timeframe: M5.
   - Zoom inicial: Últimas 1000 barras.
   - **Indicadores Obrigatórios (Hardcoded para a demo se necessário):**
     - SMA 21 períodos (Cor: **Azul**).
     - SMA 200 períodos Aritmética (Cor: **Preta**).
     - EMA 9 períodos (Cor: **Vermelha**).

**Tarefas:**
- [ ] Criar/Ajustar `home.html` com navegação para `/charts`.
- [ ] Editar o JavaScript do gráfico (provavelmente `static/js/live_chart.js` ou script inline) para plotar as linhas recebidas do backend com as cores hexadecimais corretas:
  - SMA 21: `#0000FF` (Blue)
  - SMA 200: `#000000` (Black)
  - EMA 9: `#FF0000` (Red)
- [ ] Garantir que o gráfico renderize 1000 candles sem travar.

**Critério de Aceite:**
Navegar da Home para Charts e ver as 3 linhas coloridas sobrepostas aos candles.