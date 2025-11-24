## Integração de Base Histórica Imutável (SQLite) no NewApp

Objetivo: Usar `wtnps_trade.db` apenas dentro de `newapp/` para armazenar dados históricos (OHLCV + indicadores derivados) consumidos por treinamento, replay e simulação — sem alterar o fluxo legado existente fora de `newapp/` (que continua com Parquet + MT5/YF).

### Escopo
- Somente código em `newapp/` passa a ler/escrever histórico via camada ORM/repositórios.
- Código legado (fora de `newapp/`) permanece inalterado.
- Dados são tratados como "quase imutáveis": não sobrescrever candles históricos já persistidos; apenas enriquecer com novos indicadores se necessário.

### Tabelas Alvo
Definir um modelo relacional de tabelas, possibilitando fácil e rápido uso, atualização ou inserção de dados. Atualmente a principal tabela do banco de dados é `AssetsRates` (já inclui OHLCV + campos de indicadores). Manter por enquanto `OHLCVData`, `TechnicalIndicators`, `MarketAnalysis`, `DataProviderLog` para compatibilidade futura, mas sempre = utilizar as novas estruturas definidas no novo modelo nos repositórios.

### Principais Decisões
1. Padronizar caminho absoluto do banco via env `WTNPS_SQLITE_PATH` (ex.: root do projeto) evitando caminhos relativos diferentes dependendo do diretório de execução.
2. Adicionar pipeline de ingestão histórica (fetch de providers → persistência no banco SQLite).
3. Criar leitor histórico unificado que tenta DB primeiro e faz fallback opcional para provider + persistência incremental.
4. Garantir que análises e futuros treinamentos em `newapp/` usem o leitor histórico em vez de chamar provider diretamente para ranges amplos.
5. Evitar duplicação de caches: manter arquivos Parquet do legado e opcionalmente permitir manutenção temporária dos caches no `newapp/` sem sincronizar de volta.
6. Evitar dependências circulares: manter módulos de database e data_handler independentes.
7. Garantir imutabilidade dos dados históricos: não alterar OHLCV já persistidos; apenas preencher indicadores nulos.


### Componentes a Criar
1. `newapp/src/database/ingest_historical.py`
   - Funções: `ingest_range(symbol: str, timeframe: str|int, start: str, end: str, provider: BaseDataProvider)`
   - Decide mapping timeframe string → inteiro (MT5) para armazenar em `AssetsRates.timeframe` e salva `timeframe_str`.
   - Garante idempotência: para cada candle, se já existe (unique index), não altera valores OHLC; pode opcionalmente atualizar indicadores nulos.
2. `newapp/src/data_handler/historical_reader.py`
   - Funções: `load_range(symbol, timeframe, start, end)` retornando DataFrame indexado.
   - Lógica: tenta DB → se vazio e provedor disponível → baixa → persiste → retorna.
   - Param de controle: `force_download: bool = False` para reprocessar/enriquecer indicadores (apenas se explicitamente solicitado).
3. Ajustes menores em `context_analyzer.py` (futuro) para usar `historical_reader.load_range`.
4. Ajustes em repositórios e templates se necessário (ex.: adicionar método para logar em `DataProviderLog`).
5. Documentação: atualizar `DATABASE_BACKEND.md` e `MIGRATION.md` com fluxo de ingestão.

### Fluxo de Ingestão
1. Validar conexão (SQLite default). Se `WTNPS_DB_BACKEND=sqlserver` no futuro, manter mesma interface.
2. Obter DataFrame bruto do provider.
3. Calcular indicadores mínimos (EMA9, SMA20, SMA50, SMA200) se ausentes.
4. Persistir usando `AssetsRatesRepository.save_rates_dataframe`.
5. Logar operação em `DataProviderLog` (opcional — adicionar método de repositorio se ainda não existir helper). 

### Considerações de Imutabilidade
- Regra: não alterar OHLCV já escrito (somente indicadores / metadata). Implementar via:
  - Ao salvar: se registro existe → manter open/high/low/close/tick_volume/volume/spread; apenas preencher campos de indicadores que estejam nulos/zero quando `allow_enrich=True`.
  - Config no ingest: `allow_enrich` default True.
  - Para evitar complexidade excessiva, não implementar lógica de versionamento de candles (ex.: sobrescrever OHLCV se diferente); apenas logar warning se detectar discrepância.

### Timeframes
- Utilizar timeframe como inteiro com quantidade de minutos (ex.: 5 para M5).
- Manter também `timeframe_str` para consultas textuais e legibilidade.

### Fallback & Performance
- Para intervalos grandes já persistidos: leitura direta do DB evita reprocessar caches.
- Para intervalos parcialmente persistidos: estratégia simples — ler faixa; se lacunas detectadas (dias faltantes) e `auto_fill=True`, completar.

### Scripts e Uso
Comandos (PowerShell):
```
# Ingestão inicial de um símbolo/timeframe
poetry run python newapp\src\database\ingest_historical.py --symbol WDO$ --timeframe M5 --start 2022-01-01 --end 2025-11-23

# Leitura via reader (exemplo futuro)
poetry run python -c "from newapp.src.data_handler.historical_reader import load_range; import pandas as pd; df = load_range('WDO$', 'M5', '2024-01-01', '2024-06-01'); print(df.head()); print(len(df))"
```

### Riscos & Pontos em Aberto
- Duplicidade de dados entre Parquet e DB (aceitável na transição).
- Crescimento de arquivo SQLite — avaliar compressão ou migração para SQL Server se > ~1–2 GB.
- Versionamento de feature set para treinamento futuro (possível tabela `feature_versions`).
- Conflito de timezone: garantir todos os timestamps em UTC para todo o `newapp/`.

### Próximos Passos
1. Implementar `ingest_historical.py`.
2. Implementar `historical_reader.py`.
3. Atualizar documentação.
4. Validar com testes simples inserção + leitura.
5. Planejar opcional cache warming para símbolos/timeframes mais usados.

### Testes Iniciais
- Inserção: comparar count de registros antes/depois.
- Leitura: garantir ordem cronológica e ausência de duplicatas.
- Enriquecimento: salvar novamente com novos indicadores e validar que OHLCV não mudou.

### Futuro (Opcional)
- Tabela `training_datasets` para mapear intervalo + feature set + checksum.
- API endpoints FastAPI para fornecer janelas históricas paginadas.
- Rotina diária incremental (apenas último dia recém-fechado).

---
Este plano foca em mínima invasão: tudo restrito a `newapp/`, com adoção gradual sem quebrar o fluxo existente de treinamento/simulação legado.
