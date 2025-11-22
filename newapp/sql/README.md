# SQL Server Database Configuration

## Variáveis de Ambiente

Configure as seguintes variáveis de ambiente para conexão com SQL Server:

```powershell
# Configuração para Windows Authentication (recomendado)
$env:WTNPS_DB_SERVER = "localhost"
$env:WTNPS_DB_NAME = "wtnps-trade"
$env:WTNPS_DB_TRUSTED_CONNECTION = "yes"

# OU configuração para SQL Server Authentication
$env:WTNPS_DB_SERVER = "localhost"
$env:WTNPS_DB_NAME = "wtnps-trade"
$env:WTNPS_DB_USER = "sa"
$env:WTNPS_DB_PASSWORD = "YourPassword123"
$env:WTNPS_DB_TRUSTED_CONNECTION = "no"
```

## Drivers SQL Server

### Verificar Drivers Instalados

```powershell
Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"} | Format-Table Name, Platform
```

### Drivers Recomendados

1. **ODBC Driver 17 for SQL Server** (padrão)
2. **ODBC Driver 18 for SQL Server**
3. **SQL Server Native Client 11.0**

### Instalar Driver

Se nenhum driver estiver instalado:

1. Baixe: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
2. Instale: `msodbcsql.msi`

Ou via Chocolatey:
```powershell
choco install sqlserver-odbcdriver
```

## Setup do Banco de Dados

### 1. Executar Script de Criação

```powershell
# Via sqlcmd (SQL Server Command Line)
sqlcmd -S localhost -E -i newapp\sql\setup_database.sql

# OU via SQL Server Management Studio (SSMS)
# Abra o arquivo setup_database.sql e execute (F5)
```

### 2. Verificar Criação

```powershell
sqlcmd -S localhost -E -Q "SELECT name FROM sys.databases WHERE name = 'wtnps-trade'"
```

### 3. Testar Conexão Python

```powershell
cd c:\projects\wtnps-trade
poetry run python -c "from newapp.src.database.db import get_engine; engine = get_engine(); print('✅ Conexão OK')"
```

## Estrutura das Tabelas

O SQLAlchemy criará automaticamente as tabelas na primeira execução:

- **ohlcv_data**: Dados OHLCV (Open, High, Low, Close, Volume)
- **technical_indicators**: Indicadores técnicos (EMA, SMA, RSI)
- **market_analysis**: Análises de mercado completas
- **data_provider_log**: Log de operações dos providers

### Visualizar Tabelas

```sql
USE [wtnps-trade]
GO

SELECT 
    TABLE_SCHEMA,
    TABLE_NAME,
    TABLE_TYPE
FROM INFORMATION_SCHEMA.TABLES
ORDER BY TABLE_NAME
```

## Troubleshooting

### Erro: "Database 'wtnps-trade' does not exist"

Criar manualmente:
```sql
CREATE DATABASE [wtnps-trade]
```

### Erro: "Login failed for user"

Verificar permissões:
```sql
USE [wtnps-trade]
GO
GRANT CONNECT TO [DOMAIN\Username]
GRANT SELECT, INSERT, UPDATE, DELETE TO [DOMAIN\Username]
GO
```

### Erro: "Driver not found"

Atualizar variável de ambiente:
```powershell
$env:WTNPS_DB_DRIVER = "SQL Server"  # Usar driver legado
```

## Consultas Úteis

### Contagem de Registros

```sql
SELECT 
    'ohlcv_data' AS table_name,
    COUNT(*) AS record_count
FROM ohlcv_data
UNION ALL
SELECT 
    'market_analysis',
    COUNT(*)
FROM market_analysis
```

### Últimos Registros

```sql
-- Últimos candles
SELECT TOP 10 *
FROM ohlcv_data
ORDER BY timestamp DESC

-- Últimas análises
SELECT TOP 10 *
FROM market_analysis
ORDER BY timestamp DESC
```

### Limpar Dados (Cuidado!)

```sql
-- Limpar todas as tabelas
TRUNCATE TABLE ohlcv_data
TRUNCATE TABLE technical_indicators
TRUNCATE TABLE market_analysis
TRUNCATE TABLE data_provider_log
```

## Integração com Aplicação

A aplicação FastAPI agora:

1. **Consulta o banco primeiro** para dados OHLCV
2. **Fallback para provider** (MT5/Cache/Synthetic) se banco vazio
3. **Salva automaticamente** dados fetched no banco
4. **Persiste análises** técnicas para histórico

### Fluxo de Dados

```
Requisição API
    ↓
Consulta Database
    ↓
Database vazio? → Busca Provider (MT5/Cache/Synthetic)
    ↓                      ↓
Retorna dados ←─── Salva no Database
```

## Performance

### Índices Criados

- `idx_symbol_timeframe_timestamp` (ohlcv_data)
- `idx_ti_symbol_timeframe_timestamp` (technical_indicators)
- `idx_ma_symbol_timeframe_timestamp` (market_analysis)

### Otimização de Queries

```sql
-- Estatísticas de índices
SELECT 
    OBJECT_NAME(s.object_id) AS TableName,
    i.name AS IndexName,
    s.user_seeks,
    s.user_scans,
    s.user_lookups
FROM sys.dm_db_index_usage_stats s
INNER JOIN sys.indexes i ON s.object_id = i.object_id AND s.index_id = i.index_id
WHERE OBJECT_NAME(s.object_id) LIKE '%ohlcv%'
ORDER BY s.user_seeks + s.user_scans + s.user_lookups DESC
```

## Backup

### Backup Manual

```sql
BACKUP DATABASE [wtnps-trade]
TO DISK = 'C:\Backups\wtnps-trade_backup.bak'
WITH FORMAT, INIT, NAME = 'Full Backup';
```

### Restore

```sql
RESTORE DATABASE [wtnps-trade]
FROM DISK = 'C:\Backups\wtnps-trade_backup.bak'
WITH REPLACE;
```
