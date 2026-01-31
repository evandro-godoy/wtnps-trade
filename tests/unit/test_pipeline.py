import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from src.core.event_bus import event_bus
from src.events import MarketDataEvent, SignalEvent

# Tenta importar o adaptador.
try:
    from src.modules.strategy.lstm_adapter import LSTMVolatilityAdapter
except ImportError:
    pytest.fail("❌ O arquivo src/modules/strategy/lstm_adapter.py não foi encontrado. O Agente QUANT precisa finalizar a tarefa primeiro.")

@pytest.fixture
def mock_strategy_dependencies():
    """
    Engana o adaptador interceptando o objeto 'keras' DENTRO do módulo do adaptador.
    """
    # 🎯 CORREÇÃO AQUI: Apontamos para o módulo exato onde o keras é importado
    target_keras = 'src.modules.strategy.lstm_adapter.keras.models.load_model'
    
    with patch(target_keras) as mock_load_model, \
         patch('joblib.load') as mock_joblib:
        
        # 1. Mock do Modelo
        mock_model = MagicMock()
        mock_model.predict.return_value = [[0.85]] 
        mock_load_model.return_value = mock_model
        
        # 2. Mock do Scaler
        mock_scaler = MagicMock()
        mock_scaler.transform.side_effect = lambda x: [[0.0] * x.shape[1]]
        mock_joblib.return_value = mock_scaler
        
        yield mock_load_model, mock_joblib

def test_end_to_end_flow(mock_strategy_dependencies):
    """
    Testa: MarketData -> EventBus -> Adapter -> SignalEvent
    """
    # 1. Setup: Instancia o Adaptador com caminhos falsos E lookback curto
    # Passamos lookback=5 para o teste não precisar injetar 108 candles
    adapter = LSTMVolatilityAdapter(
        model_path="models/dummy.keras", 
        scaler_path="models/dummy.scaler",
        lookback=5
    )
    
    # Registra o adaptador manualmente
    event_bus.subscribe("MARKET_DATA", adapter.on_market_data)
    
    # 2. Setup: Ouvinte espião para verificar se o sinal saiu
    received_signals = []
    def spy_handler(event):
        if isinstance(event, SignalEvent):
            received_signals.append(event)
    
    event_bus.subscribe("SIGNAL", spy_handler)
    
    # 3. Execução: Injeta candles suficientes para encher o buffer (lookback = 5)
    print("\n⚡ Injetando 10 candles no sistema...")
    for i in range(10):
        evt = MarketDataEvent(
            symbol="TEST$", timeframe="M5",
            open=10.0, high=11.0, low=9.0, close=10.5, volume=1000
        )
        event_bus.publish(evt)

    # 4. Asserção: Verificação da Vitória
    assert len(received_signals) > 0, "❌ O adaptador não gerou nenhum sinal após receber dados!"
    
    last_signal = received_signals[-1]
    assert last_signal.symbol == "TEST$"
    assert last_signal.confidence > 0.0
    print(f"✅ Sucesso! Sinal gerado: {last_signal.signal} com confiança {last_signal.confidence:.2f}")