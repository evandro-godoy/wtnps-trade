# ISSUE: BackendQuant - Slice 3 (WebSocket Frequency Filter)

## Contexto
Slice 3 introduz controlo de fluxo por cliente na camada WebSocket. O `RealtimeMarketMonitor` permanece singleton e deve continuar a emitir no ritmo maximo.

## Objetivo
Implementar filtragem/throttling por sessao WebSocket com preferencia de frequencia por cliente.

## Requisitos Obrigatorios
1. Adicionar suporte na camada WebSocket (`monitor_ws.py` ou gestor de conexoes associado) para registar a preferencia de frequencia de cada sessao conectada.
2. Implementar modos de envio:
   - `tick`: envia todos os eventos recebidos do motor.
   - `close`: envia apenas quando a flag `is_closed` do candle for verdadeira.
   - `hybrid`: envia no fecho do candle OU a cada X segundos para evitar sobrecarga.
3. Garantir que o `RealtimeMarketMonitor` continua a processar e emitir dados na velocidade maxima, delegando a responsabilidade de "deixar passar" mensagens para o gestor de WebSockets por cliente.

## Regras Arquiteturais
- Nao mover throttling para o motor principal.
- Nao introduzir EventBus, microservicos ou brokers externos.
- Preservar contrato canonico de payload; apenas a politica de entrega muda por cliente.

## Criterios de Aceite
- Cliente A em `tick` recebe todos os eventos.
- Cliente B em `close` recebe apenas candles fechados.
- Cliente C em `hybrid` recebe fechamento e heartbeat periodico entre fechamentos.
- Reconexao nao reinicia motor singleton.
- Falha de um cliente nao impacta os outros.

## Entregaveis
- Codigo implementado no backend WS.
- Testes unitarios/integracao para politica por cliente.
- Logs minimos por modo (contagem enviada/descartada por janela).

## Regra de PR (Obrigatoria)
Todos os commits e PRs desta issue devem apontar exclusivamente para a branch:
`feature/monitor-slice-3-frequency`
