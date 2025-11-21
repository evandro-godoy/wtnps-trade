"""Day Trade Simulation Engine.

Responsável por orquestrar a execução de ordens baseada em:
 - Probabilidade de sinal (modelo ML)
 - Filtro de tendência (EMA)
 - Stops dinâmicos baseados em ATR (stop e trailing)
 - Encerramento forçado no fim do pregão (EOD)

Principais métodos:
 - update: processa cada candle cronologicamente
 - get_summary: retorna estatísticas agregadas
 - reset: recomeça a simulação mantendo configurações

OBS: Esta classe NÃO carrega dados nem modelos. É orquestrada externamente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, time

from src.utils.logger import logger  # Logger central do projeto


@dataclass
class TradeRecord:
    entry_time: datetime
    exit_time: datetime
    type: str  # LONG / SHORT
    entry_price: float
    exit_price: float
    pnl: float
    reason: str


class DayTradeEngine:
    def __init__(
        self,
        initial_capital: float = 10000.0,
        cost_per_trade: float = 1.0,
        threshold: float = 0.70,
        ema_period: int = 9,
        stop_atr_multiplier: float = 2.0,
        profit_atr_multiplier: float = 4.0,
        eod_close_time: time = time(17, 30),
        last_entry_time: time = time(16, 30),
        trading_start_hour: int = 9,
        trading_end_hour: int = 17,
    ) -> None:
        self.initial_capital: float = initial_capital
        self.capital: float = initial_capital
        self.cost_per_trade: float = cost_per_trade

        # Parâmetros de estratégia
        self.threshold: float = threshold
        self.ema_period: int = ema_period
        self.stop_atr_multiplier: float = stop_atr_multiplier
        self.profit_atr_multiplier: float = profit_atr_multiplier
        self.eod_close_time: time = eod_close_time
        self.last_entry_time: time = last_entry_time
        self.trading_start_hour: int = trading_start_hour
        self.trading_end_hour: int = trading_end_hour  # Limite superior (ex: 17 -> até 16:59:59)

        # Estado da posição
        self.position: int = 0  # 0: Flat, 1: Long, -1: Short
        self.entry_price: float = 0.0
        self.stop_loss: float = 0.0
        self.take_profit: float = 0.0
        self.highest_price: float = 0.0  # Para trailing long
        self.lowest_price: float = 0.0   # Para trailing short
        self.entry_timestamp: Optional[datetime] = None

        # Histórico
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []

        logger.info(
            f"DayTradeEngine inicializada: capital={initial_capital}, threshold={threshold}, stopATR={stop_atr_multiplier}, profitATR={profit_atr_multiplier}"
        )

    # -------------------------------------------------
    # API PRINCIPAL
    # -------------------------------------------------
    def update(
        self,
        timestamp: datetime,
        open_p: float,
        high: float,
        low: float,
        close: float,
        signal_prob: float,
        atr: float,
        ema_trend: float,
    ) -> None:
        """Processa um novo candle.

        Parâmetros:
            timestamp: datetime do candle (timezone já normalizado externamente)
            open_p/high/low/close: preços do candle
            signal_prob: probabilidade (0..1) fornecida pelo modelo ML
            atr: valor corrente do ATR
            ema_trend: valor da EMA usada como filtro de tendência
        """
        # 1. Encerramento forçado (EOD)
        if self._is_after_eod(timestamp):
            if self.position != 0:
                logger.debug("Encerrando posição por EOD_FORCED")
                self._close_position(timestamp, close, "EOD_FORCED")
            self._append_equity(timestamp)
            return

        # 2. Gestão de posição existente
        if self.position != 0:
            self._manage_open_position(timestamp, high, low, close, atr)

        # 3. Lógica de entrada (apenas se flat e antes do limite de novas entradas)
        if self.position == 0 and self._can_open_new_position(timestamp):
            self._check_entry(timestamp, close, signal_prob, atr, ema_trend)

        # 4. Registrar equity (após potenciais mudanças)
        self._append_equity(timestamp)

    # -------------------------------------------------
    # LÓGICA DE ENTRADA
    # -------------------------------------------------
    def _check_entry(
        self,
        timestamp: datetime,
        price: float,
        signal_prob: float,
        atr: float,
        ema_trend: float,
    ) -> None:
        # Verifica janela de horário operacional antes de qualquer lógica de sinal
        if not self._is_within_trading_hours(timestamp):
            return

        if signal_prob <= self.threshold:
            return

        if price > ema_trend:
            # LONG
            self.position = 1
            self.entry_price = price
            self.entry_timestamp = timestamp
            self.stop_loss = price - (self.stop_atr_multiplier * atr)
            self.take_profit = price + (self.profit_atr_multiplier * atr)
            self.highest_price = price
            logger.debug(
                f"LONG aberto @ {price:.2f} SL={self.stop_loss:.2f} TP={self.take_profit:.2f} prob={signal_prob:.3f}"
            )
        elif price < ema_trend:
            # SHORT
            self.position = -1
            self.entry_price = price
            self.entry_timestamp = timestamp
            self.stop_loss = price + (self.stop_atr_multiplier * atr)
            self.take_profit = price - (self.profit_atr_multiplier * atr)
            self.lowest_price = price
            logger.debug(
                f"SHORT aberto @ {price:.2f} SL={self.stop_loss:.2f} TP={self.take_profit:.2f} prob={signal_prob:.3f}"
            )

    # -------------------------------------------------
    # GESTÃO DE POSIÇÃO
    # -------------------------------------------------
    def _manage_open_position(
        self,
        timestamp: datetime,
        high: float,
        low: float,
        close: float,
        atr: float,
    ) -> None:
        # Verificar stop/take profit
        if self.position == 1:  # LONG
            # Stop Loss
            if low <= self.stop_loss:
                self._close_position(timestamp, self.stop_loss, "STOP_LOSS")
                return
            # Take Profit
            if high >= self.take_profit:
                self._close_position(timestamp, self.take_profit, "TAKE_PROFIT")
                return
            # Trailing (ajusta stop se novo high)
            if high > self.highest_price:
                self.highest_price = high
                new_stop = self.highest_price - (self.stop_atr_multiplier * atr)
                if new_stop > self.stop_loss:
                    logger.debug(f"Ajuste Trailing LONG: {self.stop_loss:.2f} -> {new_stop:.2f}")
                    self.stop_loss = new_stop

        elif self.position == -1:  # SHORT
            if high >= self.stop_loss:
                self._close_position(timestamp, self.stop_loss, "STOP_LOSS")
                return
            if low <= self.take_profit:
                self._close_position(timestamp, self.take_profit, "TAKE_PROFIT")
                return
            if low < self.lowest_price:
                self.lowest_price = low
                new_stop = self.lowest_price + (self.stop_atr_multiplier * atr)
                if new_stop < self.stop_loss:
                    logger.debug(f"Ajuste Trailing SHORT: {self.stop_loss:.2f} -> {new_stop:.2f}")
                    self.stop_loss = new_stop

    # -------------------------------------------------
    # ENCERRAMENTO / REGISTRO
    # -------------------------------------------------
    def _close_position(self, timestamp: datetime, exit_price: float, reason: str) -> None:
        pnl: float = 0.0
        if self.position == 1:
            pnl = exit_price - self.entry_price
        elif self.position == -1:
            pnl = self.entry_price - exit_price

        pnl -= self.cost_per_trade
        self.capital += pnl

        self.trades.append(
            {
                "entry_time": self.entry_timestamp if self.entry_timestamp else timestamp,
                "exit_time": timestamp,
                "type": "LONG" if self.position == 1 else "SHORT",
                "entry_price": self.entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "reason": reason,
            }
        )
        logger.debug(
            f"Trade fechado ({reason}) {('LONG' if self.position==1 else 'SHORT')} PnL={pnl:.2f} Capital={self.capital:.2f}"
        )

        # Reset posição
        self.position = 0
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.highest_price = 0.0
        self.lowest_price = 0.0
        self.entry_timestamp = None

    def _append_equity(self, timestamp: datetime) -> None:
        self.equity_curve.append({"time": timestamp, "equity": self.capital})

    # -------------------------------------------------
    # UTILITÁRIOS / REGRAS DE TEMPO
    # -------------------------------------------------
    def _is_after_eod(self, timestamp: datetime) -> bool:
        return (timestamp.hour, timestamp.minute) >= (self.eod_close_time.hour, self.eod_close_time.minute)

    def _can_open_new_position(self, timestamp: datetime) -> bool:
        # Verifica limite para novas entradas (last_entry_time) e janela operacional básica
        within_last_entry = (timestamp.hour, timestamp.minute) <= (self.last_entry_time.hour, self.last_entry_time.minute)
        return within_last_entry and self._is_within_trading_hours(timestamp)

    def _is_within_trading_hours(self, timestamp: datetime) -> bool:
        # trading_end_hour é exclusivo para abertura (ex: 17 -> não abre às 17:00)
        return self.trading_start_hour <= timestamp.hour < self.trading_end_hour

    # -------------------------------------------------
    # RELATÓRIOS
    # -------------------------------------------------
    def get_summary(self) -> Dict[str, Any]:
        total = len(self.trades)
        wins = sum(1 for t in self.trades if t["pnl"] > 0)
        losses = sum(1 for t in self.trades if t["pnl"] <= 0)
        win_rate = (wins / total) * 100 if total > 0 else 0.0
        gross_pnl = sum(t["pnl"] for t in self.trades)
        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": win_rate,
            "gross_pnl": gross_pnl,
            "final_capital": self.capital,
            "initial_capital": self.initial_capital,
        }

    def reset(self) -> None:
        logger.info("Resetando DayTradeEngine mantendo configurações.")
        self.capital = self.initial_capital
        self.position = 0
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.highest_price = 0.0
        self.lowest_price = 0.0
        self.entry_timestamp = None
        self.trades.clear()
        self.equity_curve.clear()
