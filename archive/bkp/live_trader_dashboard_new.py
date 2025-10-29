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

# --- ALTERAÇÃO: Importa LiveTrader em vez de SimulationEngine ---
from src.live_trader import LiveTrader
# Remove a importação do SimulationEngine se existir
# from src.simulation.engine import SimulationEngine # REMOVIDO

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

class LiveTradingDashboard(tk.Tk): # Renomeado para clareza
    def __init__(self):
        super().__init__()
        self.title("WtnpsTrade Live Trader Simulation Dashboard") # Título atualizado
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
            self.destroy(); return

        self.checkbox_vars = {}; self.timeframe_comboboxes = {}
        self.market_data_labels = {}; self.auto_refresh_var = tk.BooleanVar(value=True)
        self.refresh_countdown = tk.IntVar(value=60); self.market_data_running = False
        self.monitor_mt5_connected = False

        # --- ALTERAÇÃO: Instancia LiveTrader como motor ---
        try:
            # Instancia o LiveTrader (que carrega config, mas não inicializa MT5 ou modelos ainda)
            self.trader_engine = LiveTrader(config_path='configs/main.yaml')
            # Chama o initialize do LiveTrader para conectar ao MT5 e carregar modelos
            # Faz isso em uma thread para não travar a GUI na inicialização
            self.initialization_thread = threading.Thread(target=self._initialize_trader_engine, daemon=True)
            self.initialization_thread.start()
        except Exception as e:
             log.critical(f"Erro fatal ao inicializar LiveTrader: {e}", exc_info=True)
             messagebox.showerror("Erro de Inicialização", f"Não foi possível inicializar o LiveTrader.\nErro: {e}")
             self.destroy(); return

        # --- Layout Principal (sem alterações estruturais) ---
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(expand=True, fill=tk.BOTH)

        # Frame Controles de Refresh
        refresh_controls_frame = ttk.Frame(self.main_frame)
        refresh_controls_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
        self.timer_label = ttk.Label(refresh_controls_frame, text="Próxima atualização em: 60s")
        self.timer_label.pack(side=tk.LEFT, padx=5)
        manual_refresh_button = ttk.Button(refresh_controls_frame, text="Atualizar Monitor", command=self._manual_refresh)
        manual_refresh_button.pack(side=tk.LEFT, padx=5)
        auto_refresh_check = ttk.Checkbutton(refresh_controls_frame, text="Auto Refresh (1 min)", variable=self.auto_refresh_var, command=self._toggle_auto_refresh)
        auto_refresh_check.pack(side=tk.LEFT, padx=5)

        # Frame Monitor de Mercado
        self.market_data_frame = ttk.LabelFrame(self.main_frame, text="Monitor de Mercado", padding="10")
        self.market_data_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        # Frame Simulação
        sim_frame = ttk.LabelFrame(self.main_frame, text="Simulação de Ciclo Único (LiveTrader Engine)", padding="10")
        sim_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        datetime_frame = ttk.Frame(sim_frame)
        datetime_frame.pack(side=tk.TOP, fill=tk.X, pady=(5, 10))
        # --- Campo de entrada agora especifica UTC-3 ---
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
        simulate_button = ttk.Button(sim_frame, text="Executar Simulação de Ciclo Único", command=self._trigger_simulation)
        simulate_button.pack(side=tk.TOP, pady=10)

        # Frame Logs
        log_frame = ttk.LabelFrame(self.main_frame, text="Log da Simulação", padding="10")
        log_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15, font=("Consolas", 9))
        self.log_text.pack(expand=True, fill=tk.BOTH)
        self.log_text.configure(state='disabled')

        # --- Inicialização do Monitor ---
        self.monitor_mt5_connected = self._connect_mt5_monitor()
        self._create_asset_widgets(monitor_failed=not self.monitor_mt5_connected)
        if self.monitor_mt5_connected:
            self._start_market_data_updates()
        else:
             self.log_message("ERRO: Monitor de mercado não iniciado (falha conexão MT5). Simulação PODE falhar se depender do MT5.")

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # --- Funções Auxiliares ---
    def _initialize_trader_engine(self):
        """Inicializa o LiveTrader (conecta MT5, carrega modelos) em uma thread."""
        self.is_trader_initialized = self.trader_engine.initialize()
        if self.is_trader_initialized:
            self.log_message("Motor LiveTrader inicializado com sucesso.")
        else:
            self.log_message("ERRO: Falha ao inicializar o motor LiveTrader.")
            # Desabilitar botão de simulação se a inicialização falhar?
            # self.after(0, lambda: self.simulate_button.config(state=tk.DISABLED))


    def log_message(self, message):
        """Adiciona mensagem ao log da GUI (thread-safe)."""
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
        # Se o trader_engine já inicializou, a conexão pode estar ativa
        if mt5.terminal_info():
             log.info("Monitor: Usando conexão MT5 existente.")
             return True
        elif not mt5.initialize():
            log.error(f"Monitor: Falha na inicialização do MT5: {mt5.last_error()}")
            return False
        log.info("Monitor: Conectado ao MetaTrader 5.")
        return True

    def _disconnect_mt5_monitor(self):
        """Gerencia desconexão (agora menos crítico)."""
        log.info("Monitor: Verificação de desligamento (gerenciado pelo LiveTrader Engine ou on_closing).")
        pass # Deixa o shutdown principal cuidar disso

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
        log.info("Iniciando thread de atualização do monitor de mercado.")
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
        except Exception as e: log.error(f"Erro no loop do timer: {e}", exc_info=True)
        finally:
             if self.market_data_running and self.winfo_exists(): self.after(1000, self._update_timer_and_data)

    def _manual_refresh(self):
        """Força atualização do monitor."""
        if not self.monitor_mt5_connected:
             self.log_message("Monitor não conectado ao MT5."); messagebox.showwarning("Monitor Desconectado", "...")
             return
        self.log_message("Atualização manual do monitor solicitada...")
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
         log.debug("Disparando thread para buscar dados do monitor.")
         threading.Thread(target=self._fetch_and_update_market_data, daemon=True).start()

    def _fetch_and_update_market_data(self):
        """Busca dados do monitor e agenda atualização da GUI."""
        # Garante conexão para esta thread
        if not mt5.initialize(): # Tenta reconectar se necessário
             log.warning("Monitor: Não foi possível (re)conectar ao MT5 para buscar dados.")
             self.monitor_mt5_connected = False
             # Poderia tentar limpar labels aqui via self.after
             return
        self.monitor_mt5_connected = True
        log.debug("Monitor: Buscando dados de mercado...")
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
                else: log.debug(f"Monitor: Dados inválidos/ausentes para {order_ticker}.")
            except Exception as e: log.warning(f"Monitor: Erro ao buscar dados para {order_ticker}: {e}")
            update_queue.append((labels, data))
        self.after(0, self._apply_gui_updates, update_queue)
        log.debug("Monitor: Atualização de dados concluída.")
        # Não desconecta, deixa a conexão principal ativa

    def _apply_gui_updates(self, update_queue):
         """Aplica atualizações na GUI."""
         if not self.winfo_exists(): return
         for labels, data in update_queue:
              try:
                  if 'open' in labels: labels['open'].config(text=data["open"]) # Checa se label existe
                  if 'high' in labels: labels['high'].config(text=data["high"])
                  if 'low' in labels: labels['low'].config(text=data["low"])
                  if 'last' in labels: labels['last'].config(text=data["last"])
                  if 'avg' in labels: labels['avg'].config(text=data["avg"])
                  if 'var' in labels: labels['var'].config(text=data["var"][0], foreground=data["var"][1])
              except tk.TclError: log.warning("Erro Tcl ao atualizar label.")
              except Exception as e: log.error(f"Erro inesperado ao aplicar update GUI: {e}")

    # --- Lógica de Simulação (Adaptada para LiveTrader) ---
    def _trigger_simulation(self):
        """Dispara a simulação usando o LiveTrader Engine."""
        if not hasattr(self, 'is_trader_initialized') or not self.is_trader_initialized:
             messagebox.showerror("Erro", "Motor LiveTrader não inicializado. Verifique a conexão MT5 e os logs.")
             return

        selected_tickers = [ticker for ticker, var in self.checkbox_vars.items() if var.get()]
        if not selected_tickers:
            self.log_message("Nenhum ativo selecionado para simulação."); return

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

        # Limpa o log antes de iniciar
        self.log_text.configure(state='normal'); self.log_text.delete('1.0', tk.END); self.log_text.configure(state='disabled')
        self.log_message(f"Iniciando simulação via LiveTrader Engine para: {', '.join(selected_tickers)}")

        # Executa em thread
        sim_thread = threading.Thread(target=self._run_simulation_thread,
                                      args=(selected_tickers, selected_timeframes, simulation_datetime_local),
                                      daemon=True)
        sim_thread.start()

    def _run_simulation_thread(self, tickers_to_simulate, selected_timeframes, simulation_datetime_local):
        """Executa a simulação para cada ativo usando métodos do LiveTrader Engine."""
        # Garante que o LiveTrader tenha uma conexão MT5 ativa (initialize já fez isso)
        if not mt5.terminal_info():
            self.log_message("ERRO: Conexão MT5 perdida antes da simulação.")
            return

        for data_ticker in tickers_to_simulate:
            if data_ticker not in self.trader_engine.asset_states:
                self.log_message(f"ERRO: Recursos para {data_ticker} não foram carregados pelo LiveTrader.")
                continue

            state = self.trader_engine.asset_states[data_ticker]
            asset_config = state['config']
            live_config = asset_config['live_trading']
            order_ticker = live_config.get('ticker_order', data_ticker)
            # Usa o timeframe SELECIONADO pelo usuário no dashboard
            timeframe_str = selected_timeframes.get(data_ticker, live_config['timeframe_str'])
            mt5_timeframe = self.trader_engine._get_mt5_timeframe_from_string(timeframe_str) # Usa método do LiveTrader

            self.log_message(f"--- Simulando {data_ticker} ({timeframe_str}) ---")

            try:
                # 1. Buscar dados (usando o provider do LiveTrader)
                # O LiveTrader usa 300 barras por padrão em seu loop, replicamos isso
                latest_data = self.trader_engine.provider.get_latest_rates(data_ticker, 300, mt5_timeframe, simulation_datetime_local)
                if latest_data.empty:
                    self.log_message(f"Não foi possível obter dados para {data_ticker}."); continue
                last_candle_time = latest_data.index[-1].strftime('%Y-%m-%d %H:%M:%S %Z')

                # 2. Gerar features (usando a estratégia carregada pelo LiveTrader)
                strategy_instance = state["strategy"]
                featured_data = strategy_instance.define_features(latest_data)
                X_live = featured_data[strategy_instance.get_feature_names()].dropna()
                if X_live.empty:
                    self.log_message(f"Dados insuficientes para features em {data_ticker}."); continue

                # 3. Gerar sinal (usando o modelo carregado pelo LiveTrader)
                model_instance = state["model"]
                if not model_instance:
                     self.log_message(f"Modelo não carregado para {data_ticker}, pulando predição.")
                     signal = -1 # Sinal de Hold/Erro
                     signal_text = "N/A (sem modelo)"
                else:
                    # Verifica lookback antes de prever
                    min_lookback = getattr(model_instance, 'lookback', 1)
                    if len(X_live) < min_lookback:
                        self.log_message(f"Dados insuficientes ({len(X_live)}<{min_lookback}) para predição IA em {data_ticker}.")
                        signal = -1
                        signal_text = "N/A (dados insuficientes)"
                    else:
                        predictions = model_instance.predict(X_live)
                        if predictions is not None and len(predictions) > 0:
                            signal = int(predictions[-1])
                            signal_text = 'COMPRA' if signal == 1 else 'VENDA'
                        else:
                            self.log_message(f"Modelo {data_ticker} não retornou predições.")
                            signal = -1
                            signal_text = "N/A (erro predição)"


                # 4. Obter preço sugerido e indicadores (similar ao notebook)
                suggested_price, price_source = 0.0, "N/A"
                stop_price = None
                symbol_info = mt5.symbol_info_tick(order_ticker)
                if symbol_info and symbol_info.time_msc > 0:
                    tick_time = datetime.fromtimestamp(symbol_info.time, tz=pytz.utc)
                    if abs((latest_data.index[-1] - tick_time).total_seconds()) < self.trader_engine.provider._timeframe_to_minutes(mt5_timeframe) * 60 * 1.5:
                        suggested_price = symbol_info.ask if signal == 1 else symbol_info.bid
                        price_source = "Tick MT5"
                if suggested_price == 0.0 and not latest_data.empty: # Fallback
                     suggested_price = latest_data['close'].iloc[-1]
                     price_source = "Último Fechamento"

                # Calcula Stop
                if suggested_price > 0 and signal != -1:
                    stop_loss_pct = asset_config['trading_rules']['stop_loss_pct']
                    stop_price = suggested_price * (1 - stop_loss_pct) if signal == 1 else suggested_price * (1 + stop_loss_pct)

                # Coleta indicadores
                last_indicators = featured_data.iloc[-1]
                indicator_keys = strategy_instance.get_feature_names() if hasattr(strategy_instance, 'get_feature_names') else []
                common_indicators = ['ema9', 'ema21', 'ema50', 'ema200', 'close', 'high', 'low']
                keys_to_log = sorted(list(set(indicator_keys + common_indicators)))
                indicators_dict = {}
                for key in keys_to_log:
                     if key in last_indicators:
                          value = last_indicators.get(key)
                          if isinstance(value, (float, np.floating)):
                               indicators_dict[key.upper()] = f"{value:.5f}" if pd.notna(value) else "N/A"
                          elif pd.notna(value): indicators_dict[key.upper()] = str(value)
                          else: indicators_dict[key.upper()] = "N/A"
                indicators_str = " | ".join([f"{k}={v}" for k, v in indicators_dict.items()]) if indicators_dict else "Nenhum"


                # 5. Logar a sugestão detalhada
                price_str = f"{suggested_price:.5f}" if suggested_price > 0 else "N/A"
                stop_str = f"{stop_price:.5f}" if stop_price is not None else "N/A"
                log_msg = (
                    f"Resultado {data_ticker} ({timeframe_str}) @ {last_candle_time}:\n"
                    f"  SINAL IA: {signal_text} ({signal})\n"
                    f"  Preço Sugerido: {price_str} (Fonte: {price_source})\n"
                    f"  Stop Sugerido: {stop_str}\n"
                    f"  Indicadores: {indicators_str}\n"
                    f"  Ticker Ordem: {order_ticker}"
                )
                self.log_message(log_msg)

                # 6. Simular envio da ordem (chama _execute_trade do LiveTrader)
                # Apenas se houver sinal válido (0 ou 1)
                if signal in [0, 1]:
                    # Nota: O _execute_trade do LiveTrader atualiza o state['position'] internamente
                    # Isso pode causar dessincronia se o dashboard for usado para múltiplos cliques
                    # sem resetar o estado. Para simulação pura, isso é aceitável.
                    self.trader_engine._execute_trade(data_ticker, 'BUY' if signal == 1 else 'SELL')
                else:
                     self.log_message(f"  Ação: Nenhuma ordem enviada (Sinal={signal_text})")


            except Exception as e:
                log_err = f"Erro ao simular {data_ticker}: {e}"
                logging.error(log_err, exc_info=True)
                self.log_message(log_err)

        self.log_message("--- Simulação Concluída ---")


    def _set_datetime_now(self):
         """Preenche campos com hora local atual."""
         try:
             local_tz_str = "America/Sao_Paulo"
             local_tz = pytz.timezone(local_tz_str)
             now_local = datetime.now(local_tz)
             self.sim_date_entry.delete(0, tk.END); self.sim_date_entry.insert(0, now_local.strftime("%Y-%m-%d"))
             self.sim_time_entry.delete(0, tk.END); self.sim_time_entry.insert(0, now_local.strftime("%H:%M"))
         except pytz.exceptions.UnknownTimeZoneError:
              messagebox.showerror("Erro Timezone", f"Timezone local '{local_tz_str}' não reconhecido.")
              now_utc = datetime.now(pytz.utc)
              self.sim_date_entry.delete(0, tk.END); self.sim_date_entry.insert(0, now_utc.strftime("%Y-%m-%d"))
              self.sim_time_entry.delete(0, tk.END); self.sim_time_entry.insert(0, now_utc.strftime("%H:%M"))

    def _clear_datetime(self):
         """Limpa campos de data/hora."""
         self.sim_date_entry.delete(0, tk.END); self.sim_date_entry.insert(0, "YYYY-MM-DD")
         self.sim_time_entry.delete(0, tk.END); self.sim_time_entry.insert(0, "HH:MM")

    # --- Função de Fechamento ---
    def _on_closing(self):
        """Handler para fechar a janela."""
        log.info("Fechando dashboard...")
        self.market_data_running = False
        # Aguarda thread do monitor
        if hasattr(self, 'market_data_thread') and self.market_data_thread.is_alive():
             try: self.market_data_thread.join(timeout=0.5)
             except RuntimeError: pass
        # Desliga conexão MT5 (se ativa)
        if mt5.terminal_info():
             log.info("Desconectando do MetaTrader 5...")
             mt5.shutdown()
        log.info("Desligamento concluído.")
        self.destroy()

# --- Bloco Principal ---
if __name__ == "__main__":
    app = LiveTradingDashboard()
    app.mainloop()