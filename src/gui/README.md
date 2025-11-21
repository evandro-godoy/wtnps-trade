# Interface Gráfica do Monitor em Tempo Real

## Visão Geral

Interface gráfica moderna construída com **tkinter** para controlar e visualizar o **RealTimeMonitor** do projeto wtnps-trade. Permite operar o monitor de forma amigável e acompanhar alertas de trading ML em tempo real.

## Arquitetura

### Componentes Principais

**1. MonitorApp (`src/gui/monitor_ui.py`)**
- Classe principal da GUI
- Gerencia interface, controles e exibição de dados
- Comunicação thread-safe via `queue.Queue`

**2. RealTimeMonitor Adaptado (`src/live/monitor_engine.py`)**
- Suporte a `ui_callback` para comunicação com GUI
- Controle via `self.running` (variável booleana)
- Método `stop()` para parada graciosa

**3. Thread Separation**
- **Main Thread**: GUI (tkinter) - responsividade
- **Background Thread**: Monitor - processamento de dados e ML

## Recursos da Interface

### 📊 Header (Informações do Ativo)

Exibe em destaque:
- **Ticker**: Símbolo do ativo (WDO$)
- **Preço Atual**: Atualizado em tempo real
- **Timeframe**: Período dos candles (M5)
- **Status**: Indicador visual (● PARADO / ● RODANDO)
  - Vermelho: Monitor parado
  - Verde: Monitor em execução

### 🎮 Controles

**Botão Start/Stop:**
- **Estado Inicial**: "▶ INICIAR MONITORAMENTO" (verde)
- **Estado Ativo**: "■ PARAR MONITORAMENTO" (vermelho)
- Toggle automático ao clicar

**Botão Limpar Logs:**
- Remove todos os eventos da tela
- Útil para reset visual

### 📋 Área de Logs e Alertas (Treeview)

**Colunas:**
| Coluna | Descrição | Formato |
|--------|-----------|---------|
| Data/Hora | Timestamp do evento | DD/MM/YYYY HH:MM:SS |
| Tipo | Classificação | TICK, INFO, ALERT |
| Preço | Cotação atual | R$ XXX.XXX,XX |
| Probabilidade ML | % do modelo | XX.XX% |
| Mensagem | Descrição do evento | Texto livre |

**Ordenação:**
- Eventos mais recentes aparecem **no topo**
- Auto-scroll para mostrar último evento
- Limite de 1000 eventos (remove antigos automaticamente)

**Destaque Visual (Tags):**
- 🟡 **ALERT**: Fundo amarelo - probabilidade > 65%
- 🔵 **INFO**: Fundo azul claro - probabilidade 55-65%
- ⚪ **TICK**: Fundo branco - candle processado (< 55%)

## Como Usar

### Pré-requisitos

1. **Modelo Treinado:**
   ```powershell
   poetry run python train_model.py
   ```

2. **MetaTrader 5:**
   - Terminal aberto
   - Logado no servidor
   - Conectado à internet

3. **Configuração:**
   - `configs/main.yaml` com asset WDO$ configurado

### Execução

```powershell
poetry run python run_monitor_gui.py
```

### Workflow

1. **Iniciar**: Clique em "▶ INICIAR MONITORAMENTO"
   - GUI inicializa o monitor em background
   - Status muda para "● RODANDO" (verde)
   - Warm-up: Carrega 500 candles históricos

2. **Monitorar**: Acompanhe eventos na tabela
   - **TICK**: Processamento normal de candles
   - **INFO**: Probabilidade moderada (55-65%)
   - **ALERT**: Oportunidade detectada (>65%)

3. **Parar**: Clique em "■ PARAR MONITORAMENTO"
   - Monitor para graciosamente
   - Thread encerrada
   - Status volta para "● PARADO" (vermelho)

4. **Fechar**: Clique no X da janela
   - Se monitor rodando: confirmação de parada
   - Encerramento limpo de recursos

## Integração Thread-Safe

### Arquitetura de Comunicação

```
┌─────────────────────┐         ┌──────────────────────┐
│  Background Thread  │         │    Main Thread       │
│  (Monitor Loop)     │         │    (GUI/Tkinter)     │
└──────────┬──────────┘         └──────────┬───────────┘
           │                               │
           │  Callback com data_dict       │
           ├──────────────────────────────>│
           │                               │
           │  Queue.put(event)             │
           │                               │
           │                     ┌─────────▼─────────┐
           │                     │  update_queue     │
           │                     │  (thread-safe)    │
           │                     └─────────┬─────────┘
           │                               │
           │                     Queue.get_nowait()
           │                               │
           │                     ┌─────────▼─────────┐
           │                     │  _poll_queue()    │
           │                     │  (root.after 100ms)│
           │                     └─────────┬─────────┘
           │                               │
           │                     Atualiza Widgets
           │                     (Treeview, Labels)
           │                               │
```

### Callback do Monitor

O monitor chama `ui_callback(data_dict)` a cada candle processado:

```python
{
    'type': 'ALERT',  # TICK, INFO ou ALERT
    'timestamp': datetime.now(),
    'price': 125680.00,
    'probability': 72.15,
    'direction': 'CALL',  # CALL ou PUT
    'ema_20': 125320.50,
    'message': '🚨 ALERTA DE VOLATILIDADE - CALL'
}
```

### Polling da Queue

Método `_poll_queue()` executa a cada 100ms via `root.after()`:
- Processa todos os eventos pendentes na queue
- Atualiza widgets de forma segura (main thread)
- Reagenda automaticamente

## Personalização

### Configurações Ajustáveis (em `monitor_ui.py`)

```python
class MonitorApp:
    def __init__(self, root):
        # Configurações do monitor
        self.ticker = "WDO$"              # Altere o ticker
        self.timeframe = "M5"             # M1, M5, M15, M30, H1, H4, D1
        self.threshold_alert = 0.65       # Limite para ALERTA (>65%)
        self.threshold_log = 0.55         # Limite para INFO (>55%)
        self.buffer_size = 500            # Candles históricos
```

### Estilos Visuais

Tema: **clam** (moderno)

Cores principais:
- **Botão Start**: Verde (#28a745)
- **Botão Stop**: Vermelho (#dc3545)
- **Status Rodando**: Verde (#28a745)
- **Status Parado**: Vermelho (#dc3545)
- **Ticker**: Azul (#007bff)
- **Preço**: Verde (#28a745)

## Exemplo de Sessão

```
14:30:05 - TICK processado - Preço: R$ 125.450,00 - Prob: 42.18%
14:35:05 - INFO - Probabilidade Moderada - Preço: R$ 125.520,00 - Prob: 58.34%
14:40:05 - TICK processado - Preço: R$ 125.490,00 - Prob: 48.92%
14:45:05 - ALERT - 🚨 ALERTA DE VOLATILIDADE - CALL - Preço: R$ 125.680,00 - Prob: 72.15%
14:50:05 - INFO - Probabilidade Moderada - Preço: R$ 125.710,00 - Prob: 61.23%
```

## Tratamento de Erros

### Erro ao Iniciar Monitor

**Sintomas:**
- MessageBox de erro ao clicar em "Iniciar"
- Monitor não inicia

**Causas comuns:**
1. MT5 não está aberto/logado
2. Modelo não treinado
3. Configuração inválida

**Soluções:**
1. Abra o MT5 e faça login
2. Execute `poetry run python train_model.py`
3. Valide `configs/main.yaml`

### Monitor Para Inesperadamente

**Sintomas:**
- Status volta para "PARADO"
- MessageBox de erro

**Causas:**
- Conexão MT5 perdida
- Erro no processamento de features
- Dados insuficientes

**Ação:**
- Verifique logs no console
- Reconecte MT5
- Reinicie o monitor

## Logs no Console

Mesmo com GUI, logs continuam no console para debug:

```
2025-11-21 14:30:00 - INFO - [monitor_engine] ✓ MT5 conectado com sucesso
2025-11-21 14:30:02 - INFO - [monitor_engine] ✓ Modelo carregado
2025-11-21 14:30:05 - INFO - [monitor_engine] WARM-UP: Buscando 500 velas...
2025-11-21 14:35:05 - CRITICAL - [monitor_engine] 🚨 ALERTA DE VOLATILIDADE 🚨
```

## Limitações Conhecidas

1. **Ticker Único**: Suporta apenas 1 ativo por vez
2. **Histórico**: Máximo 1000 eventos em memória
3. **Reconnect**: Manual (requer restart do monitor)
4. **Gráficos**: Não implementado (somente tabela)

## Próximas Melhorias

- [ ] Multi-ticker (monitor vários ativos simultaneamente)
- [ ] Gráficos em tempo real (candlestick + indicadores)
- [ ] Exportação de logs (CSV/Excel)
- [ ] Notificações sonoras para alertas
- [ ] Dashboard de estatísticas (win rate, drawdown)
- [ ] Configuração via GUI (sem editar código)
- [ ] Temas claro/escuro
- [ ] Integração com Telegram

## Arquivos Relacionados

```
wtnps-trade/
├── run_monitor_gui.py          # Script de execução da GUI
├── src/
│   ├── gui/
│   │   ├── __init__.py
│   │   └── monitor_ui.py       # Interface gráfica completa
│   └── live/
│       ├── monitor_engine.py   # Monitor adaptado com callbacks
│       └── README.md
└── configs/
    └── main.yaml               # Configuração
```

## Troubleshooting

### "Falha ao iniciar monitor"
**Solução**: Certifique-se que o MT5 está aberto, logado e conectado.

### "FileNotFoundError: models/..."
**Solução**: Execute `poetry run python train_model.py` antes.

### GUI não responde
**Causa**: Monitor travou na thread de background.
**Solução**: Feche a janela (forçado) e reinicie.

### Eventos não aparecem
**Causa**: Queue não está sendo processada.
**Debug**: Verifique logs no console para erros na `_poll_queue()`.

## Suporte

Para problemas ou dúvidas:
1. Consulte logs no console
2. Verifique `src/live/README.md` para detalhes do monitor
3. Revise configurações em `configs/main.yaml`
