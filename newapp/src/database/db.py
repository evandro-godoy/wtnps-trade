"""Database configuration and connection management for SQL Server.

Provides SQLAlchemy engine and session management for wtnps-trade database.
"""
from __future__ import annotations

import os
import logging
from typing import Optional, Generator
from urllib.parse import quote_plus

from sqlalchemy import create_engine, Engine, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

# Database configuration from environment variables
DB_BACKEND = os.getenv('WTNPS_DB_BACKEND', 'sqlite')  # 'sqlite' or 'sqlserver'
SQLITE_PATH = os.getenv('WTNPS_SQLITE_PATH', './wtnps_trade.db')
DB_DRIVER = os.getenv('WTNPS_DB_DRIVER', 'ODBC Driver 17 for SQL Server')
DB_SERVER = os.getenv('WTNPS_DB_SERVER', 'localhost')
DB_NAME = os.getenv('WTNPS_DB_NAME', 'wtnps-trade')
DB_USER = os.getenv('WTNPS_DB_USER', '')  # Empty for Windows Authentication
DB_PASSWORD = os.getenv('WTNPS_DB_PASSWORD', '')
DB_TRUSTED_CONNECTION = os.getenv('WTNPS_DB_TRUSTED_CONNECTION', 'yes')

# SQLAlchemy base for ORM models
Base = declarative_base()

# Global engine and session factory (initialized lazily)
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_connection_string() -> str:
    """Build database connection string based on backend type.
    
    Supports:
    - SQLite (default, no server required)
    - SQL Server (production, requires SQL Server installation)
    
    Returns:
        Connection string for SQLAlchemy
    """
    backend = DB_BACKEND.lower()
    
    if backend == 'sqlite':
        # SQLite - local file database
        logger.info(f"Using SQLite database: {SQLITE_PATH}")
        return f"sqlite:///{SQLITE_PATH}"
        
    elif backend == 'sqlserver':
        # SQL Server with ODBC
        if DB_TRUSTED_CONNECTION.lower() == 'yes':
            # Windows Authentication
            connection_string = (
                f"DRIVER={{{DB_DRIVER}}};"
                f"SERVER={DB_SERVER};"
                f"DATABASE={DB_NAME};"
                f"Trusted_Connection=yes;"
            )
        else:
            # SQL Server Authentication
            connection_string = (
                f"DRIVER={{{DB_DRIVER}}};"
                f"SERVER={DB_SERVER};"
                f"DATABASE={DB_NAME};"
                f"UID={DB_USER};"
                f"PWD={DB_PASSWORD};"
            )
        
        # URL encode for SQLAlchemy
        encoded = quote_plus(connection_string)
        logger.info(f"Using SQL Server: {DB_SERVER}/{DB_NAME}")
        return f"mssql+pyodbc:///?odbc_connect={encoded}"
        
    else:
        raise ValueError(
            f"Unsupported database backend: '{backend}'. "
            f"Set WTNPS_DB_BACKEND to 'sqlite' or 'sqlserver'"
        )


def get_engine() -> Engine:
    """Get or create SQLAlchemy engine (singleton pattern).
    
    Returns:
        SQLAlchemy engine instance.
    """
    global _engine
    
    if _engine is None:
        connection_string = get_connection_string()
        
        # Engine configuration varies by backend
        engine_args = {
            'echo': False,  # Set True for SQL logging
        }
        
        if DB_BACKEND.lower() == 'sqlite':
            # SQLite-specific configuration
            engine_args.update({
                'connect_args': {'check_same_thread': False},  # Allow multi-threading
            })
        else:
            # SQL Server configuration
            engine_args.update({
                'poolclass': NullPool,  # Disable pooling for better concurrency
            })
        
        _engine = create_engine(connection_string, **engine_args)

        # SQLite pragmas to mitigate locking and improve write concurrency
        if DB_BACKEND.lower() == 'sqlite':
            @event.listens_for(_engine, 'connect')
            def set_sqlite_pragmas(dbapi_connection, connection_record):  # type: ignore
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute('PRAGMA journal_mode=WAL;')
                    cursor.execute('PRAGMA synchronous=NORMAL;')
                    cursor.execute('PRAGMA busy_timeout=5000;')
                finally:
                    cursor.close()
        
        # Test connection
        try:
            with _engine.connect() as conn:
                backend_name = "SQLite" if DB_BACKEND.lower() == 'sqlite' else "SQL Server"
                logger.info(f"✅ {backend_name} connected successfully")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            raise
    
    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create session factory.
    
    Returns:
        SQLAlchemy sessionmaker instance.
    """
    global _SessionLocal
    
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
    
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Dependency function for FastAPI to get database session.
    
    Yields:
        SQLAlchemy session that auto-closes after request.
        
    Example:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """Initialize database schema (create all tables).
    
    Should be called on application startup.
    """
    engine = get_engine()
    
    # Import all models here to ensure they're registered
    from newapp.src.database import models  # noqa: F401
    
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized")


def close_database():
    """Close database connections.
    
    Should be called on application shutdown.
    """
    global _engine
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
        logger.info("Database connections closed")
