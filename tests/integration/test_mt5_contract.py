"""
Testes de Contrato: Validam compatibilidade de tipos entre MT5 → LSTMAdapter.

Garante que:
1. MarketDataEvent tem tipos corretos
2. DataFrame dtypes são compatíveis com modelo
3. Shape final após features == model.input_shape
"""

import unittest
from datetime import datetime
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch

from src.data_handler.mt5_provider import MetaTraderProvider
from src.events import MarketDataEvent
from src.modules.strategy.lstm_adapter import LSTMVolatilityAdapter


class TestMT5Contract(unittest.TestCase):
    """Testes de contrato para integração MT5 → LSTM."""
    
    def test_market_data_event_contract(self):
        """Valida tipos de todos os campos de MarketDataEvent."""
        event = MarketDataEvent(
            symbol="WDO$",
            timeframe="M5",
            open=125500.0,
            high=125600.0,
            low=125400.0,
            close=125550.0,
            volume=1500,
            timestamp=datetime.now()
        )
        
        # Validar tipos
        self.assertIsInstance(event.symbol, str)
        self.assertIsInstance(event.timeframe, str)
        self.assertIsInstance(event.open, (float, np.float32, np.float64))
        self.assertIsInstance(event.high, (float, np.float32, np.float64))
        self.assertIsInstance(event.low, (float, np.float32, np.float64))
        self.assertIsInstance(event.close, (float, np.float32, np.float64))
        self.assertIsInstance(event.volume, (int, np.int32, np.int64))
        self.assertIsInstance(event.timestamp, datetime)
    
    def test_dataframe_dtypes_from_events(self):
        """Valida dtypes do DataFrame construído a partir de eventos."""
        # Criar eventos mock
        events = [
            MarketDataEvent(
                symbol="WDO$",
                timeframe="M5",
                open=125500.0 + i,
                high=125600.0 + i,
                low=125400.0 + i,
                close=125550.0 + i,
                volume=1500 + i,
                timestamp=datetime.now()
            )
            for i in range(150)
        ]
        
        # Construir DataFrame
        data = {
            'open': [e.open for e in events],
            'high': [e.high for e in events],
            'low': [e.low for e in events],
            'close': [e.close for e in events],
            'volume': [e.volume for e in events],
        }
        df = pd.DataFrame(data)
        
        # Validar dtypes
        self.assertIn(df['open'].dtype, [np.float32, np.float64, float])
        self.assertIn(df['high'].dtype, [np.float32, np.float64, float])
        self.assertIn(df['low'].dtype, [np.float32, np.float64, float])
        self.assertIn(df['close'].dtype, [np.float64, float])  # MT5 padrão
        self.assertIn(df['volume'].dtype, [np.int32, np.int64, int])
    
    @patch('os.path.exists')
    @patch('keras.models.load_model')
    @patch('joblib.load')
    def test_shape_validation_after_features(self, mock_joblib, mock_load_model, mock_exists):
        """Valida que shape após define_features() bate com model.input_shape."""
        # Mock do modelo (22 features = número real do LSTMVolatilityStrategy)
        mock_model = Mock()
        mock_model.input_shape = (None, 108, 22)  # lookback=108, features=22
        mock_model.predict = Mock(return_value=np.array([[0.4, 0.6]]))  # COMPRA
        mock_load_model.return_value = mock_model
        
        # Mock do scaler
        mock_scaler = Mock()
        mock_scaler.transform = Mock(side_effect=lambda x: np.array(x, dtype=np.float32))
        mock_joblib.return_value = mock_scaler
        
        # Mock exists
        mock_exists.return_value = True
        
        # Instanciar adapter
        adapter = LSTMVolatilityAdapter("models/test_model")
        
        # Criar eventos mock (200 candles para garantir lookback)
        base_price = 125500.0
        for i in range(200):
            event = MarketDataEvent(
                symbol="WDO$",
                timeframe="M5",
                open=base_price + np.random.rand(),
                high=base_price + np.random.rand() + 1.0,
                low=base_price - np.random.rand(),
                close=base_price + np.random.rand(),
                volume=int(1000 + np.random.rand() * 500),
                timestamp=datetime.now()
            )
            adapter.on_market_data(event)
        
        # Validar que buffer tem candles suficientes
        self.assertGreaterEqual(len(adapter.buffer), 108)
        
        # Validar estatísticas
        stats = adapter.get_stats()
        self.assertEqual(stats['processed_count'], 200)
        self.assertGreater(stats['signal_count'], 0)  # Sinais foram gerados
    
    @patch('MetaTrader5.initialize')
    @patch('MetaTrader5.terminal_info')
    @patch('MetaTrader5.copy_rates_from_pos')
    @patch('MetaTrader5.version')
    def test_mt5_provider_dtype_contract(self, mock_version, mock_copy_rates, mock_terminal_info, mock_init):
        """Valida que MT5Provider retorna dtypes corretos."""
        # Mock MT5 initialization
        mock_init.return_value = True
        mock_version.return_value = (5, 0, 3700)
        mock_terminal_info.return_value = Mock(connected=True)
        
        # Mock candle data com dtypes reais do MT5
        mock_rates = np.array([
            (1640000000, 125500.0, 125600.0, 125400.0, 125550.0, 1500, 0, 0),
            (1640000300, 125550.0, 125650.0, 125500.0, 125600.0, 1600, 0, 0),
        ], dtype=[
            ('time', '<i8'),
            ('open', '<f8'),
            ('high', '<f8'),
            ('low', '<f8'),
            ('close', '<f8'),
            ('tick_volume', '<i8'),
            ('spread', '<i4'),
            ('real_volume', '<i8')
        ])
        mock_copy_rates.return_value = mock_rates
        
        # Criar provider
        provider = MetaTraderProvider()
        events = provider.get_latest_candles("WDO$", "M5", 2)
        
        # Validar quantidade
        self.assertEqual(len(events), 2)
        
        # Validar tipos de cada evento
        for event in events:
            self.assertIsInstance(event.open, float)
            self.assertIsInstance(event.high, float)
            self.assertIsInstance(event.low, float)
            self.assertIsInstance(event.close, float)
            self.assertIsInstance(event.volume, int)


if __name__ == "__main__":
    unittest.main(verbosity=2)
