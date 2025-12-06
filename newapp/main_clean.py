from fastapi import FastAPI, Request, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from newapp.configs.config import STATIC_DIR, TEMPLATES_DIR, APP_NAME, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, DEFAULT_LIMIT
from newapp.src.data_handler.provider import get_default_provider
from newapp.src.data_handler.hybrid_data_loader import get_hybrid_candles
from newapp.src.database.db import get_db
from newapp.src.ml.legacy_monitor_engine import get_legacy_monitor_engine
from newapp.plotting import create_dashboard_chart
import pandas as pd
import logging

logger = logging.getLogger(__name__)


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
data_provider = get_default_provider()

app = FastAPI(title=f"{APP_NAME} - Clean Home")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_recent_ohlc(
    symbol: str,
    timeframe: str,
    limit: int,
    db: Session = None,
    background_tasks: BackgroundTasks = None
) -> pd.DataFrame:
    """Fetch recent OHLC data using hybrid strategy (DB-first, provider fallback).
    
    Args:
        symbol: Asset symbol
        timeframe: Timeframe string
        limit: Number of candles
        db: Database session (if None, uses provider only)
        background_tasks: FastAPI BackgroundTasks for async persistence
        
    Returns:
        DataFrame with OHLCV data
    """
    try:
        if db is not None:
            # Use hybrid loader (DB-first with async persist)
            df = get_hybrid_candles(db, symbol, timeframe, limit, background_tasks)
            if df.empty:
                logger.warning(f"Hybrid loader returned empty DataFrame for {symbol} {timeframe}")
            return df
        else:
            # Fallback to provider only
            df = data_provider.get_latest_candles(
                ticker=symbol,
                timeframe=timeframe,
                count=limit
            )
            if df.empty:
                logger.warning(f"Provider returned empty DataFrame for {symbol} {timeframe}")
            return df
    except Exception as e:
        logger.error(f"Error fetching OHLC data: {e}")
        return pd.DataFrame()


@app.get("/", response_class=HTMLResponse)
@app.get("/home-clean", response_class=HTMLResponse)
async def home_clean(request: Request):
    return templates.TemplateResponse("home_clean.html", {"request": request})


@app.get("/charts-clean", response_class=HTMLResponse)
async def charts_clean(
    request: Request,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Serve clean charts page with Bokeh candlestick chart.
    Fixed parameters: WDO$, M5, 1500 barras."""
    import time
    
    # Fixed parameters (no longer from query params)
    symbol = "WDO$"
    timeframe = "M5"
    limit = 1500
    
    # Fetch OHLC data using hybrid loader
    df = get_recent_ohlc(symbol, timeframe, limit, db, background_tasks)
    
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
    
    return templates.TemplateResponse('charts_clean.html', {
        'request': request,
        'version': int(time.time()),
        'bokeh_script': script,
        'bokeh_div': div
    })


@app.get("/simulation", response_class=HTMLResponse)
async def simulation(
    request: Request,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Serve simulation page with replay controls and ML predictions."""
    import time
    
    # Fetch OHLC data using hybrid loader
    df = get_recent_ohlc(symbol, timeframe, limit, db, background_tasks)
    
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
    
    return templates.TemplateResponse('charts_simulation.html', {
        'request': request,
        'symbol': symbol,
        'timeframe': timeframe,
        'limit': limit,
        'version': int(time.time()),
        'bokeh_script': script,
        'bokeh_div': div
    })


@app.get("/health", response_class=HTMLResponse)
async def healthcheck():
    return HTMLResponse(content="OK", status_code=200)


@app.get("/api/monitor-predictions")
async def get_monitor_predictions(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    count: int = 10,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Get monitor predictions using EXACT legacy logic.
    
    Returns real predictions matching monitor_ui.py output:
    - Direction (CALL/PUT) based on EMA20
    - Signal (COMPRA/VENDA) mapped from direction
    - Complete technical analysis (RSI, Trend, Patterns, Support/Resistance)
    - Validation status
    """
    from datetime import datetime, timezone
    
    try:
        # Get fresh data from provider
        provider = get_default_provider()
        data = provider.get_latest_candles(ticker=symbol, timeframe=timeframe, count=500)
        
        if data.empty:
            return {
                'predictions': [],
                'latest_candle_time': None,
                'is_market_open': False,
                'error': 'No data available'
            }
        
        # Get latest candle time for market status
        latest_candle_time = data.index[-1]
        latest_candle_time_str = latest_candle_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Check if market is open (last candle within 10 minutes)
        now_utc = datetime.now(timezone.utc)
        if latest_candle_time.tzinfo is None:
            latest_candle_time = latest_candle_time.replace(tzinfo=timezone.utc)
        
        time_diff = (now_utc - latest_candle_time).total_seconds()
        is_market_open = time_diff < 600  # 10 minutes
        
        # === Get prediction using LEGACY MONITOR ENGINE ===
        engine = get_legacy_monitor_engine()
        
        # Generate predictions for last N completed candles
        predictions = []
        
        # Use sliding window to get last N predictions
        for i in range(max(1, len(data) - count), len(data)):
            subset = data.iloc[:i+1]
            pred_result = engine.predict_on_candle(subset, symbol, timeframe)
            
            if pred_result:
                # Format for frontend (matching legacy monitor output)
                timestamp_str = pred_result['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(pred_result['timestamp'], 'strftime') else str(pred_result['timestamp'])
                
                # Probability text
                prob_pct = round(pred_result['probability'] * 100, 2)
                
                # Message formatting (like legacy monitor)
                if prob_pct >= 65:
                    # ALERT message
                    target = pred_result['resistance'] if pred_result['direction'] == 'CALL' else pred_result['support']
                    validation_icon = "✅" if pred_result['signal_valid'] else "⚠️"
                    message = (
                        f"{validation_icon} SINAL {pred_result['direction']} ({prob_pct:.1f}%) | "
                        f"Tendência: {pred_result['trend']} ({pred_result['trend_strength']}) | "
                        f"Padrão: {pred_result['pattern']} | "
                        f"Alvo: {target:.2f}"
                    )
                elif prob_pct >= 55:
                    # INFO message
                    message = (
                        f"📊 Prob. Moderada ({prob_pct:.1f}%) | "
                        f"Tendência: {pred_result['trend']} | "
                        f"RSI: {pred_result['rsi']:.0f} ({pred_result['rsi_condition']})"
                    )
                else:
                    # TICK message
                    message = f"Candle processado | Tendência: {pred_result['trend']}"
                
                predictions.append({
                    'timestamp': timestamp_str,
                    'tipo': pred_result['signal'],
                    'direction': pred_result['direction'],
                    'preco': int(pred_result['price']),
                    'prob_ml': prob_pct,
                    'mensagem': message,
                    'indicators': {
                        'close': pred_result['price'],
                        'ema_9': pred_result['ema_9'],
                        'ema_20': pred_result['ema_20'],
                        'sma_20': pred_result['sma_20'],
                        'sma_50': pred_result['sma_50'],
                        'rsi_14': pred_result['rsi']
                    },
                    'analysis': {
                        'trend': pred_result['trend'],
                        'trend_strength': pred_result['trend_strength'],
                        'rsi': pred_result['rsi'],
                        'rsi_condition': pred_result['rsi_condition'],
                        'support': pred_result['support'],
                        'resistance': pred_result['resistance'],
                        'pattern': pred_result['pattern'],
                        'signal_valid': pred_result['signal_valid']
                    }
                })
        
        # Return last N predictions
        results = predictions[-count:] if predictions else []
        
        return {
            'predictions': results,
            'latest_candle_time': latest_candle_time_str,
            'is_market_open': is_market_open,
            'source': 'legacy_monitor_engine',
            'error': None
        }
        
    except Exception as e:
        logger.error(f"Error in monitor predictions: {e}", exc_info=True)
        return {
            'predictions': [],
            'latest_candle_time': None,
            'is_market_open': False,
            'error': str(e),
            'source': 'legacy_monitor_engine'
        }
