# WTNPS Trade - Framework de Backtesting Algorítmico

Um framework modular e robusto em Python para o desenvolvimento, backtesting e análise de estratégias de trading algorítmico. Este projeto foi construído com base em princípios de engenharia de software para garantir testabilidade, reprodutibilidade e escalabilidade.

## Filosofia Arquitetural

A ferramenta foi projetada com base em três pilares principais para permitir a iteração e experimentação rápidas:

1.  **Modularidade (Strategy as a Plug-in):** Cada estratégia de trading é uma classe autocontida que se "pluga" ao motor principal, permitindo a fácil adição de novas lógicas sem alterar o núcleo do sistema.
2.  **Configuração-Driven:** A execução dos backtests é controlada inteiramente por um arquivo de configuração (`configs/main.yaml`), eliminando a necessidade de alterar o código-fonte para testar diferentes ativos, períodos ou parâmetros.
3.  **Testabilidade:** O framework foi desenvolvido com testes unitários e de integração (`pytest`) para garantir a confiabilidade de cada componente (pipeline de dados, estratégias, motor de backtest).

## Estrutura do Projeto

```
wtnps-trade/
├── configs/              # Arquivos de configuração (YAML)
│   └── main.yaml
├── src/                  # Código-fonte principal da aplicação
│   ├── data_handler/       # Módulo para aquisição e cache de dados
│   ├── strategies/         # Onde cada estratégia de trading é implementada
│   ├── backtest_engine/    # O motor de validação Walk-Forward
│   ├── reporting/          # Módulo para geração de relatórios visuais
│   └── run.py              # Ponto de entrada para executar os backtests
├── tests/                # Testes unitários e de integração
├── .cache_data/          # (Gerado) Cache local de dados de mercado
├── report.html           # (Gerado) Relatório de saída do último backtest
└── pyproject.toml        # Definição do projeto e suas dependências (Poetry)
```

## Setup e Instalação

**Pré-requisitos:**
* Git
* Python (versão ^3.10, conforme `pyproject.toml`)
* [Poetry](https://python-poetry.org/docs/#installation) (gerenciador de dependências)

**Passos para instalação:**

1.  **Clone o repositório:**
    ```bash
    git clone URL_DO_SEU_REPOSITORIO.git
    cd wtnps-trade
    ```

2.  **Instale as dependências:**
    O Poetry criará um ambiente virtual e instalará todas as bibliotecas necessárias definidas no `pyproject.toml`.
    ```bash
    poetry install
    ```

## Como Usar

A execução de um backtest completo é feita em dois passos simples:

1.  **Ajuste a Configuração:**
    Abra o arquivo `configs/main.yaml` e edite os parâmetros conforme desejado:
    * `data_settings`: Defina o `ticker` do ativo e o intervalo de datas.
    * `backtest_settings`: Escolha a estratégia a ser test