# src/gui/chart_widget.py

"""
Widget de Gráfico de Candlestick para Monitor em Tempo Real.

Utiliza matplotlib e mplfinance para renderizar gráficos de candlestick
com indicadores técnicos (EMA, SMA, suporte/resistência).
"""

import logging
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Optional, List, Dict
import pandas as pd
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import mplfinance as mpf

logger = logging.getLogger(__name__)


class CandlestickChartWidget(ttk.Frame):
    """
    Widget tkinter com gráfico de candlestick embedado.
    
    Features:
    - Renderização de candles OHLC usando mplfinance
    - Overlay de indicadores técnicos (EMA, SMA)
    - Linhas de suporte/resistência
    - Atualização eficiente (sem redesenhar tudo)
    - Limite de candles visíveis (performance)
    
    Attributes:
        max_candles (int): Máximo de candles visíveis no gráfico
        candles_data (list): Lista de dicts com dados OHLC
        indicators_data (dict): Dados de indicadores técnicos
    """
    
    def __init__(
        self,
        parent,
        max_candles: int = 200,
        **kwargs
    ):
        """
        Inicializa o widget de gráfico.
        
        Args:
            parent: Widget pai do tkinter
            max_candles: Número máximo de candles a exibir (default: 200)
            **kwargs: Argumentos adicionais para ttk.Frame
        """
        super().__init__(parent, **kwargs)
        
        self.max_candles = max_candles
        self.candles_data = []
        self.indicators = {
            'ema9': [],
            'sma20': [],
            'sma50': [],
            'support': None,
            'resistance': None
        }
        
        # Configuração do estilo mplfinance
        self.mpf_style = mpf.make_mpf_style(
            base_mpf_style='charles',
            marketcolors=mpf.make_marketcolors(
                up='#26a69a',
                down='#ef5350',
                edge='inherit',
                wick={'up': '#26a69a', 'down': '#ef5350'},
                volume='in'
            ),
            gridcolor='#e0e0e0',
            gridstyle='--',
            y_on_right=True
        )
        
        self._setup_chart()
        
        logger.info(f"CandlestickChartWidget inicializado (max_candles={max_candles})")
    
    def _setup_chart(self):
        """Inicializa o matplotlib Figure e Canvas."""
        # Cria figura matplotlib
        self.figure = Figure(figsize=(12, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        
        # Canvas tkinter
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)
        
        # Configuração inicial
        self.ax.text(
            0.5, 0.5,
            'Aguardando dados...',
            horizontalalignment='center',
            verticalalignment='center',
            transform=self.ax.transAxes,
            fontsize=14,
            color='gray'
        )
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        
        self.canvas.draw()
    
    def add_candle(self, candle_data: dict):
        """
        Adiciona novo candle ao gráfico.
        
        Args:
            candle_data: Dict com keys: time, open, high, low, close, volume
        """
        try:
            # Valida dados
            required_keys = ['time', 'open', 'high', 'low', 'close', 'volume']
            if not all(k in candle_data for k in required_keys):
                logger.warning(f"Candle data incompleto: {candle_data.keys()}")
                return
            
            # Adiciona à lista
            self.candles_data.append(candle_data)
            
            # Limita ao máximo de candles
            if len(self.candles_data) > self.max_candles:
                self.candles_data = self.candles_data[-self.max_candles:]
                
                # Ajusta indicadores também
                for key in ['ema9', 'sma20', 'sma50']:
                    if len(self.indicators[key]) > self.max_candles:
                        self.indicators[key] = self.indicators[key][-self.max_candles:]
            
            # Atualiza gráfico
            self._update_chart()
            
        except Exception as e:
            logger.error(f"Erro ao adicionar candle: {e}", exc_info=True)
    
    def update_indicators(
        self,
        ema9: Optional[float] = None,
        sma20: Optional[float] = None,
        sma50: Optional[float] = None,
        support: Optional[float] = None,
        resistance: Optional[float] = None
    ):
        """
        Atualiza valores de indicadores técnicos.
        
        Args:
            ema9: Valor da EMA(9)
            sma20: Valor da SMA(20)
            sma50: Valor da SMA(50)
            support: Nível de suporte
            resistance: Nível de resistência
        """
        # Adiciona valores às listas
        if ema9 is not None:
            self.indicators['ema9'].append(ema9)
        if sma20 is not None:
            self.indicators['sma20'].append(sma20)
        if sma50 is not None:
            self.indicators['sma50'].append(sma50)
        
        # Níveis de suporte/resistência (valores únicos)
        if support is not None:
            self.indicators['support'] = support
        if resistance is not None:
            self.indicators['resistance'] = resistance
    
    def _update_chart(self):
        """Redesenha o gráfico com os dados atuais."""
        try:
            if len(self.candles_data) == 0:
                return
            
            # Converte para DataFrame
            df = pd.DataFrame(self.candles_data)
            
            # Garante que time é datetime
            if not pd.api.types.is_datetime64_any_dtype(df['time']):
                df['time'] = pd.to_datetime(df['time'])
            
            # Define time como index
            df.set_index('time', inplace=True)
            
            # Renomeia colunas para formato mplfinance (Open, High, Low, Close, Volume)
            df.rename(columns={
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }, inplace=True)
            
            # Prepara addplot para indicadores
            addplots = []
            
            # EMA9
            if len(self.indicators['ema9']) == len(df):
                ema9_series = pd.Series(self.indicators['ema9'], index=df.index)
                addplots.append(
                    mpf.make_addplot(ema9_series, color='blue', width=1.5, label='EMA(9)')
                )
            
            # SMA20
            if len(self.indicators['sma20']) == len(df):
                sma20_series = pd.Series(self.indicators['sma20'], index=df.index)
                addplots.append(
                    mpf.make_addplot(sma20_series, color='orange', width=1.5, label='SMA(20)')
                )
            
            # SMA50
            if len(self.indicators['sma50']) == len(df):
                sma50_series = pd.Series(self.indicators['sma50'], index=df.index)
                addplots.append(
                    mpf.make_addplot(sma50_series, color='red', width=1.5, label='SMA(50)')
                )
            
            # Limpa figura
            self.figure.clear()
            
            # Cria novo axes
            self.ax = self.figure.add_subplot(111)
            
            # Plota com mplfinance
            kwargs = {
                'type': 'candle',
                'style': self.mpf_style,
                'ax': self.ax,
                'volume': False,
                'ylabel': 'Preço',
                'datetime_format': '%H:%M',
                'xrotation': 15
            }
            
            if addplots:
                kwargs['addplot'] = addplots
            
            mpf.plot(df, **kwargs)
            
            # Adiciona linhas de suporte/resistência
            if self.indicators['support'] is not None:
                self.ax.axhline(
                    y=self.indicators['support'],
                    color='green',
                    linestyle='--',
                    linewidth=1,
                    alpha=0.7,
                    label=f"Suporte: {self.indicators['support']:.2f}"
                )
            
            if self.indicators['resistance'] is not None:
                self.ax.axhline(
                    y=self.indicators['resistance'],
                    color='red',
                    linestyle='--',
                    linewidth=1,
                    alpha=0.7,
                    label=f"Resistência: {self.indicators['resistance']:.2f}"
                )
            
            # Adiciona legenda se houver indicadores
            if addplots or self.indicators['support'] or self.indicators['resistance']:
                self.ax.legend(loc='upper left', fontsize=8)
            
            # Atualiza canvas (assíncrono para melhor performance)
            self.canvas.draw_idle()
            
        except Exception as e:
            logger.error(f"Erro ao atualizar gráfico: {e}", exc_info=True)
    
    def clear(self):
        """Limpa todos os dados do gráfico."""
        self.candles_data = []
        self.indicators = {
            'ema9': [],
            'sma20': [],
            'sma50': [],
            'support': None,
            'resistance': None
        }
        
        # Limpa figura
        self.figure.clear()
        self.ax = self.figure.add_subplot(111)
        self.ax.text(
            0.5, 0.5,
            'Aguardando dados...',
            horizontalalignment='center',
            verticalalignment='center',
            transform=self.ax.transAxes,
            fontsize=14,
            color='gray'
        )
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        
        self.canvas.draw()
        
        logger.info("Gráfico limpo")
