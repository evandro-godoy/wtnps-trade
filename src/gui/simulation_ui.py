"""Tkinter GUI for running Day Trade simulations using existing strategies.

Separation of Concerns:
 - Esta interface apenas orquestra carregamento de config, dados, modelo e engine.
 - Lógica de trading permanece em DayTradeEngine e Strategy classes.
"""
from __future__ import annotations

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from typing import Dict, Any, Optional, List

import yaml
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import threading

# Ajustar path para permitir `import src.*` quando executado diretamente
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(ROOT_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from src.utils.logger import logger
from src.simulation.daytrade_engine import DayTradeEngine
from src.strategies.lstm_volatility import LSTMVolatilityStrategy
from src.data_handler.provider import get_provider_instance  # Factory de provedores
import importlib

CONFIG_PATH = os.path.join(PROJECT_DIR, "configs", "main.yaml")

class SimulationApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("WTNPS DayTrade Simulation")
        self.geometry("760x560")
        self.resizable(True, True)

        self.assets_config: Dict[str, Any] = {}
        self.selected_asset: tk.StringVar = tk.StringVar()
        self.selected_strategy: tk.StringVar = tk.StringVar()
        self.initial_capital_var: tk.StringVar = tk.StringVar(value="1000.0")
        self.cost_per_trade_var: tk.StringVar = tk.StringVar(value="1.0")
        self.threshold_var: tk.StringVar = tk.StringVar(value="0.70")
        self.stop_atr_var: tk.StringVar = tk.StringVar(value="2.0")
        self.profit_atr_var: tk.StringVar = tk.StringVar(value="4.0")
        self.start_date_var: tk.StringVar = tk.StringVar(value="2024-01-01")
        self.end_date_var: tk.StringVar = tk.StringVar(value="2024-03-01")

        self.run_button: Optional[ttk.Button] = None
        self.save_button: Optional[ttk.Button] = None
        self.cancel_button: Optional[ttk.Button] = None
        self.asset_combo: Optional[ttk.Combobox] = None
        self.strategy_combo: Optional[ttk.Combobox] = None
        self.progress_bar: Optional[ttk.Progressbar] = None
        self.progress_label: Optional[ttk.Label] = None

        self.trades: List[Dict[str, Any]] = []
        self.summary_text: Optional[tk.Text] = None
        self.equity_curve: List[Dict[str, Any]] = []
        self.cancel_simulation: bool = False
        self.canvas_widget: Optional[FigureCanvasTkAgg] = None

        self._build_ui()
        self._load_config()

    # -------------------------------------------------
    # UI BUILD
    # -------------------------------------------------
    def _build_ui(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # Asset selection
        ttk.Label(frame, text="Ativo:").grid(row=0, column=0, sticky=tk.W)
        self.asset_combo = ttk.Combobox(frame, textvariable=self.selected_asset, state="readonly")
        self.asset_combo.grid(row=0, column=1, sticky=tk.W, pady=3)
        self.asset_combo.bind("<<ComboboxSelected>>", self._on_asset_changed)

        # Strategy selection
        ttk.Label(frame, text="Estratégia:").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.strategy_combo = ttk.Combobox(frame, textvariable=self.selected_strategy, state="readonly", width=20)
        self.strategy_combo.grid(row=0, column=3, sticky=tk.W, pady=3)

        # Parameters grid
        params = [
            ("Capital Inicial", self.initial_capital_var),
            ("Custo por Trade", self.cost_per_trade_var),
            ("Threshold Prob.", self.threshold_var),
            ("Stop ATR Mult.", self.stop_atr_var),
            ("Profit ATR Mult.", self.profit_atr_var),
            ("Data Início", self.start_date_var),
            ("Data Fim", self.end_date_var),
        ]
        for i, (label, var) in enumerate(params, start=1):
            ttk.Label(frame, text=f"{label}:").grid(row=i, column=0, sticky=tk.W)
            ttk.Entry(frame, textvariable=var, width=16).grid(row=i, column=1, sticky=tk.W, pady=3)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=8, column=0, columnspan=4, pady=8, sticky=tk.EW)
        
        self.run_button = ttk.Button(btn_frame, text="Executar Simulação", command=self._on_run)
        self.run_button.pack(side=tk.LEFT, padx=2)

        self.cancel_button = ttk.Button(btn_frame, text="Cancelar", command=self._on_cancel, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=2)

        self.save_button = ttk.Button(btn_frame, text="Salvar Relatório", command=self._on_save, state=tk.DISABLED)
        self.save_button.pack(side=tk.LEFT, padx=2)

        # Progress bar
        self.progress_label = ttk.Label(frame, text="")
        self.progress_label.grid(row=9, column=0, columnspan=4, sticky=tk.W)
        self.progress_bar = ttk.Progressbar(frame, mode="determinate", length=400)
        self.progress_bar.grid(row=10, column=0, columnspan=4, sticky=tk.EW, pady=(0, 5))

        # Summary box
        ttk.Label(frame, text="Resumo da Simulação:").grid(row=11, column=0, columnspan=2, sticky=tk.W, pady=(10, 2))
        self.summary_text = tk.Text(frame, height=8, wrap=tk.WORD)
        self.summary_text.grid(row=12, column=0, columnspan=4, sticky="nsew")

        # Chart area
        ttk.Label(frame, text="Curva de Equity:").grid(row=13, column=0, columnspan=2, sticky=tk.W, pady=(10, 2))
        chart_frame = ttk.Frame(frame)
        chart_frame.grid(row=14, column=0, columnspan=4, sticky="nsew")

        frame.columnconfigure(3, weight=1)
        frame.rowconfigure(12, weight=1)
        frame.rowconfigure(14, weight=2)

    # -------------------------------------------------
    # CONFIG
    # -------------------------------------------------
    def _load_config(self) -> None:
        """Carrega e normaliza o arquivo de configuração principal.

        Estrutura esperada: assets é uma lista de dicionários com chave 'ticker'.
        Converte para dict: ticker -> asset_cfg.
        """
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            raw_assets = cfg.get("assets", [])
            if not isinstance(raw_assets, list):
                raise ValueError("Campo 'assets' deve ser uma lista no YAML.")
            normalized: Dict[str, Dict[str, Any]] = {}
            for asset_cfg in raw_assets:
                ticker = asset_cfg.get("ticker")
                if not ticker:
                    continue
                normalized[ticker] = asset_cfg
            self.assets_config = normalized
            asset_list = list(self.assets_config.keys())
            self.asset_combo["values"] = asset_list
            if asset_list:
                self.selected_asset.set(asset_list[0])
                self._update_strategy_list(asset_list[0])
            logger.info(f"Config carregada. Ativos: {asset_list}")
        except FileNotFoundError:
            messagebox.showerror("Erro", f"Arquivo de configuração não encontrado: {CONFIG_PATH}")
        except Exception as exc:
            messagebox.showerror("Erro", f"Falha ao carregar config: {exc}")
            logger.exception("Erro ao carregar configuração")

    def _on_asset_changed(self, event=None) -> None:
        """Handler when asset selection changes - updates strategy dropdown."""
        asset = self.selected_asset.get()
        if asset:
            self._update_strategy_list(asset)

    def _update_strategy_list(self, asset: str) -> None:
        """Populates strategy dropdown based on selected asset."""
        asset_cfg = self.assets_config.get(asset)
        if not asset_cfg:
            return
        strategies = asset_cfg.get("strategies", [])
        strategy_names = [s.get("name", "Unknown") for s in strategies if s.get("name")]
        self.strategy_combo["values"] = strategy_names
        if strategy_names:
            self.selected_strategy.set(strategy_names[0])
        else:
            self.selected_strategy.set("")

    def _on_cancel(self) -> None:
        """Cancels running simulation."""
        self.cancel_simulation = True
        logger.info("Cancelamento solicitado pelo usuário.")

    # -------------------------------------------------
    # RUN SIMULATION
    # -------------------------------------------------
    def _on_run(self) -> None:
        """Runs simulation in separate thread to avoid freezing UI."""
        self.cancel_simulation = False
        self.run_button.configure(state=tk.DISABLED)
        self.cancel_button.configure(state=tk.NORMAL)
        self.save_button.configure(state=tk.DISABLED)
        self.progress_bar["value"] = 0
        self.progress_label.config(text="Iniciando...")
        
        # Run in thread
        thread = threading.Thread(target=self._run_simulation_thread, daemon=True)
        thread.start()

    def _run_simulation_thread(self) -> None:
        """Actual simulation logic running in background thread."""
        try:
            asset = self.selected_asset.get()
            if not asset:
                self.after(0, lambda: messagebox.showwarning("Aviso", "Selecione um ativo."))
                self._reset_ui_after_run()
                return

            strategy_name = self.selected_strategy.get()
            if not strategy_name:
                self.after(0, lambda: messagebox.showwarning("Aviso", "Selecione uma estratégia."))
                self._reset_ui_after_run()
                return

            initial_capital = float(self.initial_capital_var.get())
            cost_per_trade = float(self.cost_per_trade_var.get())
            threshold = float(self.threshold_var.get())
            stop_mult = float(self.stop_atr_var.get())
            profit_mult = float(self.profit_atr_var.get())
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get()
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if end_dt <= start_dt:
                messagebox.showerror("Erro", "Data fim deve ser posterior à data início.")
                return

            asset_cfg = self.assets_config.get(asset)
            if asset_cfg is None:
                self.after(0, lambda: messagebox.showerror("Erro", f"Ativo {asset} não encontrado na config."))
                self._reset_ui_after_run()
                return

            # Localiza estratégia selecionada
            strategies = asset_cfg.get("strategies", [])
            strategy_cfg = None
            for s in strategies:
                if s.get("name") == strategy_name:
                    strategy_cfg = s
                    break
            if strategy_cfg is None:
                self.after(0, lambda: messagebox.showerror("Erro", f"Estratégia {strategy_name} não encontrada."))
                self._reset_ui_after_run()
                return

            provider_name = strategy_cfg.get("provider", "MetaTrader5")
            strategy_module = strategy_cfg.get("module", "lstm_volatility")
            # Timeframe preferencial: usar data.timeframe_model se existir, senão fallback M15
            data_cfg = strategy_cfg.get("data", {}) if isinstance(strategy_cfg.get("data"), dict) else {}
            timeframe_model = data_cfg.get("timeframe_model", "M15")
            timeframe = timeframe_model  # String timeframe para provider

            # Carregar provider (factory aceita apenas nome)
            provider = get_provider_instance(provider_name)
            logger.info(f"Provider '{provider_name}' carregado para ativo {asset} (timeframe={timeframe}).")

            # Obter dados
            self._update_progress(5, "Baixando dados...")
            # Para MetaTrader5 precisamos de constante; aproveita método interno se existir
            if provider_name.lower() == "metatrader5" and hasattr(provider, "_get_mt5_timeframe"):
                mt5_tf = provider._get_mt5_timeframe(timeframe)
                data_df = provider.get_data(ticker=asset, start_date=start_date, end_date=end_date, timeframe=mt5_tf)
            else:
                # YFinance provider espera string
                data_df = provider.get_data(ticker=asset, start_date=start_date, end_date=end_date, timeframe=timeframe)
            if data_df is None or data_df.empty:
                self.after(0, lambda: messagebox.showerror("Erro", "Nenhum dado retornado para o período."))
                self._reset_ui_after_run()
                return
            if not isinstance(data_df.index, pd.DatetimeIndex):
                self.after(0, lambda: messagebox.showerror("Erro", "Dados não possuem índice datetime."))
                self._reset_ui_after_run()
                return

            # Instanciar estratégia dinamicamente e carregar modelo
            self._update_progress(10, f"Carregando estratégia {strategy_name}...")
            try:
                strategy_class = self._load_strategy_class(strategy_module, strategy_name)
                strategy = strategy_class()
            except Exception as exc:
                self.after(0, lambda e=exc: messagebox.showerror("Erro", f"Falha ao instanciar estratégia: {e}"))
                logger.exception(f"Erro ao carregar estratégia {strategy_name}")
                self._reset_ui_after_run()
                return

            model_prefix = os.path.join(PROJECT_DIR, "models", f"{asset}_{strategy_name}_{timeframe}_prod")
            try:
                model_wrapper = strategy.load(model_prefix)
            except FileNotFoundError:
                self.after(0, lambda: messagebox.showerror("Erro", f"Modelo não encontrado: {model_prefix}"))
                self._reset_ui_after_run()
                return
            except Exception as exc:
                self.after(0, lambda e=exc: messagebox.showerror("Erro", f"Falha ao carregar modelo: {e}"))
                logger.exception("Erro carregando modelo")
                self._reset_ui_after_run()
                return

            # Gerar features
            self._update_progress(20, "Gerando features...")
            features_df = strategy.define_features(data_df)
            feature_cols = strategy.get_feature_names()
            missing_cols = [c for c in feature_cols if c not in features_df.columns]
            if missing_cols:
                self.after(0, lambda m=missing_cols: messagebox.showerror("Erro", f"Features ausentes: {m}"))
                self._reset_ui_after_run()
                return

            # Engine
            self._update_progress(25, "Inicializando engine...")
            engine = DayTradeEngine(
                initial_capital=initial_capital,
                cost_per_trade=cost_per_trade,
                threshold=threshold,
                stop_atr_multiplier=stop_mult,
                profit_atr_multiplier=profit_mult,
            )

            # Loop de simulação
            self._update_progress(30, "Executando simulação...")
            probs_cache = []
            total_candles = len(features_df)
            for idx in range(total_candles):
                if self.cancel_simulation:
                    logger.info("Simulação cancelada pelo usuário.")
                    self.after(0, lambda: messagebox.showinfo("Cancelado", "Simulação cancelada."))
                    self._reset_ui_after_run()
                    return

                # Update progress every 100 candles
                if idx % 100 == 0:
                    progress = 30 + int((idx / total_candles) * 60)
                    self._update_progress(progress, f"Processando candle {idx}/{total_candles}...")
                # Recorta até o índice atual para formar janela
                window_df = features_df.iloc[: idx + 1]
                # Probabilidade (usa apenas classe positiva)
                proba_arr = model_wrapper.predict_proba(window_df[feature_cols])
                if len(proba_arr) == 0:
                    continue
                signal_prob = float(proba_arr[-1, 1])  # último ponto
                probs_cache.append(signal_prob)

                row = window_df.iloc[-1]
                atr = float(row.get("atr", 0.0))
                ema_trend = float(row.get("ema_9", row.get("close")))
                ts = window_df.index[-1].to_pydatetime()

                engine.update(
                    timestamp=ts,
                    open_p=float(row.get("open")),
                    high=float(row.get("high")),
                    low=float(row.get("low")),
                    close=float(row.get("close")),
                    signal_prob=signal_prob,
                    atr=atr,
                    ema_trend=ema_trend,
                )

            self._update_progress(95, "Finalizando...")
            self.trades = engine.trades
            self.equity_curve = engine.equity_curve
            summary = engine.get_summary()
            
            # Update UI in main thread
            self.after(0, lambda: self._display_summary(summary, probs_cache))
            self.after(0, lambda: self._plot_equity_curve())
            self._update_progress(100, "Concluído!")
            self.after(0, lambda: self.save_button.configure(state=tk.NORMAL))
            self.after(0, lambda: messagebox.showinfo("Concluído", "Simulação finalizada."))
            self._reset_ui_after_run()

        except ValueError as ve:
            self.after(0, lambda e=ve: messagebox.showerror("Erro de Valor", str(e)))
            logger.exception("Erro de valor na simulação")
            self._reset_ui_after_run()
        except Exception as exc:
            self.after(0, lambda e=exc: messagebox.showerror("Erro", f"Falha na simulação: {e}"))
            logger.exception("Falha inesperada na simulação")
            self._reset_ui_after_run()

    def _load_strategy_class(self, module_name: str, class_name: str):
        """Dynamically loads strategy class from module name."""
        try:
            module = importlib.import_module(f"src.strategies.{module_name}")
            strategy_class = getattr(module, class_name)
            return strategy_class
        except (ImportError, AttributeError) as e:
            logger.error(f"Não foi possível carregar {class_name} de {module_name}: {e}")
            raise

    def _update_progress(self, value: int, text: str) -> None:
        """Updates progress bar and label in main thread."""
        def update():
            self.progress_bar["value"] = value
            self.progress_label.config(text=text)
        self.after(0, update)

    def _reset_ui_after_run(self) -> None:
        """Resets UI state after simulation completes or is cancelled."""
        def reset():
            self.run_button.configure(state=tk.NORMAL)
            self.cancel_button.configure(state=tk.DISABLED)
        self.after(0, reset)

    # -------------------------------------------------
    # DISPLAY SUMMARY
    # -------------------------------------------------
    def _display_summary(self, summary: Dict[str, Any], probs_cache: List[float]) -> None:
        self.summary_text.delete("1.0", tk.END)
        lines = [
            f"Total Trades: {summary['total_trades']}",
            f"Wins: {summary['wins']}",
            f"Losses: {summary['losses']}",
            f"Win Rate (%): {summary['win_rate_pct']:.2f}",
            f"Gross PnL: {summary['gross_pnl']:.2f}",
            f"Initial Capital: {summary['initial_capital']:.2f}",
            f"Final Capital: {summary['final_capital']:.2f}",
            f"Avg Prob (últimos sinais): { (sum(probs_cache)/len(probs_cache)) if probs_cache else 0.0:.3f}",
        ]
        self.summary_text.insert(tk.END, "\n".join(lines))

    # -------------------------------------------------
    # SAVE REPORT
    # -------------------------------------------------
    def _plot_equity_curve(self) -> None:
        """Plots equity curve using matplotlib."""
        if not self.equity_curve:
            logger.warning("Nenhuma curva de equity para plotar.")
            return

        # Clear previous chart
        if self.canvas_widget:
            self.canvas_widget.get_tk_widget().destroy()

        # Create figure
        fig = Figure(figsize=(8, 3), dpi=80)
        ax = fig.add_subplot(111)

        # Extract data
        times = [e["time"] for e in self.equity_curve]
        equity = [e["equity"] for e in self.equity_curve]

        # Plot
        ax.plot(times, equity, linewidth=1.5, color="#2E86AB")
        ax.set_xlabel("Tempo")
        ax.set_ylabel("Capital")
        ax.set_title("Evolução do Capital")
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate(rotation=45)
        fig.tight_layout()

        # Embed in tkinter
        chart_frame = self.summary_text.master.nametowidget(self.summary_text.master.winfo_children()[-1].winfo_name())
        # Find chart_frame by row 14
        for widget in self.summary_text.master.winfo_children():
            info = widget.grid_info()
            if info.get("row") == 14:
                chart_frame = widget
                break

        self.canvas_widget = FigureCanvasTkAgg(fig, master=chart_frame)
        self.canvas_widget.draw()
        self.canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _on_save(self) -> None:
        if not self.trades:
            messagebox.showwarning("Aviso", "Nenhum trade para salvar.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("Texto", "*.txt")]
        )
        if not file_path:
            return
        try:
            df = pd.DataFrame(self.trades)
            df.to_csv(file_path, index=False)
            messagebox.showinfo("Sucesso", f"Relatório salvo em {file_path}")
            logger.info(f"Relatório de trades salvo em {file_path}")
        except Exception as exc:
            messagebox.showerror("Erro", f"Falha ao salvar relatório: {exc}")
            logger.exception("Erro salvando relatório")


if __name__ == "__main__":
    app = SimulationApp()
    app.mainloop()
