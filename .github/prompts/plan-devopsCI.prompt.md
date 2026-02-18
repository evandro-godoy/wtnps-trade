# 🔧 Prompt DEVOPS - CI/CD & Infraestrutura Sprint 3

**Agent:** DEVOPS  
**Escopo:** Resolver CI failure + Validar infraestrutura  
**Prazo:** 1-2 dias  
**Status:** Fase 3.3 bloqueada por CI ❌

---

## 📋 Missão

O PR feature/newapp-ui (#2) falha em CI test. Investigar root cause, resolver, validar merge-readiness. Garantir GitHub Actions pipeline está green antes de FULLSTACK executar testes Fase 3.3.

---

## 🎯 Tarefas Específicas

### Task 1: Investigar CI Failure
**Objetivo:** Identificar why test falhou, não é erro em código  
**Entrada:** PR #2 metadata + workflow logs  
**Saída:** Root cause document + fix recomendado

**Passo a passo:**
1. Acessar https://github.com/evandro-godoy/wtnps-trade/pull/2
2. Revisar "Checks" tab → ver qual test falhou (test job)
3. Coletar logs completos do workflow falho
4. Verificar se é:
   - Dependência não instalada (requirements.txt)?
   - Ambiente CI diferente (Python version, OS)?
   - Configuração fixtures (banco de dados, timeouts)?
   - Arquivo não staged (.gitignore)?

### Task 2: Fix + Validate Locally
**Objetivo:** Replicar falha local, aplicar fix, validar  
**Entrada:** Root cause + PR code  
**Saída:** Commit fixado, CI verde

**Passo a passo:**
1. Checkout PR branch localmente:
   ```bash
   git fetch origin feature/newapp-ui
   git checkout feature/newapp-ui
   ```
2. Replicar env pipeline (poetry install, test command)
3. Aplicar fix mínimo (pode ser .gitignore, requirements.txt, test config)
4. Validar:
   ```bash
   poetry run pytest tests/ -v
   ```
5. Push fix para PR branch

### Task 3: GitHub Actions Validation
**Objetivo:** Confirmar CI workflow rerun passa  
**Entrada:** Commit fixado + Actions config  
**Saída:** CI green ✅ + aprovação merge

**Passo a passo:**
1. No GitHub, trigger manual rerun de failed job
2. Monitorar workflow até complete
3. Validar ALL checks passam (tests, lint, type)
4. Documentar em PR comment: "CI resolved - ready for Fullstack testing"

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

- [ ] Root cause documentado (1-3 linhas explicativo)
- [ ] Fix aplicado + commited
- [ ] CI verde no PR (all checks passing)
- [ ] GitHub Actions workflow logs salvos em referência
- [ ] PR comment com "DEVOPS cleared for merge"

---

## 📌 Referências

- PR: https://github.com/evandro-godoy/wtnps-trade/pull/2
- Copilot Instructions: [.github/copilot-instructions.md](../../.github/copilot-instructions.md)
- Mestre Orchestration: `plan-masterOrchestration.prompt.md`

---

**Próximo:** Após CI ✅, comunicar PLAN para context. Não aguarde; FULLSTACK começa testes em paralelo.
