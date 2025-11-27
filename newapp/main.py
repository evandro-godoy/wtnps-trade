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
import asyncio
from datetime import datetime, timezone

import pandas as pd
from fastapi import FastAPI, APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
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
    AssetsRatesRepository,
)
from newapp.src.live.monitor_engine import RealtimeMarketMonitor
from newapp.src.backtest.engine import BacktestEngine, BacktestConfig
from newapp.src.database.models import BacktestRun, BacktestTrade
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

# Monitor instances (global state for WebSocket streaming)
active_monitors: Dict[str, RealtimeMarketMonitor] = {}
websocket_connections: List[WebSocket] = []

class MonitorManager:
    """Manage active monitor instances and WebSocket connections."""
    
    @staticmethod
    def get_or_create_monitor(ticker: str, timeframe: str) -> RealtimeMarketMonitor:
        """Get existing monitor or create new one."""
        key = f"{ticker}_{timeframe}"
        if key not in active_monitors:
            logger.info(f"Creating new monitor: {ticker} @ {timeframe}")
            monitor = RealtimeMarketMonitor(
                ticker=ticker,
                timeframe_str=timeframe,
                buffer_size=500,
                enable_db_persistence=False
            )
            active_monitors[key] = monitor
        return active_monitors[key]
    
    @staticmethod
    async def broadcast_update(data: Dict[str, Any]) -> None:
        """Broadcast update to all connected WebSocket clients."""
        if not websocket_connections:
            return
        
        # Prepare JSON-serializable data
        message = {
            'timestamp': data['timestamp'].isoformat() if isinstance(data['timestamp'], datetime) else str(data['timestamp']),
            'ticker': data['ticker'],
            'timeframe': data['timeframe'],
            'ohlcv': data['ohlcv'],
            'indicators': data['indicators'],
            'analysis': data['analysis']
        }
        
        # Send to all connections
        dead_connections = []
        for ws in websocket_connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to WebSocket: {e}")
                dead_connections.append(ws)
        
        # Remove dead connections
        for ws in dead_connections:
            websocket_connections.remove(ws)

monitor_manager = MonitorManager()

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
    
    # Map timeframe string to integer (seconds)
    timeframe_map = {
        "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
        "H1": 3600, "H4": 14400, "D1": 86400, "W1": 604800, "MN1": 2592000
    }
    timeframe_int = timeframe_map.get(timeframe.upper(), 300)
    
    # Try database first using AssetsRates (main table)
    df = AssetsRatesRepository.get_rates(db, symbol, timeframe_int, limit)
    source = "Database"
    
    # Fallback to provider if insufficient data
    if df.empty or len(df) < limit:
        logger.info(f"Database has {len(df)} candles, fetching from provider...")
        df = get_recent_ohlc(symbol, timeframe, limit)
        source = "Provider"
        
        # Save to database (AssetsRates table)
        if not df.empty:
            try:
                AssetsRatesRepository.save_rates(db, df, symbol, timeframe_int, timeframe)
                logger.info(f"Saved {len(df)} candles to AssetsRates database")
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

# =============================================================================
# MONITOR ROUTES (Real-time market monitoring)
# =============================================================================

@router.get('/monitor', response_class=HTMLResponse)
async def monitor_page(request: Request) -> HTMLResponse:
    """Real-time market monitor page.

    Displays live market data with WebSocket streaming.
    """
    import time
    return templates.TemplateResponse('monitor.html', {
        'request': request,
        'app_version': APP_VERSION,
        'version': int(time.time())
    })


@router.post('/api/monitor/start')
async def start_monitor(
    ticker: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME
) -> JSONResponse:
    """Start real-time monitoring for a ticker.

    Args:
        ticker: Asset symbol
        timeframe: Timeframe string

    Returns:
        JSON response with status
    """
    try:
        monitor = monitor_manager.get_or_create_monitor(ticker, timeframe)

        if not monitor.running:
            # Register broadcast callback
            monitor.register_callback(
                lambda data: asyncio.create_task(monitor_manager.broadcast_update(data))
            )

            # Start monitor in background
            asyncio.create_task(monitor.start_async())

            logger.info(f"Monitor started: {ticker} @ {timeframe}")
            return JSONResponse({
                'status': 'started',
                'ticker': ticker,
                'timeframe': timeframe,
                'message': f'Monitor started for {ticker} @ {timeframe}'
            })
        else:
            return JSONResponse({
                'status': 'already_running',
                'ticker': ticker,
                'timeframe': timeframe,
                'message': f'Monitor already running for {ticker} @ {timeframe}'
            })

    except Exception as e:
        logger.error(f"Failed to start monitor: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/api/monitor/stop')
async def stop_monitor(
    ticker: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME
) -> JSONResponse:
    """Stop monitoring for a ticker.

    Args:
        ticker: Asset symbol
        timeframe: Timeframe string

    Returns:
        JSON response with status
    """
    key = f"{ticker}_{timeframe}"
    if key in active_monitors:
        monitor = active_monitors[key]
        monitor.stop()
        del active_monitors[key]
        logger.info(f"Monitor stopped: {ticker} @ {timeframe}")
        return JSONResponse({
            'status': 'stopped',
            'ticker': ticker,
            'timeframe': timeframe
        })
    else:
        return JSONResponse({
            'status': 'not_found',
            'ticker': ticker,
            'timeframe': timeframe,
            'message': f'No monitor found for {ticker} @ {timeframe}'
        })


@router.get('/api/monitor/status')
async def monitor_status() -> JSONResponse:
    """Get status of all active monitors.

    Returns:
        JSON response with list of active monitors
    """
    monitors_info = []
    for key, monitor in active_monitors.items():
        state = monitor.get_current_state()
        monitors_info.append(state)

    return JSONResponse({
        'active_monitors': len(active_monitors),
        'websocket_connections': len(websocket_connections),
        'monitors': monitors_info
    })


@app.websocket('/ws/monitor')
async def websocket_monitor(websocket: WebSocket):
    """WebSocket endpoint for real-time market data streaming.

    Clients connect to receive live updates from active monitors.
    """
    await websocket.accept()
    websocket_connections.append(websocket)
    logger.info(f"WebSocket connected. Total connections: {len(websocket_connections)}")

    try:
        # Keep connection alive
        while True:
            # Receive messages from client (heartbeat)
            data = await websocket.receive_text()
            logger.debug(f"Received from WebSocket: {data}")
            await websocket.send_json({'type': 'pong', 'timestamp': datetime.now().isoformat()})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)
        logger.info(f"WebSocket removed. Remaining connections: {len(websocket_connections)}")


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
    """Redirect root to /home for new UI."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url='/home')


@router.get('/home', response_class=HTMLResponse)
async def home_page(request: Request) -> HTMLResponse:
    """Serve home page with sidebar navigation.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Rendered HTML template for home page
    """
    import time
    
    return templates.TemplateResponse('home.html', {
        'request': request,
        'app_version': APP_VERSION,
        'version': int(time.time())
    })


@router.get('/charts', response_class=HTMLResponse)
async def charts_page(
    request: Request,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT
) -> HTMLResponse:
    """Serve charts page with embedded Bokeh candlestick chart.
    
    Args:
        request: FastAPI request object
        symbol: Asset symbol (default: WDO$)
        timeframe: Timeframe string (default: M5)
        limit: Number of candles (default: 500)
        
    Returns:
        Rendered HTML template with Bokeh chart components
    """
    import time
    
    # Validate limit
    if limit > MAX_LIMIT:
        limit = MAX_LIMIT
    
    # Fetch OHLC data
    df = get_recent_ohlc(symbol, timeframe, limit)
    
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
    
    return templates.TemplateResponse('charts.html', {
        'request': request,
        'symbol': symbol,
        'timeframe': timeframe,
        'limit': limit,
        'app_version': APP_VERSION,
        'version': int(time.time()),
        'bokeh_script': script,
        'bokeh_div': div
    })


@router.get('/dashboard', response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Serve legacy dashboard HTML page with embedded Bokeh chart.
    
    DEPRECATED: Use /charts instead. Kept for backward compatibility.
    
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


@router.get('/analysis', response_class=HTMLResponse)
async def analysis_page(request: Request) -> HTMLResponse:
    """Analysis page placeholder.
    
    TODO: Implement comprehensive market analysis interface.
    """
    import time
    return templates.TemplateResponse('home.html', {
        'request': request,
        'app_version': APP_VERSION,
        'version': int(time.time())
    })


@router.get('/backtest', response_class=HTMLResponse)
async def backtest_page(request: Request) -> HTMLResponse:
    """Backtest page with real-time streaming progress."""
    import time
    from datetime import datetime, timedelta
    # Default period: last 30 days ending now (UTC naive for interface)
    end_dt = datetime.now(timezone.utc).replace(microsecond=0, second=0)
    start_dt = end_dt - timedelta(days=30)
    return templates.TemplateResponse('backtest.html', {
        'request': request,
        'app_version': APP_VERSION,
        'version': int(time.time()),
        'default_start': start_dt.isoformat(),
        'default_end': end_dt.isoformat(),
    })

@app.websocket('/ws/backtest')
async def websocket_backtest(websocket: WebSocket):
    """WebSocket endpoint for streaming backtest progress.

    Client protocol:
        1. Connect.
        2. Send JSON: {"action":"start","symbol":"WDO$","timeframe":"M5","start":"YYYY-MM-DDTHH:MM:SS","end":"YYYY-MM-DDTHH:MM:SS","initial_capital":100000,"position_size":1,"update_interval":5}
        3. Receive 'init' with candle list.
        4. Receive 'progress' snapshots and final 'complete'.
    """
    await websocket.accept()  # BREAKPOINT: Primeira linha após botão "Iniciar" pressionado
    try:
        import json
        msg = await websocket.receive_text()  # BREAKPOINT: Recebe parâmetros do frontend
        params = json.loads(msg)
        if params.get('action') != 'start':
            await websocket.send_json({'type': 'error', 'message': 'Expected action=start'})
            return
        symbol = params.get('symbol', DEFAULT_SYMBOL)
        timeframe = params.get('timeframe', DEFAULT_TIMEFRAME)
        start = params.get('start')
        end = params.get('end')
        initial_capital = float(params.get('initial_capital', 100000.0))
        position_size = float(params.get('position_size', 1.0))
        update_interval = int(params.get('update_interval', 5))

        now = datetime.now(timezone.utc)
        # Parse dates and ensure UTC timezone
        if end:
            end_dt = datetime.fromisoformat(end)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
        else:
            end_dt = now
        
        if start:
            start_dt = datetime.fromisoformat(start)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
        else:
            start_dt = end_dt - pd.Timedelta(days=30)
        
        if start_dt >= end_dt:
            await websocket.send_json({'type': 'error', 'message': 'start must be before end'})
            return

        tf_int = _map_timeframe_to_int(timeframe)
        # Create a short-lived DB session
        db_session: Session = next(get_db())
        engine = BacktestEngine(db_session, BacktestConfig(
            symbol=symbol,
            timeframe_int=tf_int,
            timeframe_str=timeframe,
            start_date=start_dt,
            end_date=end_dt,
            initial_capital=initial_capital,
            position_size=position_size,
        ))
        # Preload prices for init message
        engine._load_prices()
        if engine.df is None or engine.df.empty:
            await websocket.send_json({'type': 'error', 'message': 'No data for range'})
            return
        candles = []
        for ts, row in engine.df.iterrows():
            candles.append({
                'time': ts.isoformat(),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close'])
            })
        await websocket.send_json({
            'type': 'init',
            'symbol': symbol,
            'timeframe': timeframe,
            'start': start_dt.isoformat(),
            'end': end_dt.isoformat(),
            'candles': candles,
            'total': len(candles)
        })

        async def send_snapshot(snap: dict):
            try:
                await websocket.send_json(snap)
            except Exception:
                pass
        # Run streaming execution
        await engine.run_backtest_stream(send_snapshot, update_interval=update_interval)
    except WebSocketDisconnect:
        logger.info('Backtest WebSocket disconnected')
    except Exception as e:
        logger.error(f'Backtest WebSocket error: {e}', exc_info=True)
        try:
            await websocket.send_json({'type': 'error', 'message': str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass# =============================================================================
# BACKTEST API
# =============================================================================

def _map_timeframe_to_int(tf: str) -> int:
    """Map timeframe string to persisted integer (seconds).

    The AssetsRates table stores timeframe as seconds (see ingest_historical.py).
    Previous implementation used minutes, causing mismatches and empty queries.
    """
    mapping_seconds = {
        "M1": 60,
        "M5": 5 * 60,
        "M15": 15 * 60,
        "M30": 30 * 60,
        "H1": 60 * 60,
        "H4": 4 * 60 * 60,
        "D1": 24 * 60 * 60,
        "W1": 7 * 24 * 60 * 60,
        "MN1": 30 * 24 * 60 * 60,
    }
    return mapping_seconds.get(tf.upper(), 5 * 60)


@router.post('/api/backtest/run')
async def api_backtest_run(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    start: str | None = None,
    end: str | None = None,
    initial_capital: float = 100_000.0,
    position_size: float = 1.0,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """Execute a backtest over stored historical data.

    Args:
        symbol: Asset symbol
        timeframe: Timeframe string (e.g. M5)
        start: ISO start datetime (default: 90 days atrás)
        end: ISO end datetime (default: now)
        initial_capital: Starting capital
        position_size: Position size (lotes simulados)

    Returns:
        Summary metrics + run_id
    """
    try:
        now = datetime.now(timezone.utc)
        # Parse dates and ensure UTC timezone
        if end:
            end_dt = datetime.fromisoformat(end)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
        else:
            end_dt = now
        
        if start:
            start_dt = datetime.fromisoformat(start)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
        else:
            start_dt = end_dt - pd.Timedelta(days=90)
        
        if start_dt >= end_dt:
            raise HTTPException(status_code=400, detail="start must be before end")

        tf_int = _map_timeframe_to_int(timeframe)
        cfg = BacktestConfig(
            symbol=symbol,
            timeframe_int=tf_int,
            timeframe_str=timeframe,
            start_date=start_dt,
            end_date=end_dt,
            initial_capital=initial_capital,
            position_size=position_size,
        )
        engine = BacktestEngine(db, cfg)
        summary = engine.run_backtest()
        return JSONResponse(summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/api/backtest/run/{run_id}')
async def api_backtest_run_get(run_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    """Retrieve stored backtest run + trades."""
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    trades = (
        db.query(BacktestTrade)
        .filter(BacktestTrade.run_id == run_id)
        .order_by(BacktestTrade.entry_time)
        .all()
    )
    trades_payload = []
    for t in trades:
        trades_payload.append({
            'id': t.id,
            'entry_time': t.entry_time.isoformat(),
            'exit_time': t.exit_time.isoformat() if t.exit_time else None,
            'direction': t.direction,
            'entry_price': t.entry_price,
            'exit_price': t.exit_price,
            'pnl': t.pnl,
            'return_pct': t.return_pct,
            'reason_exit': t.reason_exit,
        })
    payload = {
        'run_id': run.id,
        'symbol': run.symbol,
        'timeframe': run.timeframe,
        'start_date': run.start_date.isoformat(),
        'end_date': run.end_date.isoformat(),
        'strategy': run.strategy,
        'initial_capital': run.initial_capital,
        'final_capital': run.final_capital,
        'net_profit': run.net_profit,
        'total_trades': run.total_trades,
        'wins': run.wins,
        'losses': run.losses,
        'win_rate': run.win_rate,
        'profit_factor': run.profit_factor,
        'max_drawdown': run.max_drawdown,
        'avg_trade_return': run.avg_trade_return,
        'trades': trades_payload,
    }
    return JSONResponse(payload)


@router.get('/settings', response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    """Settings page placeholder.
    
    TODO: Implement settings/configuration interface.
    """
    import time
    return templates.TemplateResponse('home.html', {
        'request': request,
        'app_version': APP_VERSION,
        'version': int(time.time())
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
