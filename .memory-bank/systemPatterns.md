# System Patterns: WTNPS-TRADE

Este documento descreve os padrões arquiteturais, de design e fluxos de dados utilizados no monólito atual (`newapp/`). Qualquer nova implementação deve seguir estritamente estes padrões.

## 🏛️ 1. Padrão Arquitetural Macro: Monólito Assíncrono (FastAPI)
O sistema é um monólito centrado no **FastAPI**. Ele atua simultaneamente como:
1.  **Servidor Web:** Renderiza os templates Jinja2 (ex: `charts_clean.html`).
2.  **API REST:** Fornece endpoints de dados históricos (ex: `/api/chart_data`).
3.  **Servidor WebSocket:** Mantém conexões persistentes com os clientes para atualizações de cotações em tempo real.
4.  **Orquestrador de Background:** Gerencia o loop infinito do motor de trading (`MonitorEngine`) rodando em paralelo (via `BackgroundTasks` ou `Threading`).

### 1.1 Padrão Operacional Realtime: Singleton + Always-On
Para o módulo de monitoramento em tempo real, o motor deve seguir o padrão **Singleton/Always-On**:
* **Instância única por ativo/timeframe:** apenas uma instância viva de `RealtimeMarketMonitor` por chave lógica (ex: `WDO$-M5`, `WIN$-M5`).
* **Bootstrap no ciclo de vida da aplicação:** a criação e inicialização ocorre no `lifespan` do FastAPI, não em ação manual da UI.
* **Frontend passivo:** telas e clientes WebSocket apenas consomem stream; não controlam start/stop do motor principal.
* **Fan-out centralizado:** o endpoint WebSocket atua como camada de broadcast dos dados já produzidos pelo motor central.
* **Resiliência operacional:** reconexão de clientes WS não recria motores; apenas reanexa consumidores ao stream existente.

## 🔄 2. Padrão de Comunicação e UI (Frontend-Backend)
A interface não deve fazer "polling" (requisições repetidas REST) para obter novos candles. O fluxo padrão é:
* **Initial Load (Carga Inicial):** Quando a página carrega, o JavaScript (`live_chart.js`) faz um `GET` via REST para buscar as últimas N barras (ex: 1000 barras) e renderiza o gráfico Plotly.
* **Live Updates (Tempo Real):** O frontend abre uma conexão WebSocket com o `WebSocketManager` (`newapp/src/api/websocket_manager.py`). 
* **Push:** Sempre que o `MonitorEngine` processa um novo candle/sinal, ele utiliza o `WebSocketManager.broadcast()` para empurrar o JSON diretamente para o gráfico, que insere o novo ponto usando `Plotly.extendTraces`.

### 2.2 Frontend como "casca burra" (UI-ready payload)
No monitor realtime, o frontend deve atuar como camada de renderização simples:
* **Sem fallback de dados no JS:** regras de default, tratamento de nulos, arredondamentos e classificação devem ficar no backend.
* **Contrato único de exibição:** payload já chega pronto para UI (`UI-ready`), reduzindo lógica condicional em `monitor.js`.
* **Falha rápida de contrato:** mensagem fora do schema deve ser bloqueada no backend (não propagada como payload parcialmente inválido).

### 2.1 Template Inheritance (Jinja2) como padrão de UI
Para reduzir duplicação e estabilizar manutenção do frontend server-side:
* **`base.html` obrigatório:** componentes estruturais compartilhados (sidebar, head comum, scripts base, containers) devem residir no template base.
* **Páginas derivadas (`monitor.html`, `charts.html`)** devem usar `{% extends 'base.html' %}` e sobrescrever apenas blocos de conteúdo específicos.
* **Sem duplicação estrutural:** menu lateral, shell de layout e imports comuns não devem ser copiados entre páginas.
* **Compatibilidade incremental:** a herança deve preservar IDs/classes esperados pelo JavaScript existente para evitar regressão no comportamento realtime.

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
5.  **Broadcast (prioritário):** Dispara o payload final via WebSocket para a Interface Gráfica.
6.  **Persist (desacoplado):** Salva candle e inferência no Banco de Dados em fluxo assíncrono independente.

## 🧠 6. Padrão de Estratégia e ML (Adapter de Inferência)
O ML não treina em tempo de execução, atua apenas em **modo de inferência**.
* **Carregamento de Artefatos (Slice 1):** os artefatos `keras` (`*_lstm.keras`) e `joblib` (`*_scaler.joblib`) devem seguir **Lazy Loading com cache em memória**; não devem ser carregados no startup da API.
* **Validação de Shape:** Antes de chamar `model.predict()`, os dados formatados devem obrigatoriamente validar o *input_shape* (ex: `(1, 108, n_features)`) para evitar crashes silenciosos ou retornos inconsistentes.

### 6.1 Lazy Loading + Cache em Memória (FastAPI assíncrono)

No módulo realtime (`newapp`), o padrão oficial para inferência é:

* **Sem preload no lifespan:** startup do FastAPI não deve carregar modelos/scalers para evitar bloqueio da subida da API.
* **Carga sob demanda:** no primeiro candle que exigir predição, verificar cache (`if model is None: load_model()`).
* **Cache por ativo/estratégia/timeframe:** após carregados, artefatos permanecem em memória para predições subsequentes rápidas.
* **I/O bloqueante fora do Event Loop:** carregamento de TensorFlow/Keras/Joblib deve ocorrer em thread separada (`asyncio.to_thread` ou equivalente) para não degradar REST/WS.
* **Single-flight no primeiro carregamento:** proteger concorrência para evitar cargas duplicadas quando múltiplos candles chegam simultaneamente.

### 6.2 Regras obrigatórias de implementação

1. A classe de predição deve encapsular cache de `model`, `scaler` e metadados por chave de ativo.
2. O método assíncrono de predição deve garantir que a rotina de load bloqueante rode fora do loop principal.
3. Falhas de carregamento devem ser tratadas sem derrubar o processo FastAPI, retornando erro controlado e log estruturado.
4. Requisições/realtime já conectadas por WebSocket não podem ser interrompidas por operações de load de artefatos.

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

## 🧪 9. Padrão de Testes Realtime: Replay Engine via Banco (DI)

Para testes automatizados do `RealtimeMarketMonitor` (Always-On), o padrão oficial é **Injeção de Dependência (DI)** da fonte de dados:

* **Produção permanece inalterada:** o fluxo padrão com MT5 (`mt5.initialize()`, terminal e provider oficial) continua igual no runtime normal.
* **Isolamento em testes:** durante `pytest`, o monitor deve aceitar um provedor injetado de replay, sem abrir/conectar MetaTrader.
* **Fonte de replay:** o provedor de testes lê candles do banco do projeto (SQLite/SQL Server/Postgres), consumindo tabelas existentes de assets/rates.
* **Contrato canônico preservado:** mesmo em replay, o payload emitido deve manter estrutura de produção (`ohlcv`, `indicators`, `analysis`, `ml`, `decision`).
* **Sem acoplamento ao MT5 no teste:** testes não devem depender de terminal aberto, credenciais ou ambiente local do MetaTrader.

### 9.1 Regras de implementação (obrigatórias)

1. `RealtimeMarketMonitor` deve receber a fonte de dados por construtor/factory (DI), com default apontando para provider de produção.
2. O provider de replay deve implementar a mesma interface pública esperada pelo monitor (`get_latest_candles`/equivalente).
3. O caminho de testes deve usar Repository/DB como origem de dados históricos e nunca chamar `mt5.initialize()`.
4. A suíte de testes deve validar emissão de eventos em callback/fila WebSocket com sequência de candles reproduzível.

### 9.2 Critérios de aceite de arquitetura para CI

* CI executa testes do monitor sem instanciar MT5.
* Replays a partir do banco produzem fluxo contínuo de eventos válidos.
* Diferenças entre produção e teste ficam restritas ao provider injetado (não ao loop de negócio).

## 🗄️ 10. Eventual Consistency: Persistência em Background (Slice 1)

Para o monitor realtime, a persistência de mercado/predição deve seguir **consistência eventual** com prioridade para latência de entrega em WebSocket.

* **Desacoplamento obrigatório:** envio WS e gravação em banco não podem compartilhar caminho síncrono bloqueante.
* **Prioridade de latência:** `_process_new_candle` deve concluir o broadcast sem aguardar commit.
* **Persistência assíncrona:** gravação via `asyncio.create_task()`, `asyncio.Queue` com worker interno, ou mecanismo equivalente de background task.
* **Resiliência de falha:** erro de persistência não derruba stream WS; falha deve ser logada e tratada para retry/dead-letter local conforme política definida.

### 10.1 Regras de implementação

1. O método de broadcast e o método de `AssetsRatesRepository` devem executar de forma independente.
2. O tempo de resposta de `_process_new_candle` não pode incluir tempo de commit de banco.
3. A fila/worker de persistência deve preservar ordem temporal por ativo/timeframe.
4. Shutdown do app deve drenar tarefas pendentes de persistência com timeout controlado.

### 10.2 Observabilidade mínima

* Métricas recomendadas: tamanho de fila, latência de persistência, taxa de erro de write, backlog por ativo.
* Logs estruturados: `persist_enqueue`, `persist_success`, `persist_failure`, `persist_retry`.

## 📦 11. Strict Data Contracts para WebSocket (Pydantic)

Todas as mensagens do WebSocket do monitor devem seguir validação estrita via `pydantic.BaseModel` antes do envio ao cliente.

* **Schema canônico obrigatório:** `MonitorPayload` com blocos `ohlcv`, `indicators`, `analysis`, `ml`, `decision`.
* **Serialização backend-first:** campos críticos devem sair formatados/normalizados pelo backend.
* **Nulos controlados:** backend deve evitar `null` em campos essenciais de UI (ex.: probabilidade) por meio de default/normalização no modelo.
* **Sem regra de negócio no frontend:** funções de fallback/classificação no JS (ex.: `toNumberOrNull`, `classifySeverity`) deixam de ser fonte de verdade.

### 11.1 Regras de implementação

1. O payload WS deve ser instanciado por `MonitorPayload` (ou equivalente) antes de broadcast.
2. Formatações visuais críticas (probabilidade válida, arredondamentos-base, sinal/status coerentes) devem ser tratadas durante construção/serialização do modelo.
3. Erros de validação devem ser logados com contexto e não devem derrubar o loop realtime.
4. O contrato deve ser versionável sem quebrar clientes (adicionar campos opcionais com compatibilidade progressiva).

### 11.2 Benefícios operacionais esperados

* Redução de bugs de renderização no `monitor.js`.
* Menor complexidade de frontend e menor custo de manutenção.
* Consistência de payload entre WebSocket, monitor e testes de contrato.

## 🌿 12. Git Workflow: Shared Feature Branch (Slice 1)

Para coordenação de múltiplos agentes no Slice 1, o fluxo oficial de integração é por **Feature Branch Compartilhada**.

* **Branch base do slice:** `feature/monitor-slice-1` (criada a partir de `main`).
* **Sem PR direto para `main`:** durante esta fase, nenhuma tarefa de BackendQuant/Fullstack/Guardian abre PR alvo `main`.
* **Integração incremental:** cada agente entrega commits/PRs para `feature/monitor-slice-1`, permitindo validação conjunta do slice.
* **Gate arquitetural:** merge para `main` ocorre apenas após validação ponta a ponta do Architect sobre a branch compartilhada.

### 12.1 Regras operacionais obrigatórias

1. Todos os commits e Pull Requests do Slice 1 devem ter como alvo `feature/monitor-slice-1`.
2. Issues do Slice 1 devem explicitar essa regra no enunciado para evitar desvios de fluxo.
3. A revisão final arquitetural consolida backend, frontend e testes antes de qualquer merge para `main`.