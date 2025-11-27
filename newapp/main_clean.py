from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from newapp.configs.config import STATIC_DIR, TEMPLATES_DIR, APP_NAME, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, DEFAULT_LIMIT
from newapp.src.data_handler.provider import get_default_provider
from newapp.plotting import create_dashboard_chart
import pandas as pd


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
data_provider = get_default_provider()

app = FastAPI(title=f"{APP_NAME} - Clean Home")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_recent_ohlc(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Fetch recent OHLC data using data provider."""
    try:
        df = data_provider.get_latest_candles(
            ticker=symbol,
            timeframe=timeframe,
            count=limit
        )
        return df
    except Exception as e:
        print(f"Error fetching OHLC data: {e}")
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
    limit: int = DEFAULT_LIMIT
):
    """Serve clean charts page with only the Bokeh candlestick chart."""
    import time
    
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
    
    return templates.TemplateResponse('charts_clean.html', {
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
    timeframe: str = DEFAULT_TIMEFRAME
):
    """Get recent monitor predictions based on actual chart data."""
    from datetime import datetime, timedelta
    import random
    
    # Get actual OHLC data to base predictions on
    try:
        df = get_recent_ohlc(symbol, timeframe, 20)
        
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
