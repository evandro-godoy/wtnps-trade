"""Legacy Monitor Engine - Replica comportamento exacto do monitor_ui.py.

Utiliza a mesma lógica:
1. Carrega estratégia LSTM
2. Calcula features e predições
3. Usa MarketContextAnalyzer para análise técnica
4. Mapeia sinal para CALL/PUT baseado em EMA20
5. Retorna contexto técnico completo
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from newapp.src.analysis.context_analyzer import MarketContextAnalyzer
from newapp.src.data_handler.provider import get_default_provider

logger = logging.getLogger(__name__)


class LegacyMonitorEngine:
    """Engine que replica exatamente o comportamento do monitor_ui.py legado."""
    
    def __init__(self):
        """Initialize legacy monitor engine."""
        self.repo_root = self._get_repository_root()
        self.models_dir = self.repo_root / 'newapp' / 'models'
        
        # Initialize context analyzer (identical to legacy)
        self.context_analyzer = MarketContextAnalyzer(
            ema_fast=9,
            sma_fast=20,
            sma_slow=50,
            sma_lookback=200,
            rsi_period=14,
            lookback_levels=20,
            strong_candle_threshold=0.65
        )
        
        # Cache para modelos carregados
        self._model_cache: Dict[str, Tuple] = {}
        
        logger.info("LegacyMonitorEngine initialized")
    
    def _get_repository_root(self) -> Path:
        """Find repository root."""
        current = Path(__file__).resolve()
        for parent in [current] + list(current.parents):
            if (parent / 'pyproject.toml').exists():
                return parent
        return Path(__file__).resolve().parents[3]
    
    def _load_strategy_class(self, strategy_name: str, module_name: str):
        """Load strategy class from newapp.src.strategies."""
        cache_key = f"{module_name}.{strategy_name}"
        if hasattr(self, '_strategy_cache') and cache_key in self._strategy_cache:
            return self._strategy_cache[cache_key]
        
        try:
            module_path = f"newapp.src.strategies.{module_name}"
            module = __import__(module_path, fromlist=[strategy_name])
            strategy_class = getattr(module, strategy_name)
            
            if not hasattr(self, '_strategy_cache'):
                self._strategy_cache = {}
            self._strategy_cache[cache_key] = strategy_class
            
            logger.info(f"Loaded strategy: {strategy_name} from {module_name}")
            return strategy_class
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load strategy {strategy_name}: {e}")
            raise
    
    def _load_model(self, symbol: str, strategy_name: str, timeframe: str, module_name: str):
        """Load trained model exactly like legacy."""
        cache_key = f"{symbol}_{strategy_name}_{timeframe}"
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]
        
        model_prefix = self.models_dir / f"{symbol}_{strategy_name}_{timeframe}_prod"
        strategy_class = self._load_strategy_class(strategy_name, module_name)
        
        try:
            import joblib
            model = strategy_class.load(str(model_prefix))
            
            scaler_path = f"{model_prefix}_scaler.joblib"
            params_path = f"{model_prefix}_params.joblib"
            
            scaler = joblib.load(scaler_path) if Path(scaler_path).exists() else None
            params = joblib.load(params_path) if Path(params_path).exists() else {}
            
            self._model_cache[cache_key] = (model, scaler, params)
            logger.info(f"Model loaded: {model_prefix}")
            return model, scaler, params
            
        except Exception as e:
            logger.error(f"Error loading model {cache_key}: {e}")
            raise
    
    def predict_on_candle(
        self,
        data: pd.DataFrame,
        symbol: str,
        timeframe: str,
        strategy_name: str = "LSTMVolatilityStrategy",
        module_name: str = "lstm_volatility"
    ) -> Dict:
        """
        Predict on last COMPLETED candle using EXACT legacy logic.
        
        Returns full context like monitor_ui.py:
        {
            'timestamp': datetime,
            'probability': float (0-1),
            'direction': str (CALL/PUT based on EMA20),
            'signal': str (COMPRA/VENDA based on direction),
            'price': float,
            'trend': str (ALTA/BAIXA/LATERAL),
            'trend_strength': str (FORTE/MODERADA/FRACA),
            'rsi': float,
            'rsi_condition': str,
            'ema_9': float,
            'ema_20': float,
            'sma_20': float,
            'sma_50': float,
            'support': float,
            'resistance': float,
            'pattern': str,
            'signal_valid': bool
        }
        """
        if data.empty or len(data) < 200:
            logger.warning(f"Insufficient data for prediction: {len(data)} candles")
            return None
        
        try:
            # Load model and strategy
            model, scaler, params = self._load_model(symbol, strategy_name, timeframe, module_name)
            strategy_class = self._load_strategy_class(strategy_name, module_name)
            strategy_params = params.get('strategy_params', {})
            strategy = strategy_class(**strategy_params)
            
            # === STEP 1: Calculate features (EXACTLY like monitor_engine.py) ===
            features_df = strategy.define_features(data.copy())
            
            # Check sufficient data
            if len(features_df) < strategy.lookback + 10:
                logger.warning(f"Insufficient data after features: {len(features_df)}")
                return None
            
            # === STEP 2: Calculate EMA20 for direction (CALL/PUT) ===
            if 'ema_20' not in features_df.columns:
                features_df['ema_20'] = features_df['close'].ewm(span=20, adjust=False).mean()
            
            # === STEP 3: Prepare data for prediction ===
            lookback = strategy.lookback
            features_subset = features_df.tail(lookback + 20)
            feature_cols = strategy.get_feature_names()
            
            missing_features = [col for col in feature_cols if col not in features_subset.columns]
            if missing_features:
                logger.error(f"Missing features: {missing_features}")
                return None
            
            X_input = features_subset[feature_cols]
            
            # === STEP 4: Generate prediction ===
            proba = model.predict_proba(X_input)
            
            if len(proba) == 0:
                logger.warning("No predictions generated (insufficient sequences)")
                return None
            
            # Get LAST prediction (most recent candle)
            prob_class1 = float(proba[-1, 1])  # Probability of class 1 (volatility)
            
            # === STEP 5: Get last candle data ===
            last_candle = data.iloc[-1]
            current_time = data.index[-1]
            current_price = float(last_candle['close'])
            ema_20 = float(features_df['ema_20'].iloc[-1])
            ema_9 = float(features_df.get('ema_9', features_df['close'].ewm(span=9, adjust=False).mean()).iloc[-1])
            
            # === STEP 6: Determine DIRECTION based on EMA20 (EXACT legacy logic) ===
            direction = "CALL" if current_price > ema_20 else "PUT"
            signal = "COMPRA" if direction == "CALL" else "VENDA"
            
            # === STEP 7: Full technical analysis ===
            context = self.context_analyzer.analyze(data)
            
            # === STEP 8: Signal validation (optional, like legacy) ===
            signal_valid, validation_reason = self.context_analyzer.validate_signal(
                ml_direction=direction,
                context=context,
                require_trend_alignment=False
            )
            
            # === STEP 9: Return complete context ===
            result = {
                'timestamp': current_time,
                'probability': prob_class1,
                'direction': direction,
                'signal': signal,
                'price': current_price,
                'ema_9': ema_9,
                'ema_20': ema_20,
                'sma_20': float(context.get('sma_fast', 0)),
                'sma_50': float(context.get('sma_slow', 0)),
                'trend': context['trend'],
                'trend_strength': context['trend_strength'],
                'rsi': float(context['rsi']),
                'rsi_condition': context['rsi_condition'],
                'support': float(context['support']),
                'resistance': float(context['resistance']),
                'pattern': context['pattern'],
                'signal_valid': signal_valid,
                'validation_reason': validation_reason
            }
            
            logger.debug(f"Prediction: {signal} ({prob_class1*100:.2f}%) - {direction}")
            return result
            
        except Exception as e:
            logger.error(f"Error in predict_on_candle: {e}", exc_info=True)
            return None


# Singleton instance
_engine_instance: Optional[LegacyMonitorEngine] = None


def get_legacy_monitor_engine() -> LegacyMonitorEngine:
    """Get or create singleton instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LegacyMonitorEngine()
    return _engine_instance
