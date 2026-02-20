# Fase 1: Plano de Correção — Divergências de Contrato (Handoff)

**Data:** 2026-02-20  
**Status:** Bloqueante para Smoke Test Fase 1  
**Prioridade:** 🔴 **CRÍTICA**  
**Escopo:** Corrigir TypeErrors em `RealtimeMarketMonitor.warm_up()`  

---

## 📋 Resumo Executivo

Durante o smoke test da Fase 1, o sistema monolítico subiu com sucesso, porém **o ciclo de aquecimento (warm-up) do monitor falhou** devido a divergências de interface entre módulos (Provider, Repository, Monitor).

**Dois TypeErrors mapeados:**
1. ✋ **`HybridProvider.get_latest_candles()` recebe `symbol`, mas espera `ticker`**
2. ⚠️ **`AssetsRatesRepository.get_latest_market_data()` não existe (método fantasma)**

**Prognóstico:** Ambos são corrigíveis em menos de 15 minutos.

---

## 🔍 Diagnóstico Detalhado

### Erro 1: HybridProvider TypeError

**Arquivo:** `newapp/src/live/monitor_engine.py`  
**Linhas:** 141-144  
**Tipo:** Parameter Name Mismatch

**Código Atual (❌ ERRADO):**
```python
def _warm_up(self) -> None:
    """Warm up buffer with historical candles."""
    logger.info(f"WARM-UP: Fetching {self.buffer_size} historical candles...")
    
    try:
        data = self.provider.get_latest_candles(
            symbol=self.ticker,              # ❌ ERRO: 'symbol' não existe
            timeframe=self.timeframe_str,
            limit=self.buffer_size           # ❌ ERRO: 'limit' não existe
        )
```

**Erro de Execução:**
```
TypeError: HybridProvider.get_latest_candles() got an unexpected 
keyword argument 'symbol' at line 141
```

**Root Cause:**  
O método `HybridProvider.get_latest_candles()` foi definido com assinatura:
```python
def get_latest_candles(
    self,
    ticker: str,        # ← espera 'ticker' não 'symbol'
    timeframe: Any,
    count: int          # ← espera 'count' não 'limit'
) -> pd.DataFrame:
```

**A Correção:**

| Linha | Mudar De | Mudar Para | Razão |
|-------|----------|-----------|-------|
| 141 | `symbol=self.ticker` | `ticker=self.ticker` | Assinatura exige `ticker` |
| 144 | `limit=self.buffer_size` | `count=self.buffer_size` | Assinatura exige `count` |

**Código Corrigido (✅ CERTO):**
```python
data = self.provider.get_latest_candles(
    ticker=self.ticker,              # ✅ CORRETO
    timeframe=self.timeframe_str,
    count=self.buffer_size           # ✅ CORRETO
)
```

---

### Erro 2: AssetsRatesRepository.get_latest_market_data()

**Status:** Método não existe

**Diagnóstico:**  
A busca semântica em toda a codebase (`newapp/src/**`) **NÃO ENCONTRA** nenhuma chamada ou definição de `get_latest_market_data()`.

**Métodos Alternativos Disponíveis em AssetsRatesRepository:**

```python
# ✅ Opção A: Busca as últimas N candles do banco (RECOMENDADO)
@staticmethod
def get_latest_candles(
    db: Session,
    symbol: str,
    timeframe: str,
    limit: int = 500
) -> pd.DataFrame:
    """Retorna últimas N candles do banco (DB)"""
    
# ✅ Opção B: Busca todas as taxas (se histórico completo é necessário)
@staticmethod
def get_all_rates(
    db: Session,
    symbol: str,
    timeframe: str
) -> pd.DataFrame:
    """Retorna todos os records para um ativo/timeframe"""
```

**Ação Recomendada:**  
- Se o monitor precisa de dados históricos do banco: **NÃO USE** (o monitor usa `HybridProvider`, não banco).
- Se há plano futuro para usar repository no monitor: Implementar método específico com contrato claro.
- **ATUAL:** O relatório de smoke test menciona "linha 146", mas esse erro parece ser **fantasma** (não ocorre no código atual).

---

## ✅ Verificação de Pré-Requisitos

Antes de corrigir, validar:

- [ ] **Arquivo `newapp/src/live/monitor_engine.py` está sendo usado** como entrypoint padrão?
  - Verificar: `newapp/src/api/main.py` inicializa `RealtimeMarketMonitor`
  
- [ ] **Versão de HybridProvider é realmente** `provider.py` linha 735+?
  - Verificar: `grep -n "def get_latest_candles" newapp/src/data_handler/provider.py`
  
- [ ] **Estado corrente de AssetsRatesRepository não inclui `get_latest_market_data()`?**
  - Verificar: `grep -n "def get_latest_market_data" newapp/src/database/repository.py` (deve retornar 0 matches)

---

## 🔧 Plano de Correção (3 Ações)

### Ação A: Corrigir Parameter Names em monitor_engine.py

**Arquivo:** `newapp/src/live/monitor_engine.py`  
**Linhas:** 141-144  
**Tipo:** Find & Replace

```diff
-        data = self.provider.get_latest_candles(
-            symbol=self.ticker,
+        data = self.provider.get_latest_candles(
+            ticker=self.ticker,
             timeframe=self.timeframe_str,
-            limit=self.buffer_size
+            count=self.buffer_size
         )
```

**Validação Pós-Correção:**
```bash
# 1. Syntax check
python -m py_compile newapp/src/live/monitor_engine.py

# 2. Type check (se Pylance/Mypy está disponível)
mypy newapp/src/live/monitor_engine.py

# 3. Runtime check: executar warm-up sem erro
poetry run python -c "
from newapp.src.live.monitor_engine import RealtimeMarketMonitor
m = RealtimeMarketMonitor(ticker='WDO$', timeframe_str='M5', buffer_size=100)
m._warm_up()
print('✅ warm_up() executado sem TypeError')
"
```

---

### Ação B: Auditar Chamadas para get_latest_market_data()

**Objetivo:** Confirmar se o método "fantasma" é realmente usado em algum lugar.

```bash
# Buscar TODAS as referências de 'get_latest_market_data'
grep -r "get_latest_market_data" newapp/src/

# Esperado: nenhum resultado (0 matches)
```

**Se houver matches:**
- Localizar arquivo e linha
- Determinar intenção (DB query vs. Provider call)
- Substituir por método correto:
  - Se espera dados do **provider**: use `HybridProvider.get_latest_candles(ticker, timeframe, count)`
  - Se espera dados do **banco**: use `AssetsRatesRepository.get_latest_candles(db, symbol, timeframe, limit)`

---

### Ação C: Adicionar Teste de Integração

**Objetivo:** Prevenir regressão futura.

**Novo Arquivo:** `newapp/tests/test_monitor_engine_contracts.py`

```python
"""Test data contract consistency between components."""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from newapp.src.live.monitor_engine import RealtimeMarketMonitor
from newapp.src.data_handler.provider import HybridProvider


class TestMonitorEngineContracts:
    """Validate parameter contracts in warm_up()."""
    
    def test_warm_up_calls_provider_with_correct_params(self):
        """
        ENSURE: monitor_engine calls HybridProvider.get_latest_candles
        WITH: ticker=..., timeframe=..., count=...
        NOT: symbol=..., limit=...
        """
        # Mock HybridProvider
        with patch('newapp.src.live.monitor_engine.get_default_provider') as mock_provider_factory:
            mock_provider = MagicMock(spec=HybridProvider)
            mock_provider_factory.return_value = mock_provider
            
            # Create mock DataFrame
            mock_df = pd.DataFrame({
                'open': [100],
                'high': [102],
                'low': [99],
                'close': [101],
                'volume': [1000]
            })
            mock_provider.get_latest_candles.return_value = mock_df
            
            # Instantiate monitor and warm up
            monitor = RealtimeMarketMonitor(
                ticker='WDO$',
                timeframe_str='M5',
                buffer_size=100
            )
            monitor._warm_up()
            
            # Assert correct parameters were passed
            mock_provider.get_latest_candles.assert_called_once_with(
                ticker='WDO$',       # Must be 'ticker' not 'symbol'
                timeframe='M5',
                count=100            # Must be 'count' not 'limit'
            )
            
            # Assert buffer was populated
            assert monitor.buffer_df is not None
            assert len(monitor.buffer_df) == 1
```

**Executar:**
```bash
poetry run pytest newapp/tests/test_monitor_engine_contracts.py -v
```

---

## 📊 Checklist de Conclusão

- [ ] **Ação A:** Corrigir `symbol` → `ticker` e `limit` → `count` em monitor_engine.py
- [ ] **Validação A:** Executar `poetry run python -c "from newapp.src.live.monitor_engine import RealtimeMarketMonitor; m = RealtimeMarketMonitor(); m._warm_up()"` sem TypeError
- [ ] **Ação B:** Confirmar 0 matches para `grep -r "get_latest_market_data" newapp/src/`
- [ ] **Ação C:** Adicionar teste de contrato `test_monitor_engine_contracts.py`
- [ ] **Smoke Test:** Re-executar checklist Fase 1, seção 1 (Startup/Shutdown/Lifecycle)
- [ ] **Git Commit:** Message: `fix: correct parameter names in monitor_engine warm_up (#XXX)`

---

## 📚 Referências de Design

- Memory Bank: `.memory-bank/systemPatterns.md` (Seção 7: Data Contract)
- Provider Reference: `newapp/src/data_handler/provider.py` (HybridProvider, lines 735+)
- Repository Reference: `newapp/src/database/repository.py` (AssetsRatesRepository)
- Monitor Engine: `newapp/src/live/monitor_engine.py` (RealtimeMarketMonitor)

---

## 📝 Notas Arquiteturais

A divergência raiz ocorreu porque:

1. **HybridProvider** foi projetado com nomenclatura `ticker` (padrão de trading, referência a symbol)
2. **Repository Pattern** tradicionalmente usa `symbol` (nomenclatura de banco de dados)
3. **Monitor** foi escrito antes de a padronização estar clara, causando mismatch

**Lição:** Toda camada de abstração (Provider → Repository → Service) deve ter contrato explícito de **nomes de parâmetro**, não apenas tipos.

A atualização de `systemPatterns.md` (Seção 7) estabelece esse contrato de forma permanente para evitar regressão.

---

## Próximos Passos Pós-Correção

1. ✅ Passar no Smoke Test Fase 1 (especialmente seção 1 e 6)
2. ✅ Executar Monitor com sucesso em `/api/monitor/start`
3. ✅ WebSocket `/ws/monitor` começa a enviar eventos de streaming
4. 📅 Iniciar Fase 2: Estabilidade do Buffer + Persistência em Banco
