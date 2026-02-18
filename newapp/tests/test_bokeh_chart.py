"""
Test Bokeh chart generation in isolation
"""
import sys
sys.path.insert(0, r'c:\projects\wtnps-trade')

from newapp.plotting import create_dashboard_chart

# Mock OHLC data
mock_data = [
    {
        'time': '2025-11-22T10:00:00',
        'open': 100.0,
        'high': 101.0,
        'low': 99.5,
        'close': 100.5,
        'volume': 1000
    },
    {
        'time': '2025-11-22T10:05:00',
        'open': 100.5,
        'high': 102.0,
        'low': 100.0,
        'close': 101.5,
        'volume': 1500
    }
]

try:
    script, div = create_dashboard_chart(mock_data)
    print("✅ Bokeh chart generation SUCCESS")
    print(f"Script length: {len(script)} chars")
    print(f"Div length: {len(div)} chars")
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
