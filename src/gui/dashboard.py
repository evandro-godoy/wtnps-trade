import tkinter as tk
from tkinter import ttk, scrolledtext
import yaml
from pathlib import Path
import MetaTrader5 as mt5
import threading
import time
import importlib
import logging
from datetime import datetime
import sys
import pandas as pd

# Adiciona a raiz do projeto ao path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# --- NOVA IMPORTAÇÃO DO MOTOR DE SIMULAÇÃO ---
from src.simulation.engine import SimulationEngine

# Configuração básica do logging para a GUI
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TradingDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WtnpsTrade Dashboard v2.1 - Simulation Engine")
        self.geometry("950x750") # Ajustado para novo layout

        # --- Carrega Configuração ---
        try:
            with open(project_root / "configs/main.yaml", "r") as file:
                self.config = yaml.safe_load(file)
            self.assets_config = [
                asset for asset in self.config["assets"] if asset.get("enabled", False)
            ]
        except Exception as e:
            logging.error(f"Erro ao carregar configuração: {e}")
            self.destroy()
            return

        self.checkbox_vars = {}
        self.timeframe_comboboxes = {}
        self.market_data_labels = {}
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.refresh_countdown = tk.IntVar(value=60)
        self.market_data_running = False

        # --- Instancia o Novo Motor de Simulação ---
        try:
            self.simulation_engine = SimulationEngine()
        except Exception as e:
            logging.error(f"Erro ao inicializar SimulationEngine: {e}")
            self.destroy()
            return

        # --- Layout Principal ---
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(expand=True, fill=tk.BOTH)

        # --- Frame Controles de Refresh ---
        refresh_controls_frame = ttk.Frame(self.main_frame)
        refresh_controls_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
        self.timer_label = ttk.Label(refresh_controls_frame, text="Próxima atualização em: 60s")
        self.timer_label.pack(side=tk.LEFT, padx=5)
        manual_refresh_button = ttk.Button(refresh_controls_frame, text="Atualizar Agora", command=self._manual_refresh)
        manual_refresh_button.pack(side=tk.LEFT, padx=5)
        auto_refresh_check = ttk.Checkbutton(refresh_controls_frame, text="Auto Refresh (1 min)", variable=self.auto_refresh_var)
        auto_refresh_check.pack(side=tk.LEFT, padx=5)

        # --- Frame Monitor de Mercado ---
        self.market_data_frame = ttk.LabelFrame(self.main_frame, text="Monitor de Mercado", padding="10")
        self.market_data_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        # --- Frame Simulação ---
        sim_frame = ttk.LabelFrame(self.main_frame, text="Simulação de Ciclo Único", padding="10")
        sim_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        self.asset_selection_frame = ttk.Frame(sim_frame)
        self.asset_selection_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        simulate_button = ttk.Button(sim_frame, text="Executar Simulação de Ciclo Único", command=self._trigger_simulation)
        simulate_button.pack(side=tk.TOP, pady=10)

        # --- Frame Logs ---
        log_frame = ttk.LabelFrame(self.main_frame, text="Log da Simulação", padding="10")
        log_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, font=("Consolas", 9))
        self.log_text.pack(expand=True, fill=tk.BOTH)
        self.log_text.configure(state='disabled')

        # --- Inicialização ---
        # A conexão MT5 agora é gerenciada principalmente pelo SimulationEngine
        # Mas ainda precisamos de uma para o monitor de mercado
        if not self._connect_mt5_monitor():
             self.log_message("ERRO: Não foi possível conectar ao MT5 para monitoramento.")
        else:
            self._create_asset_widgets()
            self._start_market_data_updates()

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # --- Funções de Log e Conexão ---
    def log_message(self, message):
        if not hasattr(self, 'log_text') or not self.log_text.winfo_exists(): return
        try:
            self.log_text.configure(state='normal')
            self.log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state='disabled')
        except tk.TclError: pass

    def _connect_mt5_monitor(self):
        # Conexão separada para o monitor, pode falhar sem impedir a simulação
        if not mt5.initialize():
            logging.warning(f"Monitor: Falha na inicialização do MT5: {mt5.last_error()}")
            return False
        logging.info("Monitor: Conectado ao MetaTrader 5.")
        return True
        
    def _disconnect_mt5_monitor(self):
        logging.info("Monitor: Desconectando do MetaTrader 5...")
        mt5.shutdown() # O SimulationEngine gerencia sua própria conexão

    # --- Criação de Widgets (sem alterações significativas) ---
    def _create_asset_widgets(self):
        for widget in self.asset_selection_frame.winfo_children(): widget.destroy()
        for widget in self.market_data_frame.winfo_children(): widget.destroy()
        self.market_data_labels.clear(); self.checkbox_vars.clear(); self.timeframe_comboboxes.clear()
        headers = ["Ativo", "Abertura", "Máxima", "Mínima", "Último", "Médio", "Variação %"]
        for col, header in enumerate(headers):
            lbl = ttk.Label(self.market_data_frame, text=header, font=('Arial', 9, 'bold'))
            lbl.grid(row=0, column=col, padx=5, pady=2, sticky="w")

        for row_idx, asset_config in enumerate(self.assets_config, start=1):
            data_ticker = asset_config['ticker']
            order_ticker = asset_config['live_trading'].get('ticker_order', data_ticker)
            asset_labels = {}
            lbl_ticker = ttk.Label(self.market_data_frame, text=order_ticker, width=12)
            lbl_ticker.grid(row=row_idx, column=0, padx=5, pady=2, sticky="w")
            asset_labels['ticker'] = lbl_ticker
            for col_idx, key in enumerate(['open', 'high', 'low', 'last', 'avg', 'var'], start=1):
                lbl_data = ttk.Label(self.market_data_frame, text="-", width=10, anchor="e")
                lbl_data.grid(row=row_idx, column=col_idx, padx=5, pady=2, sticky="e")
                asset_labels[key] = lbl_data
            self.market_data_labels[order_ticker] = asset_labels

            asset_sim_frame = ttk.Frame(self.asset_selection_frame)
            asset_sim_frame.pack(side=tk.LEFT, padx=10, pady=2)
            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(asset_sim_frame, text=data_ticker, variable=var)
            chk.pack(side=tk.LEFT, padx=(0, 5))
            self.checkbox_vars[data_ticker] = var
            configured_tf = asset_config['live_trading']['timeframe_str']
            tf_options = sorted(list(set(["M5", "M15", "H1", "D1", configured_tf])))
            tf_combo = ttk.Combobox(asset_sim_frame, values=tf_options, width=5, state="readonly")
            tf_combo.set(configured_tf)
            tf_combo.pack(side=tk.LEFT)
            self.timeframe_comboboxes[data_ticker] = tf_combo

    # --- Lógica de Atualização de Dados de Mercado (sem alterações significativas) ---
    def _start_market_data_updates(self):
        self.market_data_running = True
        self.market_data_thread = threading.Thread(target=self._update_market_data_loop, daemon=True)
        self.market_data_thread.start()

    def _update_market_data_loop(self):
        while self.market_data_running:
            try:
                current_countdown = self.refresh_countdown.get()
                if self.auto_refresh_var.get():
                    if current_countdown <= 0:
                        self._fetch_and_update_market_data_threadsafe() # Chama via thread-safe wrapper
                        self.refresh_countdown.set(60)
                    else:
                        self.refresh_countdown.set(current_countdown - 1)
                    timer_text = f"Próxima atualização em: {self.refresh_countdown.get()}s"
                else:
                    timer_text = "Auto Refresh: OFF"
                self.after(0, self.timer_label.config, {"text": timer_text})
            except Exception as e: logging.error(f"Erro no loop de atualização: {e}")
            time.sleep(1)

    def _manual_refresh(self):
        self.log_message("Atualização manual solicitada...")
        self._fetch_and_update_market_data_threadsafe()
        self.refresh_countdown.set(60)

    def _fetch_and_update_market_data_threadsafe(self):
         # Executa a busca em thread para não travar
         refresh_thread = threading.Thread(target=self._fetch_and_update_market_data, daemon=True)
         refresh_thread.start()

    def _fetch_and_update_market_data(self):
        if not self._connect_mt5_monitor(): return
        for order_ticker, labels in self.market_data_labels.items():
            try:
                rates = mt5.copy_rates_from_pos(order_ticker, mt5.TIMEFRAME_D1, 0, 1)
                tick = mt5.symbol_info_tick(order_ticker)
                if rates is not None and len(rates) > 0 and tick:
                    lr = rates[0]; o, h, l = lr['open'], lr['high'], lr['low']
                    lp = tick.last; avg = (h + l) / 2
                    var = ((lp / o) - 1) * 100 if o > 0 else 0
                    v_col = "green" if var >= 0 else "red"; v_txt = f"{var:+.2f}%"
                    # Atualiza GUI (agendado via self.after)
                    self.after(0, labels['open'].config, {"text": f"{o:.2f}"})
                    self.after(0, labels['high'].config, {"text": f"{h:.2f}"})
                    self.after(0, labels['low'].config, {"text": f"{l:.2f}"})
                    self.after(0, labels['last'].config, {"text": f"{lp:.2f}"})
                    self.after(0, labels['avg'].config, {"text": f"{avg:.2f}"})
                    self.after(0, labels['var'].config, {"text": v_txt, "foreground": v_col})
            except Exception as e:
                logging.warning(f"Monitor: Erro ao buscar dados para {order_ticker}: {e}")
                self.after(0, lambda lbls=labels: [lbl.config(text="-") for k, lbl in lbls.items() if k != 'ticker'])
        self._disconnect_mt5_monitor()

    # --- Lógica de Simulação (Refatorada) ---
    def _trigger_simulation(self):
        """Dispara a simulação usando o SimulationEngine."""
        selected_tickers = [ticker for ticker, var in self.checkbox_vars.items() if var.get()]
        if not selected_tickers:
            self.log_message("Nenhum ativo selecionado para simulação.")
            return

        selected_timeframes = { ticker: self.timeframe_comboboxes[ticker].get()
                                for ticker in selected_tickers if ticker in self.timeframe_comboboxes }

        self.log_message(f"Iniciando simulação via Engine para: {', '.join(selected_tickers)}")
        sim_thread = threading.Thread(target=self._run_simulation_thread,
                                      args=(selected_tickers, selected_timeframes),
                                      daemon=True)
        sim_thread.start()

    def _run_simulation_thread(self, tickers_to_simulate, selected_timeframes):
        """Executa a simulação para cada ativo selecionado usando o SimulationEngine."""
        for data_ticker in tickers_to_simulate:
            timeframe_str = selected_timeframes.get(data_ticker, "D1") # Pega TF selecionado
            self.after(0, self.log_message, f"--- Simulando {data_ticker} ({timeframe_str}) via Engine ---")

            # Chama o motor de simulação
            result = self.simulation_engine.run_simulation_cycle(data_ticker, timeframe_str)

            # Formata e loga o resultado detalhado
            if result.get("error"):
                log_msg = f"ERRO {data_ticker}: {result['error']}"
            else:
                indicators_str = " | ".join([f"{k}={v}" for k, v in result["indicators"].items()])
                log_msg = (
                    f"SINAL {result['ticker']} ({result['timeframe']}): {result['signal']}\n"
                    f"  Preço Sugerido: {result['suggested_price']:.2f} (Fonte: {result['price_source']})\n"
                    f"  Stop Sugerido: {result['stop_price']:.2f}\n"
                    f"  Ref. Candle: {result['timestamp']}\n"
                    f"  Setup Válido: {'Sim' if result['setup_valid'] else 'Não'}\n"
                    f"  Indicadores: {indicators_str}\n"
                    f"  Ticker Ordem: {result['order_ticker']}"
                )
            # Usa self.after para garantir que a atualização da GUI ocorra na thread principal
            self.after(0, self.log_message, log_msg)

        self.after(0, self.log_message, "--- Simulação Concluída ---")

    # --- Função de Fechamento ---
    def _on_closing(self):
        """Handler para fechar a janela."""
        logging.info("Fechando dashboard...")
        self.market_data_running = False
        if hasattr(self, 'market_data_thread') and self.market_data_thread.is_alive():
             self.market_data_thread.join(timeout=1.0)
        self._disconnect_mt5_monitor() # Desconecta o monitor
        if hasattr(self, 'simulation_engine'):
             self.simulation_engine.shutdown() # Desconecta o motor de simulação
        self.destroy()

if __name__ == "__main__":
    app = TradingDashboard()
    app.mainloop()