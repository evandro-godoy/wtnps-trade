# WTNPS Trade - Framework de Trading Algorítmico

Um framework modular e robusto em Python para o desenvolvimento, simulação, backtesting e execução de estratégias de trading algorítmico, com foco principal em modelos de Machine Learning (como LSTM) e integração direta com o MetaTrader 5.

## Filosofia Arquitetural

O projeto evoluiu para um sistema híbrido que opera com base em quatro pilares principais, permitindo uma separação clara de responsabilidades e alta capacidade de experimentação:

1.  **Config-Driven (Guiado por Configuração):** O coração do sistema é o arquivo `configs/main.yaml`. Ele controla *tudo*: quais ativos operar, quais estratégias usar, os parâmetros de dados, as regras de trading (Stop Loss/Take Profit), os parâmetros de execução ao vivo e as regras de setup técnico.
2.  **Modularidade (Strategy as a Plug-in):** Cada estratégia de trading (ex: `LSTMStrategy`) é uma classe autocontida que herda de `src/strategies/base.py`. O framework carrega dinamicamente a estratégia definida no `main.yaml`, permitindo a fácil adição de novas lógicas sem alterar os motores principais.
3.  **Lógica Híbrida (IA + Setup Técnico):** O sistema utiliza um processo de decisão em duas etapas:
      * **Sinal da IA:** Um modelo de Machine Learning (ex: LSTM) gera o sinal primário (Compra/Venda).
      * **Filtro de Setup:** O módulo `src/setups/analyzer.py` valida esse sinal contra um conjunto de regras técnicas (ex: `price_above_ma`) definidas na seção `setup` do `main.yaml`. Uma operação só é considerada válida se *ambas* as condições forem atendidas.
4.  **Motores Duplos (Simulação e Live):** O projeto possui dois motores de execução distintos:
      * `src/simulation/engine.py`: Usado para simulações, "market replay" e análises (como as vistas nos notebooks). Ele pode simular a lógica de decisão para qualquer ponto no tempo.
      * `src/live_trader.py`: O motor de operação em tempo real. Ele se conecta ao MT5, monitora novos candles e pode `sugerir` ou `executar` trades reais.
5.  **Dashboards:** O projeto possui algumas interfaces, ainda em construção, para uso dos motores de forma mais amigável.

## Estrutura do Projeto

```
wtnps-trade/
├── configs/
│   └── main.yaml                     # Arquivo mestre de configuração
├── models/                           # Modelos de IA (.keras) e scalers (.joblib)
├── src/
│   ├── data_handler/
│   │   └── provider.py               # Provedores de dados (MetaTraderProvider, YFinanceProvider)
│   ├── strategies/
│   │   ├── base.py                   # Classe base abstrata para estratégias
│   │   ├── lstm.py                   # Implementação da estratégia com LSTM e KerasWrapper
│   │   └── random_forest.py          # Implementação da estratégia com LSTM e KerasWrapper
│   ├── setups/
│   │   └── analyzer.py               # Avaliador das regras de setup (ex: médias móveis)
│   ├── simulation/
│   │   └── engine.py                 # Motor para simulação e "market replay"
│   ├── backtest_engine/
│   │   └── runner.py                 # Lógica de simulação de P/L (Stop Loss/Take Profit)
│   ├── gui/
│   │   ├── dashboard.py              # Interface para uso do motor engine.py
│   │   └── live_trader_dashboard.py  # Interface para uso do simulador simulate_single_cicle do live_trader.py
│   ├── reporting/
│   │   └── plot.py                   # Mecanismo para geração de relatórios
│   └── live_trader.py                # Motor principal para trading ao vivo com MT5
├── notebooks/
│   └── simulation/         # Notebooks para testar o 'SimulationEngine'
├── tests/                  # Testes unitários e de integração
├── .cache_data/            # (Gerado) Cache local de dados de mercado (Parquet)
├── train_model.py          # Script para treinar os modelos de IA
└── pyproject.toml          # Definição do projeto e dependências (Poetry)
```

## Stack de Tecnologia

O projeto utiliza as seguintes tecnologias principais:

  * **Python:** ^3.12
  * **Poetry:** Para gerenciamento de dependências.
  * **MetaTrader 5:** Usado como provedor de dados primário e para execução de ordens.
  * **TensorFlow / Keras:** Para a construção e treinamento dos modelos LSTM.
  * **Scikit-learn:** Usado para o `MinMaxScaler` e como wrapper para o modelo Keras.
  * **Pandas / Numpy:** Para manipulação e análise de dados.
  * **PyYAML:** Para carregar os arquivos de configuração.

## Fluxo de Trabalho (Como Usar)

O uso do framework é dividido em três etapas principais:

### 1\. Configuração

Tudo começa no arquivo `configs/main.yaml`. Antes de treinar ou executar, você deve definir:

  * `global_settings`: Paths para salvar modelos e relatórios.
  * `assets`: A lista de ativos para operar. Para cada ativo:
      * `ticker`: O ticker usado para *dados históricos* (ex: "WDO$").
      * `provider`: `MetaTrader5` ou `YFinance`.
      * `strategy_module` / `strategy_name`: O nome do arquivo e da classe da estratégia a ser usada (ex: `lstm`, `LSTMStrategy`).
      * `data`: O intervalo de datas e o timeframe para *treinamento* do modelo (ex: "H1").
      * `trading_rules`: Regras financeiras como `initial_capital`, `stop_loss_pct`, `take_profit_pct`.
      * `live_trading`: Parâmetros para execução real, incluindo `ticker_order` (o ticker para enviar ordens, ex: "WDOX25"), `timeframe_str` (timeframe de operação), `execution_mode` (`suggest` ou `execute`) e `trade_volume`.
      * `setup`: Uma lista de regras de filtro técnico. Ex: `{type: 'price_above_ma', period: 20}`.

### 2\. Treinamento de Modelos

Uma vez configurado, treine os modelos de IA para os ativos habilitados:

```bash
poetry run python train_model.py
```

Este script:

1.  Lê o `configs/main.yaml`.
2.  Para cada ativo, busca os dados históricos (via MT5 ou YFinance).
3.  Carrega a estratégia (ex: `LSTMStrategy`) e prepara as features e o "target".
4.  Define e treina o modelo (ex: `KerasLSTMWrapper`).
5.  Salva o modelo treinado (ex: `WDO$_prod_model.keras`) e o scaler (ex: `WDO$_prod_scaler.joblib`) no diretório definido em `global_settings`.

### 3\. Execução

O framework pode ser executado em três modos distintos:

#### Modo 1: Trading ao Vivo

Este modo é para operação em tempo real e utiliza o `src/live_trader.py`.

```bash
poetry run python src/live_trader.py
```

O `LiveTrader`:

1.  Conecta-se ao MetaTrader 5.
2.  Carrega os modelos treinados e as configurações para os ativos habilitados.
3.  Entra em um loop contínuo, verificando novos candles para o timeframe de `live_trading`.
4.  A cada novo candle, executa a lógica completa (features, sinal da IA, validação de setup).
5.  Se o modo de execução for `suggest`, ele apenas imprimirá a sugestão de trade no log.
6.  Se o modo de execução for `execute`, ele enviará a ordem de compra ou venda diretamente para o MT5 usando o `ticker_order` especificado.

* O `LiveTrader` também possuí um método chamado `simulate_single_cycle` que permite a simular operações.

#### Modo 2: Simulação e Análise (Market Replay)

Este modo é ideal para depuração, análise e para os *notebooks* de simulação. Ele utiliza o `src/simulation/engine.py`.

```bash
poetry run python src/simulation/engine.py
```

O `SimulationEngine` carrega os modelos treinados e permite executar um único ciclo de simulação (`run_simulation_cycle`) para um ativo, timeframe e data/hora específicos. Ele retorna um dicionário detalhado com:

  * O sinal da IA (Compra/Venda).
  * A validade do setup (True/False).
  * O sinal final (Compra/Venda/Hold).
  * O preço sugerido, stop e os valores dos indicadores naquele momento.

#### Modo 3: Dashboards

Este modo permite visualizar dados dos ativos 

## Instalação

**Pré-requisitos:**

  * Git
  * Python (versão ^3.12, conforme `pyproject.toml`)
  * [Poetry](https://python-poetry.org/docs/#installation) (gerenciador de dependências)

**Passos para instalação:**

1.  **Clone o repositório:**

    ```bash
    git clone URL_DO_SEU_REPOSITORIO.git
    cd wtnps-trade
    ```

2.  **Instale as dependências:**
    O Poetry criará um ambiente virtual e instalará todas as bibliotecas necessárias definidas no `pyproject.toml` (incluindo pandas, tensorflow, metatrader5, etc.).

    ```bash
    poetry install
    ```