# System Patterns: WTNPS-TRADE

Este documento descreve os padrões arquiteturais, de design e fluxos de dados utilizados no monólito atual (`newapp/`). Qualquer nova implementação deve seguir estritamente estes padrões.

## 🏛️ 1. Padrão Arquitetural Macro: Monólito Assíncrono (FastAPI)
O sistema é um monólito centrado no **FastAPI**. Ele atua simultaneamente como:
1.  **Servidor Web:** Renderiza os templates Jinja2 (ex: `charts_clean.html`).
2.  **API REST:** Fornece endpoints de dados históricos (ex: `/api/chart_data`).
3.  **Servidor WebSocket:** Mantém conexões persistentes com os clientes para atualizações de cotações em tempo real.
4.  **Orquestrador de Background:** Gerencia o loop infinito do motor de trading (`MonitorEngine`) rodando em paralelo (via `BackgroundTasks` ou `Threading`).

## 🔄 2. Padrão de Comunicação e UI (Frontend-Backend)
A interface não deve fazer "polling" (requisições repetidas REST) para obter novos candles. O fluxo padrão é:
* **Initial Load (Carga Inicial):** Quando a página carrega, o JavaScript (`live_chart.js`) faz um `GET` via REST para buscar as últimas N barras (ex: 1000 barras) e renderiza o gráfico Plotly.
* **Live Updates (Tempo Real):** O frontend abre uma conexão WebSocket com o `WebSocketManager` (`newapp/src/api/websocket_manager.py`). 
* **Push:** Sempre que o `MonitorEngine` processa um novo candle/sinal, ele utiliza o `WebSocketManager.broadcast()` para empurrar o JSON diretamente para o gráfico, que insere o novo ponto usando `Plotly.extendTraces`.

## 💾 3. Padrões de Banco de Dados (SQLite + SQLAlchemy)
A persistência de dados utiliza o padrão **Repository** sobre um ORM (SQLAlchemy) configurado para SQLite (`newapp/src/database/`).
* **Engine & Session:** Gerenciados centralmente em `db.py`.
* **Models:** Entidades de banco de dados definidas em `models.py` (ex: Tabelas para `market_data` e `predictions`).
* **Repository (`repository.py`):** Toda interação com o banco de dados (inserir candle, buscar histórico, salvar sinal) passa por métodos da classe Repository. **Os agentes nunca devem executar SQL cru ou acessar a `Session` diretamente fora do Repository.**
* **Migração Futura:** O código usa SQLite, mas as tipagens do SQLAlchemy foram construídas prevendo uma transição "suave" para SQL Server.

## 📈 4. Padrão de Ingestão de Dados: "Hybrid Data Loader"
Como modelos LSTM exigem um histórico grande (ex: 108 barras de *lookback* + cálculo de médias de 200 períodos), o sistema usa uma abordagem híbrida (`newapp/src/data_handler/hybrid_data_loader.py`) para evitar sobrecarregar a API do MetaTrader 5:
* **Base Estática (Parquet):** O sistema lê arquivos ultra-rápidos `.parquet` (`newapp/.cache_data/`) gerados pelo `HistoricalReader` para carregar o histórico "profundo" quase instantaneamente.
* **Conexão MT5 (`Provider`):** O `mt5_provider.py` inicializa o terminal do MetaTrader 5 via biblioteca `MetaTrader5`. Ele busca apenas as barras mais recentes (o "delta").
* **Merge:** O `HybridDataLoader` concatena o DataFrame do Parquet com o DataFrame do MT5 de forma transparente para o restante do sistema.

## ⚙️ 5. Padrão do Motor de Monitoramento (`MonitorEngine`)
Localizado em `newapp/src/live/monitor_engine.py`, este é o loop principal do negócio. Ele segue um padrão estrito de execução cíclica:
1.  **Sleep/Wait:** Aguarda o tempo necessário para o fechamento da próxima barra (Timeframe M5).
2.  **Fetch:** Solicita os dados atualizados ao `HybridDataLoader`.
3.  **Enrich (Cálculos):** Passa o DataFrame pelo `calculate_indicators.py` para gerar as dezenas de colunas de features técnicas (SMA, EMA, RSI, MACD, etc.).
4.  **Infer:** Passa os dados enriquecidos para a Estratégia (ML).
5.  **Persist:** Salva o novo candle e o resultado da inferência no Banco de Dados via `Repository`.
6.  **Broadcast:** Dispara o payload final via WebSocket para a Interface Gráfica.

## 🧠 6. Padrão de Estratégia e ML (Adapter de Inferência)
O ML não treina em tempo de execução, atua apenas em **modo de inferência**.
* **Carregamento de Artefatos:** A classe `LSTMVolatilityStrategy` (`newapp/src/strategies/lstm_volatility.py`) deve instanciar o modelo `keras` (`*_lstm.keras`) e os scalers do `joblib` (`*_scaler.joblib`) no método `__init__` para mantê-los em memória. 
* **Validação de Shape:** Antes de chamar `model.predict()`, os dados formatados devem obrigatoriamente validar o *input_shape* (ex: `(1, 108, n_features)`) para evitar crashes silenciosos ou retornos inconsistentes.

## 🔗 7. Contrato de Assinaturas de Dados (Data Contract)

**Este padrão previne divergências de interface entre módulos.** Toda chamada entre Provider → Repository → Service deve respeitar os follow:

### 7.1 Nomenclatura Unificada

| Contexto | Nome Correto | Uso |
|----------|-------------|-----|
| **Data Provider** | `ticker` | Símbolo do ativo (ex: `WDO$`) |
| **Repository** | `symbol` | Símbolo no banco de dados |
| **Parameter Count** | `count` | Número de registros a buscar (Provider→Cache) |
| **Parameter Limit** | `limit` | Número máximo de registros (Repository/DB) |

**Regra de Ouro:** Ao cruzar limites de camada (Provider → Repository), adaptar nomes de parâmetro conforme necessário, mas NUNCA passar `symbol` para Provider ou `ticker` para Repository sem tradução explícita.

### 7.2 Assinaturas de Contrato Críticas

#### **A. HybridProvider.get_latest_candles()**
```python
Location: newapp/src/data_handler/provider.py (line 735)

def get_latest_candles(
    self,
    ticker: str,        # ✅ Always "ticker" (not "symbol")
    timeframe: Any,     # Timeframe object or string (M1, M5, H1, etc.)
    count: int          # ✅ Always "count" (not "limit")
) -> pd.DataFrame:
```

**Retorno:** DataFrame com colunas `[open, high, low, close, volume]`, index timezone-aware (UTC).

**Fallback:** MT5 → Cache Parquet → Synthetic (nunca falha).

---

#### **B. AssetsRatesRepository.get_latest_candles()**
```python
Location: newapp/src/database/repository.py (line 438)

@staticmethod
def get_latest_candles(
    db: Session,
    symbol: str,        # ✅ Always "symbol" at Repository level
    timeframe: str,
    limit: int = 500    # ✅ Always "limit" (database constraint)
) -> pd.DataFrame:
```

**Retorno:** DataFrame com OHLCV histórico do banco, chronological order.

**Nota:** NÃO EXISTE `get_latest_market_data()`. Use `get_latest_candles()` ou `get_all_rates()` conforme contexto.

---

#### **C. MarketContextAnalyzer.analyze()**
```python
Location: newapp/src/analysis/context_analyzer.py

def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: DataFrame with columns [open, high, low, close, volume]
    Output: Same DataFrame + enriched indicator columns
            (ema_9, sma_20, sma_50, sma_200, rsi_14, etc.)
    """
```

**Regra:** O analisador enriquece IN-PLACE; nunca retorna colunas faltantes.

### 7.3 Checklist para Implementadores

- [ ] Ao chamar `HybridProvider.get_latest_candles()`, use `ticker=...`, `count=...`
- [ ] Ao chamar `AssetsRatesRepository.get_latest_candles()`, use `symbol=...`, `limit=...`
- [ ] Se necessário converter `ticker` ↔ `symbol`, fazer no ponto de cruzamento (ex: monitor_engine.py)
- [ ] Nunca passar `None` ou valores não-validados; sempre validar tipos antes de chamar
- [ ] DataFrame retornado deve validar colunas obrigatórias antes de usar: `['open', 'high', 'low', 'close', 'volume']`
- [ ] Sempre usar `pd.DataFrame.set_index('time')` e garantir que index é datetime com timezone UTC

## 🚦 8. Regra Estrita de Consolidação de Sinais (ML + Análise Técnica) e UX

Esta regra é **canônica do legado** e deve ser preservada no monólito (`run_monitor_gui.py` -> `src/gui/monitor_ui.py` -> `src/live/monitor_engine.py` + `context_analyzer.py`).

### 8.1 Classificação por limiares de probabilidade (estrita)

No legado, a classificação usa comparadores estritos (`>`), não inclusivos:

- **ALERT (crítico):** `prob_class1 > 0.65` (ou `prob_pct > 65.0`)
- **INFO (moderado):** `prob_class1 > 0.55` e não ALERT
- **TICK (normal):** `prob_class1 <= 0.55`

Observação importante de borda:
- `prob_class1 == 0.65` **não** entra em ALERT (cai em INFO).
- `prob_class1 == 0.55` **não** entra em INFO (cai em TICK).

### 8.2 Trava de contexto técnico para validar/bloquear sinal

A validação no legado acontece via `MarketContextAnalyzer.validate_signal(...)` e deve alimentar o bloco `decision` no payload.

Regras de bloqueio:
- Bloquear `CALL/COMPRA` quando `rsi_condition == 'SOBRECOMPRADO'`.
- Bloquear `PUT/VENDA` quando `rsi_condition == 'SOBREVENDIDO'`.
- Bloquear `CALL/COMPRA` quando `pattern == 'REJEICAO_ALTA'`.
- Bloquear `PUT/VENDA` quando `pattern == 'REJEICAO_BAIXA'`.

Regra opcional de tendência:
- `require_trend_alignment=False` no fluxo realtime legado (tendência não bloqueia por padrão, apenas contextualiza).

Resultado obrigatório de decisão:
- `signal_valid: bool`
- `validation_reason: str`
- Para logs críticos: `Status: VALIDADO` quando `signal_valid=true`; caso contrário `Status: NÃO VALIDADO`.

### 8.3 Mapeamento visual legado (categorias, cores e ícones)

Padrão dos logs/tabelas na UI legado:
- **ALERT**: fundo `#fff3cd`, texto `#856404`, ícone de criticidade `🚨`, mensagem de validação com `✅` (validado) ou `⚠️` (não validado).
- **INFO**: fundo `#d1ecf1`, texto `#0c5460`, ícone `📊`.
- **TICK**: fundo `#ffffff`, texto `#6c757d`.

No frontend web (`monitor` em Grid), o CSS deve preservar esta semântica visual por categoria para manter equivalência operacional com o legado.