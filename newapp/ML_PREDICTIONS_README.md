# ML Predictions - Real-time Integration

## Visão Geral

Sistema de predições ML em tempo real integrado à interface web do **newapp**. Utiliza modelos treinados (`LSTMVolatilityStrategy`) para gerar sinais de trading sobre os dados do gráfico em tempo real.

---

## Arquitetura

### Componentes Principais

1. **MLPredictionEngine** (`newapp/src/ml/prediction_engine.py`)
   - Carrega modelos treinados de `newapp/models/`
   - Usa estratégias do `newapp/src/strategies/` para feature engineering
   - Gera predições thread-safe (stateless)

2. **API Endpoint** (`/api/monitor-predictions`)
   - FastAPI route que expõe predições via REST
   - Usa `HybridDataLoader` para dados em tempo real (DB + MT5)
   - Retorna JSON com sinais, probabilidades e preços

3. **Frontend** (`newapp/templates/charts_clean.html`)
   - Grid de predições atualizado via JavaScript
   - Tabela com timestamp, tipo (COMPRA/VENDA), preço e probabilidade ML
   - Auto-refresh a cada clique no botão ou mudança de símbolo/timeframe

---

## Fluxo de Execução

### 1. Treinamento do Modelo

```powershell
# Treinar modelos LSTM para WDO$ e WIN$ (M5)
poetry run python newapp/train_model.py
```

**Saída esperada:**
- `newapp/models/WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras`
- `newapp/models/WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib`
- `newapp/models/WDO$_LSTMVolatilityStrategy_M5_prod_params.joblib`

### 2. Iniciar Servidor Web

```powershell
poetry run uvicorn newapp.main:app --reload --host 127.0.0.1 --port 8000
```

**Logs esperados:**
```
✅ Database initialized
MLPredictionEngine initialized (models: C:\projects\wtnps-trade\newapp\models)
Application startup complete.
```

### 3. Acessar Interface

Abra no navegador:
```
http://127.0.0.1:8000/charts-clean
```

**Elementos da interface:**
- **Gráfico Bokeh:** Candlestick chart com 500 candles (real-time via MT5)
- **Grid de Predições:** Tabela com últimas 10 predições do modelo LSTM
- **Controles:** Seletor de símbolo (WDO$, WIN$), timeframe (M1-D1), e número de candles

### 4. Geração de Predições

Ao carregar a página ou clicar em "Refresh", o frontend chama:

```http
GET /api/monitor-predictions?symbol=WDO$&timeframe=M5&count=10
```

**Processo interno:**
1. `MLPredictionEngine.predict_latest()` busca 500 candles via `HybridDataLoader`
2. Carrega modelo `WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras`
3. Estratégia `LSTMVolatilityStrategy.define_features()` gera 22 features técnicas
4. Modelo LSTM gera predições (probabilidade de classe 1 = COMPRA)
5. Sinais mapeados: `prob >= 0.5` → COMPRA, `prob < 0.5` → VENDA
6. Retorna JSON com timestamp, tipo, preço, prob_ml

**Exemplo de resposta:**
```json
{
  "predictions": [
    {
      "timestamp": "2025-11-28T10:35:00+00:00",
      "tipo": "COMPRA",
      "preco": 124500.0,
      "prob_ml": 78,
      "mensagem": "Signal from WDO$_LSTMVolatilityStrategy_M5"
    },
    ...
  ],
  "symbol": "WDO$",
  "timeframe": "M5",
  "count": 10
}
```

---

## Modelos Disponíveis

### WDO$ (Mini Dólar)
- **Modelo:** `WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras`
- **Timeframe:** M5
- **Features:** 22 (retorno, gap, roc_3/8, ema_9, sma_20/200, rsi, atr, etc.)
- **Lookback:** 108 candles
- **Target:** Explosões de volatilidade (threshold=2.5x desvio padrão)

### WIN$ (Mini Índice)
- **Modelo:** `WIN$_LSTMVolatilityStrategy_M5_prod_lstm.keras`
- **Timeframe:** M5
- **Mesma arquitetura:** LSTM 64 units, dropout 0.2, 30 epochs

---

## Detalhes Técnicos

### Feature Engineering (LSTMVolatilityStrategy)

**Dinâmica de Preços (5 features):**
- `retorno`: Retorno percentual do close
- `gap`: Gap entre close anterior e open atual
- `roc_3`, `roc_8`: Rate of Change 3 e 8 períodos
- `retorno_relativo`: Retorno dividido por ATR normalizado

**Indicadores Técnicos (9 features):**
- `ema_9`: Exponential Moving Average 9
- `sma_20`, `sma_50`, `sma_200`: Simple Moving Averages
- `rsi_14`: Relative Strength Index
- `band_width`: Bollinger Bands width (volatilidade)
- `atr`, `atr_norm`: Average True Range e normalizado

**Morfologia do Candle (5 features):**
- `body_rel`: Tamanho relativo do corpo (body/range)
- `high_rel`, `low_rel`: Posição de high/low
- `upper_shadow_rel`, `lower_shadow_rel`: Tamanho dos pavios

**Embeddings Temporais (3 features):**
- `hour_sin`, `hour_cos`: Codificação circular da hora
- `day_sin`, `day_cos`: Codificação circular do dia da semana

### Arquitetura do Modelo LSTM

```python
Sequential([
    LSTM(64, return_sequences=False, input_shape=(lookback, n_features)),
    Dropout(0.2),
    Dense(32, activation='relu'),
    Dropout(0.2),
    Dense(1, activation='sigmoid')  # Binary classification
])
```

**Treinamento:**
- **Otimizador:** Adam
- **Loss:** Binary Crossentropy
- **Métricas:** Accuracy
- **Class Weights:** Balanceamento automático (0: 1.11, 1: 0.91)
- **Early Stopping:** patience=5, monitor='val_loss'

**Performance (WDO$ M5):**
- **Train Accuracy:** 73.12%
- **Test Accuracy:** 72.86%
- **Test Precision:** 70.63%
- **Test Recall:** 64.87%
- **Test F1:** 0.6764

---

## Troubleshooting

### Erro: "Modelo não encontrado"

**Problema:** API retorna 404 ao chamar `/api/monitor-predictions`

**Solução:**
```powershell
# Verificar existência dos modelos
ls newapp/models/WDO$_LSTMVolatilityStrategy_M5_prod_*

# Se vazio, treinar novamente
poetry run python newapp/train_model.py
```

### Warning: "Nenhuma sequência para predição"

**Problema:** Logs mostram `WARNING - Nenhuma sequência para predição. Retornando array vazio.`

**Causa:** LSTM precisa de `lookback=108` candles + indicadores (50 candles mínimo).

**Solução:** Já corrigido no código - `predict_latest()` agora busca 500 candles automaticamente.

### Grid vazio na interface

**Problema:** Tabela de predições mostra "Carregando predições..." eternamente.

**Debug:**
1. Abrir DevTools do navegador (F12)
2. Console → verificar erros de JavaScript
3. Network tab → verificar resposta de `/api/monitor-predictions`

**Possíveis causas:**
- CORS bloqueado (improvável em localhost)
- Modelo não carregado (ver logs do servidor)
- Dados insuficientes no MT5 (checar conexão)

### Predições sempre VENDA (ou sempre COMPRA)

**Problema:** Modelo gera sempre o mesmo sinal.

**Causa:** Modelo não convergiu durante treinamento ou dados de treino desbalanceados.

**Solução:**
1. Verificar relatório HTML em `newapp/reports/models/WDO$_LSTMVolatilityStrategy_M5_*.html`
2. Checar distribuição de classes (deve ser próximo de 50/50)
3. Se muito desbalanceado, ajustar `volatility_multiplier` em `newapp/configs/main.yaml`
4. Retreinar com `poetry run python newapp/train_model.py`

---

## Próximos Passos

### Melhorias Planejadas

1. **WebSocket Streaming:**
   - Atualização automática de predições sem refresh manual
   - Integração com `RealtimeMarketMonitor` para sinais em tempo real

2. **Múltiplos Modelos:**
   - Suporte para DRL (DDQN) além de LSTM
   - Ensemble de modelos (voting ou stacking)

3. **Backtesting Visual:**
   - Overlay de predições sobre gráfico Bokeh
   - Marcadores de sinais COMPRA/VENDA com stop/take profit

4. **Dashboard de Performance:**
   - Métricas de acurácia em tempo real
   - Gráfico de retorno acumulado das predições
   - Heatmap de performance por hora/dia

5. **Filtros de Setup:**
   - Integração com `SetupAnalyzer` (legacy `src/setups/analyzer.py`)
   - Validação de sinais ML com regras técnicas (MA crossover, RSI, etc.)

---

## Logs Importantes

### Startup (Sucesso)
```
2025-11-28 10:40:26,508 - INFO - [newapp.src.ml.prediction_engine] MLPredictionEngine initialized (models: C:\projects\wtnps-trade\newapp\models)
2025-11-28 10:40:26,559 - INFO - [newapp.main] ✅ Database initialized
INFO:     Application startup complete.
```

### Carregamento de Modelo (Sucesso)
```
2025-11-28 10:39:31,466 - INFO - [newapp.src.ml.prediction_engine] Loaded strategy: LSTMVolatilityStrategy from lstm_volatility
2025-11-28 10:39:32,085 - INFO - [root] Modelo carregado de C:\projects\wtnps-trade\newapp\models\WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras
2025-11-28 10:39:32,096 - INFO - [newapp.src.ml.prediction_engine] Model loaded: C:\projects\wtnps-trade\newapp\models\WDO$_LSTMVolatilityStrategy_M5_prod
```

### Predição (Sucesso)
```
INFO:     127.0.0.1:53600 - "GET /api/monitor-predictions?symbol=WDO$&timeframe=M5 HTTP/1.1" 200 OK
```

---

## Referências

- **Treinamento:** `newapp/TRAINING_README.md`
- **Estratégia LSTM:** `newapp/src/strategies/lstm_volatility.py`
- **Endpoint API:** `newapp/main.py` (linha ~350)
- **Frontend:** `newapp/templates/charts_clean.html`
- **Relatórios de Treino:** `newapp/reports/models/` (HTML com métricas)
