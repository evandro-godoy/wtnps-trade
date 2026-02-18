# Database Backend Choice

## Current Status
SQL Server não está instalado/disponível nesta máquina.

## Opções Disponíveis

### Opção 1: SQLite (RECOMENDADO para desenvolvimento)
**Vantagens:**
- ✅ Sem necessidade de servidor externo
- ✅ Arquivo único portável
- ✅ Suporte completo do SQLAlchemy
- ✅ Mesmo código ORM funciona
- ✅ Perfeito para desenvolvimento/testes

**Desvantagens:**
- ❌ Menor performance em alta concorrência
- ❌ Sem autenticação de usuário nativa

**Implementação:**
```python
# Alterar em newapp/src/database/db.py
def get_connection_string() -> str:
    return "sqlite:///./wtnps_trade.db"
```

### Opção 2: SQL Server (Para produção)
**Vantagens:**
- ✅ Alta performance em ambientes empresariais
- ✅ Autenticação Windows/SQL
- ✅ Ferramentas de administração robustas
- ✅ Backup/restore avançado

**Desvantagens:**
- ❌ Requer instalação SQL Server
- ❌ Mais complexo para configurar
- ❌ Licenciamento (Express é gratuito)

**Instalação:**
1. Download SQL Server Express:
   https://www.microsoft.com/en-us/sql-server/sql-server-downloads
2. Instalar com autenticação Windows
3. Iniciar serviço: `Start-Service MSSQLSERVER`

### Opção 3: PostgreSQL
**Vantagens:**
- ✅ Open source completo
- ✅ Excelente performance
- ✅ Recursos avançados

**Desvantagens:**
- ❌ Requer instalação servidor
- ❌ Mais complexo que SQLite

## Recomendação

Para **desenvolvimento local**: Use SQLite (mudança de 2 linhas)
Para **produção/nuvem**: Use SQL Server ou PostgreSQL

## Próximos Passos

Escolha uma opção:

1. **SQLite (rápido):**
   ```powershell
   # Alterar configs para SQLite e testar
   poetry run python newapp\tests\test_database.py
   ```

2. **SQL Server (completo):**
   ```powershell
   # Instalar SQL Server Express
   # Depois executar setup
   poetry run python newapp\setup_database.py
   ```

3. **Híbrido (melhor dos dois mundos):**
   - SQLite para desenvolvimento
   - SQL Server para produção
   - Trocar via variável de ambiente `WTNPS_DB_BACKEND`
