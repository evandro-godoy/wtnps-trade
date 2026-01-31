---
name: '🏛️ Tarefa ARCHITECT'
about: Desenvolvimento de infraestrutura, core e refatoração estrutural
title: "[ARCHITECT] Implementar: <Nome do Componente>"
labels: 'agent:architect, domain:core'
assignees: ''
---

## 🎯 Objetivo
## 📂 Contexto & Arquivos
- **Alvo:** `src/core/` ou `src/modules/`
- **Dependências:** `src/core/event_bus.py`, `src/core/config.py`

## 🛠️ Especificações Técnicas
1. **Padrão de Projeto:** Singleton, Factory ou Adapter (especificar).
2. **Isolamento:** Garanta que este módulo não acople lógica de negócios indevida.
3. **Tipagem:** Python Type Hints estritos.

## 🔗 Dependências & Bloqueios
- [ ] O `EventBus` suporta esta funcionalidade?
- [ ] Configurações necessárias existem em `config.yaml`?

## 📦 Definition of Done (DoD)
- [ ] Código implementado e documentado (Docstrings).
- [ ] Sem violações de arquitetura (circular imports).
- [ ] Testes de integração básicos passando.