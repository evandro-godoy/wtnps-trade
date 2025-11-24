from datetime import datetime, timedelta
import asyncio

from newapp.src.backtest.engine import BacktestEngine, BacktestConfig
from newapp.src.database import get_db
from newapp.main import _map_timeframe_to_int

async def main():
    db = next(get_db())
    cfg = BacktestConfig(
        symbol='WDO$',
        timeframe_int=_map_timeframe_to_int('M5'),
        timeframe_str='M5',
        start_date=datetime.utcnow() - timedelta(days=2),
        end_date=datetime.utcnow(),
        initial_capital=100000.0,
        position_size=1.0,
    )
    engine = BacktestEngine(db, cfg)

    async def cb(snap: dict):
        t = snap.get('type')
        if t == 'progress':
            print(f"PROG {snap['index']}/{snap['total']} {snap['signal']} price={snap['price']:.2f}")
        elif t == 'complete':
            print(f"DONE buy={snap['buy_signals']} sell={snap['sell_signals']} candles={snap['total_candles']}")

    await engine.run_backtest_stream(cb, update_interval=200)

if __name__ == '__main__':
    asyncio.run(main())
