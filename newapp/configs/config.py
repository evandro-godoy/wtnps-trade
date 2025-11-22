"""Configuration module for newapp web application.

Centralizes application settings, environment variables, and constants.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal
import os

# Application metadata
APP_NAME = "WTNPS Trade Web UI"
APP_VERSION = "0.2.0"
APP_DESCRIPTION = "FastAPI web interface for algorithmic trading with ML/DRL strategies"

# Directory paths
APP_ROOT = Path(__file__).parent.parent  # newapp/ directory
PROJECT_ROOT = APP_ROOT.parent           # wtnps-trade/ directory
STATIC_DIR = APP_ROOT / 'static'
TEMPLATES_DIR = APP_ROOT / 'templates'
CACHE_DIR = APP_ROOT / '.cache_data'
MODELS_DIR = PROJECT_ROOT / 'models'

# Default trading parameters
DEFAULT_SYMBOL = "WDO$"
DEFAULT_TIMEFRAME = "M5"
DEFAULT_LIMIT = 500
MAX_LIMIT = 5000  # Maximum candles per request

# Data provider configuration
ProviderType = Literal['mt5', 'cache', 'synthetic', 'hybrid']
DEFAULT_PROVIDER: ProviderType = 'hybrid'

# Server configuration
HOST = os.getenv('WTNPS_HOST', '0.0.0.0')
PORT = int(os.getenv('WTNPS_PORT', '8100'))
RELOAD = os.getenv('WTNPS_RELOAD', 'true').lower() == 'true'

# Logging configuration
LOG_LEVEL = os.getenv('WTNPS_LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(levelname)s - [%(name)s] %(message)s'

# CORS configuration (for cloud deployments)
ALLOWED_ORIGINS = os.getenv('WTNPS_ALLOWED_ORIGINS', '*').split(',')

# Feature flags
ENABLE_MT5 = os.getenv('WTNPS_ENABLE_MT5', 'true').lower() == 'true'
ENABLE_CACHE = os.getenv('WTNPS_ENABLE_CACHE', 'true').lower() == 'true'
ENABLE_SYNTHETIC = os.getenv('WTNPS_ENABLE_SYNTHETIC', 'true').lower() == 'true'

# Timeframe mappings
VALID_TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]

# Chart configuration
CHART_DEFAULT_WIDTH = 1200
CHART_DEFAULT_HEIGHT = 600
CHART_STYLE = 'yahoo'  # mplfinance style

def validate_config() -> None:
    """Validate configuration on startup.
    
    Raises:
        ValueError: If critical configuration is invalid
    """
    # Ensure directories exist
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Validate timeframe
    if DEFAULT_TIMEFRAME not in VALID_TIMEFRAMES:
        raise ValueError(f"Invalid DEFAULT_TIMEFRAME: {DEFAULT_TIMEFRAME}")
    
    # Validate provider
    valid_providers: list[ProviderType] = ['mt5', 'cache', 'synthetic', 'hybrid']
    if DEFAULT_PROVIDER not in valid_providers:
        raise ValueError(f"Invalid DEFAULT_PROVIDER: {DEFAULT_PROVIDER}")


# Run validation on import
validate_config()
