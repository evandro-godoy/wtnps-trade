import numpy as np  
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
    # 🎯 Apontamos para o módulo exato onde o keras é importado
    target_keras = 'src.modules.strategy.lstm_adapter.keras.models.load_model'
    
    with patch(target_keras) as mock_load_model, \
         patch('joblib.load') as mock_joblib:
        
        # 1. Mock do Modelo
        mock_model = MagicMock()
        # 🎯 CORREÇÃO 1: O retorno deve ser um ARRAY NUMPY, não uma lista.
        # Isso evita o erro "AttributeError: 'list' object has no attribute 'tolist'"
        mock_model.predict.return_value = np.array([[0.85]])
        mock_load_model.return_value = mock_model
        
        # 2. Mock do Scaler
        mock_scaler = MagicMock()
        # 🎯 CORREÇÃO 2: Usamos np.zeros(x.shape) para devolver um array do MESMO TAMANHO da entrada.
        # Isso evita o erro "ValueError: cannot reshape array..."
        mock_scaler.transform.side_effect = lambda x: np.zeros(x.shape)
        mock_joblib.return_value = mock_scaler
        
        yield mock_load_model, mock_joblib

def test_end_to_end_flow(mock_strategy_dependencies):
    """
    Testa: MarketData -> EventBus -> Adapter -> SignalEvent
    """
    # 1. Setup: Instancia o Adaptador com caminhos falsos E lookback curto
    adapter = LSTMVolatilityAdapter(
        model_path="models/dummy.keras", 
        scaler_path="models/dummy.scaler",
        lookback=5,
        event_bus=event_bus  
    )
    
    # Registra o adaptador manualmente
    event_bus.subscribe("MARKET_DATA", adapter.on_market_data)
    
    # 2. Setup: Ouvinte espião para verificar se o sinal saiu
    received_signals = []
    def spy_handler(event):
        if isinstance(event, SignalEvent):
            received_signals.append(event)
    
    event_bus.subscribe("SIGNAL", spy_handler)
    
    # 3. Execução: Injeta candles suficientes para encher o buffer e aquecer indicadores
    print("\n⚡ Injetando 100 candles no sistema...")
    # Aumentamos de 10 para 100 para garantir que indicadores (RSI, MA) tenham dados
    for i in range(100): 
        evt = MarketDataEvent(
            symbol="TEST$", timeframe="M5",
            # Variamos o preço ligeiramente para não ser uma linha reta perfeita (opcional, mas bom)
            open=10.0 + (i * 0.1), 
            high=11.0 + (i * 0.1), 
            low=9.0 + (i * 0.1), 
            close=10.5 + (i * 0.1), 
            volume=1000
        )
        event_bus.publish(evt)

    # 4. Asserção: Verificação da Vitória
    assert len(received_signals) > 0, "❌ O adaptador não gerou nenhum sinal após receber dados!"
    
    last_signal = received_signals[-1]
    assert last_signal.symbol == "TEST$"
    assert last_signal.confidence > 0.0
    print(f"✅ Sucesso! Sinal gerado: {last_signal.signal} com confiança {last_signal.confidence:.2f}")