# Project Brief: WTNPS-TRADE

## 🎯 Visão Geral
O WTNPS-TRADE é um sistema de trading algorítmico focado no mercado brasileiro (B3), operando ativos como WDO$ e WIN$ via MetaTrader 5 (MT5). O sistema combina ingestão de dados em tempo real e histórico, análise técnica, predição de mercado via modelos de Machine Learning (LSTM) e visualização interativa em dashboards web.

## 🏛️ Arquitetura e Padrões (O Monólito FastAPI)
O sistema opera em uma arquitetura monolítica fortemente baseada em **FastAPI**, orquestrando tanto o backend de processamento quanto a entrega do frontend.

* **Backend (API & WebSockets):** Utiliza FastAPI (`newapp/src/api/main.py`) para servir rotas REST e gerenciar conexões WebSocket (`WebSocketManager`). O WebSocket é a espinha dorsal para atualizar a interface gráfica em tempo real sem sobrecarregar o navegador.
* **Frontend (UI):** Renderização server-side com Jinja2 (`newapp/templates/charts_clean.html`) combinada com JavaScript vanilla e bibliotecas como Plotly.js para os gráficos (`newapp/static/js`).
* **Motor de Monitoramento:** O `MonitorEngine` (`newapp/src/live/monitor_engine.py`) é o coração do sistema. Ele roda em uma thread/tarefa paralela (background task) dentro do loop do FastAPI, buscando dados, calculando indicadores e gerando predições.

## ⚙️ Componentes Técnicos Críticos

### 1. Hybrid Data Provider (Dados Híbridos)
O sistema utiliza uma abordagem híbrida inteligente para garantir performance e robustez (`newapp/src/data_handler/hybrid_data_loader.py`):
* **Dados Históricos:** Carregados a partir de arquivos `.parquet` ultra-rápidos locais (ex: `MT5_WDO_M5_...parquet`) para compor o *lookback* necessário para os cálculos (ex: 1000 barras).
* **Dados Live:** Buscados em tempo real via MT5 Provider, mesclados instantaneamente com o histórico para alimentar os cálculos de ML e UI.

### 2. Persistência de Dados (Database)
O projeto migrou para o uso ativo de banco de dados relacional (`newapp/src/database`), utilizando SQLAlchemy (SQLite no momento, com estrutura pronta para SQL Server).
* O banco armazena o histórico estático, os dados de mercado atualizados (`market_data`) e as predições geradas (`predictions`), permitindo auditoria e backtesting avançado.
* O fluxo exige que novos candles e sinais calculados pelo `MonitorEngine` sejam gravados no banco em tempo de execução.

### 3. Machine Learning (Inferência LSTM)
O motor analítico depende de modelos pré-treinados localizados na pasta de artefatos (`newapp/models/others/`).
* A classe `LSTMVolatilityStrategy` carrega arquivos `.keras` e `.joblib` (scalers e parâmetros) estritamente acoplados aos ativos (WDO$, WIN$).
* A estratégia depende do cálculo preciso de dezenas de indicadores técnicos (SMA, EMA, RSI, MACD, Bollinger Bands) fornecidos pelo módulo `newapp/src/utils/calculate_indicators.py` para montar os *features* no formato exato que o modelo espera.

## 🛠️ Diretrizes de Desenvolvimento para os Agentes
1. **Foco no Monólito:** Não crie abstrações prematuras como sistemas de mensageria complexos (EventBus). A comunicação entre o motor de trading e a interface deve ser feita diretamente via instâncias de classes, FastAPI Background Tasks e WebSockets.
2. **Contexto Híbrido:** Ao lidar com dados, sempre considere a existência do `HybridDataLoader`. O sistema não puxa 1000 candles do MT5 toda vez; ele mescla os candles novos com a base Parquet/DB existente.
3. **Fluidez Visual:** Alterações na interface (`charts_clean.html`, `live_chart.js`) devem focar em não travar o DOM. Os dados chegam via WebSocket e devem ser inseridos no gráfico (Plotly) de forma iterativa.