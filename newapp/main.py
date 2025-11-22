"""Standalone FastAPI web application providing a demonstrative
interface for technical analysis results of WDO$ using existing data
provider logic.

Features:
- GET / -> HTML page with latest OHLC (WDO$ M5) and candlestick chart (last 500 bars)
- GET /api/ohlc -> JSON OHLC data service with fallback strategies

The application attempts to use MetaTrader5 provider; if unavailable it
falls back to cached parquet or synthetic data generation.
"""
from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime, timedelta
import random

import pandas as pd
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

try:
    from src.data_handler.provider import MetaTraderProvider  # type: ignore
    import MetaTrader5 as mt5  # type: ignore
except Exception:  # MetaTrader might not be installed in cloud env
    MetaTraderProvider = None  # type: ignore
    mt5 = None  # type: ignore

from pathlib import Path
from src.utils.logger import logger

APP_ROOT = Path(__file__).parent
CACHE_DIR = Path(__file__).parent.parent / '.cache_data'

app = FastAPI(title="WTNPS Trade Demo UI", version="0.1.0")
router = APIRouter()

# Static & templates
app.mount("/static", StaticFiles(directory=str(APP_ROOT / 'static')), name="static")
templates = Jinja2Templates(directory=str(APP_ROOT / 'templates'))

SYMBOL = "WDO$"
TIMEFRAME_STR = "M5"
LIMIT = 500

# Mapping timeframe string to MT5 constant (local copy for decoupling)
MT5_TIMEFRAME_MAP: Dict[str, Any] = {
    "M1": getattr(mt5, 'TIMEFRAME_M1', None) if mt5 else None,
    "M5": getattr(mt5, 'TIMEFRAME_M5', None) if mt5 else None,
    "M15": getattr(mt5, 'TIMEFRAME_M15', None) if mt5 else None,
    "M30": getattr(mt5, 'TIMEFRAME_M30', None) if mt5 else None,
    "H1": getattr(mt5, 'TIMEFRAME_H1', None) if mt5 else None,
    "H4": getattr(mt5, 'TIMEFRAME_H4', None) if mt5 else None,
    "D1": getattr(mt5, 'TIMEFRAME_D1', None) if mt5 else None,
}


def _generate_synthetic(limit: int) -> pd.DataFrame:
    """Generate synthetic OHLC data as final fallback (random walk)."""
    base_price = 100000.0
    rows: List[Dict[str, Any]] = []
    current = base_price
    now = datetime.utcnow()
    for i in range(limit):
        ts = now - timedelta(minutes=5 * (limit - i))
        change = random.uniform(-50, 50)
        open_price = current
        close_price = max(10.0, open_price + change)
        high_price = max(open_price, close_price) + random.uniform(0, 30)
        low_price = min(open_price, close_price) - random.uniform(0, 30)
        volume = random.randint(500, 5000)
        rows.append({
            'time': ts,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': volume
        })
        current = close_price
    df = pd.DataFrame(rows).set_index('time')
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def _load_cached(limit: int) -> pd.DataFrame | None:
    """Attempt to load cached parquet for M5 WDO$ if available."""
    if not CACHE_DIR.exists():
        return None
    # Pattern similar to provider naming: MT5_WDO__M5_* ; ticker '$' removed
    candidates = sorted([p for p in CACHE_DIR.glob('MT5_WDO__M5_*.parquet')])
    if not candidates:
        return None
    latest = candidates[-1]
    try:
        df = pd.read_parquet(latest)
        if not isinstance(df.index, pd.DatetimeIndex):
            return None
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        df = df.tail(limit)
        return df
    except Exception as exc:
        logger.warning(f"Falha ao carregar cache {latest}: {exc}")
        return None


def _fetch_mt5(symbol: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    """Fetch data via MetaTraderProvider if available and connected."""
    if MetaTraderProvider is None or mt5 is None:
        return None
    timeframe_const = MT5_TIMEFRAME_MAP.get(timeframe.upper())
    if timeframe_const is None:
        return None
    try:
        provider = MetaTraderProvider()
        if not provider.is_connected():
            return None
        df = provider.get_latest_candles(symbol.replace('$',''), timeframe_const, limit)
        if df is None or df.empty:
            return None
        return df.tail(limit)
    except Exception as exc:
        logger.warning(f"MT5 fetch falhou: {exc}")
        return None


def get_recent_ohlc(symbol: str = SYMBOL, timeframe: str = TIMEFRAME_STR, limit: int = LIMIT) -> pd.DataFrame:
    """Retrieve recent OHLC bars using provider, cache or synthetic fallback."""
    # Try MT5
    df = _fetch_mt5(symbol, timeframe, limit)
    if df is not None:
        return df
    # Try cache
    cached = _load_cached(limit)
    if cached is not None:
        logger.info("Usando dados de cache para OHLC demonstrativo.")
        return cached
    # Synthetic
    logger.info("Usando dados sintéticos (fallback) para OHLC demonstrativo.")
    return _generate_synthetic(limit)


@router.get('/api/ohlc', response_class=JSONResponse)
async def api_ohlc(symbol: str = SYMBOL, timeframe: str = TIMEFRAME_STR, limit: int = LIMIT) -> Dict[str, Any]:
    """Return OHLC data in JSON format for chart rendering."""
    if limit <= 0 or limit > 5000:
        raise HTTPException(status_code=400, detail='limit fora do intervalo permitido')
    df = get_recent_ohlc(symbol, timeframe, limit)
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
    return {'symbol': symbol, 'timeframe': timeframe, 'count': len(records), 'latest': latest, 'data': records}


@router.get('/', response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Serve main dashboard HTML page."""
    return templates.TemplateResponse('index.html', {'request': request, 'symbol': SYMBOL, 'timeframe': TIMEFRAME_STR, 'limit': LIMIT})


app.include_router(router)

if __name__ == '__main__':  # Dev convenience
    import uvicorn
    uvicorn.run('newapp.main:app', host='0.0.0.0', port=8100, reload=True)
