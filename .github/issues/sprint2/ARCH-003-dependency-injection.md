# [ARCHITECT] Injeção de Dependências no main.py

## 🎯 Objetivo
Atualizar main.py para usar MetaTraderProvider real (substituir loop de teste) e injetar via DI.

## 📂 Contexto & Arquivos
- **Alvo:** `src/main.py`
- **Dependências:** `src/data_handler/mt5_provider.py`, `src/core/config.py`, `.env`

## 🛠️ Especificações Técnicas
1. **Instanciar MetaTraderProvider em main.py:**
   ```python
   try:
       provider = MetaTraderProvider()
       logger.info("✅ MetaTraderProvider inicializado")
   except ConnectionError as e:
       logger.critical(f"❌ Falha ao conectar MT5: {e}")
       sys.exit(1)  # Fail Fast - sem retry loops
   ```

2. **Estratégia Fail Fast:**
   - Se `MetaTraderProvider` lançar exceção → logar + `sys.exit(1)` imediato
   - NÃO implementar loops de reconexão nesta Sprint
   - NÃO usar try/except que silencia erro e continua
   - Sistema deve PARAR se dependências críticas falharem

3. **Carregamento de LSTMAdapter:**
   ```python
   try:
       strategy = LSTMVolatilityAdapter(model_prefix)
       logger.info("✅ LSTM Adapter carregado")
   except (FileNotFoundError, ValueError) as e:
       logger.critical(f"❌ Falha ao carregar modelo: {e}")
       sys.exit(1)  # Fail Fast
   ```

4. **Configuração .env:**
   - Ler variáveis: `MT5_PATH`, `MT5_LOGIN`, `MT5_SERVER`, `MT5_PASSWORD`
   - Se variável ausente → lançar `EnvironmentError`:
     ```python
     if not os.getenv("MT5_LOGIN"):
         raise EnvironmentError("MT5_LOGIN não definido em .env")
     ```

5. **Remover Mock Loop:**
   - Eliminar loop de geração de candles falsos
   - Sistema agora depende 100% do MT5 real

## 🔗 Dependências & Bloqueios
- [ ] DATA-001 (MT5Provider) deve estar merged ✅
- [ ] `.env.example` criado com template

## 📦 Definition of Done (DoD)
- [ ] main.py usa `MetaTraderProvider` (0 mocks)
- [ ] Fail Fast implementado: exceção → sys.exit(1)
- [ ] Nenhum try/except que silencia erro
- [ ] Logs mostram mensagem clara antes de exit
- [ ] `.env` validado ao startup (todas variáveis presentes)
- [ ] README explica: "Sistema para se MT5 não conectar (design intencional)"
- [ ] Teste manual: desligar MT5 → sistema exit(1) com log claro

## 📊 Estimativa
- **Story Points:** 8
- **Horas:** 10h
- **Prioridade:** 🔴 ALTA (depende de DATA-001)
