import pandas as pd
import numpy as np

class DayTradeEngine:
    def __init__(self, initial_capital=10000, cost_per_trade=1.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.cost_per_trade = cost_per_trade
        
        # Estado da Posição
        self.position = 0  # 0: Flat, 1: Long, -1: Short
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.highest_price = 0.0  # Para Trailing Stop
        self.lowest_price = 0.0   # Para Trailing Stop
        
        # Histórico
        self.trades = []
        self.equity_curve = []
        
    def update(self, timestamp, open_p, high, low, close, signal_prob, atr, ema_trend):
        """
        Processa um candle e toma decisões de trading.
        
        Parâmetros:
            signal_prob: Probabilidade do modelo (0.0 a 1.0)
            atr: Valor do ATR atual (para cálculo de stops)
            ema_trend: Valor da Média Móvel (para filtro de tendência)
        """
        
        # 1. Verificar Encerramento de Dia (EOD - End of Day)
        # Se passar das 17:30, zera tudo à mercado.
        if timestamp.hour >= 17 and timestamp.minute >= 30:
            if self.position != 0:
                self._close_position(timestamp, close, "EOD_FORCED")
            self.equity_curve.append({'time': timestamp, 'equity': self.capital})
            return

        # 2. Gestão de Posição Aberta (Stops e Trailing)
        if self.position != 0:
            self._manage_position(timestamp, high, low, close, atr)
        
        # 3. Lógica de Entrada (Apenas se Flat e horário permitido)
        # Horário de entrada: 09:05 até 16:30
        if self.position == 0 and (9 <= timestamp.hour < 16 or (timestamp.hour == 16 and timestamp.minute <= 30)):
            self._check_entry(timestamp, close, signal_prob, atr, ema_trend)

        # Registrar Equity
        self.equity_curve.append({'time': timestamp, 'equity': self.capital})

    def _check_entry(self, timestamp, price, signal_prob, atr, ema_trend):
        """
        Lógica de Entrada:
        1. Modelo diz que tem Volatilidade (Prob > 0.70)
        2. Filtro de Tendência (Preço vs EMA) define a direção.
        """
        THRESHOLD = 0.70  # Nossa "régua" otimizada
        
        if signal_prob > THRESHOLD:
            # Setup de Tendência + Volatilidade
            if price > ema_trend:
                # Compra (Long)
                self.position = 1
                self.entry_price = price
                # Stop Técnico: 2.0x ATR
                self.stop_loss = price - (2.0 * atr)
                # Alvo Inicial (opcional, pois usamos Trailing): 4.0x ATR
                self.take_profit = price + (4.0 * atr)
                self.highest_price = price
                
            elif price < ema_trend:
                # Venda (Short)
                self.position = -1
                self.entry_price = price
                self.stop_loss = price + (2.0 * atr)
                self.take_profit = price - (4.0 * atr)
                self.lowest_price = price

    def _manage_position(self, timestamp, high, low, close, atr):
        """Gestão de Risco e Trailing Stop"""
        
        # A. Verificar Stop Loss e Take Profit
        if self.position == 1: # Long
            if low <= self.stop_loss:
                self._close_position(timestamp, self.stop_loss, "STOP_LOSS")
                return
            if high >= self.take_profit:
                self._close_position(timestamp, self.take_profit, "TAKE_PROFIT")
                return
            
            # B. Trailing Stop (Dinâmico)
            # Se o preço subir, puxa o stop para proteger lucro
            if high > self.highest_price:
                self.highest_price = high
                # Novo stop é a máxima menos 1.5x ATR (aperta o stop na tendência)
                new_stop = high - (1.5 * atr)
                if new_stop > self.stop_loss:
                    self.stop_loss = new_stop

        elif self.position == -1: # Short
            if high >= self.stop_loss:
                self._close_position(timestamp, self.stop_loss, "STOP_LOSS")
                return
            if low <= self.take_profit:
                self._close_position(timestamp, self.take_profit, "TAKE_PROFIT")
                return
            
            # Trailing Stop Short
            if low < self.lowest_price:
                self.lowest_price = low
                new_stop = low + (1.5 * atr)
                if new_stop < self.stop_loss:
                    self.stop_loss = new_stop

    def _close_position(self, timestamp, price, reason):
        """Calcula PnL e registra trade"""
        pnl = 0
        if self.position == 1:
            pnl = price - self.entry_price
        elif self.position == -1:
            pnl = self.entry_price - price
            
        # Deduzir custos (Slippage + Taxas simuladas)
        pnl -= self.cost_per_trade
        
        self.capital += pnl
        self.trades.append({
            'entry_time': timestamp, # Simplificação (na real seria o tempo da entrada)
            'exit_time': timestamp,
            'type': 'LONG' if self.position == 1 else 'SHORT',
            'entry': self.entry_price,
            'exit': price,
            'pnl': pnl,
            'reason': reason
        })
        self.position = 0