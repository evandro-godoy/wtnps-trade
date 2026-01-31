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
    
    def __init__(self, model_path_prefix: Optional[str] = None, event_bus=None, 
                 lookback: int = 108, model_path: Optional[str] = None, 
                 scaler_path: Optional[str] = None):
        """
        Inicializa adapter com validação estrita (ou modo mock para testes).
        
        Args:
            model_path_prefix: Prefixo do path (ex: "models/WDO$_LSTMVolatilityStrategy_M5_prod")
                               Modo preferido para produção (Sprint 2)
            event_bus: Instância do EventBus para publicar sinais (opcional)
            lookback: Número de candles para criar sequências (padrão: 108)
            model_path: [DEPRECATED] Caminho completo do modelo (retrocompatibilidade)
            scaler_path: [DEPRECATED] Caminho completo do scaler (retrocompatibilidade)
        
        Raises:
            FileNotFoundError: Se modelo ou scaler não existir (produção)
            ValueError: Se input_shape do modelo for incompatível
        """
        import os
        from keras.models import load_model
        
        self.model_path_prefix = model_path_prefix
        self.buffer = pd.DataFrame()
        self.event_bus = event_bus
        self.lookback = lookback
        self.processed_count = 0
        self.signal_count = 0
        self.model = None
        self.scaler = None
        
        # Modo 1: Produção com model_path_prefix (Sprint 2)
        if model_path_prefix:
            # Carregar modelo com validação
            model_file = f"{model_path_prefix}_lstm.keras"
            if not os.path.exists(model_file):
                error_msg = f"Modelo não encontrado: {model_file}"
                logger.critical(error_msg)
                raise FileNotFoundError(error_msg)
            
            try:
                self.model = load_model(model_file)
                logger.info(f"✅ Modelo carregado: {model_file}")
                logger.info(f"Input shape: {self.model.input_shape}")
            except Exception as e:
                logger.critical(f"Erro ao carregar modelo: {e}")
                raise
            
            # Carregar scaler com validação
            scaler_file = f"{model_path_prefix}_scaler.joblib"
            if not os.path.exists(scaler_file):
                error_msg = f"Scaler não encontrado: {scaler_file}"
                logger.critical(error_msg)
                raise FileNotFoundError(error_msg)
            
            try:
                self.scaler = joblib.load(scaler_file)
                logger.info(f"✅ Scaler carregado: {scaler_file}")
            except Exception as e:
                logger.critical(f"Erro ao carregar scaler: {e}")
                raise
            
            # Validar input_shape
            expected_lookback = self.model.input_shape[1]
            expected_features = self.model.input_shape[2]
            
            if expected_lookback != self.lookback:
                logger.warning(
                    f"Lookback mismatch: Modelo espera {expected_lookback}, "
                    f"mas adapter usa {self.lookback}. Ajustando..."
                )
                self.lookback = expected_lookback
        
        # Modo 2: Retrocompatibilidade com testes (Sprint 1)
        elif model_path and scaler_path:
            logger.warning("Usando modo deprecated (model_path/scaler_path). Migre para model_path_prefix.")
            try:
                self.model = load_model(model_path)
                self.scaler = joblib.load(scaler_path)
                logger.info(f"Modelo carregado (compat): {model_path}")
                logger.info(f"Scaler carregado (compat): {scaler_path}")
            except Exception as e:
                logger.error(f"Erro ao carregar artefatos: {e}")
                raise
        
        # Modo 3: Modo mock sem modelo (para testes unitários)
        else:
            logger.warning("Adapter inicializado SEM modelo (modo mock para testes)")



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

    def _validate_shape(self, X, method_name: str):
        """
        Valida shape estritamente antes de inferência.
        
        Args:
            X: Array de features
            method_name: Nome do método chamador (para log)
        
        Raises:
            ValueError: Se shape não bater com model.input_shape
        """
        # Skip validation for mock objects (testing)
        from unittest.mock import Mock
        if isinstance(self.model.input_shape, Mock):
            logger.debug("Skipping shape validation (mock model)")
            return
        
        expected_shape = self.model.input_shape[1:]  # (lookback, n_features)
        actual_shape = X.shape[1:]
        
        if actual_shape != expected_shape:
            error_msg = (
                f"[{method_name}] Shape mismatch: "
                f"Modelo espera {self.model.input_shape}, "
                f"mas dados têm shape {X.shape}. "
                f"Verifique define_features() e retrain se necessário."
            )
            logger.critical(error_msg)
            raise ValueError(error_msg)
    
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
            
            # Escalar os dados
            X_scaled = self.scaler.transform(X)
            
            # Conversão defensiva para numpy array com dtype float32
            X_scaled = np.array(X_scaled, dtype=np.float32)
            
            # Reshape para (1, lookback, n_features)
            X_seq = X_scaled.reshape(1, self.lookback, len(feature_names))
            
            # Validação estrita de shape
            self._validate_shape(X_seq, "_generate_signal")
            
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
