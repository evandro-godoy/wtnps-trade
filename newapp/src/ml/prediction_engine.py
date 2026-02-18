"""ML Prediction Engine - Integrates newapp trained models for real predictions.

Loads LSTM/DRL models from newapp/models/ directory and generates trading signals
using the newapp strategy classes with real-time data.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Strategy cache to avoid repeated imports
_strategy_cache: Dict[str, any] = {}


def _load_strategy_class(strategy_name: str, module_name: str):
    """Load strategy class from newapp.src.strategies.
    
    Args:
        strategy_name: Class name (e.g., "LSTMVolatilityStrategy")
        module_name: Module name (e.g., "lstm_volatility")
        
    Returns:
        Strategy class
    """
    cache_key = f"{module_name}.{strategy_name}"
    if cache_key in _strategy_cache:
        return _strategy_cache[cache_key]
    
    try:
        module_path = f"newapp.src.strategies.{module_name}"
        module = __import__(module_path, fromlist=[strategy_name])
        strategy_class = getattr(module, strategy_name)
        _strategy_cache[cache_key] = strategy_class
        logger.info(f"Loaded strategy: {strategy_name} from {module_name}")
        return strategy_class
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to load strategy {strategy_name}: {e}")
        raise


def _get_repository_root() -> Path:
    """Find repository root by looking for pyproject.toml."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / 'pyproject.toml').exists():
            return parent
    # Fallback to 3 levels up from newapp/src/ml/
    return Path(__file__).resolve().parents[3]


class MLPredictionEngine:
    """Engine for generating ML predictions using newapp trained models.
    
    Features:
    - Loads LSTM/DRL models from newapp/models/ directory
    - Uses newapp strategy classes for feature engineering
    - Returns signals with probabilities and technical indicators
    - Thread-safe (stateless predictions)
    """
    
    def __init__(self, models_dir: Optional[Path] = None):
        """Initialize prediction engine.
        
        Args:
            models_dir: Path to models directory (default: newapp/models/)
        """
        self.repo_root = _get_repository_root()
        self.models_dir = models_dir or (self.repo_root / 'newapp' / 'models')
        
        # Cache for loaded models {"SYMBOL_STRATEGY_TIMEFRAME": model}
        self._model_cache: Dict[str, Tuple[any, any, Dict]] = {}
        
        logger.info(f"MLPredictionEngine initialized (models: {self.models_dir})")
    
    def _load_model(self, symbol: str, strategy_name: str, timeframe: str, module_name: str):
        """Load trained model, scaler, and params from disk.
        
        Args:
            symbol: Asset symbol (e.g., "WDO$")
            strategy_name: Strategy class name
            timeframe: Timeframe string
            module_name: Strategy module name for loading class
            
        Returns:
            Tuple of (model, scaler, params_dict)
        """
        cache_key = f"{symbol}_{strategy_name}_{timeframe}"
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]
        
        # Model file paths
        model_prefix = self.models_dir / f"{symbol}_{strategy_name}_{timeframe}_prod"
        
        # Load strategy class to use its load method
        strategy_class = _load_strategy_class(strategy_name, module_name)
        
        try:
            # Use strategy's load method
            model = strategy_class.load(str(model_prefix))
            logger.info(f"Model loaded: {model_prefix}")
            
            # Load scaler and params (if exist)
            import joblib
            scaler_path = f"{model_prefix}_scaler.joblib"
            params_path = f"{model_prefix}_params.joblib"
            
            scaler = joblib.load(scaler_path) if Path(scaler_path).exists() else None
            params = joblib.load(params_path) if Path(params_path).exists() else {}
            
            self._model_cache[cache_key] = (model, scaler, params)
            return model, scaler, params
            
        except FileNotFoundError as e:
            logger.error(f"Model not found: {model_prefix} - {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading model {cache_key}: {e}")
            raise
    
    def predict_batch(
        self,
        data: pd.DataFrame,
        symbol: str,
        timeframe: str,
        strategy_name: str = "LSTMVolatilityStrategy",
        module_name: str = "lstm_volatility",
        count: int = 10
    ) -> List[Dict]:
        """Generate predictions for recent COMPLETED candles using newapp models.
        
        IMPORTANT: Excludes the last candle (currently in formation) from predictions
        to ensure we only predict on closed candles with final prices.
        
        Args:
            data: DataFrame with OHLCV data (index=datetime, tz-aware)
            symbol: Asset symbol (e.g., "WDO$")
            timeframe: Timeframe string (e.g., "M5")
            strategy_name: Strategy class name (default: "LSTMVolatilityStrategy")
            module_name: Strategy module name (default: "lstm_volatility")
            count: Number of recent COMPLETED candles to predict (default: 10)
            
        Returns:
            List of prediction dicts with timestamp, signal, probability, etc.
        """
        if data.empty:
            logger.warning(f"Empty data for {symbol} {timeframe}")
            return []
        
        try:
            # Load model, scaler, params
            model, scaler, params = self._load_model(symbol, strategy_name, timeframe, module_name)
            
            # Load strategy class for feature engineering
            strategy_class = _load_strategy_class(strategy_name, module_name)
            strategy_params = params.get('strategy_params', {})
            strategy = strategy_class(**strategy_params)
            
            # Generate features using ALL data (including last candle for feature calculation)
            data_with_features = strategy.define_features(data.copy())
            feature_names = strategy.get_feature_names()
            
            if data_with_features.empty or len(data_with_features) < 200:
                logger.warning(f"Insufficient data after feature generation for {symbol} {timeframe}: {len(data_with_features)}")
                return []
            
            # Prepare full feature matrix for LSTM sequence creation
            X_full = data_with_features[feature_names]
            
            # Generate predictions using the full data
            predictions = []
            if hasattr(model, 'predict_proba'):
                # Classification model (LSTM, RandomForest)
                y_proba = model.predict_proba(X_full)[:, 1]  # Probability of class 1 (COMPRA)
                y_pred = (y_proba >= 0.5).astype(int)
            else:
                # Fallback for models without predict_proba
                y_pred = model.predict(X_full)
                y_proba = np.full(len(y_pred), 0.7)  # Default confidence
            
            if len(y_pred) == 0:
                logger.warning(f"No predictions generated for {symbol} {timeframe}")
                return []
            
            logger.info(f"Generated {len(y_pred)} raw predictions from model")
            
            # Get indices of completed candles (exclude last one in formation)
            # Since LSTM uses lookback, predictions array is already shorter than input
            # We need to map predictions back to original timestamps
            
            # The model returns predictions starting from index=lookback
            lookback = strategy_params.get('lookback', 108)
            
            # Get timestamps for all candles that have predictions
            prediction_start_idx = lookback
            available_timestamps = data_with_features.index[prediction_start_idx:]
            
            # Exclude the LAST candle from results (in formation)
            # But keep data for LSTM sequence calculation
            completed_timestamps = available_timestamps[:-1] if len(available_timestamps) > 1 else available_timestamps
            
            # Get last N completed predictions
            num_to_return = min(count, len(completed_timestamps))
            selected_timestamps = completed_timestamps[-num_to_return:]
            
            # Map predictions to selected completed timestamps
            for i, timestamp in enumerate(selected_timestamps):
                # Find index in predictions array
                pred_idx = len(y_pred) - num_to_return + i
                if pred_idx < 0 or pred_idx >= len(y_pred):
                    continue
                
                pred_class = int(y_pred[pred_idx])
                prob = float(y_proba[pred_idx])
                
                # Map class to signal (1=COMPRA, 0=VENDA/HOLD)
                signal = 'COMPRA' if pred_class == 1 else 'VENDA'
                
                # Get price from completed candle
                price = float(data.loc[timestamp, 'close']) if timestamp in data.index else 0.0
                
                # Extract indicators from features
                indicators = {}
                if timestamp in data_with_features.index:
                    row = data_with_features.loc[timestamp]
                    for feat in feature_names:
                        if feat in row.index:
                            val = row[feat]
                            if not pd.isna(val):
                                indicators[feat] = float(val)
                
                predictions.append({
                    'timestamp': timestamp,
                    'signal': signal,
                    'probability': prob,
                    'price': price,
                    'indicators': indicators,
                    'model': f"{symbol}_{strategy_name}_{timeframe}"
                })
            
            logger.info(f"Returning {len(predictions)} predictions for COMPLETED candles (excluded last in-formation)")
            return predictions
            
        except Exception as e:
            logger.error(f"Error in predict_batch for {symbol} {timeframe}: {e}", exc_info=True)
            return []
    
    def predict_latest(
        self,
        symbol: str,
        timeframe: str,
        count: int = 10,
        strategy_name: str = "LSTMVolatilityStrategy",
        module_name: str = "lstm_volatility"
    ) -> List[Dict]:
        """Generate predictions for latest candles using hybrid data loader.
        
        Args:
            symbol: Asset symbol
            timeframe: Timeframe string
            count: Number of recent candles to predict
            strategy_name: Strategy class name
            module_name: Strategy module name
            
        Returns:
            List of predictions (same format as predict_batch)
        """
        # Get latest data from hybrid provider
        from newapp.src.data_handler.provider import get_default_provider
        
        provider = get_default_provider()
        # Request more candles to ensure LSTM has enough lookback
        # LSTM needs lookback (108) + feature calculation (50) + prediction count
        required_candles = 108 + 50 + count
        data = provider.get_latest_candles(
            ticker=symbol,
            timeframe=timeframe,
            count=max(required_candles, 500)  # Minimum 500 for safety
        )
        
        if data.empty:
            logger.warning(f"No data available for {symbol} {timeframe}")
            return []
        
        logger.info(f"Fetched {len(data)} candles for predictions (need {required_candles})")
        
        # Run predictions on last N candles
        return self.predict_batch(data, symbol, timeframe, strategy_name, module_name, count)


# Singleton instance
_engine_instance: Optional[MLPredictionEngine] = None


def get_prediction_engine() -> MLPredictionEngine:
    """Get or create singleton prediction engine instance.
    
    Returns:
        MLPredictionEngine instance
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = MLPredictionEngine()
    return _engine_instance
