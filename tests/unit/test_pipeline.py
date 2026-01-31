# tests/unit/test_pipeline.py
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from src.core.event_bus import event_bus
from src.events import MarketDataEvent, SignalEvent

# Tenta importar o adaptador. Se o QUANT não terminou o trabalho, isso vai falhar (o que é bom!)
try:
    from src.modules.strategy.lstm_adapter import LSTMVolatilityAdapter
except ImportError:
    pytest.fail("❌ O arquivo src/modules/strategy/lstm_adapter.py não foi encontrado. O Agente QUANT precisa finalizar a tarefa primeiro.")

@pytest.fixture
def mock_strategy_dependencies():
    """
    Engana o adaptador para ele achar que carregou os modelos reais.
    Isso permite testar a lógica do código sem os arquivos pesados.
    """
    with patch('tensorflow.keras.models.load_model') as mock_keras, \
         patch('joblib.load') as mock_joblib:
        
        # 1. Mock do Modelo Keras (Sempre diz que a probabilidade é alta: 0.85)
        mock_model = MagicMock()
        mock_model.predict.return_value = [[0.85]] 
        mock_keras.return_value = mock_model
        
        # 2. Mock do Scaler e Params
        mock_scaler = MagicMock()
        # Retorna array de zeros com shape correto quando chamar transform()
        mock_scaler.transform.side_effect = lambda x: [[0.0] * x.shape[1]]
        mock_joblib.return_value = mock_scaler
        
        # Quando carregar 'params', retorna um dict fictício
        # O side_effect ajuda a diferenciar qual joblib.load foi chamado, 
        # mas para simplificar, vamos assumir que o mock retorna o scaler, 
        # e ajustamos o Adapter para ser robusto ou mockamos especificamente o params.
        # Estratégia melhor: Mockar os atributos da classe diretamente no teste abaixo.
        
        yield mock_keras, mock_joblib

def test_end_to_end_flow(mock_strategy_dependencies):
    """
    Testa: MarketData -> EventBus -> Adapter -> SignalEvent
    """
    # 1. Setup: Instancia o Adaptador com caminhos falsos (os mocks vão interceptar)
    # Precisamos garantir que o joblib carregue os parametros corretos
    with patch('joblib.load') as loader:
        # Primeiro call (scaler), Segundo call (params)
        loader.side_effect = [MagicMock(), {'lookback': 5, 'n_features': 10}]
        
        adapter = LSTMVolatilityAdapter("models/dummy_model")
    
    # Registra o adaptador manualmente (como o main.py faria)
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