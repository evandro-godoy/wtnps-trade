# Deep Reinforcement Learning (DRL) - Integração WTNPS Trade

## 📋 Visão Geral

Esta integração adiciona capacidades de **Deep Reinforcement Learning** ao framework `wtnps-trade`, permitindo que agentes DDQN (Double Deep Q-Network) aprendam estratégias de trading diretamente através de recompensas baseadas em performance.

A implementação é **totalmente compatível** com a arquitetura modular existente:
- ✅ Usa `configs/main.yaml` para configuração
- ✅ Herda de `BaseStrategy` 
- ✅ Funciona com `SimulationEngine` e `live_trader.py`
- ✅ Consome dados via `MetaTraderProvider` ou `YFinanceProvider`

---

## 🏗️ Arquitetura

### Componentes Criados

```
src/
├── environments/
│   └── trading_env.py         # Ambiente de treinamento customizado
├── agents/
│   └── drl_agent.py           # Agente DDQN com replay buffer
├── strategies/
│   └── drl_strategy.py        # Interface de inferência (herda BaseStrategy)

train_drl_model.py              # Script de treinamento principal
```

### Fluxo de Dados

```
TREINAMENTO:
configs/main.yaml → TradingEnv → MetaTraderProvider → Dados Históricos
                       ↓
                   DDQNAgent (DDQN) → Treina Q-Network
                       ↓
                   Modelo Salvo (models/WDO$_DRL_prod_drl.keras)

INFERÊNCIA:
SimulationEngine → DRLStrategy.load() → Q-Network
       ↓
Estado (market_features + position) → Q-Network → Ação (0/1/2)
       ↓
SetupAnalyzer (opcional) → Decisão Final
```

---

## 🎯 Como Funciona

### 1. Ambiente de Trading (`TradingEnv`)

O ambiente **não** herda de `gym.Env` (customizado para nosso projeto).

#### Estado (State)
```python
State = [market_features, position_feature]
```
- **Market features** (9 dimensões):
  - `log_return`, `log_return_5`, `log_return_10`, `log_return_20`
  - `log_volume_change`
  - `volatility_10`, `volatility_20`
  - `price_percentile_20`
  - `rsi`

- **Position feature** (3 dimensões, one-hot):
  - `[1,0,0]` = Venda (short)
  - `[0,1,0]` = Hold (cash)
  - `[0,0,1]` = Compra (long)

**Total: 12 dimensões**

#### Ações (Actions)
- `0`: VENDA (short)
- `1`: HOLD (neutro)
- `2`: COMPRA (long)

#### Recompensa (Reward)
Baseada em **log returns do portfólio** (FinancialTradingasaGameDRL.pdf):

```python
PnL = (preço_atual - preço_anterior) / preço_anterior  # Ajustado por posição
Custo = transaction_cost_pct se mudou posição
Reward = log( (1 + PnL - Custo) )
```

---

### 2. Agente DDQN (`DDQNAgent`)

Implementa **Double Deep Q-Learning** com:
- **Online Network**: Atualizada a cada step
- **Target Network**: Atualizada a cada `tau` steps (estabilidade)
- **Replay Buffer**: Armazena até 1M experiências
- **Epsilon-Greedy**: Exploração decai de 1.0 → 0.01

#### Arquitetura da Q-Network
```
Input (state_dim=12) 
    → Dense(256, relu) 
    → Dense(256, relu) 
    → Dropout(0.1)
    → Output(3)  # Q-values para cada ação
```

---

### 3. Estratégia DRL (`DRLStrategy`)

Implementa a interface `BaseStrategy` para compatibilidade com o engine:

```python
# Carregamento (usado por SimulationEngine)
model = DRLStrategy.load("models/WDO$_DRL_prod")

# Inferência (engine constrói o estado internamente)
q_values = model.predict(state_vector)
action = np.argmax(q_values)  # 0, 1, ou 2
```

**Diferencial**: O `SimulationEngine` rastreia a posição atual (`self.asset_positions`) para construir o `position_feature` corretamente a cada ciclo.

---

## 🚀 Guia de Uso

### Passo 1: Configuração

Adicione a estratégia DRL ao seu ativo em `configs/main.yaml`:

```yaml
assets:
  - ticker: "WDO$"
    enabled: true
    
    strategies:
      # Estratégia LSTM (tradicional)
      - name: "LSTMStrategy"
        module: "lstm"
        provider: "MetaTrader5"
        data:
          start_date: "2023-01-01"
          end_date: "2025-10-31"
          timeframe_model: "D1"
        training_trading_rules:
          initial_capital: 5000
          stop_loss_pct: 0.01
          take_profit_pct: 0.03
      
      # Estratégia DRL (nova!)
      - name: "DRLStrategy"
        module: "drl_strategy"
        provider: "MetaTrader5"
        data:
          start_date: "2023-01-01"
          end_date: "2025-10-31"
          timeframe_model: "D1"
        training_trading_rules:
          initial_capital: 5000
          stop_loss_pct: 0.01  # Usado como custo de transação no ambiente
          take_profit_pct: 0.03
    
    # Regras gerais de live trading (aplicadas a todas as estratégias)
    trading_rules:
      initial_capital: 5000
      stop_loss_ticks: 20
      stop_loss_pct: 0.01
      take_profit_pct: 0.03
    
    live_trading:
      enabled: false  # Habilite após testes
      ticker_order: "WDOX25"
      timeframe_str: "M5"
      execution_mode: "suggest"
      trade_volume: 1.0
    
    setup: []  # DRL não usa setups de TA (opcional)
```

**Nota**: Cada ticker pode ter **múltiplas estratégias**. A primeira estratégia da lista é usada para live trading.

### Passo 2: Treinamento

Execute o script de treinamento:

```powershell
poetry run python train_drl_model.py
```

O script irá:
1. Listar ativos disponíveis no config
2. Pedir o ticker (ex: `WDO$_DRL`)
3. Pedir número de episódios (default: 1000)
4. Treinar o agente DDQN
5. Salvar o modelo em `models/WDO$_DRL_prod_drl.keras`

**Exemplo de saída**:
```
Episode  100/1000 | Reward(100):  -0.0234 | Reward(10):  -0.0189 | Epsilon: 0.6000
Episode  200/1000 | Reward(100):  -0.0112 | Reward(10):   0.0045 | Epsilon: 0.2000
Episode  500/1000 | Reward(100):   0.0231 | Reward(10):   0.0412 | Epsilon: 0.0100
```

**⏱️ Tempo estimado**: ~10-30 minutos (depende do hardware e número de episódios)

### Passo 3: Teste (Simulação)

Use o `SimulationEngine` para testar o modelo treinado:

```python
# Em um notebook ou script
from src.simulation.engine import SimulationEngine
from datetime import datetime

engine = SimulationEngine()

result = engine.run_simulation_cycle(
    asset_symbol="WDO$",
    strategy_name="DRLStrategy",  # Especifica qual estratégia usar
    timeframe_str="D1",
    target_datetime_local=datetime(2025, 10, 15, 12, 0)
)

print(result)
# {
#   'ai_signal': 'COMPRA',
#   'ai_signal_code': 2,
#   'setup_valid': True,
#   'final_decision': 'COMPRA',
#   'current_price': 123456.0,
#   ...
# }
```

**Ou use o notebook existente**:
- `notebooks/simulation/engine_simulation_single_cycle.ipynb`

### Passo 4: Live Trading (Opcional)

Configure `live_trading.enabled: true` no config e execute:

```powershell
poetry run python src/live_trader.py
```

⚠️ **ATENÇÃO**: Teste EXTENSIVAMENTE em modo `suggest` antes de usar `execute`!

---

## 📊 Monitoramento e Métricas

Durante o treinamento, o agente registra:
- **Recompensa por episódio**: `agent.rewards_history`
- **Epsilon (exploração)**: `agent.epsilon_history`
- **Loss da Q-Network**: `agent.losses`
- **Steps por episódio**: `agent.steps_per_episode`

Você pode estender `train_drl_model.py` para salvar essas métricas em CSV ou usar TensorBoard.

---

## 🔧 Hiperparâmetros

Hiperparâmetros padrão (ajustáveis em `train_drl_model.py`):

```python
{
    'learning_rate': 0.0001,
    'gamma': 0.99,                      # Fator de desconto
    'epsilon_start': 1.0,
    'epsilon_end': 0.01,
    'epsilon_decay_steps': 250,         # Episódios para decay linear
    'epsilon_exponential_decay': 0.99,
    'replay_capacity': 1_000_000,
    'architecture': (256, 256),         # Camadas ocultas
    'l2_reg': 1e-6,
    'tau': 100,                         # Target network update freq
    'batch_size': 4096
}
```

### Dicas de Ajuste
- **Overfitting**: Aumente `l2_reg`, reduza `architecture`
- **Underfitting**: Aumente `architecture`, `num_episodes`
- **Exploração insuficiente**: Aumente `epsilon_decay_steps`
- **Instabilidade**: Reduza `learning_rate`, aumente `tau`

---

## 🧪 Extensões Possíveis

### 1. DRQN (Deep Recurrent Q-Network)
Adicione camadas LSTM à Q-Network para memória temporal:

```python
# Em drl_agent.py
from tensorflow.keras.layers import LSTM

layers.append(LSTM(128, return_sequences=False))
```

Ajuste `TradingEnv` para retornar sequências de estados.

### 2. Prioritized Experience Replay
Priorize experiências com maior TD-error:

```python
# Em ReplayBuffer
def sample(self, batch_size):
    priorities = np.abs(self.td_errors) + 1e-6
    probs = priorities / priorities.sum()
    indices = np.random.choice(len(self), batch_size, p=probs)
    ...
```

### 3. Multi-Asset DRL
Treine um único agente para múltiplos ativos:
- Adicione `asset_id` ao estado
- Compartilhe Q-Network entre ativos

### 4. Dueling DQN
Separe value e advantage streams na Q-Network:

```python
# Camada de saída dupla
value = Dense(1)(x)
advantage = Dense(num_actions)(x)
q_values = value + (advantage - tf.reduce_mean(advantage))
```

---

## 🐛 Troubleshooting

### Problema: "Modelo DRL não encontrado"
**Solução**: Execute `train_drl_model.py` primeiro.

### Problema: Recompensas sempre negativas
**Causas**:
- Custos de transação muito altos (`stop_loss_pct`)
- Epsilon muito alto (ainda explorando)
- Dados insuficientes

**Solução**: Reduza `stop_loss_pct`, aumente episódios de treino.

### Problema: "KeyError: 'WDO$_DRL'"
**Solução**: Verifique se o ticker está em `configs/main.yaml` e `enabled: true`.

### Problema: Q-values explodem (NaN/Inf)
**Causas**: Learning rate muito alto, gradientes explodem

**Solução**: 
- Reduza `learning_rate` (ex: 0.00001)
- Adicione gradient clipping:
```python
optimizer = Adam(learning_rate=lr, clipnorm=1.0)
```

---

## 📚 Referências

1. **FinancialTradingasaGameDRL.pdf**: Framework teórico (State, Reward, log returns)
2. **04_q_learning_for_trading.ipynb**: Implementação base do DDQN
3. **Playing Atari with Deep Reinforcement Learning** (Mnih et al., 2013): DQN original
4. **Human-level control through deep RL** (Mnih et al., 2015): Target network
5. **Deep Reinforcement Learning with Double Q-learning** (van Hasselt, 2015): DDQN

---

## ✅ Checklist de Validação

Antes de usar em produção:

- [ ] Modelo treinado em pelo menos 1000 episódios
- [ ] Recompensa média positiva nos últimos 100 episódios
- [ ] Testado em `SimulationEngine` com dados out-of-sample
- [ ] Comparado com estratégia buy-and-hold
- [ ] Verificado em diferentes condições de mercado (alta, baixa, lateral)
- [ ] Testado em modo `suggest` por pelo menos 1 semana
- [ ] Documentado hiperparâmetros e resultados de treino

---

## 🤝 Contribuindo

Para adicionar melhorias ao módulo DRL:

1. Implemente a feature em `src/agents/` ou `src/environments/`
2. Mantenha compatibilidade com `BaseStrategy`
3. Atualize este README
4. Adicione testes em `tests/`

---

## 📧 Contato

Para dúvidas sobre a integração DRL, consulte:
- `README.md` principal do projeto
- `.github/copilot-instructions.md`
- Issues no repositório

---

**Status**: ✅ Produção | **Versão**: 1.0 | **Data**: 2025-11-07
