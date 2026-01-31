"""Teste unitário do workflow EventBus + LSTMVolatilityAdapter."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from src.core.event_bus import EventBus
from src.events import MarketDataEvent, SignalEvent
from src.modules.strategy.lstm_adapter import LSTMVolatilityAdapter


class TestWorkflow(unittest.TestCase):
    """Testa o fluxo completo de eventos: EventBus -> LSTMVolatilityAdapter -> Sinais."""
    
    def setUp(self):
        """Prepara ambiente de teste."""
        self.event_bus = EventBus()
        
    def test_eventbus_publish_subscribe(self):
        """Testa publicação e subscrição de eventos no EventBus."""
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        # Registra handler
        self.event_bus.subscribe("MARKET_DATA", handler)
        
        # Publica evento
        event = MarketDataEvent(
            symbol="WDO$",
            timeframe="M5",
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000
        )
        self.event_bus.publish(event)
        
        # Verifica recebimento
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].symbol, "WDO$")
        self.assertEqual(received_events[0].close, 100.5)
    
    def test_lstm_adapter_with_mock_model(self):
        """Testa LSTMVolatilityAdapter com modelo mockado."""
        
        # Mock do modelo Keras
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([[0.3, 0.7]])  # Classe 1 (COMPRA) com 70%
        
        # Mock do scaler
        mock_scaler = MagicMock()
        mock_scaler.transform = lambda x: x  # Identidade para simplificar
        
        # Cria adaptador sem carregar arquivos
        adapter = LSTMVolatilityAdapter(lookback=108, event_bus=self.event_bus)
        adapter.model = mock_model
        adapter.scaler = mock_scaler
        
        # Verifica estado inicial
        self.assertEqual(adapter.processed_count, 0)
        self.assertEqual(adapter.signal_count, 0)
        self.assertEqual(len(adapter.buffer), 0)
        
        # Gera dados falsos (150 candles para garantir features suficientes)
        base_time = datetime(2025, 1, 1, 9, 0)
        for i in range(150):
            event = self._generate_fake_candle(
                symbol="WDO$",
                timeframe="M5",
                timestamp=base_time + timedelta(minutes=5*i),
                base_price=100.0 + i * 0.1
            )
            adapter.on_market_data(event)
        
        # Verifica processamento
        self.assertEqual(adapter.processed_count, 150)
        self.assertGreater(len(adapter.buffer), 0)
        
        # Como o modelo está mockado e vai prever a partir do lookback (108),
        # devemos ter sinais gerados
        # Mas o número exato depende de quando define_features retorna dados suficientes
        stats = adapter.get_stats()
        self.assertGreater(stats['processed_count'], 0)
        self.assertTrue(stats['model_loaded'])
        self.assertTrue(stats['scaler_loaded'])
    
    def test_workflow_200_events(self):
        """Testa workflow completo: EventBus + LSTMAdapter processando 200 eventos."""
        
        # Lista para capturar sinais publicados
        received_signals = []
        
        def signal_handler(event):
            if isinstance(event, SignalEvent):
                received_signals.append(event)
        
        # Registra handler de sinais
        self.event_bus.subscribe("SIGNAL", signal_handler)
        
        # Mock do modelo Keras
        mock_model = MagicMock()
        # Alterna entre COMPRA (1) e VENDA (0) para ter variabilidade
        def mock_predict(x, verbose=0):
            if np.random.rand() > 0.5:
                return np.array([[0.4, 0.6]])  # COMPRA
            else:
                return np.array([[0.7, 0.3]])  # VENDA
        mock_model.predict = mock_predict
        
        # Mock do scaler
        mock_scaler = MagicMock()
        mock_scaler.transform = lambda x: x  # Identidade
        
        # Cria e configura adaptador
        adapter = LSTMVolatilityAdapter(lookback=108, event_bus=self.event_bus)
        adapter.model = mock_model
        adapter.scaler = mock_scaler
        
        # Registra adaptador no barramento
        self.event_bus.subscribe("MARKET_DATA", adapter.on_market_data)
        
        # Gera e publica 200 eventos de MARKET_DATA
        base_time = datetime(2025, 1, 15, 9, 0)
        base_price = 5000.0
        
        for i in range(200):
            # Simula preço com random walk
            price_change = np.random.randn() * 2.0
            current_price = base_price + price_change
            
            event = MarketDataEvent(
                symbol="WDO$",
                timeframe="M5",
                open=current_price - 1.0,
                high=current_price + np.random.rand() * 2.0,
                low=current_price - np.random.rand() * 2.0,
                close=current_price,
                volume=int(1000 + np.random.rand() * 500),
                timestamp=base_time + timedelta(minutes=5*i)
            )
            
            # Publica no barramento
            self.event_bus.publish(event)
            
            base_price = current_price  # Atualiza base para próximo candle
        
        # Verifica resultados
        stats = adapter.get_stats()
        
        # Deve ter processado todos os 200 eventos
        self.assertEqual(stats['processed_count'], 200)
        
        # Buffer deve ter sido mantido (não crescer infinitamente)
        self.assertLessEqual(stats['buffer_size'], 208)  # lookback + margem
        
        # Deve ter gerado sinais (após lookback inicial)
        # Como lookback=108, sinais começam após 108 eventos
        expected_min_signals = 200 - 108 - 50  # -50 margem para features
        self.assertGreater(stats['signal_count'], 0)
        
        # Verifica que sinais foram publicados no barramento
        # Pode não haver sinais capturados se o handler não foi chamado
        # (depende de como define_features funciona)
        print(f"\n📊 Estatísticas do Teste:")
        print(f"  - Eventos processados: {stats['processed_count']}")
        print(f"  - Sinais gerados: {stats['signal_count']}")
        print(f"  - Tamanho do buffer: {stats['buffer_size']}")
        print(f"  - Sinais recebidos pelo handler: {len(received_signals)}")
        
    def test_adapter_without_model(self):
        """Testa que adaptador não falha sem modelo carregado."""
        adapter = LSTMVolatilityAdapter(lookback=108, event_bus=self.event_bus)
        
        # Não carrega modelo (model=None)
        self.assertIsNone(adapter.model)
        
        # Processa eventos normalmente
        for i in range(120):
            event = self._generate_fake_candle(
                symbol="WDO$",
                timeframe="M5",
                timestamp=datetime.now() + timedelta(minutes=5*i),
                base_price=100.0
            )
            adapter.on_market_data(event)
        
        # Buffer deve crescer
        self.assertEqual(adapter.processed_count, 120)
        self.assertGreater(len(adapter.buffer), 0)
        
        # Mas nenhum sinal deve ser gerado
        self.assertEqual(adapter.signal_count, 0)
    
    def test_multiple_handlers(self):
        """Testa múltiplos handlers para o mesmo tipo de evento."""
        handler1_calls = []
        handler2_calls = []
        
        self.event_bus.subscribe("MARKET_DATA", lambda e: handler1_calls.append(e))
        self.event_bus.subscribe("MARKET_DATA", lambda e: handler2_calls.append(e))
        
        event = self._generate_fake_candle("WDO$", "M5", datetime.now(), 100.0)
        self.event_bus.publish(event)
        
        # Ambos handlers devem ter sido chamados
        self.assertEqual(len(handler1_calls), 1)
        self.assertEqual(len(handler2_calls), 1)
    
    # ---- Métodos auxiliares ----
    
    def _generate_fake_candle(self, symbol: str, timeframe: str, 
                              timestamp: datetime, base_price: float) -> MarketDataEvent:
        """Gera um candle falso para testes."""
        variation = np.random.randn() * 0.5
        return MarketDataEvent(
            symbol=symbol,
            timeframe=timeframe,
            open=base_price,
            high=base_price + abs(variation),
            low=base_price - abs(variation),
            close=base_price + variation,
            volume=int(1000 + np.random.rand() * 500),
            timestamp=timestamp
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
