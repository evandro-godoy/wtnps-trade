"""Adaptador da estratégia LSTM Volatility para arquitetura event-driven."""

import logging
import numpy as np
import pandas as pd
import joblib
from tensorflow import keras
from typing import Optional

from src.events import MarketDataEvent, SignalEvent
from src.strategies.lstm_volatility import LSTMVolatilityStrategy

logger = logging.getLogger(__name__)


class LSTMVolatilityAdapter:
    """Adaptador que converte eventos de mercado em sinais usando modelo LSTM."""
    
    def __init__(self, model_path: Optional[str] = None, scaler_path: Optional[str] = None,
                 lookback: int = 108, event_bus=None):
        """
        Inicializa o adaptador LSTM.
        
        Args:
            model_path: Caminho para o modelo .keras (opcional para testes com mock)
            scaler_path: Caminho para o scaler .joblib (opcional para testes com mock)
            lookback: Número de candles para criar sequências
            event_bus: Instância do EventBus para publicar sinais (opcional)
        """
        self.model = None
        self.scaler = None
        self.lookback = lookback
        self.buffer = pd.DataFrame()
        self.event_bus = event_bus
        self.processed_count = 0
        self.signal_count = 0
        
        if model_path and scaler_path:
            self.load_artifacts(model_path, scaler_path)

    def load_artifacts(self, model_path: str, scaler_path: str):
        """Carrega modelo e scaler dos arquivos."""
        try:
            self.model = keras.models.load_model(model_path)
            self.scaler = joblib.load(scaler_path)
            logger.info(f"Modelo carregado: {model_path}")
            logger.info(f"Scaler carregado: {scaler_path}")
        except Exception as e:
            logger.error(f"Erro ao carregar artefatos do modelo: {e}")
            raise

    def on_market_data(self, event: MarketDataEvent):
        """
        Handler para eventos de dados de mercado.
        
        Args:
            event: MarketDataEvent com dados OHLCV
        """
        try:
            # Converte evento para linha de DataFrame com índice temporal
            new_row = pd.DataFrame([{
                'open': event.open,
                'high': event.high,
                'low': event.low,
                'close': event.close,
                'volume': event.volume
            }], index=[event.timestamp])  # Define timestamp como índice
            
            # Adiciona ao buffer
            self.buffer = pd.concat([self.buffer, new_row])
            self.processed_count += 1
            
            # Mantém apenas lookback + margem para cálculo de features
            if len(self.buffer) > self.lookback + 100:
                self.buffer = self.buffer.iloc[-(self.lookback + 100):]
            
            # Só gera sinal se tiver dados suficientes e modelo carregado
            if len(self.buffer) >= self.lookback and self.model is not None:
                self._generate_signal(event)
                
        except Exception as e:
            logger.exception(f"Erro ao processar MarketDataEvent: {e}")

    def _generate_signal(self, event: MarketDataEvent):
        """Gera sinal de trading a partir do buffer atual."""
        try:
            # Cria features usando estratégia LSTM
            strategy = LSTMVolatilityStrategy()
            features_df = strategy.define_features(self.buffer.copy())
            
            if len(features_df) < self.lookback:
                logger.debug(f"Features insuficientes: {len(features_df)} < {self.lookback}")
                return
            
            # Obtém nomes das features esperadas
            feature_names = strategy.get_feature_names()
            
            # Extrai e normaliza features
            X = features_df[feature_names].values[-self.lookback:]
            
            if self.scaler is not None:
                X_scaled = self.scaler.transform(X)
            else:
                X_scaled = X
            
            # Escalar os dados
            X_scaled = self.scaler.transform(X)

            # 🎯 HARDENING: Garante que é array antes do reshape
            X_scaled = np.array(X_scaled)

            # Reshape para (batch_size, time_steps, n_features)
            # O erro acontecia aqui pq listas não têm .reshape()
            X_seq = X_scaled.reshape(1, self.lookback, len(feature_names))
            
            # Predição
            prediction = self.model.predict(X_seq, verbose=0)
            pred_class = int(np.argmax(prediction[0]))
            confidence = float(np.max(prediction[0]))
            
            # Mapeia predição para sinal
            signal_str = "COMPRA" if pred_class == 1 else "VENDA"
            
            # Cria evento de sinal
            signal_event = SignalEvent(
                symbol=event.symbol,
                signal=signal_str,
                confidence=confidence,
                price=event.close,
                timestamp=event.timestamp,
                metadata={
                    'strategy': 'LSTMVolatilityStrategy',
                    'prediction': pred_class,
                    'probabilities': prediction[0].tolist()
                }
            )
            
            self.signal_count += 1
            
            # Publica sinal no event bus (se disponível)
            if self.event_bus is not None:
                self.event_bus.publish(signal_event)
                logger.debug(f"Sinal publicado: {signal_str} (conf={confidence:.2f})")
            
        except Exception as e:
            logger.exception(f"Erro ao gerar sinal: {e}")

    def get_stats(self):
        """Retorna estatísticas do adaptador."""
        return {
            'processed_count': self.processed_count,
            'signal_count': self.signal_count,
            'buffer_size': len(self.buffer),
            'model_loaded': self.model is not None,
            'scaler_loaded': self.scaler is not None
        }
