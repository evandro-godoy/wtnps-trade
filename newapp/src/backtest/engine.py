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
import logging
import joblib
from pathlib import Path
try:
    from tensorflow import keras  # type: ignore
except Exception:  # pragma: no cover
    keras = None  # Fallback if TF not available in environment
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
    use_ml: bool = True  # Tenta carregar modelo se artifacts existirem
    ml_hold_band: float = 0.05  # Banda neutra para classificação (ex: 0.45-0.55 => HOLD)

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
        self.logger = logging.getLogger(__name__)
        # ML artifacts
        self.model = None
        self.scaler = None
        self.model_params: Dict[str, Any] | None = None

    # ---------------- Public API -----------------
    def run_backtest(self) -> Dict[str, Any]:
        self._load_prices()
        if self.df is None or self.df.empty:
            return {"error": "No price data found for specified range."}
        self._prepare_indicators()
        # Tenta ML
        self._load_ml_artifacts()
        if not self._generate_signals_ml():
            self._generate_signals_stub()
        self._simulate_trades()
        summary = self._compute_metrics()
        return summary

    async def run_backtest_stream(self, update_cb, update_interval: int = 5) -> Dict[str, Any]:
        """Execute streaming emitting only signal/activity log entries.

        Removes equity/drawdown/trade simulation. Emits simplified progress
        snapshots containing price, indicators and derived signal. Designed to
        feed the activity log UI (similar ao Monitor).

        Args:
            update_cb: Awaitable that receives snapshot dicts.
            update_interval: Emit snapshot every N candles (always emits on BUY/SELL and last candle).
        Returns:
            Summary dict with basic signal counts.
        """
        self._load_prices()
        if self.df is None or self.df.empty:
            return {"error": "No price data found for specified range."}
        self._prepare_indicators()
        self._load_ml_artifacts()
        if not self._generate_signals_ml():
            self._generate_signals_stub()

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

        total = len(self.df.index)
        buy_signals = 0
        sell_signals = 0

        for idx, (ts, row) in enumerate(self.df.iterrows()):
            price = float(row["close"])
            signal = self.signals.loc[ts]
            if signal == "BUY":
                buy_signals += 1
                message = "Sinal BUY - EMA9 cruzou acima da SMA20"
            elif signal == "SELL":
                sell_signals += 1
                message = "Sinal SELL - EMA9 cruzou abaixo da SMA20"
            else:
                message = "HOLD - Sem crossover"

            if (idx % update_interval == 0) or signal in ("BUY", "SELL") or idx == total - 1:
                snapshot = {
                    "type": "progress",
                    "run_id": self.run_id,
                    "index": idx + 1,
                    "total": total,
                    "timestamp": ts.isoformat(),
                    "price": price,
                    "signal": signal,
                    "ema_9": row.get("ema_9"),
                    "sma_20": row.get("sma_20"),
                    "message": message,
                }
                await update_cb(snapshot)

        # Finalize run with minimal metrics (no trades simulated)
        BacktestRunRepository.finalize_run(
            self.db,
            run_id=self.run_id,
            final_capital=cfg.initial_capital,  # unchanged
            net_profit=0.0,
            total_trades=0,
            wins=0,
            losses=0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            avg_trade_return=0.0,
        )

        summary = {
            "run_id": self.run_id,
            "symbol": cfg.symbol,
            "timeframe": cfg.timeframe_str,
            "strategy": cfg.strategy,
            "total_candles": total,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "start": cfg.start_date.isoformat(),
            "end": cfg.end_date.isoformat(),
        }
        await update_cb({"type": "complete", **summary})
        return summary

    # --------------- Internal Steps ---------------
    def _load_prices(self) -> None:
        """Carrega candles do banco. Usa versão com indicadores se disponível."""
        cfg = self.config
        # Tenta carregar indicadores completos primeiro
        df = AssetsRatesRepository.get_rates_indicators_range(
            self.db, cfg.symbol, cfg.timeframe_int, cfg.start_date, cfg.end_date
        )
        if df.empty:
            # Fallback simples
            df = AssetsRatesRepository.get_rates_range(
                self.db, cfg.symbol, cfg.timeframe_int, cfg.start_date, cfg.end_date
            )
        if df.empty:
            # Log disponível range para debug
            all_data = AssetsRatesRepository.get_rates(
                self.db, cfg.symbol, cfg.timeframe_int, limit=1
            )
            if not all_data.empty:
                self.logger.info(f"Dados disponíveis para {cfg.symbol} {cfg.timeframe_str}: última vela em {all_data.index[-1]}")
            self.df = df
            self.logger.warning(
                f"Nenhum dado encontrado para {cfg.symbol} {cfg.timeframe_str} entre {cfg.start_date} e {cfg.end_date}"
            )
            return
        self.df = df.sort_index()
        self.logger.info(
            f"Carregados {len(self.df)} candles para {cfg.symbol} {cfg.timeframe_str} (colunas: {list(self.df.columns)})"
        )

    def _prepare_indicators(self) -> None:
        assert self.df is not None
        df = self.df.copy()
        # Calcula indicadores essenciais se ausentes
        if "ema_9" not in df.columns or df["ema_9"].isna().all():
            df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        if "sma_20" not in df.columns or df["sma_20"].isna().all():
            df["sma_20"] = df["close"].rolling(window=20).mean()
        if "sma_50" not in df.columns or df["sma_50"].isna().all():
            df["sma_50"] = df["close"].rolling(window=50).mean()
        if "sma_200" not in df.columns or df["sma_200"].isna().all():
            df["sma_200"] = df["close"].rolling(window=200).mean()
        # Retornos simples (feature engineering básico)
        df["return_1"] = df["close"].pct_change()
        df["range"] = (df["high"] - df["low"]).fillna(0)
        df["close_over_sma20"] = df["close"] / df["sma_20"]
        self.df = df

    def _generate_signals_stub(self) -> None:
        """Fallback simples por crossover caso ML não esteja disponível."""
        assert self.df is not None
        df = self.df
        ema = df["ema_9"]
        sma = df["sma_20"]
        crossover_up = (ema > sma) & (ema.shift(1) <= sma.shift(1))
        crossover_down = (ema < sma) & (ema.shift(1) >= sma.shift(1))
        signals = pd.Series("HOLD", index=df.index)
        signals[crossover_up] = "BUY"
        signals[crossover_down] = "SELL"
        self.signals = signals

    # ---------------- ML Integration -----------------
    def _load_ml_artifacts(self) -> None:
        if not self.config.use_ml:
            return
        if self.config.strategy != "LSTMVolatilityStrategy":
            return
        base = Path("newapp/models")
        tf = self.config.timeframe_str
        symbol = self.config.symbol
        prefix = f"{symbol}_LSTMVolatilityStrategy_{tf}_prod"
        model_path = base / f"{prefix}_lstm.keras"
        scaler_path = base / f"{prefix}_scaler.joblib"
        params_path = base / f"{prefix}_params.joblib"
        if not model_path.exists():
            self.logger.warning(f"Modelo LSTM não encontrado: {model_path}")
            return
        if keras is None:
            self.logger.warning("TensorFlow indisponível - usando fallback de crossover")
            return
        try:
            self.model = keras.models.load_model(model_path)
            self.logger.info(f"Modelo carregado: {model_path}")
            if scaler_path.exists():
                self.scaler = joblib.load(scaler_path)
                self.logger.info("Scaler carregado")
            if params_path.exists():
                self.model_params = joblib.load(params_path)
                self.logger.info(f"Params: {self.model_params}")
        except Exception as e:
            self.logger.error(f"Falha ao carregar modelo ML: {e}")
            self.model = None

    def _generate_signals_ml(self) -> bool:
        """Gera sinais via modelo LSTM se possível.

        Retorna True se conseguiu gerar sinais ML, caso contrário False.
        """
        if self.model is None or self.scaler is None or self.model_params is None:
            return False
        assert self.df is not None
        lookback = int(self.model_params.get("lookback", 0))
        n_features = int(self.model_params.get("n_features", 0))
        df = self.df.copy()
        # Seleção de features heurística (ajustar conforme treinamento real)
        candidate_cols = [
            "open","high","low","close","volume","ema_9","sma_20","sma_50","sma_200",
            "return_1","range","close_over_sma20","support_level","resistance_level","tick_volume","spread"
        ]
        # Preserva apenas colunas existentes
        features = [c for c in candidate_cols if c in df.columns]
        # Pad com zeros se insuficiente
        if len(features) < n_features:
            self.logger.warning(
                f"Features disponíveis ({len(features)}) < n_features treinado ({n_features}); preenchendo com zeros"
            )
            for i in range(n_features - len(features)):
                col = f"pad_{i}"
                df[col] = 0.0
                features.append(col)
        X = df[features].astype(float).values
        # Normaliza
        try:
            X_scaled = self.scaler.transform(X)
        except Exception as e:
            self.logger.error(f"Erro ao aplicar scaler: {e}")
            return False
        # Construir janelas [lookback]
        sequences = []
        for i in range(len(X_scaled)):
            if i < lookback:
                sequences.append(None)
                continue
            window = X_scaled[i - lookback:i]
            sequences.append(window)
        preds = []
        for seq in sequences:
            if seq is None:
                preds.append(None)
                continue
            try:
                p = float(self.model.predict(seq[None, ...], verbose=0)[0][0])
            except Exception as e:
                self.logger.error(f"Falha predição LSTM: {e}")
                p = None
            preds.append(p)
        # Mapear para sinais
        hold_band = self.config.ml_hold_band
        signals = []
        for p in preds:
            if p is None:
                signals.append("HOLD")
            else:
                if p >= 0.5 + hold_band:
                    signals.append("BUY")
                elif p <= 0.5 - hold_band:
                    signals.append("SELL")
                else:
                    signals.append("HOLD")
        self.signals = pd.Series(signals, index=df.index)
        self.logger.info(
            f"Sinais ML gerados: BUY={sum(self.signals=='BUY')} SELL={sum(self.signals=='SELL')} HOLD={sum(self.signals=='HOLD')}"
        )
        return True

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
