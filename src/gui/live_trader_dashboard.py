import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import yaml
from pathlib import Path
import MetaTrader5 as mt5
import threading
import time
import importlib
import logging
from datetime import datetime, timezone, timedelta
import pytz
import sys
import pandas as pd
import numpy as np

# Adiciona a raiz do projeto ao path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.live_trader import LiveTrader # Importa a classe LiveTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

class LiveTradingDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Whatsneps Live Trader Simulation")
        self.geometry("1000x800")

        # --- Carrega Configuração ---
        try:
            with open(project_root / "configs/main.yaml", "r") as file:
                self.config = yaml.safe_load(file)
            self.assets_config = [
                asset for asset in self.config["assets"] if asset.get("enabled", False)
            ]
            if not self.assets_config:
                 log.warning("Nenhum ativo habilitado encontrado na configuração.")
        except Exception as e:
            log.critical(f"Erro fatal ao carregar configuração: {e}", exc_info=True)
            messagebox.showerror("Erro de Configuração", f"Não foi possível carregar 'configs/main.yaml'.\nErro: {e}")
            self.destroy() 
            return

        self.checkbox_vars = {} 
        self.timeframe_comboboxes = {}
        self.market_data_labels = {} 
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.refresh_countdown = tk.IntVar(value=60) 
        self.market_data_running = False
        self.monitor_mt5_connected = False
        self.is_trader_initialized = False

        # --- Instancia LiveTrader como motor ---
        try:
            self.trader_engine = LiveTrader(config_path='configs/main.yaml')
            # Inicialização em thread
            self.initialization_thread = threading.Thread(target=self._initialize_trader_engine, daemon=True)
            self.initialization_thread.start()
        except Exception as e:
             log.critical(f"Erro fatal LiveTrader: {e}", exc_info=True)
             messagebox.showerror("Erro Inicialização", f"{e}") 
             self.destroy()
             return

        # --- Layout Principal ---
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(expand=True, fill=tk.BOTH)

        # Controles de Refresh
        refresh_controls_frame = ttk.Frame(self.main_frame)
        refresh_controls_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
        self.timer_label = ttk.Label(refresh_controls_frame, text="Próxima atualização em: 60s") 
        self.timer_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(refresh_controls_frame, text="Atualizar Monitor", command=self._manual_refresh).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(refresh_controls_frame, text="Auto Refresh (1 min)", variable=self.auto_refresh_var, command=self._toggle_auto_refresh).pack(side=tk.LEFT, padx=5)

        # Monitor de Mercado
        self.market_data_frame = ttk.LabelFrame(self.main_frame, text="Monitor de Mercado", padding="10")
        self.market_data_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        # Frame Simulação
        sim_frame = ttk.LabelFrame(self.main_frame, text="Simulação de Ciclo Único (LiveTrader Engine)", padding="10")
        sim_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        datetime_frame = ttk.Frame(sim_frame)
        datetime_frame.pack(side=tk.TOP, fill=tk.X, pady=(5, 10))
        ttk.Label(datetime_frame, text="Simular em Data/Hora Específica (UTC-3):").pack(side=tk.LEFT, padx=(0, 5))
        self.sim_date_entry = ttk.Entry(datetime_frame, width=12)
        self.sim_date_entry.pack(side=tk.LEFT, padx=5)
        self.sim_date_entry.insert(0, "YYYY-MM-DD")
        self.sim_time_entry = ttk.Entry(datetime_frame, width=8)
        self.sim_time_entry.pack(side=tk.LEFT, padx=5)
        self.sim_time_entry.insert(0, "HH:MM")
        ttk.Button(datetime_frame, text="Agora (Local)", command=self._set_datetime_now, width=10).pack(side=tk.LEFT, padx=5) # Botão Agora usa hora local
        ttk.Button(datetime_frame, text="Limpar", command=self._clear_datetime, width=6).pack(side=tk.LEFT)
            
        self.asset_selection_frame = ttk.Frame(sim_frame) 
        self.asset_selection_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        self.simulate_button = ttk.Button(sim_frame, text="Executar Simulação de Ciclo Único", command=self._trigger_simulation, state=tk.DISABLED) 
        self.simulate_button.pack(side=tk.TOP, pady=10)

        # Frame Logs
        log_frame = ttk.LabelFrame(self.main_frame, text="Log da Simulação", padding="10") 
        log_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15, font=("Consolas", 9)) 
        self.log_text.pack(expand=True, fill=tk.BOTH)
        self.log_text.configure(state='disabled')

        # --- Inicialização do Monitor ---
        self.monitor_mt5_connected = self._connect_mt5_monitor()
        self._create_asset_widgets(monitor_failed=not self.monitor_mt5_connected)
        if self.monitor_mt5_connected: self._start_market_data_updates()
        else: self.log_message("ERRO: Monitor não iniciado (falha conexão MT5).")

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # --- Funções Auxiliares ---
    def _initialize_trader_engine(self):
        """Inicializa o LiveTrader (conecta MT5, carrega modelos) em thread."""
        log.info("Thread init LiveTrader iniciada...")
        self.is_trader_initialized = self.trader_engine.initialize() # Chama o initialize do LiveTrader
        if self.is_trader_initialized:
            self.log_message("Motor LiveTrader inicializado.")
            self.after(0, lambda: self.simulate_button.config(state=tk.NORMAL))
        else:
            self.log_message("ERRO: Falha ao inicializar LiveTrader.")
        log.info("Thread init LiveTrader concluída.")


    def log_message(self, message):
        """Adiciona mensagem ao log (thread-safe)."""
        if not hasattr(self, 'log_text') or not self.log_text.winfo_exists(): return
        def _update_log():
             try:
                 self.log_text.configure(state='normal')
                 self.log_text.insert(tk.END, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
                 self.log_text.see(tk.END)
                 self.log_text.configure(state='disabled')
             except tk.TclError: pass
        self.after(0, _update_log)

    def _connect_mt5_monitor(self):
        """Conexão MT5 para o monitor."""
        if mt5.terminal_info(): return True
        log.info("Monitor: Tentando conectar MT5...")
        if not mt5.initialize(): log.error(f"Monitor: Falha MT5: {mt5.last_error()}"); return False
        log.info("Monitor: Conectado MT5."); return True

    def _disconnect_mt5_monitor(self):
        """Gerencia desconexão."""
        log.info("Monitor: Verificação de desligamento (gerenciado pelo LiveTrader).")
        pass

    def _create_asset_widgets(self, monitor_failed=False):
        """Cria widgets do monitor e seleção de simulação."""
        # Limpa frames
        for widget in self.asset_selection_frame.winfo_children(): widget.destroy()
        for widget in self.market_data_frame.winfo_children(): widget.destroy()
        self.market_data_labels.clear(); self.checkbox_vars.clear(); self.timeframe_comboboxes.clear()

        # Cabeçalhos Monitor
        headers = ["Ativo", "Abertura", "Máxima", "Mínima", "Último", "Médio", "Variação %"]
        for col, header in enumerate(headers):
            lbl = ttk.Label(self.market_data_frame, text=header, font=('Arial', 9, 'bold'))
            lbl.grid(row=0, column=col, padx=5, pady=2, sticky="w")

        if monitor_failed:
             ttk.Label(self.market_data_frame, text="Falha conexão MT5 (monitor).", foreground="red").grid(row=1, column=0, columnspan=len(headers))

        # Linhas de Ativos
        if not self.assets_config:
            ttk.Label(self.market_data_frame, text="Nenhum ativo habilitado.").grid(row=1, column=0, columnspan=len(headers))
        else:
            for row_idx, asset_config in enumerate(self.assets_config, start=1):
                data_ticker = asset_config.get('ticker', 'N/A')
                order_ticker = asset_config.get('live_trading', {}).get('ticker_order', data_ticker)

                # Labels do Monitor (apenas se conectado)
                if not monitor_failed:
                    asset_labels = {}
                    lbl_ticker = ttk.Label(self.market_data_frame, text=order_ticker, width=12)
                    lbl_ticker.grid(row=row_idx, column=0, padx=5, pady=2, sticky="w")
                    asset_labels['ticker'] = lbl_ticker
                    for col_idx, key in enumerate(['open', 'high', 'low', 'last', 'avg', 'var'], start=1):
                        lbl_data = ttk.Label(self.market_data_frame, text="-", width=10, anchor="e")
                        lbl_data.grid(row=row_idx, column=col_idx, padx=5, pady=2, sticky="e")
                        asset_labels[key] = lbl_data
                    self.market_data_labels[order_ticker] = asset_labels

                # Controles de Simulação (sempre cria)
                asset_sim_frame = ttk.Frame(self.asset_selection_frame)
                asset_sim_frame.pack(side=tk.LEFT, padx=10, pady=2, fill=tk.X)
                var = tk.BooleanVar(value=True)
                chk = ttk.Checkbutton(asset_sim_frame, text=data_ticker, variable=var)
                chk.pack(side=tk.TOP, anchor='w')
                self.checkbox_vars[data_ticker] = var
                configured_tf = asset_config.get('live_trading', {}).get('timeframe_str', 'D1')
                tf_options = sorted(list(set(["M5", "M15", "H1", "D1", configured_tf])))
                tf_combo = ttk.Combobox(asset_sim_frame, values=tf_options, width=5, state="readonly")
                tf_combo.set(configured_tf)
                tf_combo.pack(side=tk.TOP, anchor='w', pady=(2,0))
                self.timeframe_comboboxes[data_ticker] = tf_combo

    # --- Lógica de Atualização do Monitor ---
    def _start_market_data_updates(self):
        """Inicia loop de atualização do monitor."""
        if not self.market_data_labels: return
        log.info("Iniciando thread monitor.")
        self.market_data_running = True
        self.after(1000, self._update_timer_and_data)

    def _update_timer_and_data(self):
        """Atualiza timer e dispara busca de dados."""
        if not self.market_data_running: return
        try:
            current_countdown = self.refresh_countdown.get()
            timer_needs_reset = False
            if self.auto_refresh_var.get():
                if current_countdown <= 0:
                    self._fetch_and_update_market_data_threadsafe()
                    timer_needs_reset = True
                else: self.refresh_countdown.set(current_countdown - 1)
                current_display = self.refresh_countdown.get() if not timer_needs_reset else 60
                timer_text = f"Próxima atualização em: {current_display}s"
                if timer_needs_reset: self.after(50, lambda: self.refresh_countdown.set(60))
            else: timer_text = "Auto Refresh: OFF"
            if self.winfo_exists(): self.timer_label.config(text=timer_text)
        except Exception as e: log.error(f"Erro loop timer: {e}", exc_info=True)
        finally:
             if self.market_data_running and self.winfo_exists(): self.after(1000, self._update_timer_and_data)

    def _manual_refresh(self):
        """Força atualização do monitor."""
        if not self.monitor_mt5_connected:
             self.log_message("Monitor não conectado."); messagebox.showwarning("Monitor Desconectado", "...")
             return
        self.log_message("Atualização manual monitor...")
        self._fetch_and_update_market_data_threadsafe()
        self.refresh_countdown.set(60)

    def _toggle_auto_refresh(self):
         """Ativa/desativa auto-refresh."""
         log.info(f"Auto Refresh {'Ativado' if self.auto_refresh_var.get() else 'Desativado'}.")
         if self.auto_refresh_var.get(): self.refresh_countdown.set(60)
         else: self.timer_label.config(text="Auto Refresh: OFF")

    def _fetch_and_update_market_data_threadsafe(self):
         """Inicia busca de dados do monitor em thread."""
         if not self.monitor_mt5_connected: return
         log.debug("Disparando thread busca monitor.")
         threading.Thread(target=self._fetch_and_update_market_data, daemon=True).start()

    def _fetch_and_update_market_data(self):
        """Busca dados do monitor e agenda atualização da GUI."""
        if not mt5.initialize(): # Garante conexão
             log.warning("Monitor: Falha reconexão MT5."); self.monitor_mt5_connected = False
             self.after(0, lambda: [lbls[k].config(text="-", fg="black") for lbls in self.market_data_labels.values() for k in lbls if k!='ticker'])
             return
        self.monitor_mt5_connected = True
        log.debug("Monitor: Buscando dados...")
        update_queue = []
        for order_ticker, labels in self.market_data_labels.items():
            data = {"open": "-", "high": "-", "low": "-", "last": "-", "avg": "-", "var": ("-", "black")}
            try:
                rates = mt5.copy_rates_from_pos(order_ticker, mt5.TIMEFRAME_D1, 0, 1)
                tick = mt5.symbol_info_tick(order_ticker)
                if rates is not None and len(rates) > 0 and tick and tick.time > 0:
                    lr = rates[0]; o, h, l = lr['open'], lr['high'], lr['low']
                    lp = tick.last; avg = (h + l) / 2
                    var = ((lp / o) - 1) * 100 if o > 0 else 0
                    v_col = "green" if var >= 0 else "red"; v_txt = f"{var:+.2f}%"
                    data = {"open": f"{o:.5f}", "high": f"{h:.5f}", "low": f"{l:.5f}",
                            "last": f"{lp:.5f}", "avg": f"{avg:.5f}", "var": (v_txt, v_col)}
                else: log.debug(f"Monitor: Dados inválidos {order_ticker}.")
            except Exception as e: log.warning(f"Monitor: Erro busca {order_ticker}: {e}")
            update_queue.append((labels, data))
        self.after(0, self._apply_gui_updates, update_queue)
        log.debug("Monitor: Atualização dados concluída.")
        # Não desconecta aqui

    def _apply_gui_updates(self, update_queue):
         """Aplica atualizações na GUI."""
         if not self.winfo_exists(): return
         for labels, data in update_queue:
              try:
                  if 'open' in labels: labels['open'].config(text=data["open"])
                  if 'high' in labels: labels['high'].config(text=data["high"])
                  if 'low' in labels: labels['low'].config(text=data["low"])
                  if 'last' in labels: labels['last'].config(text=data["last"])
                  if 'avg' in labels: labels['avg'].config(text=data["avg"])
                  if 'var' in labels: labels['var'].config(text=data["var"][0], foreground=data["var"][1])
              except tk.TclError: log.warning("Erro Tcl label.")
              except Exception as e: log.error(f"Erro update GUI: {e}")

    # --- Lógica de Simulação (Usa LiveTrader Engine) ---
    def _trigger_simulation(self):
        """Dispara a simulação usando o LiveTrader Engine."""
        if not self.is_trader_initialized:
             messagebox.showerror("Erro", "Motor LiveTrader não inicializado."); return

        selected_tickers = [ticker for ticker, var in self.checkbox_vars.items() if var.get()]
        if not selected_tickers:
            self.log_message("Nenhum ativo selecionado."); return

        selected_timeframes = { ticker: self.timeframe_comboboxes[ticker].get()
                                for ticker in selected_tickers if ticker in self.timeframe_comboboxes }

        # --- PROCESSAMENTO DE DATA/HORA ---
        simulation_datetime_local = None # Usará dados recentes se permanecer None
        date_str = self.sim_date_entry.get().strip()
        time_str = self.sim_time_entry.get().strip()
        user_input_date = date_str not in ["", "YYYY-MM-DD"]
        user_input_time = time_str not in ["", "HH:MM"]        

        if user_input_date and user_input_time:
            try:
                datetime_str = f"{date_str} {time_str}"
                simulation_datetime_local = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                self.log_message(f"Simulação agendada para LOCAL: {simulation_datetime_local.strftime('%Y-%m-%d %H:%M %Z%z')}")
            except (ValueError, pytz.exceptions.UnknownTimeZoneError) as e:
                messagebox.showerror("Erro de Formato/Timezone", f"Data/Hora inválida ou timezone local não reconhecido.\nUse YYYY-MM-DD e HH:MM.\nErro: {e}")
                return
        elif user_input_date or user_input_time:
             messagebox.showwarning("Entrada Incompleta", "Preencha ambos os campos de data e hora (em UTC-3) ou deixe-os como padrão.")
             return
        else:
             self.log_message("Simulando com os dados mais recentes.")

        # Limpa o log
        self.log_text.configure(state='normal'); self.log_text.delete('1.0', tk.END); self.log_text.configure(state='disabled')
        self.log_message(f"Iniciando simulação via LiveTrader para: {', '.join(selected_tickers)}")

        # Executa em thread
        sim_thread = threading.Thread(target=self._run_simulation_thread,
                                      args=(selected_tickers, selected_timeframes, simulation_datetime_local),
                                      daemon=True)
        sim_thread.start()

    def _run_simulation_thread(self, tickers_to_simulate, selected_timeframes, simulation_datetime_local):
        """Executa a simulação para cada ativo usando métodos do LiveTrader Engine."""
        # Garante conexão MT5 (LiveTrader.initialize já fez, mas verifica)
        if not mt5.terminal_info():
             if not mt5.initialize(): self.log_message("ERRO: Falha conexão MT5."); return

        for data_ticker in tickers_to_simulate:
            # --- ALTERAÇÃO: Chama o novo método simulate_single_cycle do LiveTrader ---
            timeframe_str = selected_timeframes.get(data_ticker, "D1") # Pega TF selecionado
            self.log_message(f"--- Simulando {data_ticker} ({timeframe_str}) via LiveTrader ---")

            # Chama o método de simulação do LiveTrader Engine
            result = self.trader_engine.simulate_single_cycle(data_ticker, timeframe_str, simulation_datetime_local)

            # --- Formata e loga o resultado (similar ao SimulationEngine) ---
            log_msg = f"Resultado {result.get('ticker','N/A')} ({result.get('timeframe','N/A')}) @ {result.get('timestamp','N/A')}:\n"
            if result.get("error"):
                log_msg += f"  ERRO: {result['error']}"
            else:
                indicators_list = [f"{k}={v}" for k, v in result.get("indicators", {}).items() if v != "N/A"]
                indicators_str = " | ".join(indicators_list) if indicators_list else "Nenhum"
                price_str = f"{result['suggested_price']:.5f}" if result.get('suggested_price') is not None else "N/A"
                stop_str = f"{result['stop_price']:.5f}" if result.get('stop_price') is not None else "N/A"
                setup_valid_str = 'Sim' if result.get('setup_valid') else ('Não' if result.get('setup_valid') is False else 'N/A')
                ai_signal_text = result.get('ai_signal_text', 'N/A') # Pega o texto do sinal IA

                log_msg += (
                    f"  SINAL FINAL: {result.get('signal','N/A')} (IA: {ai_signal_text} | Setup: {setup_valid_str})\n"
                    f"  Preço Sugerido: {price_str} (Fonte: {result.get('price_source','N/A')})\n"
                    f"  Stop Sugerido: {stop_str}\n"
                    f"  Indicadores: {indicators_str}\n"
                    f"  Ticker Ordem: {result.get('order_ticker','N/A')}"
                )
            self.log_message(log_msg)

        self.log_message("--- Simulação Concluída ---")
        # A conexão MT5 é gerenciada pelo LiveTrader Engine agora

    def _set_datetime_now(self):
         """Preenche campos com hora local (UTC-3)."""
         # Removido pois este dashboard simula sempre o ciclo atual
         messagebox.showinfo("Info", "Este dashboard simula apenas o ciclo de dados mais recente.")
         pass

    def _clear_datetime(self):
         """Limpa campos de data/hora."""
         # Removido pois não há mais campos de data/hora
         pass

    # --- Função de Fechamento ---
    def _on_closing(self):
        """Handler para fechar a janela."""
        log.info("Fechando dashboard...")
        self.market_data_running = False
        if hasattr(self, 'market_data_thread') and self.market_data_thread.is_alive():
             try: self.market_data_thread.join(timeout=0.5)
             except RuntimeError: pass
        # Chama o shutdown do LiveTrader Engine (que cuida do MT5)
        if hasattr(self, 'trader_engine'):
             self.trader_engine.shutdown() # Chama o shutdown explícito
        log.info("Desligamento concluído.")
        self.destroy()

# --- Bloco Principal ---
if __name__ == "__main__":
    app = LiveTradingDashboard()
    app.mainloop()