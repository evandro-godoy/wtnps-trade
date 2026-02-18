# 🔧 Prompt DEVOPS - CI/CD & Infraestrutura Sprint 3

**Agent:** DEVOPS  
**Escopo:** Validar CI na `main` + Hardening do pipeline  
**Prazo:** 1-2 dias  
**Status:** CI green na `main`

---

## 📋 Missão

Validar que o CI permanece green na `main`, revisar pipeline por regressões e garantir monitoramento contínuo durante a Fase 3.3.

---

## 🎯 Tarefas Específicas

### Task 1: Verificar CI na main
**Objetivo:** Confirmar status green e registrar evidência do workflow atual  
**Entrada:** Workflow logs da `main`  
**Saída:** Registro do status atual e pontos de atenção

**Passo a passo:**
1. Revisar o último workflow do CI na branch `main`
2. Confirmar que todos os jobs passaram (tests, lint, type)
3. Registrar logs e anotar qualquer warning recorrente

### Task 2: Hardening do pipeline
**Objetivo:** Prevenir regressões e garantir consistência do ambiente  
**Entrada:** Configs de workflow e dependencias  
**Saída:** Ajustes de robustez (se necessarios)

**Passo a passo:**
1. Validar o workflow atual (.github/workflows/ci.yml)
2. Checar versoes de Python e dependencias em `pyproject.toml`
3. Se necessario, propor ajustes leves (cache, timeouts, pin de deps)

### Task 3: Monitoramento continuo
**Objetivo:** Garantir estabilidade do CI durante a execucao da Fase 3.3  
**Entrada:** Status do GitHub Actions na `main`  
**Saída:** Alerta rapido se houver regressao

**Passo a passo:**
1. Monitorar os proximos runs do CI na `main`
2. Validar que todos os checks continuam green
3. Alertar a squad caso haja falha

---

## 🛡️ Infraestrutura Relacionada

### Arquivo crítico:
- [.github/workflows/]() → buscar workflow YAML (pytest, lint, type-check)
- [pyproject.toml](../../pyproject.toml) → verify dependencies installed
- [tests/](../../tests/) → verify test discovery works

### Configuração esperada:
```yaml
# .github/workflows/test.yml (esperado)
- name: Run Tests
  run: poetry run pytest tests/ -v
```

---

## 🔄 Dependências Downstream

| Agente | Tarefa | Bloqueia? |
|--------|--------|-----------|
| FULLSTACK | Phase 3.3 Testing | **NÃO** (paralelo) |
| PLAN | Roadmap | Não (info context) |
| Guardian | QA Audit | Não (usa outputs) |

**Não aguarde DEVOPS para iniciar testes Fase 3.3.** Os workstreams rodam paralelo.

---

## ✅ Critérios de Aceitação

- [ ] CI confirmado green na `main`
- [ ] Logs e warnings registrados
- [ ] Ajustes de robustez propostos (se necessario)
- [ ] Monitoramento continuo estabelecido

---

## 📌 Referências

- Branch: `main`
- Copilot Instructions: [.github/copilot-instructions.md](../../.github/copilot-instructions.md)
- Mestre Orchestration: `plan-masterOrchestration.prompt.md`

---

**Próximo:** Após CI ✅, comunicar PLAN para context. Não aguarde; FULLSTACK começa testes em paralelo.
