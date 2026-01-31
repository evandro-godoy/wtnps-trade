# [ARCHITECT] Injeção de Dependências no main.py

## 🎯 Objetivo
Atualizar main.py para usar MetaTraderProvider real (substituir loop de teste) e injetar via DI.

## 📂 Contexto & Arquivos
- **Alvo:** `src/main.py`
- **Dependências:** `src/data_handler/mt5_provider.py`, `src/core/config.py`, `.env`

## 🛠️ Especificações Técnicas
1. **Instanciar Provider:** `provider = MetaTraderProvider()` em `_load_modules()`
2. **Injetar no Sistema:** Conectar provider ao EventBus (publicação automática)
3. **Configuração .env:** Adicionar variáveis:
   - `MT5_PATH` (path do terminal.exe)
   - `MT5_LOGIN` (conta)
   - `MT5_SERVER` (broker)
4. **Remover Mock:** Eliminar loop de teste de candles falsos

## 🔗 Dependências & Bloqueios
- [ ] DATA-001 (MT5Provider) deve estar merged ✅
- [ ] `.env.example` criado com template

## 📦 Definition of Done (DoD)
- [ ] main.py usa provider real (0 mocks)
- [ ] `.env.example` criado e documentado
- [ ] Sistema inicia e processa candles reais
- [ ] Logs mostram "Conectado ao MT5" ao startup
- [ ] README tem seção "Setup MT5"

## 📊 Estimativa
- **Story Points:** 8
- **Horas:** 10h
- **Prioridade:** 🔴 ALTA (depende de DATA-001)
