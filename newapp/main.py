"""Standalone FastAPI web application providing a demonstrative
interface for technical analysis results of WDO$ using newapp data
provider logic.

Features:
- GET / -> HTML page with latest OHLC (WDO$ M5) and candlestick chart (last 500 bars)
- GET /api/ohlc -> JSON OHLC data service with intelligent fallback

The application uses HybridProvider with automatic fallback:
MT5 → Cache → Synthetic data generation.
"""
from __future__ import annotations

from typing import Any, Dict, List
import logging

import pandas as pd
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from sqlalchemy.orm import Session

from newapp.src.data_handler.provider import get_default_provider
from newapp.src.analysis.context_analyzer import MarketContextAnalyzer, analyze_market_context
from newapp.plotting import create_dashboard_chart
from newapp.src.database import (
    init_database,
    close_database,
    get_db,
)
from newapp.src.database.repository import (
    OHLCVRepository,
    MarketAnalysisRepository,
    DataProviderLogRepository,
)
from newapp.configs.config import (
    APP_NAME,
    APP_VERSION,
    APP_ROOT,
    STATIC_DIR,
    TEMPLATES_DIR,
    DEFAULT_SYMBOL,
    DEFAULT_TIMEFRAME,
    DEFAULT_LIMIT,
    MAX_LIMIT,
    LOG_LEVEL,
    LOG_FORMAT,
)

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

app = FastAPI(title=APP_NAME, version=APP_VERSION)
router = APIRouter()

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    logger.info("🚀 Starting NewApp...")
    try:
        init_database()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        # Continue without database (fallback to in-memory only)

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on shutdown."""
    logger.info("Shutting down NewApp...")
    close_database()
    logger.info("Database connections closed")

# Static & templates with no-cache headers
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

app.add_middleware(NoCacheMiddleware)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Initialize data provider and analyzer (singletons)
data_provider = get_default_provider()
market_analyzer = MarketContextAnalyzer()

def get_recent_ohlc(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT
) -> pd.DataFrame:
    """Retrieve recent OHLC bars using HybridProvider.
    
    Automatically handles fallback chain: MT5 → Cache → Synthetic.
    
    Args:
        symbol: Asset symbol (e.g., "WDO$")
        timeframe: Timeframe string (e.g., "M5", "H1")
        limit: Number of candles to retrieve
        
    Returns:
        DataFrame with OHLCV data, timezone-aware index
    """
    try:
        df = data_provider.get_latest_candles(symbol, timeframe, limit)
        if df.empty:
            logger.warning(f"Provider returned empty DataFrame for {symbol} {timeframe}")
        return df
    except Exception as exc:
        logger.error(f"Error fetching OHLC data: {exc}")
        # Return empty DataFrame on error
        return pd.DataFrame()


@router.get('/api/ohlc', response_class=JSONResponse)
async def api_ohlc(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Return OHLC data in JSON format for chart rendering.
    
    Tries database first, falls back to provider if no data or insufficient records.
    Saves fetched data to database for future queries.
    
    Args:
        symbol: Asset symbol (default: WDO$)
        timeframe: Timeframe string (default: M5)
        limit: Number of candles (default: 500, max: 5000)
        db: Database session (injected)
        
    Returns:
        JSON response with OHLCV data and metadata
        
    Raises:
        HTTPException: If limit is out of valid range
    """
    if limit <= 0 or limit > MAX_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f'limit deve estar entre 1 e {MAX_LIMIT}'
        )
    
    # Try database first
    df = OHLCVRepository.get_latest_candles(db, symbol, timeframe, limit)
    source = "Database"
    
    # Fallback to provider if insufficient data
    if df.empty or len(df) < limit:
        logger.info(f"Database has {len(df)} candles, fetching from provider...")
        df = get_recent_ohlc(symbol, timeframe, limit)
        source = "Provider"
        
        # Save to database
        if not df.empty:
            try:
                OHLCVRepository.save_dataframe(db, df, symbol, timeframe)
                logger.info(f"Saved {len(df)} candles to database")
            except Exception as e:
                logger.error(f"Failed to save to database: {e}")
    
    records: List[Dict[str, Any]] = []
    for ts, row in df.iterrows():
        records.append({
            'time': ts.isoformat(),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row['volume']) if 'volume' in row and not pd.isna(row['volume']) else 0
        })
    latest = records[-1] if records else None
    return {
        'symbol': symbol,
        'timeframe': timeframe,
        'count': len(records),
        'latest': latest,
        'data': records,
        'source': source  # Indicate data source
    }


@router.get('/api/analysis', response_class=JSONResponse)
async def api_analysis(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Return technical analysis of market context.
    
    Provides comprehensive technical analysis including:
    - Trend direction and strength
    - RSI condition (overbought/oversold/neutral)
    - Support and resistance levels
    - Price action patterns
    - Moving averages
    
    Args:
        symbol: Asset symbol (default: WDO$)
        timeframe: Timeframe string (default: M5)
        limit: Number of candles for analysis (default: 500)
        
    Returns:
        JSON response with technical analysis data
        
    Raises:
        HTTPException: If limit is out of valid range or no data available
    """
    if limit <= 0 or limit > MAX_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f'limit deve estar entre 1 e {MAX_LIMIT}'
        )
    
    # Get OHLC data (will use database when available)
    df = OHLCVRepository.get_latest_candles(db, symbol, timeframe, limit)
    
    if df.empty or len(df) < limit:
        # Fallback to provider
        df = get_recent_ohlc(symbol, timeframe, limit)
        
        # Save to database
        if not df.empty:
            try:
                OHLCVRepository.save_dataframe(db, df, symbol, timeframe)
            except Exception as e:
                logger.error(f"Failed to save to database: {e}")
    
    if df.empty:
        raise HTTPException(
            status_code=503,
            detail='Dados de mercado não disponíveis no momento'
        )
    
    # Perform technical analysis
    try:
        context = market_analyzer.analyze(df)
        
        # Save analysis to database
        timestamp = df.index[-1]
        try:
            MarketAnalysisRepository.save_analysis(
                db, symbol, timeframe, timestamp, context, len(df)
            )
        except Exception as e:
            logger.error(f"Failed to save analysis to database: {e}")
        
        # Add metadata
        response = {
            'symbol': symbol,
            'timeframe': timeframe,
            'candles_analyzed': len(df),
            'timestamp': timestamp.isoformat(),
            'analysis': context
        }
        
        return response
    
    except Exception as exc:
        logger.error(f"Error analyzing market: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f'Erro na análise técnica: {str(exc)}'
        )


@router.get('/api/combined', response_class=JSONResponse)
async def api_combined(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT
) -> Dict[str, Any]:
    """Return combined OHLC data and technical analysis.
    
    Convenience endpoint that combines /api/ohlc and /api/analysis
    responses into a single request, reducing client-side calls.
    
    Args:
        symbol: Asset symbol (default: WDO$)
        timeframe: Timeframe string (default: M5)
        limit: Number of candles (default: 500)
        
    Returns:
        JSON response with both OHLC data and technical analysis
        
    Raises:
        HTTPException: If limit is out of valid range or no data available
    """
    if limit <= 0 or limit > MAX_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f'limit deve estar entre 1 e {MAX_LIMIT}'
        )
    
    # Get OHLC data
    df = get_recent_ohlc(symbol, timeframe, limit)
    
    if df.empty:
        raise HTTPException(
            status_code=503,
            detail='Dados de mercado não disponíveis no momento'
        )
    
    # Build OHLC records
    records: List[Dict[str, Any]] = []
    for ts, row in df.iterrows():
        records.append({
            'time': ts.isoformat(),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row['volume']) if 'volume' in row and not pd.isna(row['volume']) else 0
        })
    
    # Perform technical analysis
    try:
        context = market_analyzer.analyze(df)
        
        # Combined response
        response = {
            'symbol': symbol,
            'timeframe': timeframe,
            'count': len(records),
            'timestamp': df.index[-1].isoformat() if not df.empty else None,
            'latest': records[-1] if records else None,
            'ohlc': records,
            'analysis': context
        }
        
        return response
    
    except Exception as exc:
        logger.error(f"Error in combined endpoint: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f'Erro ao processar dados: {str(exc)}'
        )


@router.get('/', response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Serve main dashboard HTML page with embedded Bokeh chart.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Rendered HTML template with Bokeh chart components
    """
    import time
    
    # Fetch OHLC data
    df = get_recent_ohlc(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, DEFAULT_LIMIT)
    
    # Convert to list of dicts for Bokeh
    ohlc_data = []
    for ts, row in df.iterrows():
        ohlc_data.append({
            'time': ts.isoformat(),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row['volume']) if 'volume' in row and not pd.isna(row['volume']) else 0
        })
    
    # Generate Bokeh chart components
    script, div = create_dashboard_chart(ohlc_data)
    
    return templates.TemplateResponse('index.html', {
        'request': request,
        'symbol': DEFAULT_SYMBOL,
        'timeframe': DEFAULT_TIMEFRAME,
        'limit': DEFAULT_LIMIT,
        'version': int(time.time()),
        'bokeh_script': script,
        'bokeh_div': div
    })


app.include_router(router)


if __name__ == '__main__':  # Dev convenience
    import uvicorn
    from newapp.configs.config import HOST, PORT, RELOAD
    
    uvicorn.run(
        'newapp.main:app',
        host=HOST,
        port=PORT,
        reload=RELOAD
    )
