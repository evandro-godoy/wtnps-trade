# src/live/README.md

# Módulo de Monitoramento em Tempo Real

## Visão Geral

Este módulo implementa um sistema de monitoramento em tempo real que utiliza modelos de Machine Learning treinados para gerar alertas de trading baseados em análise de volatilidade.

## Arquivos

### `monitor_engine.py`
Motor principal do sistema de monitoramento.

**Classe Principal:** `RealTimeMonitor`

**Funcionalidades:**
- Conexão com MetaTrader 5 via `MT5Provider`
- Carregamento automático de modelos treinados (LSTM Volatility)
- Buffer circular de 500 candles históricos
- Sincronização temporal com fechamento de candles
- Geração de alertas baseados em probabilidade ML
- Reconexão automática em caso de falha MT5
- Tratamento robusto de erros

## Uso

### Execução Básica

```powershell
poetry run python run_monitor.py
```

### Interrupção

Pressione `Ctrl+C` para parar graciosamente o monitoramento.

## Configuração

### Parâmetros do Monitor (em `run_monitor.py`)

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `TICKER` | "WDO$" | Ativo a monitorar |
| `TIMEFRAME` | "M5" | Timeframe dos candles (M1, M5, M15, M30, H1, H4, D1) |
| `THRESHOLD_ALERT` | 0.65 | Probabilidade mínima para gerar ALERTA (>65%) |
| `THRESHOLD_LOG` | 0.55 | Probabilidade mínima para gerar LOG (>55%) |
| `BUFFER_SIZE` | 500 | Quantidade de candles no buffer histórico |
| `CONFIG_PATH` | "configs/main.yaml" | Caminho do arquivo de configuração |

## Lógica de Alertas

### Níveis de Probabilidade

**1. Probabilidade 55% - 65% (LOG INFO)**
```
📊 Probabilidade Moderada | Hora: 2025-11-21 14:35:00 | Probabilidade: 58.34% | Preço: 125450.00
```
- Log informativo apenas
- Monitoramento passivo
- Inclui hora, probabilidade e preço

**2. Probabilidade > 65% (ALERTA CRÍTICO)**
```
🚨 ALERTA DE VOLATILIDADE 🚨 | Hora: 2025-11-21 14:40:00 | Probabilidade: 72.15% | Direção: CALL | Preço: 125680.00 | EMA(20): 125320.50
```
- Alerta crítico com direção de trade
- Inclui: hora, probabilidade, direção (CALL/PUT), preço atual e EMA(20)
- **CALL**: Preço acima da EMA(20) - sinal de compra
- **PUT**: Preço abaixo da EMA(20) - sinal de venda

## Fluxo de Processamento

### 1. Inicialização
```
1. Carrega configuração do configs/main.yaml
2. Conecta ao MetaTrader 5
3. Carrega estratégia LSTMVolatilityStrategy
4. Carrega modelo treinado de models/
5. Executa warm-up (buffer de 500 candles)
```

### 2. Loop Principal
```
1. Sincroniza com próximo fechamento de candle (HH:M0, HH:M5... + 5s)
2. Verifica conexão MT5 (reconecta se necessário)
3. Busca novo candle do MT5
4. Atualiza buffer (append novo + remove antigo)
5. Calcula features com LSTMVolatilityStrategy.define_features()
6. Calcula EMA(20) para filtro de tendência
7. Executa predição do modelo LSTM
8. Gera log/alerta conforme probabilidade
9. Retorna ao passo 1
```

## Requisitos

### Arquivos Necessários

**Modelo Treinado:**
```
models/
├── WDO$_LSTMVolatilityStrategy_M5_prod_lstm.keras
├── WDO$_LSTMVolatilityStrategy_M5_prod_scaler.joblib
└── WDO$_LSTMVolatilityStrategy_M5_prod_params.joblib
```

**Configuração:**
```
configs/main.yaml (com asset WDO$ e estratégia LSTMVolatilityStrategy configurados)
```

### Pré-requisitos

1. **MT5 Terminal:** Deve estar aberto, logado e conectado ao servidor
2. **Modelo Treinado:** Execute `poetry run python train_model.py` antes
3. **Conexão Internet:** Para sincronização de dados MT5

## Tratamento de Erros

### Reconexão Automática
- Detecta perda de conexão MT5
- Tenta reconectar automaticamente (shutdown + reinit)
- Máximo de 5 erros consecutivos antes de encerrar

### Validações
- ✓ Dados insuficientes após features
- ✓ Features faltando no DataFrame
- ✓ Sequências insuficientes para LSTM
- ✓ Buffer vazio do MT5

## Logs

### Níveis de Logging

| Módulo | Nível | Descrição |
|--------|-------|-----------|
| `monitor_engine` | INFO | Eventos principais do monitor |
| `provider` | WARNING | Reduz verbosidade de fetch de dados |
| `tensorflow` | ERROR | Silencia warnings do TensorFlow |

### Exemplo de Log Completo
```
2025-11-21 14:30:00 - INFO - [monitor_engine] ================================================================================
2025-11-21 14:30:00 - INFO - [monitor_engine] INICIALIZANDO REAL-TIME MONITOR
2025-11-21 14:30:00 - INFO - [monitor_engine] ================================================================================
2025-11-21 14:30:01 - INFO - [monitor_engine] Carregando configuração de: configs/main.yaml
2025-11-21 14:30:01 - INFO - [monitor_engine] Inicializando MetaTrader 5 Provider...
2025-11-21 14:30:02 - INFO - [monitor_engine] ✓ MT5 conectado com sucesso
2025-11-21 14:30:02 - INFO - [monitor_engine] Carregando estratégia LSTMVolatilityStrategy...
2025-11-21 14:30:02 - INFO - [monitor_engine] ✓ Estratégia carregada com sucesso
2025-11-21 14:30:02 - INFO - [monitor_engine] Carregando modelo ML treinado...
2025-11-21 14:30:03 - INFO - [monitor_engine] ✓ Modelo carregado de: models/WDO$_LSTMVolatilityStrategy_M5_prod
2025-11-21 14:30:03 - INFO - [monitor_engine] WARM-UP: Buscando 500 velas históricas...
2025-11-21 14:30:05 - INFO - [monitor_engine] ✓ Buffer inicializado com 500 candles
2025-11-21 14:30:05 - INFO - [monitor_engine] ================================================================================
2025-11-21 14:30:05 - INFO - [monitor_engine] INICIANDO MONITORAMENTO EM TEMPO REAL
2025-11-21 14:30:05 - INFO - [monitor_engine] ================================================================================
2025-11-21 14:30:05 - INFO - [monitor_engine] Aguardando próximo candle... (295s até 14:35:05)
```

## Troubleshooting

### Erro: "Falha ao conectar ao MetaTrader 5"
**Solução:** Certifique-se de que o terminal MT5 está aberto e logado.

### Erro: "FileNotFoundError: models/..."
**Solução:** Execute o treinamento primeiro:
```powershell
poetry run python train_model.py
```

### Erro: "Nenhum dado retornado do MT5"
**Soluções:**
- Verifique se o ticker está correto (WDO$, WIN$, etc.)
- Confirme que há dados disponíveis no horário atual
- Verifique conectividade com o servidor MT5

### Alerta: "Dados insuficientes após calcular features"
**Causa:** Buffer muito pequeno ou dados corrompidos.
**Solução:** Aumente `BUFFER_SIZE` para pelo menos 500 candles.

## Integração com Outros Módulos

### Dependências
```python
from src.data_handler.provider import MetaTraderProvider
from src.strategies.lstm_volatility import LSTMVolatilityStrategy
```

### Compatibilidade
- ✓ `LSTMVolatilityStrategy` v1.0+
- ✓ `MT5Provider` com suporte a `get_latest_candles()`
- ✓ Modelos treinados no formato `.keras` + `.joblib`

## Próximas Melhorias

- [ ] Salvar alertas em banco de dados (SQLite/PostgreSQL)
- [ ] Integração com Telegram para notificações
- [ ] Dashboard web em tempo real (Streamlit/Dash)
- [ ] Múltiplos tickers simultâneos
- [ ] Backtesting de alertas gerados
- [ ] Configuração de stop/target automático
