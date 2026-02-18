---
name: [ARCHITECT] Orquestração da Demo (API + Monitor)
about: Configurar o entrypoint para servir a UI e rodar o motor de análise simultaneamente.
title: "[DEMO] Configurar src/main.py para Demo Híbrida"
labels: architect, core, demo
assignees: architect-agent
---

**Contexto:**
Para a demonstração, precisamos que a execução via VS Code levante tanto o servidor Web (para exibir a UI) quanto o motor de monitoramento (para gerar os sinais).

**Requisitos do Roteiro:**
1. Execução via VS Code (`.vscode/launch.json`).
2. O sistema deve iniciar e servir as rotas `/` (Home) e `/charts` (Gráfico).

**Tarefas:**
- [ ] Refatorar `src/main.py` para usar `uvicorn.run` apontando para `src.api.main:app`.
- [ ] Garantir que o `MonitorEngine` seja instanciado em uma *background task* ou thread separada ao iniciar a API, para não bloquear o servidor.
- [ ] Verificar se as rotas em `src/api/main.py` estão mapeadas corretamente para renderizar os templates `home.html` e `charts_clean.html`.

**Critério de Aceite:**
Ao rodar o Debugger do VS Code, o terminal mostra o log do Uvicorn e o log do MonitorEngine (conectado ao MT5) simultaneamente.