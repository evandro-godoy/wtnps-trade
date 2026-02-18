from datetime import datetime, timedelta
import logging
import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path (so 'newapp' package resolves when running directly)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from newapp.src.database import init_database, get_db
from newapp.src.database.repository import AssetsRatesRepository
from newapp.src.backtest.engine import BacktestEngine, BacktestConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')

SYMBOL = 'WDO$'
TF_STR = 'M5'
TF_SECONDS = 5 * 60  # must match ingestion/storage

init_database()

db = next(get_db())

all_df = AssetsRatesRepository.get_all_rates(db, SYMBOL, TF_SECONDS)
if all_df.empty:
    print(f'NO_DATA: assets_rates empty for {SYMBOL} {TF_STR}')
    raise SystemExit(0)

min_ts = all_df.index.min()
max_ts = all_df.index.max()
print(f'RANGE_INFO: {SYMBOL} {TF_STR} candles={len(all_df)} first={min_ts} last={max_ts}')

# Backtest window selection
end_dt = max_ts
start_candidate = end_dt - timedelta(days=7)
start_dt = start_candidate if start_candidate >= min_ts else (end_dt - timedelta(days=1))
print(f'BT_WINDOW: start={start_dt} end={end_dt}')

cfg = BacktestConfig(
    symbol=SYMBOL,
    timeframe_int=TF_SECONDS,
    timeframe_str=TF_STR,
    start_date=start_dt,
    end_date=end_dt,
    initial_capital=100_000.0,
    position_size=1.0,
    strategy='ema_crossover',
    use_ml=False,
)
engine = BacktestEngine(db, cfg)
summary = engine.run_backtest()
print('BT_SUMMARY:', summary)

# Streaming smoke test (3 days)
slice_end = max_ts
slice_start = slice_end - timedelta(days=3)
cfg_stream = BacktestConfig(
    symbol=SYMBOL,
    timeframe_int=TF_SECONDS,
    timeframe_str=TF_STR,
    start_date=slice_start,
    end_date=slice_end,
    initial_capital=100_000.0,
    position_size=1.0,
    strategy='ema_crossover',
    use_ml=False,
)
engine_stream = BacktestEngine(db, cfg_stream)

stream_events = []
async def collector(ev: dict):
    stream_events.append(ev)

async def run_stream():
    await engine_stream.run_backtest_stream(collector, update_interval=100)

asyncio.run(run_stream())
print('STREAM_EVENTS_COUNT:', len(stream_events))
# Print sample events
for ev in (stream_events[:3] + stream_events[-3:]):
    print('STREAM_EVENT:', ev)
