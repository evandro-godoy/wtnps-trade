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