# [QA] Criar Teste de Contrato (Contract Test)

## 🎯 Objetivo
Validar que dados de MetaTraderProvider atendem contrato esperado por LSTMAdapter.

## 📂 Contexto & Arquivos
- **Alvo:** `tests/integration/test_mt5_contract.py`
- **Dependências:** `src/data_handler/mt5_provider.py`, `src/modules/strategy/lstm_adapter.py`

## 🛠️ Especificações Técnicas
1. **Teste de Contrato - MarketDataEvent:**
   ```python
   def test_market_data_event_contract():
       # Buscar candle real do MT5
       provider = MetaTraderProvider()
       candles = provider.get_latest_candles("WDO$", "M5", 1)
       event = candles[0]  # Primeiro MarketDataEvent
       
       # Validar tipos
       assert isinstance(event.symbol, str)
       assert isinstance(event.timeframe, str)
       assert isinstance(event.open, (float, np.float32, np.float64))
       assert isinstance(event.high, (float, np.float32, np.float64))
       assert isinstance(event.low, (float, np.float32, np.float64))
       assert isinstance(event.close, (float, np.float32, np.float64))
       assert isinstance(event.volume, (int, np.int32, np.int64))
       assert isinstance(event.timestamp, datetime)
   ```

2. **Teste de Contrato - DataFrame dtypes:**
   ```python
   def test_dataframe_dtypes_match_model():
       # Converter MarketDataEvent → DataFrame
       df = adapter._build_dataframe(events)
       
       # Validar dtypes das colunas OHLCV
       assert df['open'].dtype in [np.float32, np.float64]
       assert df['high'].dtype in [np.float32, np.float64]
       assert df['low'].dtype in [np.float32, np.float64]
       assert df['close'].dtype in [np.float64]  # MT5 padrão
       assert df['volume'].dtype in [np.int32, np.int64]
   ```

3. **Teste de Contrato - Shape após Features:**
   ```python
   def test_shape_after_define_features():
       # Processar features
       df_with_features = strategy.define_features(df)
       
       # Converter para array
       feature_cols = strategy.get_feature_names()
       X = df_with_features[feature_cols].values
       
       # Validar shape (lookback=108, n_features variável)
       assert X.shape[0] >= 108  # Mínimo de candles
       assert X.shape[1] == len(feature_cols)  # Todas features presentes
       
       # Reshape para modelo
       X_reshaped = X[-108:].reshape(1, 108, -1)
       
       # Validar shape final == model.input_shape
       assert X_reshaped.shape[1:] == model.input_shape[1:]
   ```

4. **Teste de Integração End-to-End:**
   - MT5 → Provider → EventBus → LSTMAdapter → SignalEvent
   - Validar que não há conversões de dtype que quebram
   - Verificar que `float64` do MT5 é compatível com `float32` do modelo

## 🔗 Dependências & Bloqueios
- [ ] DATA-001 (MT5Provider) deve estar merged ✅
- [ ] MT5 terminal ativo para teste (ou usar mock controlado)

## 📦 Definition of Done (DoD)
- [ ] Teste valida tipos de todos campos de MarketDataEvent
- [ ] Teste valida dtypes do DataFrame (float32/64, int32/64)
- [ ] Teste valida shape após define_features()
- [ ] Teste valida shape final == model.input_shape
- [ ] Teste end-to-end com MT5 real passa
- [ ] Se dtype incompatível → teste falha com mensagem clara
- [ ] README explica: "Contract test garante compatibilidade de tipos"

## 📊 Estimativa
- **Story Points:** 8
- **Horas:** 10h
- **Prioridade:** 🟡 MÉDIA (paralela após DATA-001)
