# Migrar de SQLite para SQL Server

## Pré-requisitos

1. **Instalar SQL Server Express** (gratuito):
   ```powershell
   # Download do instalador
   Start-Process "https://www.microsoft.com/en-us/sql-server/sql-server-downloads"
   ```

2. **Instalar SQL Server Management Studio (SSMS)**:
   ```powershell
   # Download SSMS
   Start-Process "https://aka.ms/ssmsfullsetup"
   ```

## Configuração

### 1. Criar Banco de Dados

Execute no SSMS ou via `sqlcmd`:

```sql
-- Criar banco
CREATE DATABASE [wtnps-trade];
GO

-- Criar usuário de aplicação
USE [wtnps-trade];
GO

CREATE LOGIN wtnps_app WITH PASSWORD = 'SuaSenhaForteAqui123!';
GO

CREATE USER wtnps_app FOR LOGIN wtnps_app;
GO

-- Conceder permissões
ALTER ROLE db_datareader ADD MEMBER wtnps_app;
ALTER ROLE db_datawriter ADD MEMBER wtnps_app;
ALTER ROLE db_ddladmin ADD MEMBER wtnps_app;
GO
```

### 2. Configurar Variáveis de Ambiente

No PowerShell:

```powershell
# Backend SQL Server
[System.Environment]::SetEnvironmentVariable('WTNPS_DB_BACKEND', 'sqlserver', 'User')

# Configurações do servidor
[System.Environment]::SetEnvironmentVariable('WTNPS_DB_SERVER', 'localhost', 'User')
[System.Environment]::SetEnvironmentVariable('WTNPS_DB_NAME', 'wtnps-trade', 'User')

# Autenticação SQL (usuário criado acima)
[System.Environment]::SetEnvironmentVariable('WTNPS_DB_TRUSTED_CONNECTION', 'no', 'User')
[System.Environment]::SetEnvironmentVariable('WTNPS_DB_USER', 'wtnps_app', 'User')
[System.Environment]::SetEnvironmentVariable('WTNPS_DB_PASSWORD', 'SuaSenhaForteAqui123!', 'User')
```

**OU usar Windows Authentication (mais seguro):**

```powershell
[System.Environment]::SetEnvironmentVariable('WTNPS_DB_BACKEND', 'sqlserver', 'User')
[System.Environment]::SetEnvironmentVariable('WTNPS_DB_SERVER', 'localhost', 'User')
[System.Environment]::SetEnvironmentVariable('WTNPS_DB_NAME', 'wtnps-trade', 'User')
[System.Environment]::SetEnvironmentVariable('WTNPS_DB_TRUSTED_CONNECTION', 'yes', 'User')
```

### 3. Criar Esquema

Execute o script:

```powershell
sqlcmd -S localhost -E -i newapp\sql\setup_database.sql
```

### 4. Reiniciar Aplicação

```powershell
# Reiniciar terminal para carregar variáveis
exit

# Nova sessão
cd C:\projects\wtnps-trade
poetry run python newapp\tests\test_database.py
```

Se tudo estiver OK, verá:
```
Backend: sqlserver
✅ Connected to SQL Server
```

### 5. Migrar Dados Existentes (Opcional)

Se já tem dados no SQLite:

```powershell
poetry run python -c "
import sqlite3
import pandas as pd
from newapp.src.database import get_session_factory
from newapp.src.database.repository import OHLCVRepository

# Ler do SQLite
conn = sqlite3.connect('wtnps_trade.db')
df = pd.read_sql('SELECT * FROM ohlcv_data', conn)
conn.close()

# Salvar no SQL Server (com WTNPS_DB_BACKEND=sqlserver)
SessionLocal = get_session_factory()
db = SessionLocal()
# ... converter e salvar
"
```

## Acesso Externo com SQL Server

### Via SSMS:
- Server: `localhost`
- Authentication: 
  - **SQL Server**: Login `wtnps_app`, senha configurada
  - **Windows**: Sua conta Windows
- Database: `wtnps-trade`

### Via DBeaver:
- Driver: SQL Server (jTDS)
- Host: `localhost`
- Port: `1433`
- Database: `wtnps-trade`
- Username: `wtnps_app`
- Password: (senha configurada)

### Via Azure Data Studio:
- Connection type: Microsoft SQL Server
- Server: `localhost`
- Database: `wtnps-trade`
- Authentication: SQL Login ou Windows

## Voltar para SQLite

```powershell
[System.Environment]::SetEnvironmentVariable('WTNPS_DB_BACKEND', 'sqlite', 'User')
```

Reiniciar terminal.
