"""Backtest module for newapp.

Provides backtesting capabilities with streaming progress updates.
"""
from newapp.src.backtest.engine import BacktestEngine, BacktestConfig

__all__ = ['BacktestEngine', 'BacktestConfig']
