import hashlib, sqlite3, pandas as pd
path = 'wtnps_trade.db'
conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
cur = conn.cursor()
cur.execute("SELECT count(*) FROM assets_rates WHERE symbol='WDO$' AND timeframe=5")
row_count = cur.fetchone()[0]
df = pd.read_sql_query("SELECT timestamp, open, high, low, close, ema_9, sma_20, sma_50, sma_200 FROM assets_rates WHERE symbol='WDO$' AND timeframe=5 ORDER BY timestamp", conn, parse_dates=['timestamp'])
conn.close()
hash_before = hashlib.sha256(df[['open','high','low','close']].to_csv(index=False).encode()).hexdigest()
null_counts = {c:int(((df[c].isna()) | (df[c]==0)).sum()) for c in ['ema_9','sma_20','sma_50','sma_200']}
print('ROW_COUNT_BEFORE', row_count)
print('OHLC_HASH_BEFORE', hash_before)
print('INDICATOR_ZERO_COUNTS_BEFORE', null_counts)
print('HEAD_BEFORE')
print(df.head(3).to_string())