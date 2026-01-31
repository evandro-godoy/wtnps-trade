# [DATA] Implementar MetaTraderProvider

## 🎯 Objetivo
Criar classe MetaTraderProvider que conecta ao MT5 e publica dados reais no EventBus.

## 📂 Contexto & Arquivos
- **Alvo:** `src/data_handler/mt5_provider.py`
- **Dependências:** `MetaTrader5`, `src/core/event_bus.py`, `src/events.py`

## 🛠️ Especificações Técnicas
1. **Interface:** Implementar método `get_latest_candles(symbol, timeframe, count)`
2. **Conexão MT5:** Usar `mt5.initialize()`, validar conexão
3. **Publicação:** Converter candles MT5 → `MarketDataEvent` → `event_bus.publish()`
4. **Configuração:** Ler credenciais MT5 de `.env` (path, login, server)

## 🔗 Dependências & Bloqueios
- [ ] MT5 terminal instalado e rodando
- [ ] Credenciais configuradas em `.env`
- [ ] EventBus operacional (Sprint 1 ✅)

## 📦 Definition of Done (DoD)
- [ ] Classe implementada e documentada (Docstrings)
- [ ] Conexão MT5 validada (testa com terminal ativo)
- [ ] Dados reais publicados no EventBus
- [ ] Testes de integração básicos passando
- [ ] README atualizado com instruções de setup MT5

## 📊 Estimativa
- **Story Points:** 13
- **Horas:** 16h
- **Prioridade:** 🔴 ALTA (bloqueia ARCH-003)
