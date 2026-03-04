# [FULLSTACK] Slice 1 — Template Inheritance (base.html) + Monitor WS Passivo

**Assignee:** @Fullstack  
**Labels:** `frontend`, `fullstack`, `jinja2`, `websocket`, `monitor`, `priority:high`, `slice-1`  
**Milestone sugerido:** Slice 1 — Fundação do Monitor em Tempo Real

> **Instrução de integração (obrigatória):** Todos os commits e Pull Requests desta tarefa devem ter como alvo a branch `feature/monitor-slice-1` e **NÃO** a `main`.

---

## 📋 Contexto
`monitor.html` e `charts.html` repetem estrutura comum de layout (especialmente sidebar), o que dificulta manutenção. Em paralelo, `monitor.js` ainda contém responsabilidades de controle de motor que não pertencem à camada de UI no modelo Always-On.

---

## 🎯 Objetivo
Implementar a fundação frontend do Slice 1 com:
1. **Herança de templates Jinja2** via `base.html`.
2. Extração dos componentes repetidos (sidebar/layout shell) para o template base.
3. Ajuste do `monitor.js` para consumo passivo do WebSocket (somente ouvir/renderizar dados).

---

## 📁 Arquivos-alvo
- `newapp/templates/base.html` (novo)
- `newapp/templates/monitor.html`
- `newapp/templates/charts.html`
- `newapp/static/js/monitor.js`
- `newapp/static/css/*` (somente se necessário para preservar layout após herança)

---

## 🔧 Tarefas
- [ ] Criar `base.html` com blocos Jinja2 (`title`, `content`, `scripts`) e layout compartilhado.
- [ ] Extrair sidebar de `monitor.html` e `charts.html` para `base.html`.
- [ ] Atualizar `monitor.html` e `charts.html` para usar `{% extends 'base.html' %}` e manter apenas conteúdo específico.
- [ ] Revisar imports de CSS/JS para evitar duplicação e regressão visual.
- [ ] Refatorar `monitor.js` para conexão WS passiva:
  - abre conexão;
  - escuta mensagens;
  - atualiza UI;
  - remove chamadas que iniciam/paralisam motor no backend.
- [ ] Garantir compatibilidade com reconexão WS sem gatilho de start de engine.

---

## ✅ Critérios de aceite
- [ ] `base.html` centraliza sidebar e estrutura compartilhada entre telas.
- [ ] `monitor.html` e `charts.html` derivam de `base.html` sem duplicar shell de layout.
- [ ] `monitor.js` não chama endpoint/ação para iniciar ou parar monitor no backend.
- [ ] Monitor continua recebendo e renderizando stream WS em tempo real.
- [ ] Sem regressão de navegação visual entre páginas.

---

## 🧪 Validação manual mínima
- [ ] Navegar entre `/monitor` e `/charts` e validar consistência do menu lateral.
- [ ] Abrir `/monitor` com backend rodando e confirmar atualização por mensagens WS.
- [ ] Conferir console browser sem erros de template/script duplicado.

---

## 🔗 Referências
- `.memory-bank/systemPatterns.md` (Template Inheritance + fluxo WS)
- `.memory-bank/activeContext.md` (Slice 1 Fundação)
- `newapp/INTERFACE_README.md`
