# newapp/src/strategies/__init__.py
"""Strategy module for ML model training."""

from newapp.src.strategies.base import BaseStrategy, calculate_target
from newapp.src.strategies.lstm_volatility import LSTMVolatilityStrategy, LSTMVolatilityWrapper

__all__ = [
    'BaseStrategy',
    'calculate_target',
    'LSTMVolatilityStrategy',
    'LSTMVolatilityWrapper',
]
