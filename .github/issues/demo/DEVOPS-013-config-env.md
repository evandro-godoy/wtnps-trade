---
name: [DEVOPS] Configuração de Ambiente Demo
about: Preparar arquivos de configuração e launch para a demonstração.
title: "[OPS] Setup de Configuração (main.yaml) e Launch.json"
labels: devops, config, vscode
assignees: devops-agent
---

**Contexto:**
A demonstração segue um roteiro estrito que depende da ordem dos ativos e da execução correta via IDE.

**Tarefas:**
- [ ] Editar `configs/main.yaml`:
  - Garantir que a lista `tickers` comece com `WDO$` (ou o contrato atual `WDOJ26` conforme necessidade do MT5).
  - Verificar configurações de conexão MT5.
- [ ] Atualizar `.vscode/launch.json`:
  - Criar uma configuração "Python: Demo Start" que execute `src/main.py`.
  - Definir variáveis de ambiente necessárias (ex: `PYTHONPATH=.`).
- [ ] Validar dependências no `poetry.lock` para garantir que `uvicorn`, `fastapi` e `jinja2` estejam instalados.

**Critério de Aceite:**
Pressionar F5 no VS Code inicia a aplicação sem erros de "ModuleNotFoundError" e conecta ao MT5 configurado.