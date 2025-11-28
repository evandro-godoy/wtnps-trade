# ML Model Training Workflow - newapp

## 📋 Visão Geral

Workflow completo de treinamento de modelos ML para o newapp, adaptado do sistema legado com integração ao novo ecossistema (HybridDataLoader + SQLAlchemy).

## 🏗️ Arquitetura

### Componentes Criados

1. **Estratégias (`newapp/src/strategies/`)**
   - `base.py`: Interface abstrata (idêntica ao legado)
   - `lstm_volatility.py`: Estratégia LSTM para detecção de volatilidade
   - Lógica de negócio **mantida inalterada** do legado

2. **Configuração (`newapp/configs/main.yaml`)**
   - Define ativos, estratégias e hiperparâmetros
   - Similar ao `configs/main.yaml` do legado, mas usa `HybridDataLoader`

3. **Script de Treinamento (`newapp/train_model.py`)**
   - Adapta `train_model.py` do legado
   - Busca dados via `HybridDataLoader` (DB-first)
   - Salva modelos em `newapp/models/`
   - Persiste métricas no database `wtnps_trade.db`

4. **Database (`newapp/src/database/`)**
   - **Modelo**: `TrainingRun` em `models.py`
   - **Repositório**: `TrainingRunRepository` em `repository.py`
   - Armazena métricas, confusion matrix, loss history, feature stats

## 📂 Estrutura de Diretórios

```
newapp/
├── models/                          # Modelos treinados (.keras, .joblib)
│   ├── WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras
│   ├── WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib
│   └── WDO$_LSTMVolatilityStrategy_M5_prod_params.joblib
├── reports/models/                  # Relatórios HTML/JSON/TXT
├── src/strategies/                  # Estratégias de ML
│   ├── base.py
│   └── lstm_volatility.py
├── configs/
│   └── main.yaml                    # Configuração de treinamento
└── train_model.py                   # Script principal
```

## 🚀 Como Usar

### 1. Configurar Ativos e Estratégias

Edite `newapp/configs/main.yaml`:

```yaml
global_settings:
  model_directory: "c:/projects/wtnps-trade/newapp/models"
  reports_directory: "c:/projects/wtnps-trade/newapp/reports/models"

assets:
  - ticker: "WDO$"
    enabled: true
    strategies:
      - name: "LSTMVolatilityStrategy"
        module: "lstm_volatility"
        provider: "HybridDataLoader"
        data:
          start_date: "2022-05-01"
          end_date: "2025-11-19"
          timeframe_model: "M5"
        strategy_params:
          lookback: 108
          lstm_units: 64
          dropout_rate: 0.2
          epochs: 30
          batch_size: 256
          target_period: 12
          volatility_multiplier: 2.5
```

### 2. Executar Treinamento

```powershell
cd c:\projects\wtnps-trade
poetry run python newapp/train_model.py
```

### 3. Monitorar Progresso

O script irá:
1. ✅ Carregar configurações de `newapp/configs/main.yaml`
2. 🔍 Buscar dados via `HybridDataLoader` (DB → Provider fallback)
3. 🧮 Gerar features e targets usando a estratégia
4. 🏋️ Treinar o modelo LSTM com early stopping
5. 📊 Avaliar métricas (accuracy, precision, recall, F1)
6. 💾 Salvar modelo em `newapp/models/`
7. 📄 Gerar relatórios em `newapp/reports/models/`
8. 🗄️ Persistir métricas no database `wtnps_trade.db`

### 4. Verificar Resultados

**Modelos salvos:**
```
newapp/models/
├── WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras      # Modelo Keras
├── WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib   # MinMaxScaler
└── WDO$_LSTMVolatilityStrategy_M5_prod_params.joblib   # Metadata (lookback, n_features)
```

**Relatórios gerados:**
```
newapp/reports/models/
├── WDO$_LSTMVolatilityStrategy_M5_20251128_073900.json  # Métricas estruturadas
├── WDO$_LSTMVolatilityStrategy_M5_20251128_073900.txt   # Resumo textual
└── WDO$_LSTMVolatilityStrategy_M5_20251128_073900.html  # Relatório visual (gráficos)
```

**Métricas no database:**
```sql
SELECT * FROM training_runs 
WHERE symbol = 'WDO$' AND strategy_name = 'LSTMVolatilityStrategy' 
ORDER BY created_at DESC LIMIT 1;
```

## 📊 Dados Armazenados no Database

A tabela `training_runs` contém:

- **Identificação**: symbol, strategy_name, timeframe_str
- **Período**: start_date, end_date
- **Métricas de Treino**: train_accuracy, train_precision, train_recall, train_f1
- **Métricas de Teste**: test_accuracy, test_precision, test_recall, test_f1
- **Confusion Matrix**: train_tn, train_fp, train_fn, train_tp (e teste)
- **Distribuição de Classes**: train_class_0_count, train_class_1_count
- **Metadata**: strategy_params (JSON), feature_stats (JSON), loss_history (JSON)
- **Performance**: training_duration_seconds, total_epochs

## 🔧 Integração com Prediction Engine

Os modelos treinados são automaticamente carregados pelo `MLPredictionEngine`:

```python
from newapp.src.ml.prediction_engine import get_prediction_engine

engine = get_prediction_engine()
predictions = engine.predict_latest(
    symbol="WDO$",
    timeframe="M5",
    count=10,
    strategy_name="LSTMVolatilityStrategy"
)
```

## 📈 Análise de Treinamentos

Use o repositório para consultar histórico:

```python
from newapp.src.database.db import get_db
from newapp.src.database.repository import TrainingRunRepository

db = next(get_db())

# Último treinamento
latest = TrainingRunRepository.get_latest_training_run(
    db, symbol="WDO$", strategy_name="LSTMVolatilityStrategy", timeframe_str="M5"
)
print(f"Test Accuracy: {latest.test_accuracy:.2%}")
print(f"Test F1: {latest.test_f1:.4f}")

# Histórico completo
history = TrainingRunRepository.get_all_training_runs(
    db, symbol="WDO$", limit=10
)
for run in history:
    print(f"{run.created_at} - Test Acc: {run.test_accuracy:.2%}")
```

## ⚠️ Diferenças do Legado

| Aspecto | Legado | newapp |
|---------|--------|--------|
| **Data Source** | `MetaTraderProvider` direto | `HybridDataLoader` (DB-first) |
| **Modelo Dir** | `models/` (raiz) | `newapp/models/` |
| **Relatórios** | `reports/models/` (raiz) | `newapp/reports/models/` |
| **Config** | `configs/main.yaml` | `newapp/configs/main.yaml` |
| **Persistência** | Apenas arquivos | Arquivos + Database (`training_runs`) |
| **Import Path** | `from src.strategies` | `from newapp.src.strategies` |

## 🎯 Nomenclatura de Modelos

Padrão legado mantido:
```
{TICKER}_{STRATEGY_NAME}_{TIMEFRAME}_prod_{MODULE}.{EXT}
```

Exemplos:
- `WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras`
- `WIN$_LSTMVolatilityStrategy_M5_prod_scaler.joblib`

## 🔍 Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'newapp'"
**Solução:** Execute sempre da raiz do projeto:
```powershell
cd c:\projects\wtnps-trade
poetry run python newapp/train_model.py
```

### Erro: "DataFrame vazio para {symbol}"
**Causa:** `HybridDataLoader` não encontrou dados no DB nem no provider.

**Solução:** Verifique se:
1. Database tem dados: `SELECT COUNT(*) FROM assets_rates WHERE symbol = 'WDO$'`
2. Provider está configurado (MT5 rodando)
3. Datas no config são válidas

### Warning: "Dados insuficientes para treino (X amostras)"
**Causa:** Menos de 100 candles após limpeza de NaNs.

**Solução:** Ajuste `start_date` no config para período maior.

## 📝 Próximos Passos

1. ✅ Treinamento funcional com HybridDataLoader
2. ✅ Persistência de métricas no database
3. ✅ Integração com MLPredictionEngine
4. 🔲 Interface web para visualizar histórico de treinamentos
5. 🔲 Automação de retreinamento periódico
6. 🔲 Comparação de modelos (A/B testing)
7. 🔲 Alertas de degradação de performance

## 📚 Referências

- Legacy: `train_model.py`, `src/strategies/lstm_volatility.py`
- Database: `newapp/src/database/models.py` (TrainingRun)
- Repository: `newapp/src/database/repository.py` (TrainingRunRepository)
- Prediction: `newapp/src/ml/prediction_engine.py`
