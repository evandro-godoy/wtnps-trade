"""Quick script to check database contents."""
import sqlite3

conn = sqlite3.connect('wtnps_trade.db')
cursor = conn.cursor()

# Count OHLCV records
cursor.execute('SELECT COUNT(*) FROM ohlcv_data')
total_ohlcv = cursor.fetchone()[0]
print(f'Total OHLCV records: {total_ohlcv}')

# Group by symbol/timeframe
cursor.execute('SELECT symbol, timeframe, COUNT(*) as count FROM ohlcv_data GROUP BY symbol, timeframe')
for symbol, timeframe, count in cursor.fetchall():
    print(f'  {symbol} {timeframe}: {count} candles')

# Count Market Analysis
cursor.execute('SELECT COUNT(*) FROM market_analysis')
total_analysis = cursor.fetchone()[0]
print(f'\nTotal Market Analysis records: {total_analysis}')

# Latest analysis
if total_analysis > 0:
    cursor.execute('''
        SELECT symbol, timeframe, timestamp, trend_direction, rsi, candles_count 
        FROM market_analysis 
        ORDER BY timestamp DESC 
        LIMIT 3
    ''')
    print('\nLatest analyses:')
    for row in cursor.fetchall():
        print(f'  {row[0]} {row[1]} @ {row[2]} - Trend: {row[3]}, RSI: {row[4]}, Candles: {row[5]}')

conn.close()
print('\n✅ Database check complete')
