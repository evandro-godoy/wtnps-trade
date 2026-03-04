# ISSUE: Fullstack - Slice 3 (UI Frequency Selector)

## Contexto
No Slice 3, o utilizador deve escolher a densidade de atualizacao recebida no monitor em tempo real.

## Objetivo
Adicionar seletor de frequencia na UI e enviar preferencia ao backend via WebSocket.

## Requisitos Obrigatorios
1. Adicionar um controlo na interface (`monitor.html`), como dropdown ou radio buttons, para os modos:
   - `Em Tempo Real (Tick)`
   - `Fecho de Vela (Close)`
   - `Hibrido`
2. Atualizar `monitor.js` para enviar a preferencia ao backend via WebSocket:
   - ao estabelecer conexao, e/ou
   - ao alterar opcao na UI.
   - Exemplo de mensagem: `{ "action": "set_frequency", "mode": "hybrid" }`.

## Regras de UX/Contrato
- A selecao deve ter estado visual claro (modo ativo).
- A mudanca de modo deve ser aplicada sem recarregar pagina.
- Em reconexao de WS, reenviar preferencia atual automaticamente.
- Manter compatibilidade com payload canonico existente (nao quebrar render atual).

## Criterios de Aceite
- Usuario consegue alternar entre `tick`, `close` e `hybrid` na tela.
- `monitor.js` envia mensagem de configuracao com `action=set_frequency` e `mode` valido.
- Estado de UI permanece consistente apos reconnect.
- Sem regressao visual no monitor.

## Entregaveis
- Ajustes em `monitor.html` e `monitor.js`.
- Validacao manual guiada (passos de teste no PR).
- Se houver testes frontend, incluir cobertura da troca de modo.

## Regra de PR (Obrigatoria)
Todos os commits e PRs desta issue devem apontar exclusivamente para a branch:
`feature/monitor-slice-3-frequency`
