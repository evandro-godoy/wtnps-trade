"""MetaTrader 5 Data Provider - Fail Fast Connection Strategy."""

import logging
from datetime import datetime
from typing import List, Optional
import MetaTrader5 as mt5
import pandas as pd

from src.core.event_bus import event_bus
from src.events import MarketDataEvent

logger = logging.getLogger(__name__)


class MetaTraderProvider:
    """
    Provider para dados do MetaTrader 5.
    
    Estratégia Fail Fast: Se MT5 não conectar, lança ConnectionError.
    Sem retry loops nesta versão (Sprint 2 MVP).
    
    Raises:
        ConnectionError: Se mt5.initialize() falhar
        ValueError: Se symbol não for encontrado
    """
    
    def __init__(self):
        """Inicializa conexão com MT5 terminal."""
        if not mt5.initialize():
            error_msg = f"Falha ao inicializar MT5. Error: {mt5.last_error()}"
            logger.critical(error_msg)
            raise ConnectionError(error_msg)
        
        logger.info(f"✅ MT5 inicializado. Versão: {mt5.version()}")
        logger.info(f"Terminal info: {mt5.terminal_info()}")
    
    def get_latest_candles(
        self, 
        symbol: str, 
        timeframe: str, 
        count: int
    ) -> List[MarketDataEvent]:
        """
        Busca últimos N candles do MT5 e retorna como MarketDataEvents.
        
        Args:
            symbol: Símbolo do ativo (ex: "WIN$", "WDO$")
            timeframe: Timeframe (ex: "M5", "M15", "H1")
            count: Número de candles
        
        Returns:
            Lista de MarketDataEvent
        
        Raises:
            ConnectionError: Se MT5 não estiver conectado
            ValueError: Se symbol não for encontrado ou dados inválidos
        """
        # Validar conexão
        if not mt5.terminal_info():
            error_msg = "MT5 não está conectado"
            logger.critical(error_msg)
            raise ConnectionError(error_msg)
        
        # Mapear timeframe string para constante MT5
        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        
        mt5_timeframe = timeframe_map.get(timeframe)
        if mt5_timeframe is None:
            raise ValueError(f"Timeframe inválido: {timeframe}")
        
        # Buscar candles
        rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, count)
        
        if rates is None or len(rates) == 0:
            error_msg = f"Nenhum dado retornado para {symbol} {timeframe}. Error: {mt5.last_error()}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Converter para DataFrame
        df = pd.DataFrame(rates)
        
        # Validar colunas esperadas
        required_cols = ['time', 'open', 'high', 'low', 'close', 'tick_volume']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"Dados do MT5 não têm colunas esperadas: {required_cols}")
        
        # Validar dtypes
        assert df['open'].dtype in [float, 'float64'], f"open dtype inválido: {df['open'].dtype}"
        assert df['high'].dtype in [float, 'float64'], f"high dtype inválido: {df['high'].dtype}"
        assert df['low'].dtype in [float, 'float64'], f"low dtype inválido: {df['low'].dtype}"
        assert df['close'].dtype in [float, 'float64'], f"close dtype inválido: {df['close'].dtype}"
        
        # Converter para MarketDataEvents
        events = []
        for _, row in df.iterrows():
            event = MarketDataEvent(
                symbol=symbol,
                timeframe=timeframe,
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row['tick_volume']),
                timestamp=datetime.fromtimestamp(row['time'])
            )
            events.append(event)
        
        logger.info(f"✅ Buscados {len(events)} candles de {symbol} {timeframe}")
        return events
    
    def publish_to_eventbus(self, events: List[MarketDataEvent]):
        """Publica lista de eventos no barramento."""
        for event in events:
            event_bus.publish(event)
        logger.debug(f"Publicados {len(events)} eventos no EventBus")
    
    def shutdown(self):
        """Encerra conexão com MT5."""
        mt5.shutdown()
        logger.info("🛑 MT5 desconectado")
    
    def __del__(self):
        """Destrutor - garante shutdown."""
        try:
            mt5.shutdown()
        except:
            pass
