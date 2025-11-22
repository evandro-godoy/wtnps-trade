"""Repository pattern for database operations.

Provides high-level CRUD operations for OHLCV data and analysis results.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from newapp.src.database.models import (
    OHLCVData,
    TechnicalIndicators,
    MarketAnalysis,
    DataProviderLog,
)

logger = logging.getLogger(__name__)


class OHLCVRepository:
    """Repository for OHLCV data operations."""
    
    @staticmethod
    def save_dataframe(
        db: Session,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> int:
        """Save DataFrame with OHLCV data to database.
        
        Args:
            db: Database session
            df: DataFrame with columns: time, open, high, low, close, volume
            symbol: Asset symbol (e.g., "WDO$")
            timeframe: Timeframe string (e.g., "M5")
            
        Returns:
            Number of records inserted/updated
        """
        count = 0
        
        for timestamp, row in df.iterrows():
            # Check if record exists
            existing = db.query(OHLCVData).filter(
                and_(
                    OHLCVData.symbol == symbol,
                    OHLCVData.timeframe == timeframe,
                    OHLCVData.timestamp == timestamp
                )
            ).first()
            
            if existing:
                # Update existing record
                existing.open = float(row['open'])
                existing.high = float(row['high'])
                existing.low = float(row['low'])
                existing.close = float(row['close'])
                existing.volume = int(row['volume']) if 'volume' in row else 0
                existing.updated_at = datetime.utcnow()
            else:
                # Insert new record
                ohlcv = OHLCVData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=timestamp,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume']) if 'volume' in row else 0,
                )
                db.add(ohlcv)
            
            count += 1
        
        db.commit()
        logger.info(f"Saved {count} OHLCV records for {symbol} {timeframe}")
        return count
    
    @staticmethod
    def get_latest_candles(
        db: Session,
        symbol: str,
        timeframe: str,
        limit: int = 500
    ) -> pd.DataFrame:
        """Retrieve latest candles from database.
        
        Args:
            db: Database session
            symbol: Asset symbol
            timeframe: Timeframe string
            limit: Maximum number of candles
            
        Returns:
            DataFrame with OHLCV data (time-indexed)
        """
        records = (
            db.query(OHLCVData)
            .filter(
                and_(
                    OHLCVData.symbol == symbol,
                    OHLCVData.timeframe == timeframe
                )
            )
            .order_by(desc(OHLCVData.timestamp))
            .limit(limit)
            .all()
        )
        
        if not records:
            return pd.DataFrame()
        
        # Convert to DataFrame
        data = []
        for record in reversed(records):  # Reverse to get chronological order
            data.append({
                'time': record.timestamp,
                'open': record.open,
                'high': record.high,
                'low': record.low,
                'close': record.close,
                'volume': record.volume,
            })
        
        df = pd.DataFrame(data)
        df.set_index('time', inplace=True)
        
        logger.info(f"Retrieved {len(df)} OHLCV records for {symbol} {timeframe}")
        return df
    
    @staticmethod
    def get_candles_range(
        db: Session,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Retrieve candles within date range.
        
        Args:
            db: Database session
            symbol: Asset symbol
            timeframe: Timeframe string
            start_date: Start datetime
            end_date: End datetime
            
        Returns:
            DataFrame with OHLCV data
        """
        records = (
            db.query(OHLCVData)
            .filter(
                and_(
                    OHLCVData.symbol == symbol,
                    OHLCVData.timeframe == timeframe,
                    OHLCVData.timestamp >= start_date,
                    OHLCVData.timestamp <= end_date
                )
            )
            .order_by(OHLCVData.timestamp)
            .all()
        )
        
        if not records:
            return pd.DataFrame()
        
        data = []
        for record in records:
            data.append({
                'time': record.timestamp,
                'open': record.open,
                'high': record.high,
                'low': record.low,
                'close': record.close,
                'volume': record.volume,
            })
        
        df = pd.DataFrame(data)
        df.set_index('time', inplace=True)
        return df


class MarketAnalysisRepository:
    """Repository for market analysis operations."""
    
    @staticmethod
    def save_analysis(
        db: Session,
        symbol: str,
        timeframe: str,
        timestamp: datetime,
        analysis: Dict[str, Any],
        candles_analyzed: int
    ) -> MarketAnalysis:
        """Save market analysis results to database.
        
        Args:
            db: Database session
            symbol: Asset symbol
            timeframe: Timeframe string
            timestamp: Analysis timestamp
            analysis: Analysis dict from MarketContextAnalyzer
            candles_analyzed: Number of candles analyzed
            
        Returns:
            Created MarketAnalysis record
        """
        # Check if record exists
        existing = db.query(MarketAnalysis).filter(
            and_(
                MarketAnalysis.symbol == symbol,
                MarketAnalysis.timeframe == timeframe,
                MarketAnalysis.timestamp == timestamp
            )
        ).first()
        
        # Extract data from analysis dict (support both flat and nested formats)
        # Flat format (from context_analyzer)
        if 'trend' in analysis and isinstance(analysis['trend'], str):
            trend_direction = analysis.get('trend')
            trend_strength = analysis.get('trend_strength')
            support_levels = str(analysis.get('support', ''))
            resistance_levels = str(analysis.get('resistance', ''))
            patterns = analysis.get('pattern', '')
            rsi_value = analysis.get('rsi')
            ema_9_value = analysis.get('ema_fast')
            sma_20_value = analysis.get('sma_fast')
            sma_50_value = analysis.get('sma_slow')
        else:
            # Nested format (for compatibility)
            trend = analysis.get('trend', {})
            levels = analysis.get('levels', {})
            price_action = analysis.get('price_action', {})
            moving_averages = analysis.get('moving_averages', {})
            
            trend_direction = trend.get('direction')
            trend_strength = trend.get('strength')
            support_levels = ','.join([str(s) for s in levels.get('supports', [])])
            resistance_levels = ','.join([str(r) for r in levels.get('resistances', [])])
            patterns = ','.join(price_action.get('patterns', []))
            rsi_value = analysis.get('rsi')
            ema_9_value = moving_averages.get('ema9')
            sma_20_value = moving_averages.get('sma20')
            sma_50_value = moving_averages.get('sma50')
        
        if existing:
            # Update existing
            existing.trend_direction = trend_direction
            existing.trend_strength = trend_strength
            existing.support_levels = support_levels
            existing.resistance_levels = resistance_levels
            existing.patterns = patterns
            existing.rsi = rsi_value
            existing.ema_9 = ema_9_value
            existing.sma_20 = sma_20_value
            existing.sma_50 = sma_50_value
            existing.candles_analyzed = candles_analyzed
            record = existing
        else:
            # Create new
            record = MarketAnalysis(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                trend_direction=trend_direction,
                trend_strength=trend_strength,
                support_levels=support_levels,
                resistance_levels=resistance_levels,
                patterns=patterns,
                rsi=rsi_value,
                ema_9=ema_9_value,
                sma_20=sma_20_value,
                sma_50=sma_50_value,
                candles_analyzed=candles_analyzed
            )
            db.add(record)
        
        db.commit()
        db.refresh(record)
        
        logger.info(f"Saved market analysis for {symbol} {timeframe}")
        return record
    
    @staticmethod
    def get_latest_analysis(
        db: Session,
        symbol: str,
        timeframe: str
    ) -> Optional[MarketAnalysis]:
        """Get latest market analysis.
        
        Args:
            db: Database session
            symbol: Asset symbol
            timeframe: Timeframe string
            
        Returns:
            Latest MarketAnalysis record or None
        """
        return (
            db.query(MarketAnalysis)
            .filter(
                and_(
                    MarketAnalysis.symbol == symbol,
                    MarketAnalysis.timeframe == timeframe
                )
            )
            .order_by(desc(MarketAnalysis.timestamp))
            .first()
        )


class DataProviderLogRepository:
    """Repository for data provider logging."""
    
    @staticmethod
    def log_operation(
        db: Session,
        symbol: str,
        timeframe: str,
        provider_type: str,
        candles_count: int,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> DataProviderLog:
        """Log data provider operation.
        
        Args:
            db: Database session
            symbol: Asset symbol
            timeframe: Timeframe string
            provider_type: Provider name (MT5, Cache, Synthetic)
            candles_count: Number of candles fetched
            success: Whether operation succeeded
            error_message: Optional error message
            
        Returns:
            Created DataProviderLog record
        """
        log_entry = DataProviderLog(
            symbol=symbol,
            timeframe=timeframe,
            provider_type=provider_type,
            candles_count=candles_count,
            success=success,
            error_message=error_message,
        )
        
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        
        return log_entry
