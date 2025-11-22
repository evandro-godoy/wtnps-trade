"""Database package for newapp.

Provides database models, session management, and CRUD operations.
"""
from newapp.src.database.db import (
    get_engine,
    get_db,
    get_session_factory,
    init_database,
    close_database,
    Base,
)

from newapp.src.database.models import (
    OHLCVData,
    TechnicalIndicators,
    MarketAnalysis,
    DataProviderLog,
)

__all__ = [
    # Database connection
    'get_engine',
    'get_db',
    'get_session_factory',
    'init_database',
    'close_database',
    'Base',
    
    # Models
    'OHLCVData',
    'TechnicalIndicators',
    'MarketAnalysis',
    'DataProviderLog',
]
