"""SQLAlchemy ORM models for wtnps-trade database.

Defines database schema for OHLCV data, technical indicators, and analysis results.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Index,
    BigInteger, Boolean, Text, ForeignKey
)
from sqlalchemy.orm import relationship

from newapp.src.database.db import Base

class AssetsRates(Base):
    """Rates candlestick data table.
    
    Stores Open, High, Low, Close, Volume, Indicators data for various symbols and timeframes.
    """
    __tablename__ = 'assets_rates'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    timeframe = Column(Integer, nullable=False, index=True)
    timeframe_str = Column(String(20), nullable=True, index=True)
    
    
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    tick_volume = Column(Integer, nullable=True)
    volume = Column(Integer, nullable=True)
    spread = Column(Integer, nullable=True)


    support_level = Column(Boolean, default=False, nullable=True)
    resistance_level = Column(Boolean, default=False, nullable=True)

    ema_9 = Column(Float, nullable=True)
    sma_20 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    sma_200 = Column(Float, nullable=True)

    # Metadata (existing legacy schema contains only created_at)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Composite unique constraint
    __table_args__ = (
        Index('idx_symbol_timestamp_timeframe', 'symbol', 'timestamp', 'timeframe', unique=True),
    )
    
    def __repr__(self):
        return f"<AssetsRates(symbol={self.symbol}, timestamp={self.timestamp}, timeframe={self.timeframe}, close={self.close})>"

class OHLCVData(Base):
    """OHLCV candlestick data table.
    
    Stores Open, High, Low, Close, Volume data for various symbols and timeframes.
    """
    __tablename__ = 'ohlcv_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Composite unique constraint
    __table_args__ = (
        Index('idx_symbol_timeframe_timestamp', 'symbol', 'timeframe', 'timestamp', unique=True),
    )
    
    def __repr__(self):
        return f"<OHLCVData(symbol={self.symbol}, timeframe={self.timeframe}, timestamp={self.timestamp}, close={self.close})>"


class TechnicalIndicators(Base):
    """Technical indicators calculated from OHLCV data.
    
    Stores moving averages, RSI, and other technical indicators.
    """
    __tablename__ = 'technical_indicators'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # Moving Averages
    ema_9 = Column(Float, nullable=True)
    sma_20 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    
    # Oscillators
    rsi_14 = Column(Float, nullable=True)
    
    # Trend
    trend_direction = Column(String(10), nullable=True)  # ALTA, BAIXA, LATERAL
    trend_strength = Column(Float, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_ti_symbol_timeframe_timestamp', 'symbol', 'timeframe', 'timestamp', unique=True),
    )
    
    def __repr__(self):
        return f"<TechnicalIndicators(symbol={self.symbol}, timeframe={self.timeframe}, timestamp={self.timestamp})>"


class MarketAnalysis(Base):
    """Market context analysis results.
    
    Stores comprehensive market analysis including support/resistance levels,
    price action patterns, and trading recommendations.
    """
    __tablename__ = 'market_analysis'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # Trend Analysis
    trend_direction = Column(String(10), nullable=True)
    trend_strength = Column(Float, nullable=True)
    
    # Support/Resistance Levels (stored as JSON-like strings)
    support_levels = Column(Text, nullable=True)  # Comma-separated values
    resistance_levels = Column(Text, nullable=True)  # Comma-separated values
    
    # Price Action Patterns (stored as JSON-like strings)
    patterns = Column(Text, nullable=True)  # Comma-separated pattern names
    
    # RSI
    rsi = Column(Float, nullable=True)
    
    # Moving Averages
    ema_9 = Column(Float, nullable=True)
    sma_20 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    
    # Metadata
    candles_analyzed = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_ma_symbol_timeframe_timestamp', 'symbol', 'timeframe', 'timestamp', unique=True),
    )
    
    def __repr__(self):
        return f"<MarketAnalysis(symbol={self.symbol}, timeframe={self.timeframe}, timestamp={self.timestamp})>"


class DataProviderLog(Base):
    """Log of data provider operations.
    
    Tracks which provider was used for data fetching (MT5, Cache, Synthetic).
    """
    __tablename__ = 'data_provider_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    provider_type = Column(String(20), nullable=False)  # MT5, Cache, Synthetic
    candles_count = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Optional metadata
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<DataProviderLog(symbol={self.symbol}, provider={self.provider_type}, candles={self.candles_count})>"


class BacktestRun(Base):
    """Stores summary information for a backtest execution.

    Aggregates performance metrics and references its trades.
    """
    __tablename__ = 'backtest_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    strategy = Column(String(50), nullable=True)
    initial_capital = Column(Float, nullable=True)
    final_capital = Column(Float, nullable=True)
    net_profit = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True)
    wins = Column(Integer, nullable=True)
    losses = Column(Integer, nullable=True)
    win_rate = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    avg_trade_return = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    trades = relationship('BacktestTrade', back_populates='run', cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return (
            f"<BacktestRun(symbol={self.symbol}, timeframe={self.timeframe}, "
            f"period={self.start_date}..{self.end_date})>"
        )


class BacktestTrade(Base):
    """Individual simulated trade for a backtest run."""
    __tablename__ = 'backtest_trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey('backtest_runs.id', ondelete='CASCADE'), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    entry_time = Column(DateTime, nullable=False, index=True)
    exit_time = Column(DateTime, nullable=True, index=True)
    direction = Column(String(4), nullable=False)  # BUY / SELL
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    return_pct = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    reason_exit = Column(String(50), nullable=True)  # STOP / TAKE / SIGNAL / END
    indicators_snapshot = Column(Text, nullable=True)  # JSON serialized indicators for audit/debug
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship('BacktestRun', back_populates='trades')

    def __repr__(self) -> str:
        return (
            f"<BacktestTrade(symbol={self.symbol}, dir={self.direction}, "
            f"entry={self.entry_time}, exit={self.exit_time})>"
        )
