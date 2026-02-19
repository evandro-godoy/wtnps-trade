# Tech Context: WTNPS-TRADE

Este documento define a stack tecnológica inegociável do projeto. Os agentes de IA devem consultar este arquivo antes de propor novas bibliotecas ou arquiteturas.

## 🛠️ Tecnologias Core (Backend)
* **Linguagem:** Python 3.12+
* **Gerenciador de Dependências:** Poetry (`pyproject.toml` / `poetry.lock`)
* **Framework Web & API:** FastAPI
* **Servidor ASGI:** Uvicorn
* **Comunicação Real-Time:** WebSockets (integrado ao FastAPI)
* **Template Engine:** Jinja2 (para renderização server-side de HTML)

## 📊 Tecnologias de Dados e Machine Learning
* **Integração de Mercado:** `MetaTrader5` (API oficial do MT5 em Python)
* **Manipulação de Dados:** `pandas` e `numpy`
* **Armazenamento em Cache (Fast Read):** `pyarrow` / `fastparquet` (para os arquivos `.parquet`)
* **Machine Learning:** * `tensorflow` / `keras` (Inferência de modelos `.keras`)
  * `scikit-learn` / `joblib` (Carregamento de scalers e parâmetros)
* **Cálculo de Indicadores:** Implementações nativas usando `pandas` (ou `TA-Lib` se estritamente configurado).

## 💾 Banco de Dados
* **ORM:** SQLAlchemy (Versão 2.0+)
* **Engine Atual:** SQLite (Arquivo local `wtnps_trade.db` ou similar na raiz/pasta database)
* **Design de Migração:** Estrutura de tipos preparada para transição futura para SQL Server.

## 🖥️ Tecnologias Frontend (UI)
* **Estrutura Base:** HTML5 e CSS3 (arquivos estáticos em `newapp/static/css/`)
* **Linguagem:** JavaScript Vanilla (ES6+)
* **Biblioteca de Gráficos:** **Plotly.js** (Mandatório para gráficos financeiros e de candlesticks interativos).
* **Restrição Frontend:** Não utilizar frameworks SPA complexos (como React, Vue ou Angular) nesta fase. A fluidez deve ser garantida via WebSockets + Plotly `extendTraces` nativo.

## ⚙️ Ambiente e Execução
* **IDE Padrão:** Visual Studio Code.
* **Entrypoint:** Execução via debugger do VS Code (`launch.json`) apontando para a inicialização do `uvicorn` e subida paralela do `MonitorEngine`.