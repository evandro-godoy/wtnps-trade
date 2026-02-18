"""
Bokeh plotting module for WTNPS Trade dashboard.
Replicates notebook general_analysis.ipynb chart style with:
- Candlesticks + Moving Averages (EMA 9, SMA 20, SMA 50)
- Volume subplot
- RSI subplot with reference lines
"""
from typing import List, Dict, Any
import pandas as pd
import numpy as np

from bokeh.plotting import figure
from bokeh.layouts import gridplot
from bokeh.models import ColumnDataSource, HoverTool, CrosshairTool, Range1d, Span
from bokeh.embed import components
from bokeh.colors.named import lime as BULL_COLOR, tomato as BEAR_COLOR
from bokeh.transform import factor_cmap


def create_dashboard_chart(ohlc_data: List[Dict[str, Any]]) -> tuple[str, str]:
    """
    Create Bokeh chart with candlestick + MA + volume + RSI subplots.
    Matches notebook general_analysis.ipynb implementation.
    
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
    
    # Format timestamp for display
    df['time_str'] = df['time'].dt.strftime('%Y-%m-%d %H:%M')
    
    # Calculate Moving Averages
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    
    # Calculate RSI (14 periods)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Create ColumnDataSource
    source = ColumnDataSource(df)
    
    # Shared x_range for synchronized zooming
    x_range = Range1d(start=0, end=len(df) - 1)
    
    # Color mapping
    COLORS = [BEAR_COLOR, BULL_COLOR]
    inc_cmap = factor_cmap('inc', COLORS, ['0', '1'])
    
    # ========== FIGURE 1: CANDLESTICK + MOVING AVERAGES ==========
    fig_candle = figure(
        sizing_mode='stretch_width',
        height=350,
        x_range=x_range,
        tools="pan,wheel_zoom,box_zoom,reset,save",
        active_drag='pan',
        active_scroll='wheel_zoom',
        title="WDO$ - M5 - 1500 barras"
    )
    
    # Candlesticks: wicks (high-low)
    fig_candle.segment('index', 'high', 'index', 'low', 
                      source=source, color="white", line_width=1)
    
    # Candlesticks: bodies (open-close)
    fig_candle.vbar(
        'index', 0.8, 'open', 'close',
        source=source,
        line_color="white",
        fill_color=inc_cmap,
        line_width=1
    )
    
    # Moving Averages
    fig_candle.line('index', 'ema_9', source=source, 
                   color="#f33012", line_width=2, alpha=0.8, 
                   legend_label="EMA 9")
    
    fig_candle.line('index', 'sma_20', source=source, 
                   color="#3439db", line_width=2, alpha=0.7,
                   legend_label="SMA 20")
    
    fig_candle.line('index', 'sma_50', source=source, 
                   color="#bf751a", line_width=2, alpha=0.6, 
                   line_dash='dashed', legend_label="SMA 50")
    
    # Styling
    fig_candle.grid.grid_line_alpha = 0.3
    fig_candle.xaxis.visible = False
    fig_candle.yaxis.axis_label = "Preço"
    fig_candle.background_fill_color = "#0a0e1a"
    fig_candle.border_fill_color = "#1a1f2e"
    fig_candle.title.text_color = "white"
    fig_candle.title.text_font_size = "14pt"
    
    # Legend styling
    fig_candle.legend.location = "top_left"
    fig_candle.legend.background_fill_alpha = 0.7
    fig_candle.legend.background_fill_color = "#1a1f2e"
    fig_candle.legend.label_text_color = "white"
    
    # Hover tooltip
    hover_candle = HoverTool(
        tooltips=[
            ("Data/Hora", "@time_str"),
            ("Open", "@open{0,0.00}"),
            ("High", "@high{0,0.00}"),
            ("Low", "@low{0,0.00}"),
            ("Close", "@close{0,0.00}"),
            ("Volume", "@volume{0,0}")
        ],
        mode='vline'
    )
    fig_candle.add_tools(hover_candle)
    
    # ========== FIGURE 2: VOLUME ==========
    fig_volume = figure(
        sizing_mode='stretch_width',
        height=100,
        x_range=fig_candle.x_range,
        tools="pan,wheel_zoom,box_zoom,reset",
        active_drag='pan',
        active_scroll='wheel_zoom'
    )
    
    # Volume bars
    fig_volume.vbar(
        'index', 0.8, 'volume',
        source=source,
        color=inc_cmap,
        line_color=None,
        alpha=0.6
    )
    
    # Styling
    fig_volume.grid.grid_line_alpha = 0.3
    fig_volume.yaxis.axis_label = "Volume"
    fig_volume.xaxis.visible = False
    fig_volume.background_fill_color = "#0a0e1a"
    fig_volume.border_fill_color = "#1a1f2e"
    
    # ========== FIGURE 3: RSI ==========
    fig_rsi = figure(
        sizing_mode='stretch_width',
        height=120,
        x_range=fig_candle.x_range,
        tools="pan,wheel_zoom,box_zoom,reset",
        active_drag='pan',
        active_scroll='wheel_zoom',
        y_range=Range1d(0, 100)
    )
    
    # RSI line
    fig_rsi.line('index', 'rsi', source=source, 
                color='#1abc9c', line_width=2, legend_label="RSI (14)")
    
    # RSI area fill
    fig_rsi.varea('index', 0, 'rsi', source=source, 
                 color='#1abc9c', alpha=0.2)
    
    # Reference lines (70 = overbought, 30 = oversold, 50 = neutral)
    hline_70 = Span(location=70, dimension='width', line_color='red', 
                   line_dash='dashed', line_width=1, line_alpha=0.5)
    hline_30 = Span(location=30, dimension='width', line_color='green', 
                   line_dash='dashed', line_width=1, line_alpha=0.5)
    hline_50 = Span(location=50, dimension='width', line_color='gray', 
                   line_dash='dotted', line_width=1, line_alpha=0.3)
    
    fig_rsi.add_layout(hline_70)
    fig_rsi.add_layout(hline_30)
    fig_rsi.add_layout(hline_50)
    
    # Styling
    fig_rsi.grid.grid_line_alpha = 0.3
    fig_rsi.yaxis.axis_label = "RSI"
    fig_rsi.xaxis.axis_label = "Candles"
    fig_rsi.background_fill_color = "#0a0e1a"
    fig_rsi.border_fill_color = "#1a1f2e"
    fig_rsi.legend.location = "top_left"
    fig_rsi.legend.background_fill_alpha = 0.7
    fig_rsi.legend.background_fill_color = "#1a1f2e"
    fig_rsi.legend.label_text_color = "white"
    
    # Crosshair linking (synchronize cursor between charts)
    crosshair = CrosshairTool(dimensions="both", line_color='lightgrey', line_alpha=0.5)
    for fig in [fig_candle, fig_volume, fig_rsi]:
        fig.add_tools(crosshair)
    
    # Stack figures vertically
    grid = gridplot(
        [[fig_candle], [fig_volume], [fig_rsi]],
        toolbar_location='right',
        sizing_mode='stretch_width'
    )
    
    # Generate HTML components
    script, div = components(grid)
    return script, div
