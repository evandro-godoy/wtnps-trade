# Testes do Workflow EventBus + LSTMVolatilityAdapter

## Visão Geral

Este documento descreve a implementação e validação do novo sistema event-driven baseado em EventBus e LSTMVolatilityAdapter.

## Arquivos Criados

### 1. `src/events.py`
Módulo de definição de eventos do sistema:
- **BaseEvent**: Classe base para todos os eventos
- **MarketDataEvent**: Evento de dados de mercado (OHLCV)
- **SignalEvent**: Evento de sinal de trading (COMPRA/VENDA)
- **OrderEvent**: Evento de ordem de execução

### 2. `src/modules/strategy/lstm_adapter.py` (Atualizado)
Adaptador que converte eventos de mercado em sinais usando modelo LSTM:
- Processa eventos `MarketDataEvent` via handler `on_market_data()`
- Acumula dados em buffer com índice temporal (DatetimeIndex)
- Gera features usando `LSTMVolatilityStrategy.define_features()`
- Faz predições com modelo Keras mockado ou real
- Publica `SignalEvent` no EventBus

**Principais características:**
- Suporte a mock do modelo Keras (facilita testes unitários)
- Buffer circular (mantém apenas lookback + margem)
- Contador de eventos processados e sinais gerados
- Tratamento de erros com logging

### 3. `tests/unit/test_workflow.py`
Suite completa de testes unitários:

#### Testes Implementados:

1. **test_eventbus_publish_subscribe**
   - Valida publicação e subscrição básica no EventBus
   - Verifica que handlers recebem eventos corretamente

2. **test_lstm_adapter_with_mock_model**
   - Testa LSTMVolatilityAdapter com modelo mockado
   - Valida acúmulo no buffer e processamento de 150 candles
   - Verifica estatísticas (processed_count, buffer_size)

3. **test_workflow_200_events** ⭐
   - **Teste principal solicitado**
   - Instancia EventBus + LSTMVolatilityAdapter
   - Registra adaptador no barramento
   - Publica 200 eventos de MARKET_DATA com candles gerados aleatoriamente
   - Verifica:
     - Todos 200 eventos foram processados
     - Buffer mantém tamanho controlado (≤ 208)
     - Sinais foram gerados após lookback inicial (93 sinais gerados)
     - Sinais publicados no EventBus foram capturados por handler
   - **Resultado**: ✅ PASSOU - 93 sinais gerados de 200 eventos

4. **test_adapter_without_model**
   - Valida comportamento sem modelo carregado (graceful degradation)
   - Buffer cresce normalmente, mas nenhum sinal é gerado

5. **test_multiple_handlers**
   - Testa múltiplos handlers para o mesmo tipo de evento
   - Verifica que todos recebem notificações

## Resultados dos Testes

```
tests/unit/test_workflow.py::TestWorkflow::test_adapter_without_model PASSED [ 20%]
tests/unit/test_workflow.py::TestWorkflow::test_eventbus_publish_subscribe PASSED [ 40%]
tests/unit/test_workflow.py::TestWorkflow::test_lstm_adapter_with_mock_model PASSED [ 60%]
tests/unit/test_workflow.py::TestWorkflow::test_multiple_handlers PASSED [ 80%]
tests/unit/test_workflow.py::TestWorkflow::test_workflow_200_events PASSED [100%]

📊 Estatísticas do Teste Principal (200 eventos):
  - Eventos processados: 200 ✅
  - Sinais gerados: 93 ✅
  - Tamanho do buffer: 200 ✅
  - Sinais recebidos pelo handler: 93 ✅

========================== 5 passed in 8.00s ==========================
```

## Como Executar

```powershell
# Todos os testes
poetry run python -m pytest tests/unit/test_workflow.py -v

# Apenas o teste de 200 eventos
poetry run python -m pytest tests/unit/test_workflow.py::TestWorkflow::test_workflow_200_events -v

# Com saída detalhada
poetry run python -m pytest tests/unit/test_workflow.py -v -s
```

## Arquitetura Validada

```
┌─────────────────┐
│  MarketData     │
│  Events (200x)  │
└────────┬────────┘
         │ publish()
         ▼
┌────────────────────┐
│    EventBus        │
│  (publish/subscribe)│
└────────┬───────────┘
         │ on_market_data()
         ▼
┌─────────────────────────┐
│ LSTMVolatilityAdapter   │
│ - Buffer (lookback=108) │
│ - Model (Keras mocked)  │
│ - Scaler (joblib)       │
└────────┬────────────────┘
         │ publish()
         ▼
┌────────────────────┐
│  SignalEvent (93x) │
│  COMPRA/VENDA      │
└────────────────────┘
```

## Pontos Importantes

### 1. Índice Temporal no Buffer
O adaptador foi corrigido para usar `pd.DataFrame(..., index=[event.timestamp])` ao invés de `ignore_index=True`. Isso garante que:
- `define_features()` pode acessar `df.index.hour`
- Features temporais são calculadas corretamente

### 2. Mock do Modelo Keras
Para evitar dependência de arquivos `.keras` pesados nos testes:
```python
mock_model = MagicMock()
mock_model.predict.return_value = np.array([[0.4, 0.6]])  # 60% COMPRA
adapter.model = mock_model
```

### 3. Buffer Circular
O adaptador mantém apenas `lookback + 100` candles para evitar crescimento infinito:
```python
if len(self.buffer) > self.lookback + 100:
    self.buffer = self.buffer.iloc[-(self.lookback + 100):]
```

### 4. Geração de Sinais
Sinais são gerados apenas quando:
- Buffer tem ≥ lookback candles (108)
- Modelo está carregado (`model is not None`)
- `define_features()` retorna dados suficientes

## Próximos Passos

1. **Integrar com LiveTrader**: Usar EventBus como backbone de comunicação
2. **Adicionar mais adaptadores**: DRLStrategy, RandomForest, etc.
3. **Persistência de eventos**: Opcional para replay/auditoria
4. **Métricas de desempenho**: Latência, throughput do barramento
5. **Testes de integração**: Validar com modelos reais (.keras)

## Dependências

- `tensorflow/keras`: Modelo LSTM
- `joblib`: Scaler de features
- `pandas`: Buffer de dados
- `pytest`: Framework de testes
- `unittest.mock`: Mock de dependências pesadas

## Autor
Implementado em 31/01/2026 para branch `feature/architecture-v2-core`
