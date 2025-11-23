"""Quick setup script for wtnps-trade database.

This script will:
1. Check if SQL Server is running
2. Create the database if it doesn't exist
3. Verify connection
"""
import subprocess
import sys
from pathlib import Path

def check_sql_server():
    """Check if SQL Server service is running."""
    print("Checking SQL Server service...")
    try:
        result = subprocess.run(
            ['powershell', '-Command', "Get-Service -Name 'MSSQL*' | Select-Object Name, Status"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
        
        if 'Running' in result.stdout:
            print("✅ SQL Server is running")
            return True
        else:
            print("❌ SQL Server is not running")
            print("Start SQL Server with:")
            print("  Start-Service MSSQLSERVER")
            return False
    except Exception as e:
        print(f"❌ Error checking SQL Server: {e}")
        return False


def create_database():
    """Create wtnps-trade database using sqlcmd."""
    print("\nCreating wtnps-trade database...")
    
    sql_file = Path(__file__).parent.parent / "sql" / "setup_database.sql"
    
    if not sql_file.exists():
        print(f"❌ SQL file not found: {sql_file}")
        return False
    
    try:
        # Try with Windows Authentication first
        print("Attempting connection with Windows Authentication...")
        result = subprocess.run(
            ['sqlcmd', '-S', 'localhost', '-E', '-i', str(sql_file)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Database created successfully")
            print(result.stdout)
            return True
        else:
            print(f"❌ sqlcmd failed: {result.stderr}")
            print("\nTroubleshooting:")
            print("1. Ensure SQL Server is running")
            print("2. Verify Windows Authentication is enabled")
            print("3. Check if your Windows user has sysadmin role")
            return False
            
    except FileNotFoundError:
        print("❌ sqlcmd not found. Install SQL Server Command Line Utilities:")
        print("  https://learn.microsoft.com/en-us/sql/tools/sqlcmd-utility")
        return False
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False


def verify_database():
    """Verify database exists."""
    print("\nVerifying database...")
    try:
        result = subprocess.run(
            ['sqlcmd', '-S', 'localhost', '-E', '-Q', 
             "SELECT name FROM sys.databases WHERE name = 'wtnps-trade'"],
            capture_output=True,
            text=True
        )
        
        if 'wtnps-trade' in result.stdout:
            print("✅ Database 'wtnps-trade' exists")
            return True
        else:
            print("❌ Database 'wtnps-trade' not found")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying database: {e}")
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("WTNPS Trade - Database Setup")
    print("=" * 60)
    
    # Step 1: Check SQL Server
    if not check_sql_server():
        sys.exit(1)
    
    # Step 2: Create database
    if not create_database():
        sys.exit(1)
    
    # Step 3: Verify
    if not verify_database():
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ Setup complete! Run the following to test:")
    print("  poetry run python newapp\\tests\\test_database.py")
    print("=" * 60)
