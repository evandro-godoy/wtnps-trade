---
name: [QUANT] Preparação de Dados e Indicadores da Demo
about: Garantir que o backend calcule e envie as médias específicas solicitadas.
title: "[DATA] Calcular Indicadores para Demo (SMA21, SMA200, EMA9)"
labels: quant, indicators, data
assignees: quant-agent
---

**Contexto:**
O frontend precisa exibir indicadores específicos. O motor de dados deve calculá-los antes de enviar o JSON para a interface.

**Requisitos Técnicos:**
1. Ativo Alvo: Primeiro da lista `main.yaml` (WDO$).
2. Histórico: 1000 barras M5.
3. Indicadores: SMA(21), SMA(200), EMA(9).

**Tarefas:**
- [ ] Verificar `src/utils/indicators.py` (ou `calculate_indicators.py`). Garantir que as funções `calculate_sma` e `calculate_ema` estejam disponíveis.
- [ ] Atualizar o endpoint de dados (em `src/api/routes/signals.py` ou onde o gráfico busca dados) para incluir essas colunas no JSON de resposta:
  - `sma_21`
  - `sma_200`
  - `ema_9`
- [ ] Executar o motor de predição (`LSTMVolatilityStrategy`) com os dados do último pregão disponível no MT5 para gerar o sinal de análise.

**Critério de Aceite:**
O JSON retornado pela API contém os arrays de dados para os candles e para os 3 indicadores solicitados.