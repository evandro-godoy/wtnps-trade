"""Backtest Engine for newapp.

Provides a lightweight, incremental backtesting workflow using existing
AssetsRates data and centralized indicators.

Strategy Logic (initial stub):
- Generates BUY when EMA9 crosses above SMA20.
- Generates SELL when EMA9 crosses below SMA20.
- Single position at a time; reverse signal closes and flips.

Future Extensions:
- Pluggable strategy classes (similar ao padrão Strategy do core).
- Parametrização de Stop/Take dinâmicos.
- Integração com modelos ML (LSTM / DRL) para sinais.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any

import math
import pandas as pd
from sqlalchemy.orm import Session

from newapp.src.database.repository import (
    AssetsRatesRepository,
    BacktestRunRepository,
    BacktestTradeRepository,
)

@dataclass
class BacktestConfig:
    symbol: str
    timeframe_int: int
    timeframe_str: str
    start_date: datetime
    end_date: datetime
    initial_capital: float = 100_000.0
    position_size: float = 1.0  # Lotes, pode ser adaptado
    strategy: str = "ema_crossover"
    stop_loss_pct: Optional[float] = None  # Ex: 0.01 (1%)
    take_profit_pct: Optional[float] = None  # Ex: 0.02 (2%)

class BacktestEngine:
    """Executes a backtest over stored candle data.

    Workflow:
        1. _load_prices: Recupera candles + indicadores.
        2. _prepare_indicators: Garante cálculo de EMA/SMA se ausente.
        3. _generate_signals_stub: Deriva sinais simples (BUY/SELL/HOLD).
        4. _simulate_trades: Itera candles aplicando lógica de posição.
        5. _compute_metrics: Calcula estatísticas de performance.
        6. Persist run + trades.
    """

    def __init__(self, db: Session, config: BacktestConfig) -> None:
        self.db = db
        self.config = config
        self.df: pd.DataFrame | None = None
        self.signals: pd.Series | None = None
        self.run_id: Optional[int] = None
        self.trades: List[Dict[str, Any]] = []

    # ---------------- Public API -----------------
    def run_backtest(self) -> Dict[str, Any]:
        self._load_prices()
        if self.df is None or self.df.empty:
            return {"error": "No price data found for specified range."}
        self._prepare_indicators()
        self._generate_signals_stub()
        self._simulate_trades()
        summary = self._compute_metrics()
        return summary

    async def run_backtest_stream(self, update_cb, update_interval: int = 5) -> Dict[str, Any]:
        """Execute backtest streaming progress snapshots.

        Args:
            update_cb: Awaitable accepting a snapshot dict.
            update_interval: Emit progress every N candles (always emits on trade events).

        Returns:
            Final summary dict (same as run_backtest).
        """
        self._load_prices()
        if self.df is None or self.df.empty:
            return {"error": "No price data found for specified range."}
        self._prepare_indicators()
        self._generate_signals_stub()

        # Prepare run row
        cfg = self.config
        run = BacktestRunRepository.create_run(
            self.db,
            symbol=cfg.symbol,
            timeframe=cfg.timeframe_str,
            start_date=cfg.start_date,
            end_date=cfg.end_date,
            strategy=cfg.strategy,
            initial_capital=cfg.initial_capital,
        )
        self.run_id = run.id

        position: Optional[Dict[str, Any]] = None
        capital = cfg.initial_capital
        peak_equity = capital
        max_drawdown = 0.0
        total = len(self.df.index)

        for idx, (ts, row) in enumerate(self.df.iterrows()):
            price = float(row["close"])
            signal = self.signals.loc[ts]

            # Compute equity and drawdown
            if position is not None:
                dir_mult = 1 if position["direction"] == "BUY" else -1
                unrealized = dir_mult * (price - position["entry_price"]) * cfg.position_size
                equity = capital + unrealized
                peak_equity = max(peak_equity, equity)
                dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0
                max_drawdown = max(max_drawdown, dd)
            else:
                equity = capital

            trade_closed = None
            trade_opened = None

            # Exit logic on reverse signal
            if position is not None and signal in ("BUY", "SELL") and signal != position["direction"]:
                dir_mult = 1 if position["direction"] == "BUY" else -1
                pnl = dir_mult * (price - position["entry_price"]) * cfg.position_size
                capital += pnl
                return_pct = pnl / cfg.initial_capital if cfg.initial_capital > 0 else 0
                BacktestTradeRepository.close_trade(
                    self.db,
                    trade_id=position["trade_id"],
                    exit_time=ts,
                    exit_price=price,
                    reason_exit="REVERSE",
                    pnl=pnl,
                    return_pct=return_pct,
                )
                trade_closed = {
                    "entry_time": position["entry_time"],
                    "exit_time": ts,
                    "direction": position["direction"],
                    "entry_price": position["entry_price"],
                    "exit_price": price,
                    "pnl": pnl,
                    "return_pct": return_pct,
                }
                self.trades.append(trade_closed)
                position = None

            # Entry logic
            if position is None and signal in ("BUY", "SELL"):
                trade = BacktestTradeRepository.add_trade(
                    self.db,
                    run_id=self.run_id,
                    symbol=cfg.symbol,
                    timeframe=cfg.timeframe_str,
                    entry_time=ts,
                    direction=signal,
                    entry_price=price,
                    stop_loss=None,
                    take_profit=None,
                    volume=cfg.position_size,
                    indicators_snapshot={
                        "ema_9": row.get("ema_9"),
                        "sma_20": row.get("sma_20"),
                    },
                )
                position = {
                    "direction": signal,
                    "entry_price": price,
                    "entry_time": ts,
                    "trade_id": trade.id,
                }
                trade_opened = {
                    "entry_time": ts,
                    "direction": signal,
                    "entry_price": price,
                }

            # Emit progress snapshot
            if (idx % update_interval == 0) or trade_opened or trade_closed or idx == total - 1:
                snapshot = {
                    "type": "progress",
                    "run_id": self.run_id,
                    "index": idx + 1,
                    "total": total,
                    "timestamp": ts.isoformat(),
                    "price": price,
                    "equity": equity,
                    "capital": capital,
                    "drawdown": max_drawdown,
                    "open_position": None if position is None else {
                        "direction": position["direction"],
                        "entry_price": position["entry_price"],
                        "entry_time": position["entry_time"].isoformat(),
                    },
                    "trade_opened": trade_opened,
                    "trade_closed": trade_closed,
                }
                await update_cb(snapshot)

        # Close final open position (END reason)
        if position is not None:
            last_ts = self.df.index[-1]
            last_price = float(self.df.iloc[-1]["close"])
            dir_mult = 1 if position["direction"] == "BUY" else -1
            pnl = dir_mult * (last_price - position["entry_price"]) * cfg.position_size
            capital += pnl
            return_pct = pnl / cfg.initial_capital if cfg.initial_capital > 0 else 0
            BacktestTradeRepository.close_trade(
                self.db,
                trade_id=position["trade_id"],
                exit_time=last_ts,
                exit_price=last_price,
                reason_exit="END",
                pnl=pnl,
                return_pct=return_pct,
            )
            trade_closed = {
                "entry_time": position["entry_time"],
                "exit_time": last_ts,
                "direction": position["direction"],
                "entry_price": position["entry_price"],
                "exit_price": last_price,
                "pnl": pnl,
                "return_pct": return_pct,
            }
            self.trades.append(trade_closed)
            snapshot = {
                "type": "progress",
                "run_id": self.run_id,
                "index": total,
                "total": total,
                "timestamp": last_ts.isoformat(),
                "price": last_price,
                "equity": capital,
                "capital": capital,
                "drawdown": max_drawdown,
                "open_position": None,
                "trade_opened": None,
                "trade_closed": trade_closed,
            }
            await update_cb(snapshot)

        self._final_capital = capital
        self._max_drawdown = max_drawdown
        summary = self._compute_metrics()
        await update_cb({"type": "complete", **summary})
        return summary

    # --------------- Internal Steps ---------------
    def _load_prices(self) -> None:
        cfg = self.config
        df = AssetsRatesRepository.get_rates_range(
            self.db, cfg.symbol, cfg.timeframe_int, cfg.start_date, cfg.end_date
        )
        if df.empty:
            self.df = df
            return
        # Ensure chronological order
        df = df.sort_index()
        self.df = df

    def _prepare_indicators(self) -> None:
        assert self.df is not None
        df = self.df.copy()
        # Indicators might already be enriched in AssetsRates; compute if missing
        if "ema_9" not in df.columns or df["ema_9"].isna().all():
            df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        if "sma_20" not in df.columns or df["sma_20"].isna().all():
            df["sma_20"] = df["close"].rolling(window=20).mean()
        self.df = df

    def _generate_signals_stub(self) -> None:
        assert self.df is not None
        df = self.df
        # BUY on ema9 crossing above sma20, SELL on crossing below
        ema = df["ema_9"]
        sma = df["sma_20"]
        crossover_up = (ema > sma) & (ema.shift(1) <= sma.shift(1))
        crossover_down = (ema < sma) & (ema.shift(1) >= sma.shift(1))
        signals = pd.Series("HOLD", index=df.index)
        signals[crossover_up] = "BUY"
        signals[crossover_down] = "SELL"
        self.signals = signals

    def _simulate_trades(self) -> None:
        assert self.df is not None and self.signals is not None
        cfg = self.config
        # Persist initial run row
        run = BacktestRunRepository.create_run(
            self.db,
            symbol=cfg.symbol,
            timeframe=cfg.timeframe_str,
            start_date=cfg.start_date,
            end_date=cfg.end_date,
            strategy=cfg.strategy,
            initial_capital=cfg.initial_capital,
        )
        self.run_id = run.id

        position: Optional[Dict[str, Any]] = None
        capital = cfg.initial_capital
        peak_equity = capital
        max_drawdown = 0.0

        for ts, row in self.df.iterrows():
            price = float(row["close"])
            signal = self.signals.loc[ts]

            # Update unrealized PnL if position open
            if position is not None:
                dir_mult = 1 if position["direction"] == "BUY" else -1
                unrealized = dir_mult * (price - position["entry_price"]) * cfg.position_size
                equity = capital + unrealized
                peak_equity = max(peak_equity, equity)
                dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0
                max_drawdown = max(max_drawdown, dd)
            else:
                equity = capital

            # Exit logic: opposite signal
            if position is not None and signal in ("BUY", "SELL") and signal != position["direction"]:
                dir_mult = 1 if position["direction"] == "BUY" else -1
                pnl = dir_mult * (price - position["entry_price"]) * cfg.position_size
                capital += pnl
                return_pct = pnl / cfg.initial_capital if cfg.initial_capital > 0 else 0
                BacktestTradeRepository.close_trade(
                    self.db,
                    trade_id=position["trade_id"],
                    exit_time=ts,
                    exit_price=price,
                    reason_exit="REVERSE",
                    pnl=pnl,
                    return_pct=return_pct,
                )
                self.trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": ts,
                    "direction": position["direction"],
                    "entry_price": position["entry_price"],
                    "exit_price": price,
                    "pnl": pnl,
                    "return_pct": return_pct,
                })
                position = None

            # Entry logic
            if position is None and signal in ("BUY", "SELL"):
                trade = BacktestTradeRepository.add_trade(
                    self.db,
                    run_id=self.run_id,
                    symbol=cfg.symbol,
                    timeframe=cfg.timeframe_str,
                    entry_time=ts,
                    direction=signal,
                    entry_price=price,
                    stop_loss=None,
                    take_profit=None,
                    volume=cfg.position_size,
                    indicators_snapshot={
                        "ema_9": row.get("ema_9"),
                        "sma_20": row.get("sma_20"),
                    },
                )
                position = {
                    "direction": signal,
                    "entry_price": price,
                    "entry_time": ts,
                    "trade_id": trade.id,
                }

        # Close final open position at last price
        if position is not None:
            last_ts = self.df.index[-1]
            last_price = float(self.df.iloc[-1]["close"])
            dir_mult = 1 if position["direction"] == "BUY" else -1
            pnl = dir_mult * (last_price - position["entry_price"]) * cfg.position_size
            capital += pnl
            return_pct = pnl / cfg.initial_capital if cfg.initial_capital > 0 else 0
            BacktestTradeRepository.close_trade(
                self.db,
                trade_id=position["trade_id"],
                exit_time=last_ts,
                exit_price=last_price,
                reason_exit="END",
                pnl=pnl,
                return_pct=return_pct,
            )
            self.trades.append({
                "entry_time": position["entry_time"],
                "exit_time": last_ts,
                "direction": position["direction"],
                "entry_price": position["entry_price"],
                "exit_price": last_price,
                "pnl": pnl,
                "return_pct": return_pct,
            })

        self._final_capital = capital
        self._max_drawdown = max_drawdown

    def _compute_metrics(self) -> Dict[str, Any]:
        if self.run_id is None:
            return {"error": "Run not executed"}
        trades = self.trades
        total_trades = len(trades)
        wins = sum(1 for t in trades if t["pnl"] > 0)
        losses = sum(1 for t in trades if t["pnl"] <= 0)
        win_rate = wins / total_trades if total_trades > 0 else 0.0
        gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
        gross_loss = -sum(t["pnl"] for t in trades if t["pnl"] < 0)
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else math.inf if gross_profit > 0 else 0.0
        avg_trade_return = (sum(t["return_pct"] for t in trades) / total_trades) if total_trades > 0 else 0.0
        net_profit = self._final_capital - self.config.initial_capital

        # Persist final metrics
        BacktestRunRepository.finalize_run(
            self.db,
            run_id=self.run_id,
            final_capital=self._final_capital,
            net_profit=net_profit,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=self._max_drawdown,
            avg_trade_return=avg_trade_return,
        )

        return {
            "run_id": self.run_id,
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe_str,
            "strategy": self.config.strategy,
            "initial_capital": self.config.initial_capital,
            "final_capital": self._final_capital,
            "net_profit": net_profit,
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": self._max_drawdown,
            "avg_trade_return": avg_trade_return,
        }

__all__ = ["BacktestConfig", "BacktestEngine"]
