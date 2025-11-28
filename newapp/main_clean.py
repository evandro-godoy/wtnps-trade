from fastapi import FastAPI, Request, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from newapp.configs.config import STATIC_DIR, TEMPLATES_DIR, APP_NAME, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, DEFAULT_LIMIT
from newapp.src.data_handler.provider import get_default_provider
from newapp.src.data_handler.hybrid_data_loader import get_hybrid_candles
from newapp.src.database.db import get_db
from newapp.src.ml.prediction_engine import get_prediction_engine
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
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Serve clean charts page with only the Bokeh candlestick chart."""
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
    
    return templates.TemplateResponse('charts_clean.html', {
        'request': request,
        'symbol': symbol,
        'timeframe': timeframe,
        'limit': limit,
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


@app.get("/api/ml-predictions")
async def get_ml_predictions(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    count: int = 10
):
    """Get ML predictions from trained models (LSTM/DRL).
    
    Returns real predictions using legacy strategy framework.
    """
    try:
        engine = get_prediction_engine()
        predictions_raw = engine.predict_latest(
            symbol=symbol,
            timeframe=timeframe,
            count=count
        )
        
        # Format for frontend
        predictions = []
        for pred in predictions_raw:
            timestamp = pred['timestamp']
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(timestamp, 'strftime') else str(timestamp)
            
            # Extract technical indicators
            indicators = pred.get('indicators', {})
            
            # Determine trend
            close = indicators.get('close', 0)
            ema9 = indicators.get('ema_9', 0)
            sma20 = indicators.get('sma_20', 0)
            
            if ema9 > sma20 and close > ema9:
                trend = 'ALTA'
            elif ema9 < sma20 and close < ema9:
                trend = 'BAIXA'
            else:
                trend = 'LATERAL'
            
            # Get probability
            prob_ml = round(pred['probability'] * 100, 1)
            
            # Build message like legacy monitor
            signal = pred['signal']
            if prob_ml >= 65:
                # ALERT - Critical message with trend
                message = f"🚨 SINAL {signal} ({prob_ml:.1f}%) | Tendência: {trend}"
            elif prob_ml >= 55:
                # INFO - Moderate probability
                rsi = indicators.get('rsi_14', 0)
                message = f"📊 Prob. Moderada ({prob_ml:.1f}%) | Tendência: {trend} | RSI: {rsi:.0f}"
            else:
                # TICK - Normal candle
                message = f"Candle processado | Tendência: {trend}"
            
            predictions.append({
                'timestamp': timestamp_str,
                'tipo': signal,
                'ai_signal': pred.get('ai_signal', signal),
                'preco': int(pred['price']),
                'prob_ml': prob_ml,
                'mensagem': message,
                'indicators': indicators,
                'trend': trend
            })
        
        return {'predictions': predictions, 'source': 'ml_engine'}
        
    except Exception as e:
        logger.error(f"Error generating ML predictions: {e}", exc_info=True)
        return {'predictions': [], 'error': str(e)}


@app.get("/api/monitor-predictions")
async def get_monitor_predictions(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    count: int = 10,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Get recent monitor predictions with market status."""
    from datetime import datetime, timezone
    
    # Get fresh data from provider
    provider = get_default_provider()
    try:
        data = provider.get_latest_candles(ticker=symbol, timeframe=timeframe, count=500)
        
        if data.empty:
            return {
                'predictions': [],
                'latest_candle_time': None,
                'is_market_open': False,
                'error': 'No data available'
            }
        
        # Get latest candle time
        latest_candle_time = data.index[-1]
        latest_candle_time_str = latest_candle_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Check if market is open (last candle within 10 minutes)
        now_utc = datetime.now(timezone.utc)
        if latest_candle_time.tzinfo is None:
            latest_candle_time = latest_candle_time.replace(tzinfo=timezone.utc)
        
        time_diff = (now_utc - latest_candle_time).total_seconds()
        is_market_open = time_diff < 600  # 10 minutes
        
        # Get ML predictions
        ml_result = await get_ml_predictions(symbol, timeframe, count=count)
        
        # Return with market status
        return {
            'predictions': ml_result.get('predictions', []),
            'latest_candle_time': latest_candle_time_str,
            'is_market_open': is_market_open,
            'source': ml_result.get('source', 'ml_engine'),
            'error': ml_result.get('error')
        }
        
    except Exception as e:
        logger.error(f"Error in monitor predictions: {e}", exc_info=True)
        return {
            'predictions': [],
            'latest_candle_time': None,
            'is_market_open': False,
            'error': str(e)
        }
    
    # Fallback to mock if ML engine fails
    logger.warning(f"ML predictions failed, using fallback: {ml_result.get('error')}")
    
    try:
        from datetime import datetime, timedelta
        import random
        
        df = get_recent_ohlc(symbol, timeframe, 20, db, background_tasks)
        
        if df.empty:
            return {'predictions': []}
        
        predictions = []
        
        # Get last 10 candles for predictions
        last_candles = df.tail(10)
        
        for idx, (timestamp, row) in enumerate(last_candles.iterrows()):
            # Use actual price data
            close_price = float(row['close'])
            
            # Simulate signal based on simple logic (for demonstration)
            if idx > 0:
                prev_close = float(last_candles.iloc[idx-1]['close'])
                price_change = close_price - prev_close
                
                # Simple signal logic: uptrend = COMPRA, downtrend = VENDA
                if price_change > 0:
                    signal = 'COMPRA' if random.random() > 0.3 else 'HOLD'
                    prob = random.uniform(0.65, 0.92)
                elif price_change < 0:
                    signal = 'VENDA' if random.random() > 0.3 else 'HOLD'
                    prob = random.uniform(0.65, 0.92)
                else:
                    signal = 'HOLD'
                    prob = random.uniform(0.45, 0.60)
            else:
                signal = random.choice(['COMPRA', 'VENDA', 'HOLD'])
                prob = random.uniform(0.55, 0.85)
            
            # Format timestamp (convert to local time if needed)
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            
            predictions.append({
                'timestamp': timestamp_str,
                'tipo': signal,
                'preco': int(close_price),
                'prob_ml': round(prob * 100, 1),
                'mensagem': f'Sinal {signal} detectado' if signal != 'HOLD' else 'Aguardando confirmação'
            })
        
        return {'predictions': predictions}
        
    except Exception as e:
        print(f"Error generating predictions: {e}")
        return {'predictions': []}
