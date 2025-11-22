# Análise de Contexto Técnico - MarketContextAnalyzer

## Visão Geral

O `MarketContextAnalyzer` é um módulo de análise técnica clássica que enriquece os sinais de Machine Learning (LSTM) com contexto de mercado, fornecendo:

- ✅ Direção e força da tendência
- ✅ Níveis de suporte e resistência
- ✅ Condição de RSI (sobrecomprado/sobrevendido)
- ✅ Padrões de price action
- ✅ Validação automática de sinais

---

## Arquitetura

### Arquivos Criados/Modificados

```
src/
├── analysis/
│   ├── __init__.py (NOVO)
│   └── context_analyzer.py (NOVO)
└── live/
    └── monitor_engine.py (MODIFICADO)

test_context_analyzer.py (NOVO)
```

---

## Classe: `MarketContextAnalyzer`

### Inicialização

```python
from src.analysis.context_analyzer import MarketContextAnalyzer

analyzer = MarketContextAnalyzer(
    ema_fast=9,          # Período da EMA rápida
    sma_fast=20          # Período da SMA rápida
    sma_slow=50,         # Período da SMA lenta
    rsi_period=14,       # Período do RSI
    lookback_levels=20,  # Períodos para suporte/resistência
    strong_candle_threshold=0.7  # % mínimo para candle forte
)
```

### Método Principal: `analyze(df)`

Executa análise técnica completa sobre um DataFrame OHLCV.

**Entrada:**
```python
df: pd.DataFrame  # Index: datetime, Columns: open, high, low, close, volume
```

**Saída:**
```python
{
    'trend': 'ALTA',                    # ALTA | BAIXA | LATERAL
    'trend_strength': 'FORTE',          # FORTE | MODERADA | FRACA
    'rsi': 65.5,                        # Valor do RSI
    'rsi_condition': 'NEUTRO',          # SOBRECOMPRADO | SOBREVENDIDO | NEUTRO
    'support': 125350.0,                # Suporte (mínima dos últimos N períodos)
    'resistance': 125680.0,             # Resistência (máxima dos últimos N períodos)
    'distance_to_support': 0.32,        # % de distância ao suporte
    'distance_to_resistance': 0.18,     # % de distância à resistência
    'pattern': 'BARRA_FORTE_ALTA',      # Padrão do último candle
    'ema_fast': 125500.0,               # EMA(9)
    'sma_slow': 125450.0,               # SMA(50)
    'current_price': 125520.0           # Preço atual
}
```

---

## Indicadores Implementados

### 1. Tendência Primária

**Critérios:**
- **ALTA:** EMA(9) > SMA(50) **E** Preço > EMA(9)
- **BAIXA:** EMA(9) < SMA(50) **E** Preço < EMA(9)
- **LATERAL:** Condições mistas

**Força da Tendência:**
- **FORTE:** Inclinação da SMA(50) > 1.0%
- **MODERADA:** Inclinação entre 0.3% e 1.0%
- **FRACA:** Inclinação < 0.3% ou tendência LATERAL

### 2. Força do Mercado (RSI)

**Indicador:** RSI(14) - Relative Strength Index

**Condições:**
- **SOBRECOMPRADO:** RSI > 70
- **SOBREVENDIDO:** RSI < 30
- **NEUTRO:** 30 ≤ RSI ≤ 70

### 3. Níveis de Suporte e Resistência

**Cálculo:**
- **Suporte:** Mínima dos últimos 20 períodos
- **Resistência:** Máxima dos últimos 20 períodos

**Distâncias:**
- Calculadas em % do preço atual
- Positivo = acima, Negativo = abaixo

### 4. Price Action - Padrões de Candle

**Padrões Detectados:**

| Padrão | Critério | Significado |
|--------|----------|-------------|
| `BARRA_FORTE_ALTA` | Corpo > 70% do range, Close > Open | Alta forte |
| `BARRA_FORTE_BAIXA` | Corpo > 70% do range, Close < Open | Baixa forte |
| `REJEICAO_ALTA` | Sombra superior > 60% do range | Rejeição de alta |
| `REJEICAO_BAIXA` | Sombra inferior > 60% do range | Rejeição de baixa |
| `NEUTRO` | Nenhum padrão claro | Indecisão |

---

## Validação de Sinais

### Método: `validate_signal(ml_direction, context, require_trend_alignment)`

Valida se um sinal de ML está alinhado com o contexto técnico.

**Parâmetros:**
```python
ml_direction: str              # 'CALL' ou 'PUT'
context: dict                  # Retorno de analyze()
require_trend_alignment: bool  # True = exige alinhamento de tendência
```

**Retorno:**
```python
(valid: bool, reason: str)
# Ex: (True, "Tendência alinhada | RSI NEUTRO")
# Ex: (False, "Sinal de CALL mas RSI está SOBRECOMPRADO")
```

**Regras de Validação:**

1. **Alinhamento de Tendência** (se `require_trend_alignment=True`):
   - CALL exige tendência ALTA
   - PUT exige tendência BAIXA

2. **RSI - Zona Extrema Contrária:**
   - ❌ CALL com RSI SOBRECOMPRADO
   - ❌ PUT com RSI SOBREVENDIDO

3. **Price Action - Rejeição Contrária:**
   - ❌ CALL com REJEICAO_ALTA
   - ❌ PUT com REJEICAO_BAIXA

---

## Integração no Monitor

### Fluxo de Processamento

```
1. LSTM gera probabilidade de volatilidade
   ↓
2. Determina direção (CALL/PUT) via EMA(20)
   ↓
3. MarketContextAnalyzer.analyze(buffer_df)
   ↓
4. validate_signal(direction, context)
   ↓
5. Enriquece alerta com contexto técnico
   ↓
6. Envia para UI com informações completas
```

### Exemplo de Alerta Enriquecido

**Antes:**
```
🚨 ALERTA DE VOLATILIDADE - CALL
Probabilidade: 78%
```

**Depois:**
```
✅ SINAL CALL (78.5%) | Tendência: ALTA (FORTE) | Padrão: BARRA_FORTE_ALTA | Alvo: 125680.00
```

### Dados Enviados para UI

```python
{
    'timestamp': datetime,
    'open': 125400.0,
    'high': 125550.0,
    'low': 125380.0,
    'close': 125520.0,
    'volume': 1500,
    'probability': 78.5,
    'direction': 'CALL',
    'ema_20': 125450.0,
    
    # Contexto técnico (NOVO)
    'trend': 'ALTA',
    'trend_strength': 'FORTE',
    'rsi': 65.5,
    'rsi_condition': 'NEUTRO',
    'support': 125350.0,
    'resistance': 125680.0,
    'pattern': 'BARRA_FORTE_ALTA',
    'signal_valid': True,
    'validation_reason': 'Tendência alinhada | RSI NEUTRO | Padrão: BARRA_FORTE_ALTA'
}
```

---

## Interface Gráfica Atualizada

### Colunas do Treeview

| Coluna | Descrição | Exemplo |
|--------|-----------|---------|
| Data/Hora (UTC) | Timestamp do candle | 21/11/2025 09:45:00 |
| Tipo | ALERT / INFO / TICK | ALERT |
| Preço | Preço de fechamento | R$ 125.520,00 |
| Prob. ML | Probabilidade LSTM | 78.5% |
| **Tendência** | **Direção e força** | **ALTA (F)** |
| **RSI** | **RSI com emoji** | **65 🔻** |
| Mensagem | Descrição enriquecida | ✅ SINAL CALL... |

### Emojis no RSI

- 🔺 (SOBRECOMPRADO) quando RSI > 70
- 🔻 (SOBREVENDIDO) quando RSI < 30
- Sem emoji quando NEUTRO

---

## Teste do Analisador

Execute o script de teste:

```powershell
poetry run python test_context_analyzer.py
```

**Exemplo de Saída:**

```
================================================================================
TESTE DO MARKET CONTEXT ANALYZER
================================================================================

1. Conectando ao MT5...
✅ MT5 conectado!

2. Buscando dados históricos do WDO$ (M5)...
✅ 200 candles carregados
   Período: 2025-11-13 12:35:00+00:00 até 2025-11-21 09:40:00+00:00

3. Inicializando MarketContextAnalyzer...
✅ Analisador inicializado!

4. Executando análise técnica completa...

================================================================================
RESULTADO DA ANÁLISE
================================================================================

📊 PREÇO ATUAL: R$ 125.520,00

📈 TENDÊNCIA
   Direção: ALTA
   Força: FORTE
   EMA(9): 125500.00
   SMA(50): 125450.00

💪 FORÇA DO MERCADO
   RSI(14): 65.50
   Condição: NEUTRO

🎯 NÍVEIS CHAVE (Últimos 20 períodos)
   Suporte: R$ 125.350,00
   Resistência: R$ 125.680,00
   Distância do Suporte: 0.32%
   Distância da Resistência: 0.18%

🕯️ PRICE ACTION
   Padrão: BARRA_FORTE_ALTA

================================================================================
TESTE DE VALIDAÇÃO DE SINAIS
================================================================================

🔼 SINAL DE CALL:
   Válido: ✅ SIM
   Razão: RSI NEUTRO | Padrão: BARRA_FORTE_ALTA

🔽 SINAL DE PUT:
   Válido: ❌ NÃO
   Razão: Sinal de PUT mas há REJEIÇÃO da BAIXA
```

---

## Uso no Monitor em Tempo Real

O `MarketContextAnalyzer` já está integrado automaticamente no `RealTimeMonitor`.

**Execute:**
```powershell
poetry run python run_monitor_gui.py
```

**Comportamento:**
1. Monitor inicializa o analisador
2. A cada candle processado, executa análise técnica
3. Valida sinais de ML contra contexto
4. Enriquece alertas com informações técnicas
5. Exibe na UI com colunas de Tendência e RSI

---

## Configuração Avançada

### Ajustar Parâmetros do Analisador

Edite `src/live/monitor_engine.py`:

```python
self.context_analyzer = MarketContextAnalyzer(
    ema_fast=9,          # Altere para 13 para tendência mais suave
    sma_slow=50,         # Altere para 200 para tendência de longo prazo
    rsi_period=14,       # Altere para 9 para RSI mais sensível
    lookback_levels=20,  # Altere para 50 para níveis mais amplos
)
```

### Ativar Validação Estrita

No `_process_new_candle`, altere:

```python
signal_valid, validation_reason = self.context_analyzer.validate_signal(
    ml_direction=direction,
    context=context,
    require_trend_alignment=True  # Exige alinhamento de tendência
)
```

**Efeito:** Apenas alertas com tendência alinhada serão marcados como válidos.

---

## Logs Enriquecidos

### Console - Alerta Crítico

```
🚨 ALERTA DE VOLATILIDADE 🚨 | 
Hora: 2025-11-21 09:45:00 | 
Probabilidade: 78.50% | 
Direção: CALL | 
Preço: 125520.00 | 
Tendência: ALTA (FORTE) | 
RSI: 65 (NEUTRO) | 
Padrão: BARRA_FORTE_ALTA | 
Suporte: 125350.00 | 
Resistência: 125680.00 | 
Alvo: 125680.00 | 
Status: VALIDADO
```

### Console - Log Informativo

```
📊 Probabilidade Moderada | 
Hora: 2025-11-21 09:50:00 | 
Probabilidade: 62.30% | 
Preço: 125490.00 | 
Tendência: ALTA | 
RSI: 58
```

---

## Próximos Passos / Melhorias Futuras

### Curto Prazo
- [ ] Adicionar ADX para força de tendência
- [ ] Implementar detecção de divergências RSI
- [ ] Adicionar Bandas de Bollinger

### Médio Prazo
- [ ] Padrões de candlestick compostos (Doji, Engolfo, etc.)
- [ ] Suporte/Resistência por Volume Profile
- [ ] Fibonacci automático

### Longo Prazo
- [ ] Machine Learning para padrões de price action
- [ ] Correlação entre múltiplos ativos
- [ ] Backtesting com análise técnica

---

## Troubleshooting

### Problema: Análise retorna "INDEFINIDO"

**Causa:** DataFrame com dados insuficientes (< 50 períodos para SMA(50))

**Solução:** Aumente `buffer_size` no monitor para pelo menos 100 candles

### Problema: Todos sinais marcados como "NÃO VALIDADO"

**Causa:** `require_trend_alignment=True` e mercado lateral

**Solução:** Use `require_trend_alignment=False` para alertas informativos

### Problema: RSI sempre em NEUTRO

**Causa:** RSI precisa de pelo menos 14 períodos + warm-up

**Solução:** Verifique se buffer tem pelo menos 30 candles

---

## Referências

- **RSI:** Desenvolvido por J. Welles Wilder Jr. (1978)
- **EMA/SMA:** Médias móveis clássicas de análise técnica
- **Price Action:** Conceitos de Steve Nison e Al Brooks

---

**Desenvolvido para:** WTNPS-TRADE  
**Versão:** 1.0  
**Data:** Novembro 2025
