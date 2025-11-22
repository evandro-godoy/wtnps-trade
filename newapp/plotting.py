"""
Bokeh plotting module for WTNPS Trade dashboard.
Replicates backtesting.py chart style with vertical subplots.
"""
from typing import List, Dict, Any
import pandas as pd
import numpy as np

from bokeh.plotting import figure
from bokeh.layouts import gridplot
from bokeh.models import ColumnDataSource, HoverTool, CrosshairTool, Range1d
from bokeh.embed import components
from bokeh.colors.named import lime as BULL_COLOR, tomato as BEAR_COLOR


def create_dashboard_chart(ohlc_data: List[Dict[str, Any]]) -> tuple[str, str]:
    """
    Create Bokeh chart with candlestick + volume subplots.
    
    Args:
        ohlc_data: List of OHLC dicts with keys: time, open, high, low, close, volume
        
    Returns:
        tuple[str, str]: (script, div) HTML components for embedding
    """
    if not ohlc_data:
        return "", "<div>No data available</div>"
    
    # Convert to DataFrame for processing
    df = pd.DataFrame(ohlc_data)
    df['time'] = pd.to_datetime(df['time'])
    df['index'] = range(len(df))
    df['inc'] = (df['close'] >= df['open']).astype(int).astype(str)
    
    # Create ColumnDataSource
    source = ColumnDataSource(df)
    
    # Shared x_range for synchronized zooming (show last 100 candles by default)
    visible_candles = min(100, len(df))
    start_idx = max(0, len(df) - visible_candles)
    x_range = Range1d(start=start_idx, end=len(df) - 1)
    
    # Color mapping
    COLORS = [BEAR_COLOR, BULL_COLOR]
    from bokeh.transform import factor_cmap
    inc_cmap = factor_cmap('inc', COLORS, ['0', '1'])
    
    # Create Candlestick Figure (80% height)
    fig_ohlc = figure(
        width=1400,
        height=500,
        x_range=x_range,
        tools="xpan,xwheel_zoom,box_zoom,reset,save",
        active_drag='xpan',
        active_scroll='xwheel_zoom',
        title=f"WDO$ - M5 ({len(df)} candles)"
    )
    
    # OHLC Candlesticks
    fig_ohlc.segment('index', 'high', 'index', 'low', source=source, color="white", line_width=1)
    fig_ohlc.vbar(
        'index', 0.8, 'open', 'close',
        source=source,
        line_color="white",
        fill_color=inc_cmap,
        line_width=1
    )
    
    # Styling
    fig_ohlc.grid.grid_line_alpha = 0.3
    fig_ohlc.xaxis.visible = False  # Hide x-axis (shown only on volume)
    fig_ohlc.yaxis.axis_label = "Price"
    fig_ohlc.background_fill_color = "#0a0e1a"
    fig_ohlc.border_fill_color = "#1a1f2e"
    
    # Hover tooltip
    hover_ohlc = HoverTool(
        tooltips=[
            ("Time", "@time{%F %H:%M}"),
            ("Open", "@open{0,0.00}"),
            ("High", "@high{0,0.00}"),
            ("Low", "@low{0,0.00}"),
            ("Close", "@close{0,0.00}"),
            ("Volume", "@volume{0,0}")
        ],
        formatters={'@time': 'datetime'},
        mode='vline'
    )
    fig_ohlc.add_tools(hover_ohlc)
    
    # Create Volume Figure (20% height)
    fig_volume = figure(
        width=1400,
        height=150,
        x_range=fig_ohlc.x_range,  # Shared range for sync
        tools="xpan,xwheel_zoom,box_zoom,reset",
        active_drag='xpan',
        active_scroll='xwheel_zoom'
    )
    
    # Volume bars
    fig_volume.vbar(
        'index', 0.8, 'volume',
        source=source,
        color=inc_cmap,
        line_color=None
    )
    
    # Styling
    fig_volume.grid.grid_line_alpha = 0.3
    fig_volume.yaxis.axis_label = "Volume"
    fig_volume.xaxis.axis_label = "Time (candles)"
    fig_volume.background_fill_color = "#0a0e1a"
    fig_volume.border_fill_color = "#1a1f2e"
    
    # Crosshair linking
    crosshair = CrosshairTool(dimensions="both", line_color='lightgrey')
    fig_ohlc.add_tools(crosshair)
    fig_volume.add_tools(crosshair)
    
    # Stack figures vertically
    grid = gridplot(
        [[fig_ohlc], [fig_volume]],
        toolbar_location='right',
        sizing_mode='stretch_width'
    )
    
    # Generate HTML components
    script, div = components(grid)
    return script, div
