## Plan: Migração para newapp

Priorizar a base já portada em newapp, alinhando dependências, configs e fluxos. Consolidar providers/estratégias para evitar duplicidade, mover execução (simulação/backtest/live) para a pilha web/DB-first, e revisar códigos redundantes. Expandir configs de newapp para cobrir fluxos legados enquanto serviços antigos são adaptados a loaders/repos únicos. Encerrar com revisão de duplicidades e limpeza.

### Steps
1. Padronizar ambiente e deps (Poetry/MT5/DB) revisando requisitos em [pyproject.toml](pyproject.toml) e [newapp/README.md](newapp/README.md).
2. Unificar configs: ampliar [newapp/configs/main.yaml](newapp/configs/main.yaml) com seções de live/backtest/setup espelhadas de [configs/main.yaml](configs/main.yaml); ajustar carregadores em [newapp/configs/config.py](newapp/configs/config.py).
3. Consolidar data layer: tornar [newapp/src/data_handler/hybrid_loader.py](newapp/src/data_handler/hybrid_loader.py) o provider padrão; adaptar consumidores legados (simulação/live/backtest) para usar o loader/repos de [newapp/src/database](newapp/src/database).
4. Estratégias/modelos: centralizar `LSTMVolatilityStrategy` em [newapp/src/strategies/lstm_volatility.py](newapp/src/strategies/lstm_volatility.py) e reexportar para flows legados; alinhar paths de modelos em [newapp/src/ml/predictor.py](newapp/src/ml/predictor.py) e [train_model.py](train_model.py) vs [newapp/train_model.py](newapp/train_model.py).
5. Migração de execução: portar simulação/backtest de [src/simulation/engine.py](src/simulation/engine.py) e [src/backtest_engine/backtest_lstm_volatility.py](src/backtest_engine/backtest_lstm_volatility.py) para os serviços web/stream em [newapp/src/backtest/stream_engine.py](newapp/src/backtest/stream_engine.py) e [newapp/src/live/monitor_engine.py](newapp/src/live/monitor_engine.py); integrar WebSocket/UI em [newapp/main.py](newapp/main.py).
6. Revisão de duplicidades: code review comparando pares providers/estratégias/backtests (root vs newapp); remover ou deprecar versões legadas após validação; atualizar testes em [newapp/tests](newapp/tests) para cobrir os fluxos migrados.

### Step 1 Tasks
- Confirmar versão do Python (3.12+) e do Poetry; atualizar se necessário.
- Rodar `poetry check` e `poetry install` no root e em newapp para validar lock/dep duplicadas.
- Mapear dependências MT5: verificar instalação do terminal, conexão, permissões e módulos MetaTrader5 no env.
- Validar drivers/DB: confirmar SQLite local (wtnps_trade.db) e, se aplicável, client SQL Server; testar string de conexão usada em newapp/src/database.
- Conferir variáveis de ambiente e paths usados por loaders (cache, models, reports) em ambos projetos; alinhar defaults em docs.
- Registrar gaps de dependências entre root/newapp (ex.: DRL/tensorflow, bokeh, fastapi) para fechar no lockfile alvo.

### Further Considerations
1. Preferir um único arquivo de config (expandir newapp/main.yaml) ou manter dois com adaptadores? Inclua como sub task a análise de prós/contras.
2. A base MT5 permanece obrigatória ou DB-first já é suficiente para produção? Manter como está.
