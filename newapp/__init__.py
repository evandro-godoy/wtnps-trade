"""NewApp - WTNPS Trade Web Interface.

Modern FastAPI-based web application for algorithmic trading with ML/DRL
strategies. Provides REST API access to market data and trading signals.

Key Features:
- HybridProvider with intelligent fallback (MT5 → Cache → Synthetic)
- Thread-safe singleton pattern for web concurrency
- Cloud-compatible (works without MetaTrader5 installed)
- Centralized configuration via environment variables
- OHLCV data endpoints with timezone-aware responses
- Technical analysis engine for market context

Quick Start:
    >>> from newapp.src.data_handler.provider import get_default_provider
    >>> from newapp.src.analysis.context_analyzer import analyze_market_context
    >>> 
    >>> provider = get_default_provider()
    >>> df = provider.get_latest_candles('WDO$', 'M5', 500)
    >>> context = analyze_market_context(df)
    
    # Run web application
    $ poetry run python -m newapp.main
    # Access: http://localhost:8100

See newapp/README.md for complete documentation.
"""

__version__ = "0.2.0"
__author__ = "WTNPS Trade Team"

from newapp.src.data_handler.provider import (
    get_default_provider,
    get_provider,
    HybridProvider,
    MetaTraderProvider,
    CacheProvider,
    SyntheticProvider,
)

from newapp.configs.config import (
    DEFAULT_SYMBOL,
    DEFAULT_TIMEFRAME,
    DEFAULT_LIMIT,
    MAX_LIMIT,
    VALID_TIMEFRAMES,
)

from newapp.src.analysis.context_analyzer import (
    MarketContextAnalyzer,
    analyze_market_context,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    
    # Provider factories
    "get_default_provider",
    "get_provider",
    
    # Provider classes
    "HybridProvider",
    "MetaTraderProvider",
    "CacheProvider",
    "SyntheticProvider",
    
    # Configuration
    "DEFAULT_SYMBOL",
    "DEFAULT_TIMEFRAME",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "VALID_TIMEFRAMES",
    
    # Analysis
    "MarketContextAnalyzer",
    "analyze_market_context",
]
