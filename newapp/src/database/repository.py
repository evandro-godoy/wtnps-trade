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
    AssetsRates
)

def _map_trend_strength_to_float(strength_str: str | None) -> float | None:
    """Map textual trend strength to numeric value for database storage.
    
    Args:
        strength_str: String value ('FORTE', 'MODERADA', 'FRACA', 'INDEFINIDO')
        
    Returns:
        Float value: FORTE=3.0, MODERADA=2.0, FRACA=1.0, INDEFINIDO=0.0, None if None
    """
    if strength_str is None:
        return None
    mapping = {
        'FORTE': 3.0,
        'MODERADA': 2.0,
        'FRACA': 1.0,
        'INDEFINIDO': 0.0,
    }
    return mapping.get(strength_str.upper(), 0.0)

logger = logging.getLogger(__name__)

class AssetsRatesRepository:
    """Repository for AssetsRates data operations.

    Provides persistence for unified OHLCV + indicadores em `AssetsRates`.
    """
    
    @staticmethod
    def save_rates_dataframe(
        db: Session,
        df: pd.DataFrame,
        symbol: str,
        timeframe: int,
        timeframe_str: Optional[str] = None,
        allow_enrich: bool = True
    ) -> int:
        """Save DataFrame with rates data to database.
        
        Args:
            db: Database session
            df: DataFrame with columns: time, open, high, low, close, tick_volume, volume, spread, indicadores opcionais
            symbol: Asset symbol (e.g., "WDO$")
            timeframe: Timeframe integer (ex.: minutos ou constante MT5)
            timeframe_str: Optional timeframe string ("M5", "H1" etc.)
            allow_enrich: If True, preenchimento de indicadores ausentes em registros existentes
            
        Returns:
            Number of records inserted/updated
        """
        count = 0
        
        for timestamp, row in df.iterrows():
            # Check if record exists
            existing = db.query(AssetsRates).filter(
                and_(
                    AssetsRates.symbol == symbol,
                    AssetsRates.timeframe == timeframe,
                    AssetsRates.timestamp == timestamp
                )
            ).first()
            
            if existing:
                # Imutabilidade parcial: não alterar OHLCV já existentes
                if allow_enrich:
                    # Atualiza somente campos de indicadores/metadata se estiverem nulos ou zero
                    if 'support_level' in row and existing.support_level is False:
                        existing.support_level = bool(row['support_level'])
                    if 'resistance_level' in row and existing.resistance_level is False:
                        existing.resistance_level = bool(row['resistance_level'])
                    if 'ema_9' in row and (existing.ema_9 is None or existing.ema_9 == 0):
                        existing.ema_9 = float(row['ema_9'])
                    if 'sma_20' in row and (existing.sma_20 is None or existing.sma_20 == 0):
                        existing.sma_20 = float(row['sma_20'])
                    if 'sma_50' in row and (existing.sma_50 is None or existing.sma_50 == 0):
                        existing.sma_50 = float(row['sma_50'])
                    if 'sma_200' in row and (existing.sma_200 is None or existing.sma_200 == 0):
                        existing.sma_200 = float(row['sma_200'])
                existing.updated_at = datetime.utcnow()
            else:
                # Insert new record
                rates = AssetsRates(
                    symbol=symbol,
                    timeframe=timeframe,
                    timeframe_str=timeframe_str,
                    timestamp=timestamp,   
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    tick_volume=int(row['tick_volume']) if 'tick_volume' in row else 0,
                    volume=int(row['volume']) if 'volume' in row else 0,
                    spread=int(row['spread']) if 'spread' in row else 0,
                    support_level=bool(row['support_level']) if 'support_level' in row else False,
                    resistance_level=bool(row['resistance_level']) if 'resistance_level' in row else False,
                    ema_9=float(row['ema_9']) if 'ema_9' in row else 0.0,
                    sma_20=float(row['sma_20']) if 'sma_20' in row else 0.0,  
                    sma_50=float(row['sma_50']) if 'sma_50' in row else 0.0,  
                    sma_200=float(row['sma_200']) if 'sma_200' in row else 0.0,        
                )
                db.add(rates)
            
            count += 1
        
        db.commit()
        logger.info(f"Saved {count} AssetsRates records for {symbol} {timeframe}")
        return count

    @staticmethod
    def get_all_rates(
        db: Session,
        symbol: str,
        timeframe: int
    ) -> pd.DataFrame:
        """Retrieve candles within date range.
        
        Args:
            db: Database session
            symbol: Asset symbol
            timeframe: Timeframe integer
            
        Returns:
            DataFrame with OHLCV data
        """
        records = (
            db.query(AssetsRates)
            .filter(
                and_(
                    AssetsRates.symbol == symbol,
                    AssetsRates.timeframe == timeframe
                )
            )
            .order_by(AssetsRates.timestamp)
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
                'tick_volume': record.tick_volume,
                'volume': record.volume,
                'spread': record.spread,
                'support_level': record.support_level,
                'resistance_level': record.resistance_level,
                'ema_9': record.ema_9,
                'sma_20': record.sma_20,
                'sma_50': record.sma_50,
                'sma_200': record.sma_200,                
            })
        
        df = pd.DataFrame(data)
        df.set_index('time', inplace=True)
        return df        

    @staticmethod
    def get_rates_range(
        db: Session,
        symbol: str,
        timeframe: int,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Retrieve candles within date range.
        
        Args:
            db: Database session
            symbol: Asset symbol
            timeframe: Timeframe integer
            start_date: Start datetime
            end_date: End datetime
            
        Returns:
            DataFrame with OHLCV data
        """
        records = (
            db.query(AssetsRates)
            .filter(
                and_(
                    AssetsRates.symbol == symbol,
                    AssetsRates.timeframe == timeframe,
                    AssetsRates.timestamp >= start_date,
                    AssetsRates.timestamp <= end_date
                )
            )
            .order_by(AssetsRates.timestamp)
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

    @staticmethod
    def get_rates_indicators_range(
        db: Session,
        symbol: str,
        timeframe: int,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Retrieve candles within date range.
        
        Args:
            db: Database session
            symbol: Asset symbol
            timeframe: Timeframe integer
            start_date: Start datetime
            end_date: End datetime
            
        Returns:
            DataFrame with OHLCV data
        """
        records = (
            db.query(AssetsRates)
            .filter(
                and_(
                    AssetsRates.symbol == symbol,
                    AssetsRates.timeframe == timeframe,
                    AssetsRates.timestamp >= start_date,
                    AssetsRates.timestamp <= end_date
                )
            )
            .order_by(AssetsRates.timestamp)
            .all()
        )
        
        if not records:
            return pd.DataFrame()
        
        data = []
        for record in records:
            data.append({
                'time': record.timestamp,
                # Include OHLC for downstream calculations (range, returns)
                'open': record.open,
                'high': record.high,
                'low': record.low,
                'close': record.close,
                'volume': record.volume,
                'ema_9': record.ema_9,
                'sma_20': record.sma_20,
                'sma_50': record.sma_50,
                'sma_200': record.sma_200,
            })
        
        df = pd.DataFrame(data)
        df.set_index('time', inplace=True)
        return df     

    @staticmethod
    def enrich_missing_indicators(
        db: Session,
        symbol: str,
        timeframe: int,
        overwrite: bool = False
    ) -> int:
        """Enrich existing AssetsRates rows with missing indicator values.

        Does NOT modify OHLCV fields. Only fills (or optionally overwrites) indicator
        columns: ema_9, sma_20, sma_50, sma_200. Utiliza cálculo baseado na coluna
        close em ordem cronológica.

        Args:
            db: Active Session
            symbol: Asset symbol
            timeframe: Timeframe integer (minutes or MT5 constant)
            overwrite: If True, recalculates and overwrites all indicator values; if False, only fills null/zero.

        Returns:
            Number of records updated.
        """
        # Fetch all rates with close needed for rolling calculations
        records = (
            db.query(AssetsRates)
            .filter(and_(AssetsRates.symbol == symbol, AssetsRates.timeframe == timeframe))
            .order_by(AssetsRates.timestamp)
            .all()
        )
        if not records:
            return 0

        # Build DataFrame for indicator computation
        from newapp.src.utils.indicators import compute_indicator_dict
        
        df = pd.DataFrame([
            {
                'time': r.timestamp,
                'close': r.close,
                'ema_9': r.ema_9,
                'sma_20': r.sma_20,
                'sma_50': r.sma_50,
                'sma_200': r.sma_200,
            }
            for r in records
        ])
        df.set_index('time', inplace=True)
        df = df.sort_index()

        # Compute indicators using centralized function
        indicators = compute_indicator_dict(df['close'])
        computed_ema9 = indicators['ema_9']
        computed_sma20 = indicators['sma_20']
        computed_sma50 = indicators['sma_50']
        computed_sma200 = indicators['sma_200']

        # Apply updates
        updated = 0
        for r in records:
            ts = r.timestamp
            def need_update(current_val, new_val):
                if overwrite:
                    return True
                return current_val is None or current_val == 0

            if need_update(r.ema_9, computed_ema9.loc[ts]):
                r.ema_9 = float(computed_ema9.loc[ts])
                updated += 1
            if need_update(r.sma_20, computed_sma20.loc[ts]):
                r.sma_20 = float(computed_sma20.loc[ts])
                updated += 1
            if need_update(r.sma_50, computed_sma50.loc[ts]):
                r.sma_50 = float(computed_sma50.loc[ts])
                updated += 1
            if need_update(r.sma_200, computed_sma200.loc[ts]):
                r.sma_200 = float(computed_sma200.loc[ts])
                updated += 1

        db.commit()
        logger.info(f"Enriched indicators for {symbol} {timeframe}: {updated} field updates")
        return updated


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
            trend_strength_raw = analysis.get('trend_strength')
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
            trend_strength_raw = trend.get('strength')
            support_levels = ','.join([str(s) for s in levels.get('supports', [])])
            resistance_levels = ','.join([str(r) for r in levels.get('resistances', [])])
            patterns = ','.join(price_action.get('patterns', []))
            rsi_value = analysis.get('rsi')
            ema_9_value = moving_averages.get('ema9')
            sma_20_value = moving_averages.get('sma20')
            sma_50_value = moving_averages.get('sma50')
        
        # Map textual strength to numeric
        trend_strength = _map_trend_strength_to_float(trend_strength_raw)
        
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

    @staticmethod
    def update_indicators_with_analyzer(
        db: Session,
        symbol: str,
        timeframe: int,
        analyzer: Optional[Any] = None
    ) -> int:
        """Calculate and update technical indicators using MarketContextAnalyzer.
        
        Retrieves all rates for the symbol/timeframe, calculates indicators using
        MarketContextAnalyzer, and updates the database with computed values.
        
        Args:
            db: Database session
            symbol: Asset symbol (e.g., "WDO$")
            timeframe: Timeframe integer (e.g., 5 for M5)
            analyzer: Optional MarketContextAnalyzer instance (creates default if None)
            
        Returns:
            Number of records updated
            
        Example:
            >>> from newapp.src.analysis.context_analyzer import MarketContextAnalyzer
            >>> analyzer = MarketContextAnalyzer(ema_fast=9, sma_fast=20, sma_slow=50)
            >>> count = AssetsRatesRepository.update_indicators_with_analyzer(
            ...     db, "WDO$", 5, analyzer
            ... )
            >>> print(f"Updated {count} records with technical indicators")
        """
        from newapp.src.analysis.context_analyzer import MarketContextAnalyzer
        
        # Create default analyzer if not provided
        if analyzer is None:
            analyzer = MarketContextAnalyzer(
                ema_fast=9,
                sma_fast=20,
                sma_slow=50,
                sma_lookback=25,
                rsi_period=14,
                lookback_levels=30
            )
        
        # Get all rates for this symbol/timeframe
        df = AssetsRatesRepository.get_all_rates(db, symbol, timeframe)
        
        if df.empty:
            logger.warning(f"No rates found for {symbol} timeframe={timeframe}")
            return 0
        
        # Calculate indicators using the analyzer's internal method
        df_with_indicators = analyzer._calculate_indicators(df)
        
        # Also calculate support/resistance for each candle (using rolling window)
        lookback = analyzer.lookback_levels
        
        # Rolling support (min low in window)
        df_with_indicators['support'] = df_with_indicators['low'].rolling(
            window=lookback, min_periods=1
        ).min()
        
        # Rolling resistance (max high in window)
        df_with_indicators['resistance'] = df_with_indicators['high'].rolling(
            window=lookback, min_periods=1
        ).max()
        
        # Mark support/resistance levels (when price touches the level)
        df_with_indicators['support_level'] = (
            df_with_indicators['low'] <= df_with_indicators['support'] * 1.001
        )
        df_with_indicators['resistance_level'] = (
            df_with_indicators['high'] >= df_with_indicators['resistance'] * 0.999
        )
        
        # Update database records
        count = 0
        for timestamp, row in df_with_indicators.iterrows():
            # Find existing record
            record = db.query(AssetsRates).filter(
                and_(
                    AssetsRates.symbol == symbol,
                    AssetsRates.timeframe == timeframe,
                    AssetsRates.timestamp == timestamp
                )
            ).first()
            
            if record:
                # Update indicators (use .get() to handle NaN values)
                record.ema_9 = float(row.get('ema_fast', 0.0)) if pd.notna(row.get('ema_fast')) else None
                record.sma_20 = float(row.get('sma_fast', 0.0)) if pd.notna(row.get('sma_fast')) else None
                record.sma_50 = float(row.get('sma_slow', 0.0)) if pd.notna(row.get('sma_slow')) else None
                record.support_level = bool(row.get('support_level', False))
                record.resistance_level = bool(row.get('resistance_level', False))
                record.updated_at = datetime.utcnow()
                count += 1
        
        db.commit()
        logger.info(f"Updated {count} AssetsRates records with technical indicators for {symbol} TF={timeframe}")
        return count


class BacktestRunRepository:
    """Persistence helper for BacktestRun records."""

    @staticmethod
    def create_run(
        db: Session,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        strategy: str,
        initial_capital: float
    ) -> 'BacktestRun':
        from newapp.src.database.models import BacktestRun
        run = BacktestRun(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            strategy=strategy,
            initial_capital=initial_capital
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def finalize_run(
        db: Session,
        run_id: int,
        final_capital: float,
        net_profit: float,
        total_trades: int,
        wins: int,
        losses: int,
        win_rate: float,
        profit_factor: float,
        max_drawdown: float,
        avg_trade_return: float
    ) -> 'BacktestRun':
        from newapp.src.database.models import BacktestRun
        run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
        if not run:
            raise ValueError(f"BacktestRun id={run_id} not found")
        run.final_capital = final_capital
        run.net_profit = net_profit
        run.total_trades = total_trades
        run.wins = wins
        run.losses = losses
        run.win_rate = win_rate
        run.profit_factor = profit_factor
        run.max_drawdown = max_drawdown
        run.avg_trade_return = avg_trade_return
        db.commit()
        db.refresh(run)
        return run


class BacktestTradeRepository:
    """Persistence helper for BacktestTrade records."""

    @staticmethod
    def add_trade(
        db: Session,
        run_id: int,
        symbol: str,
        timeframe: str,
        entry_time: datetime,
        direction: str,
        entry_price: float,
        stop_loss: float | None,
        take_profit: float | None,
        volume: float | None,
        indicators_snapshot: Dict[str, Any] | None = None
    ) -> 'BacktestTrade':
        from newapp.src.database.models import BacktestTrade
        trade = BacktestTrade(
            run_id=run_id,
            symbol=symbol,
            timeframe=timeframe,
            entry_time=entry_time,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=volume,
            indicators_snapshot=None if indicators_snapshot is None else str(indicators_snapshot)
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        return trade

    @staticmethod
    def close_trade(
        db: Session,
        trade_id: int,
        exit_time: datetime,
        exit_price: float,
        reason_exit: str,
        pnl: float,
        return_pct: float
    ) -> 'BacktestTrade':
        from newapp.src.database.models import BacktestTrade
        trade = db.query(BacktestTrade).filter(BacktestTrade.id == trade_id).first()
        if not trade:
            raise ValueError(f"BacktestTrade id={trade_id} not found")
        trade.exit_time = exit_time
        trade.exit_price = exit_price
        trade.reason_exit = reason_exit
        trade.pnl = pnl
        trade.return_pct = return_pct
        db.commit()
        db.refresh(trade)
        return trade


class TrainingRunRepository:
    """Repository for ML training run persistence.
    
    Stores training metrics and model metadata for analysis.
    """
    
    @staticmethod
    def save_training_run(
        db: Session,
        symbol: str,
        strategy_name: str,
        timeframe_str: str,
        start_date: datetime,
        end_date: datetime,
        model_path_prefix: str,
        train_metrics: Dict[str, Any],
        test_metrics: Dict[str, Any],
        class_distribution: Dict[str, Any],
        strategy_params: Optional[str] = None,
        feature_stats: Optional[str] = None,
        loss_history: Optional[str] = None,
        val_loss_history: Optional[str] = None,
        total_epochs: Optional[int] = None,
        training_duration_seconds: Optional[float] = None
    ) -> 'TrainingRun':
        """Save a new training run record.
        
        Args:
            db: Database session
            symbol: Asset symbol (e.g., "WDO$")
            strategy_name: Strategy name (e.g., "LSTMVolatilityStrategy")
            timeframe_str: Timeframe string (e.g., "M5")
            start_date: Training data start date
            end_date: Training data end date
            model_path_prefix: Path prefix where model artifacts are saved
            train_metrics: Dict with accuracy, precision, recall, f1, confusion_matrix, samples
            test_metrics: Dict with accuracy, precision, recall, f1, confusion_matrix, samples
            class_distribution: Dict with train/test class counts
            strategy_params: JSON string with strategy hyperparameters
            feature_stats: JSON string with feature statistics
            loss_history: JSON string with loss per epoch
            val_loss_history: JSON string with validation loss per epoch
            total_epochs: Number of training epochs
            training_duration_seconds: Training time in seconds
            
        Returns:
            Created TrainingRun instance
        """
        from newapp.src.database.models import TrainingRun
        
        # Extract metrics
        train_cm = train_metrics.get('confusion_matrix', {})
        test_cm = test_metrics.get('confusion_matrix', {})
        train_dist = class_distribution.get('train', {}).get('counts', {})
        test_dist = class_distribution.get('test', {}).get('counts', {})
        
        training_run = TrainingRun(
            symbol=symbol,
            strategy_name=strategy_name,
            timeframe_str=timeframe_str,
            start_date=start_date,
            end_date=end_date,
            model_path_prefix=model_path_prefix,
            # Train metrics
            train_accuracy=train_metrics.get('accuracy'),
            train_precision=train_metrics.get('precision'),
            train_recall=train_metrics.get('recall'),
            train_f1=train_metrics.get('f1'),
            train_samples=train_metrics.get('samples'),
            train_tn=train_cm.get('tn'),
            train_fp=train_cm.get('fp'),
            train_fn=train_cm.get('fn'),
            train_tp=train_cm.get('tp'),
            # Test metrics
            test_accuracy=test_metrics.get('accuracy'),
            test_precision=test_metrics.get('precision'),
            test_recall=test_metrics.get('recall'),
            test_f1=test_metrics.get('f1'),
            test_samples=test_metrics.get('samples'),
            test_tn=test_cm.get('tn'),
            test_fp=test_cm.get('fp'),
            test_fn=test_cm.get('fn'),
            test_tp=test_cm.get('tp'),
            # Class distribution
            train_class_0_count=train_dist.get(0),
            train_class_1_count=train_dist.get(1),
            test_class_0_count=test_dist.get(0),
            test_class_1_count=test_dist.get(1),
            # Additional metadata
            strategy_params=strategy_params,
            feature_stats=feature_stats,
            loss_history=loss_history,
            val_loss_history=val_loss_history,
            total_epochs=total_epochs,
            training_duration_seconds=training_duration_seconds
        )
        
        db.add(training_run)
        db.commit()
        db.refresh(training_run)
        logger.info(f"Saved TrainingRun id={training_run.id} for {symbol}/{strategy_name}/{timeframe_str}")
        return training_run
    
    @staticmethod
    def get_latest_training_run(
        db: Session,
        symbol: str,
        strategy_name: str,
        timeframe_str: str
    ) -> Optional['TrainingRun']:
        """Retrieve the most recent training run for a symbol/strategy/timeframe.
        
        Args:
            db: Database session
            symbol: Asset symbol
            strategy_name: Strategy name
            timeframe_str: Timeframe string
            
        Returns:
            Most recent TrainingRun or None
        """
        from newapp.src.database.models import TrainingRun
        
        return (
            db.query(TrainingRun)
            .filter(
                and_(
                    TrainingRun.symbol == symbol,
                    TrainingRun.strategy_name == strategy_name,
                    TrainingRun.timeframe_str == timeframe_str
                )
            )
            .order_by(desc(TrainingRun.created_at))
            .first()
        )
    
    @staticmethod
    def get_all_training_runs(
        db: Session,
        symbol: Optional[str] = None,
        strategy_name: Optional[str] = None,
        limit: int = 50
    ) -> List['TrainingRun']:
        """Retrieve training runs with optional filters.
        
        Args:
            db: Database session
            symbol: Optional symbol filter
            strategy_name: Optional strategy filter
            limit: Maximum number of records to return
            
        Returns:
            List of TrainingRun instances ordered by creation date (newest first)
        """
        from newapp.src.database.models import TrainingRun
        
        query = db.query(TrainingRun)
        
        if symbol:
            query = query.filter(TrainingRun.symbol == symbol)
        if strategy_name:
            query = query.filter(TrainingRun.strategy_name == strategy_name)
        
        return query.order_by(desc(TrainingRun.created_at)).limit(limit).all()
