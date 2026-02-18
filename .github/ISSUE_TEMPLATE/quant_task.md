---
name: '📈 Tarefa QUANT'
about: Lógica financeira, modelos de ML e análise de dados
title: "[QUANT] Modelar: <Nome da Estratégia/Análise>"
labels: 'agent:quant, domain:strategy'
assignees: ''
---

## 🎯 Objetivo Científico
## 📂 Contexto & Dados
- **Entrada:** `src/events.py` (Protocolo)
- **Modelos:** `models/` (Caminho dos artefatos)
- **Legado:** `src/strategies/...` (Para referência matemática)

## 🧠 Diretrizes (Perfil QUANT)
1. **Performance:** Vetorize cálculos com `numpy`/`pandas`.
2. **Pureza:** Não crie GUI. Seu output é sempre um `Event` ou um `DataFrame`.
3. **Validação:** Inclua sanity-checks (ex: preços negativos não existem).

## 🤝 Report ao PLAN/Scrum Master
- **Complexidade Estimada:** (Baixa/Média/Alta)
- **Risco:** (Ex: Overfitting, falta de dados)

## 📦 Definition of Done (DoD)
- [ ] Lógica implementada em `src/modules/strategy/`.
- [ ] Teste unitário com dados sintéticos (`tests/unit/`).
- [ ] Validação estatística básica (logs de métricas).