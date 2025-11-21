"""Interface gráfica profissional para simulação Day Trade.

Organizada em dois painéis: Configuração (esquerda) e Resultados (direita).
Inclui threading, barra de progresso, métricas, curva de equity e exportação.
"""
from __future__ import annotations

import sys
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from typing import Dict, Any, Optional, List

# Ajuste de path antes dos imports do pacote interno
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src directory
PROJECT_DIR = os.path.dirname(ROOT_DIR)  # project root
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import yaml
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from src.utils.logger import logger
from src.simulation.daytrade_engine import DayTradeEngine
from src.strategies.lstm_volatility import LSTMVolatilityStrategy
from src.data_handler.provider import get_provider_instance

CONFIG_PATH = os.path.join(PROJECT_DIR, "configs", "main.yaml")


class SimulationApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("WTNPS DayTrade Simulation")
        self.geometry("1180x720")
        self.minsize(1100, 680)

        # Dados de config
        self.assets_config: Dict[str, Dict[str, Any]] = {}
        self.asset_var = tk.StringVar()
        self.timeframe_var = tk.StringVar(value="M5")
        self.single_day_var = tk.BooleanVar(value=False)
        self.start_date_var = tk.StringVar(value="2025-11-01")
        self.end_date_var = tk.StringVar(value="2025-11-02")
        self.start_hour_var = tk.IntVar(value=9)
        self.end_hour_var = tk.IntVar(value=17)
        self.lookback_days_var = tk.IntVar(value=30)  # mínimo 30 dias para features

        # Estratégia / Parâmetros
        self.threshold_var = tk.DoubleVar(value=0.70)
        self.vol_mult_var = tk.DoubleVar(value=2.5)
        self.initial_capital_var = tk.DoubleVar(value=10000.0)

        # Estado de simulação
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.cancel_flag: bool = False

        # Widgets principais
        self.progress_bar: Optional[ttk.Progressbar] = None
        self.progress_label: Optional[ttk.Label] = None
        self.btn_run: Optional[ttk.Button] = None
        self.btn_cancel: Optional[ttk.Button] = None
        self.btn_export: Optional[ttk.Button] = None
        self.trade_tree: Optional[ttk.Treeview] = None
        self.metric_labels: Dict[str, ttk.Label] = {}
        self.canvas_equity: Optional[FigureCanvasTkAgg] = None

        self._build_layout()
        self._load_config()
        self._wire_events()

    # ---------------- Layout -----------------
    def _build_layout(self) -> None:
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(container)
        right = ttk.Frame(container)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Left Panel (Config) ---
        lf_data = ttk.LabelFrame(left, text="Dados")
        lf_data.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(lf_data, text="Ativo:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.asset_combo = ttk.Combobox(lf_data, textvariable=self.asset_var, state="readonly", width=14)
        self.asset_combo.grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(lf_data, text="Timeframe:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.timeframe_combo = ttk.Combobox(lf_data, textvariable=self.timeframe_var, state="readonly", width=14,
                                            values=["M1", "M5", "M15", "M30", "H1", "H4"])
        self.timeframe_combo.grid(row=1, column=1, sticky=tk.W, pady=2)
        for i in range(2):
            lf_data.columnconfigure(i, weight=1)

        lf_period = ttk.LabelFrame(left, text="Período")
        lf_period.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(lf_period, text="Início (YYYY-MM-DD)").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(lf_period, textvariable=self.start_date_var, width=14).grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(lf_period, text="Fim (YYYY-MM-DD)").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.end_entry = ttk.Entry(lf_period, textvariable=self.end_date_var, width=14)
        self.end_entry.grid(row=1, column=1, sticky=tk.W, pady=2)
        self.single_day_cb = ttk.Checkbutton(lf_period, text="Dia Único", variable=self.single_day_var, command=self._on_single_day_toggle)
        self.single_day_cb.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(lf_period, text="Hora Início").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.start_hour_spin = ttk.Spinbox(lf_period, from_=0, to=23, textvariable=self.start_hour_var, width=5)
        self.start_hour_spin.grid(row=3, column=1, sticky=tk.W, pady=2)
        ttk.Label(lf_period, text="Hora Fim").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.end_hour_spin = ttk.Spinbox(lf_period, from_=0, to=23, textvariable=self.end_hour_var, width=5)
        self.end_hour_spin.grid(row=4, column=1, sticky=tk.W, pady=2)
        ttk.Label(lf_period, text="Dias Lookback").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.lookback_spin = ttk.Spinbox(lf_period, from_=30, to=240, increment=5, textvariable=self.lookback_days_var, width=6)
        self.lookback_spin.grid(row=5, column=1, sticky=tk.W, pady=2)
        for i in range(2):
            lf_period.columnconfigure(i, weight=1)

        lf_strategy = ttk.LabelFrame(left, text="Estratégia")
        lf_strategy.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(lf_strategy, text="Threshold (0-1)").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.threshold_scale = ttk.Scale(lf_strategy, from_=0.0, to=1.0, orient="horizontal", variable=self.threshold_var,
                                         command=lambda v: self.threshold_entry_var.set(f"{float(v):.2f}"))
        self.threshold_scale.grid(row=0, column=1, sticky=tk.EW, padx=4, pady=2)
        self.threshold_entry_var = tk.StringVar(value=f"{self.threshold_var.get():.2f}")
        ttk.Entry(lf_strategy, textvariable=self.threshold_entry_var, width=6).grid(row=0, column=2, sticky=tk.W, pady=2)
        ttk.Label(lf_strategy, text="Vol Mult.").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(lf_strategy, textvariable=self.vol_mult_var, width=8).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(lf_strategy, text="Capital Inicial").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(lf_strategy, textvariable=self.initial_capital_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=2)
        for i in range(3):
            lf_strategy.columnconfigure(i, weight=1)

        lf_actions = ttk.LabelFrame(left, text="Ações")
        lf_actions.pack(fill=tk.X, padx=5, pady=5)
        self.btn_run = ttk.Button(lf_actions, text="Executar Simulação", command=self._on_run)
        self.btn_run.pack(side=tk.LEFT, padx=4, pady=4)
        self.btn_cancel = ttk.Button(lf_actions, text="Cancelar", command=self._on_cancel, state=tk.DISABLED)
        self.btn_cancel.pack(side=tk.LEFT, padx=4, pady=4)
        self.btn_export = ttk.Button(lf_actions, text="Salvar Relatório", command=self._on_export, state=tk.DISABLED)
        self.btn_export.pack(side=tk.LEFT, padx=4, pady=4)

        lf_progress = ttk.LabelFrame(left, text="Progresso")
        lf_progress.pack(fill=tk.X, padx=5, pady=5)
        self.progress_bar = ttk.Progressbar(lf_progress, mode="determinate")
        self.progress_bar.pack(fill=tk.X, padx=4, pady=4)
        self.progress_label = ttk.Label(lf_progress, text="Idle")
        self.progress_label.pack(fill=tk.X, padx=4)

        # --- Right Panel (Results) ---
        right_top = ttk.Frame(right)
        right_top.pack(fill=tk.X)

        metric_names = [
            ("total_pnl", "Resultado Total (R$)"),
            ("win_rate", "Win Rate %"),
            ("total_trades", "Total Trades"),
            ("profit_factor", "Fator de Lucro"),
        ]
        for i, (key, title) in enumerate(metric_names):
            card = ttk.LabelFrame(right_top, text=title)
            card.grid(row=0, column=i, padx=5, pady=5, sticky=tk.NSEW)
            lbl = ttk.Label(card, text="--", font=("Segoe UI", 14, "bold"))
            lbl.pack(padx=10, pady=10)
            self.metric_labels[key] = lbl
            right_top.columnconfigure(i, weight=1)

        right_mid = ttk.Frame(right)
        right_mid.pack(fill=tk.BOTH, expand=True)

        # Treeview para trades
        tv_frame = ttk.LabelFrame(right_mid, text="Log de Trades")
        tv_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        columns = ("data", "tipo", "entrada", "saida", "pnl", "motivo")
        self.trade_tree = ttk.Treeview(tv_frame, columns=columns, show="headings", height=12)
        for col, width in zip(columns, [120, 70, 80, 80, 80, 140]):
            self.trade_tree.heading(col, text=col.capitalize())
            self.trade_tree.column(col, width=width, anchor=tk.CENTER)
        vsb = ttk.Scrollbar(tv_frame, orient="vertical", command=self.trade_tree.yview)
        self.trade_tree.configure(yscroll=vsb.set)
        self.trade_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Equity Curve
        eq_frame = ttk.LabelFrame(right, text="Curva de Equity")
        eq_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.eq_frame = eq_frame

    # ---------------- Config Load -----------------
    def _load_config(self) -> None:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            raw_assets = cfg.get("assets", [])
            normalized: Dict[str, Dict[str, Any]] = {}
            for item in raw_assets:
                ticker = item.get("ticker")
                if not ticker:
                    continue
                normalized[ticker] = item
            self.assets_config = normalized
            asset_list = list(normalized.keys())
            self.asset_combo["values"] = asset_list
            if asset_list:
                self.asset_var.set(asset_list[0])
            logger.info(f"Ativos carregados: {asset_list}")
        except Exception as exc:
            messagebox.showerror("Erro", f"Falha ao carregar configuração: {exc}")
            logger.exception("Erro config")

    # ---------------- Events -----------------
    def _wire_events(self) -> None:
        self.asset_combo.bind("<<ComboboxSelected>>", lambda e: None)  # placeholder if future logic needed

    def _on_single_day_toggle(self) -> None:
        if self.single_day_var.get():
            self.end_date_var.set(self.start_date_var.get())
            self.end_entry.configure(state=tk.DISABLED)
        else:
            self.end_entry.configure(state=tk.NORMAL)

    # ---------------- Simulation Thread -----------------
    def _on_run(self) -> None:
        self.cancel_flag = False
        self.btn_run.configure(state=tk.DISABLED)
        self.btn_cancel.configure(state=tk.NORMAL)
        self.btn_export.configure(state=tk.DISABLED)
        self.progress_label.configure(text="Iniciando...")
        self.progress_bar["value"] = 0
        thread = threading.Thread(target=self._run_simulation, daemon=True)
        thread.start()

    def _on_cancel(self) -> None:
        self.cancel_flag = True
        self.progress_label.configure(text="Cancelando...")

    def _run_simulation(self) -> None:
        try:
            asset = self.asset_var.get()
            timeframe = self.timeframe_var.get()
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get()
            lookback_days = int(self.lookback_days_var.get())
            threshold = float(self.threshold_var.get())
            vol_mult = float(self.vol_mult_var.get())
            initial_capital = float(self.initial_capital_var.get())
            start_hour = int(self.start_hour_var.get())
            end_hour = int(self.end_hour_var.get())

            if not asset:
                self._fail("Selecione um ativo.")
                return
            if not timeframe:
                self._fail("Selecione um timeframe.")
                return

            # Validação e normalização de datas
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                self._fail("Formato de data inválido. Use YYYY-MM-DD.")
                return
            if start_dt > end_dt:
                logger.warning("Data início > fim; invertendo automaticamente.")
                start_dt, end_dt = end_dt, start_dt
                start_date, end_date = start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")
            # Aplicar lookback mínimo (garante >=30)
            if lookback_days < 30:
                lookback_days = 30
            extended_start_dt = start_dt - pd.Timedelta(days=lookback_days)
            extended_start_date = extended_start_dt.strftime("%Y-%m-%d")

            # Provider e dados (carrega período estendido para cálculo de features)
            provider = get_provider_instance("MetaTrader5")  # default; poderia ser dinâmico
            self._update_progress(5, f"Buscando dados (lookback {lookback_days}d)...")
            if hasattr(provider, "_get_mt5_timeframe"):
                mt5_tf = provider._get_mt5_timeframe(timeframe)
                data_df = provider.get_data(ticker=asset, start_date=extended_start_date, end_date=end_date, timeframe=mt5_tf)
            else:
                data_df = provider.get_data(ticker=asset, start_date=extended_start_date, end_date=end_date, timeframe=timeframe)
            if data_df is None or data_df.empty:
                self._fail("Dados vazios para o período.")
                return

            # Carregar modelo (mapeamento timeframe→modelo; exemplo M5 usa M15)
            model_tf_map = {"M5": "M15", "M15": "M15", "M1": "M5", "M30": "M15", "H1": "H1", "H4": "H1"}
            model_tf = model_tf_map.get(timeframe, timeframe)
            model_prefix = os.path.join(PROJECT_DIR, "models", f"{asset}_LSTMVolatilityStrategy_{model_tf}_prod")
            strategy = LSTMVolatilityStrategy()
            try:
                model_wrapper = strategy.load(model_prefix)
            except Exception as exc:
                self._fail(f"Falha ao carregar modelo: {exc}")
                return

            self._update_progress(15, "Gerando features...")
            features_df = strategy.define_features(data_df)
            feature_cols = strategy.get_feature_names()
            missing = [c for c in feature_cols if c not in features_df.columns]
            if missing:
                self._fail(f"Features ausentes: {missing}")
                return

            # Filtra janela de simulação (mantém lookback apenas para cálculo anterior)
            idx_tz = getattr(features_df.index, "tz", None)
            if idx_tz is not None:
                sim_start_ts = pd.Timestamp(start_dt, tz=idx_tz)
                sim_end_ts = pd.Timestamp(end_dt, tz=idx_tz) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            else:
                sim_start_ts = pd.Timestamp(start_dt)
                sim_end_ts = pd.Timestamp(end_dt) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            try:
                simulation_df = features_df[(features_df.index >= sim_start_ts) & (features_df.index <= sim_end_ts)]
            except Exception as f_exc:
                logger.warning(f"Falha em comparação timezone; removendo tz para filtro: {f_exc}")
                # fallback: remove tz e usa timestamps ingênuos
                try:
                    features_df_no_tz = features_df.copy()
                    features_df_no_tz.index = features_df_no_tz.index.tz_convert(None)
                    simulation_df = features_df_no_tz[(features_df_no_tz.index >= pd.Timestamp(start_dt)) & (features_df_no_tz.index <= pd.Timestamp(end_dt) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]
                except Exception as f2_exc:
                    self._fail(f"Erro ao aplicar filtro de datas: {f2_exc}")
                    return
            if simulation_df.empty:
                self._fail("Sem dados suficientes após aplicar lookback e filtro de datas.")
                return

            self._update_progress(25, "Inicializando engine...")
            engine = DayTradeEngine(
                initial_capital=initial_capital,
                threshold=threshold,
                stop_atr_multiplier=2.0,
                profit_atr_multiplier=4.0,
                trading_start_hour=start_hour,
                trading_end_hour=end_hour,
            )

            self.trades.clear()
            self.equity_curve.clear()
            probs_cache: List[float] = []

            total = len(simulation_df)
            for idx in range(total):
                if self.cancel_flag:
                    self._update_progress(100, "Cancelado")
                    self._finish(cancelled=True)
                    return
                if idx % max(1, total // 50) == 0:
                    pct = int((idx / total) * 60) + 30
                    self._update_progress(pct, f"Processando {idx}/{total}")

                # Usa todo histórico até o ponto (inclui período anterior para manter contexto)
                window_df = features_df.iloc[: features_df.index.get_indexer([simulation_df.index[idx]])[0] + 1]
                proba_arr = model_wrapper.predict_proba(window_df[feature_cols])
                if len(proba_arr) == 0:
                    continue
                signal_prob = float(proba_arr[-1, 1])
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

            self.trades = engine.trades
            self.equity_curve = engine.equity_curve
            self._update_progress(95, "Finalizando...")
            summary = engine.get_summary()
            self._finish(summary=summary, probs=probs_cache)
        except Exception as exc:
            self._fail(f"Erro inesperado: {exc}")

    # ---------------- Helpers -----------------
    def _update_progress(self, value: int, text: str) -> None:
        def cb():
            self.progress_bar["value"] = value
            self.progress_label.configure(text=text)
        self.after(0, cb)

    def _fail(self, msg: str) -> None:
        logger.error(msg)
        def cb():
            messagebox.showerror("Erro", msg)
            self.btn_run.configure(state=tk.NORMAL)
            self.btn_cancel.configure(state=tk.DISABLED)
            self.progress_label.configure(text="Falha")
        self.after(0, cb)

    def _finish(self, summary: Dict[str, Any] | None = None, probs: List[float] | None = None, cancelled: bool = False) -> None:
        def cb():
            if cancelled:
                messagebox.showinfo("Cancelado", "Simulação cancelada.")
            else:
                self._update_metrics(summary or {})
                self._populate_trades()
                self._plot_equity()
                self.btn_export.configure(state=tk.NORMAL)
                self.progress_label.configure(text="Concluído")
                self.progress_bar["value"] = 100
                messagebox.showinfo("Concluído", "Simulação finalizada.")
            self.btn_run.configure(state=tk.NORMAL)
            self.btn_cancel.configure(state=tk.DISABLED)
        self.after(0, cb)

    def _update_metrics(self, summary: Dict[str, Any]) -> None:
        total_trades = summary.get("total_trades", 0)
        gross_pnl = summary.get("gross_pnl", 0.0)
        win_rate = summary.get("win_rate_pct", 0.0)
        wins = sum(1 for t in self.trades if t["pnl"] > 0)
        losses = sum(1 for t in self.trades if t["pnl"] <= 0)
        sum_pos = sum(t["pnl"] for t in self.trades if t["pnl"] > 0)
        sum_neg = sum(t["pnl"] for t in self.trades if t["pnl"] < 0)
        profit_factor = sum_pos / abs(sum_neg) if sum_neg < 0 else 0.0
        self.metric_labels["total_pnl"].configure(text=f"{gross_pnl:.2f}")
        self.metric_labels["win_rate"].configure(text=f"{win_rate:.2f}%")
        self.metric_labels["total_trades"].configure(text=str(total_trades))
        self.metric_labels["profit_factor"].configure(text=f"{profit_factor:.2f}")

    def _populate_trades(self) -> None:
        for row in self.trade_tree.get_children():
            self.trade_tree.delete(row)
        for t in self.trades:
            self.trade_tree.insert("", tk.END, values=(
                t["exit_time"].strftime("%Y-%m-%d %H:%M"),
                t["type"],
                f"{t['entry_price']:.2f}",
                f"{t['exit_price']:.2f}",
                f"{t['pnl']:.2f}",
                t["reason"],
            ))

    def _plot_equity(self) -> None:
        if self.canvas_equity:
            self.canvas_equity.get_tk_widget().destroy()
        if not self.equity_curve:
            return
        fig = Figure(figsize=(6, 3), dpi=100)
        ax = fig.add_subplot(111)
        times = [e["time"] for e in self.equity_curve]
        equity = [e["equity"] for e in self.equity_curve]
        ax.plot(times, equity, color="#1f5c99", linewidth=1.6)
        ax.set_xlabel("Tempo")
        ax.set_ylabel("Capital")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        self.canvas_equity = FigureCanvasTkAgg(fig, master=self.eq_frame)
        self.canvas_equity.draw()
        self.canvas_equity.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _on_export(self) -> None:
        if not self.trades:
            messagebox.showwarning("Aviso", "Sem trades para exportar.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not file_path:
            return
        try:
            pd.DataFrame(self.trades).to_csv(file_path, index=False)
            messagebox.showinfo("Sucesso", f"Relatório salvo em {file_path}")
        except Exception as exc:
            messagebox.showerror("Erro", f"Falha ao salvar: {exc}")
            logger.exception("Erro export")


def main() -> None:
    app = SimulationApp()
    app.mainloop()


if __name__ == "__main__":
    main()
