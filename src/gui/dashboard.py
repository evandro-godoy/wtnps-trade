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
import pandas as pd # Adicionado para checagem de tipos

# Adiciona a raiz do projeto ao path para importações
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data_handler.provider import MetaTraderProvider
from src.strategies.lstm import KerasLSTMWrapper # Usado para checagem de tipo

# Configuração básica do logging para a GUI
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TradingDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Whatsneps Trade v1.0")
        self.geometry("900x700") # Aumentado um pouco para caber mais info

        # --- Carrega Configuração ---
        try:
            with open(project_root / "configs/main.yaml", "r") as file:
                self.config = yaml.safe_load(file)
            self.assets_config = [
                asset for asset in self.config["assets"] if asset.get("enabled", False)
            ]
            self.models_dir = project_root / self.config["global_settings"]["model_directory"]
        except Exception as e:
            logging.error(f"Erro ao carregar configuração: {e}")
            self.destroy()
            return

        self.asset_states = {}
        self.checkbox_vars = {}
        self.timeframe_comboboxes = {} # Para guardar os comboboxes de timeframe
        self.market_data_labels = {}

        # Variáveis de controle para Refresh
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.refresh_countdown = tk.IntVar(value=60)
        self.market_data_running = False

        # --- Layout Principal ---
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(expand=True, fill=tk.BOTH)

        # --- Frame Superior (Controles de Refresh) ---
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

        # Subframe para seleção (agora com timeframe)
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
        self.provider = MetaTraderProvider()
        if not self._connect_mt5():
             self.log_message("ERRO: Não foi possível conectar ao MetaTrader 5.")
        else:
            self._create_asset_widgets()
            self._start_market_data_updates() # Inicia loop para dados de mercado

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # --- Funções de Log e Conexão (sem alterações significativas) ---
    def log_message(self, message):
        if not hasattr(self, 'log_text') or not self.log_text.winfo_exists(): return
        try:
            self.log_text.configure(state='normal')
            self.log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state='disabled')
        except tk.TclError: pass # Ignora erro se a janela estiver fechando

    def _connect_mt5(self):
        if not mt5.initialize():
            logging.error(f"Falha na inicialização do MT5: {mt5.last_error()}")
            return False
        logging.info("Conectado ao MetaTrader 5.")
        return True

    def _get_mt5_timeframe_from_string(self, tf_str: str):
        tf_map = { "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
                   "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
                   "D1": mt5.TIMEFRAME_D1 }
        return tf_map.get(tf_str.upper(), mt5.TIMEFRAME_D1)

    # --- Carregamento de Modelo (sem alterações) ---
    def _load_single_asset_model(self, data_ticker):
        if data_ticker in self.asset_states: return self.asset_states[data_ticker]
        asset_config = next((asset for asset in self.assets_config if asset['ticker'] == data_ticker), None)
        if not asset_config: return None
        self.log_message(f"Carregando recursos para {data_ticker}...")
        try:
            module_path = f"src.strategies.{asset_config['strategy_module']}"
            strategy_module = importlib.import_module(module_path)
            StrategyClass = getattr(strategy_module, asset_config["strategy_name"])
            model_path = self.models_dir / f"{data_ticker}_prod_model.keras"
            scaler_path = self.models_dir / f"{data_ticker}_prod_scaler.joblib"
            if not model_path.exists() or not scaler_path.exists():
                self.log_message(f"ERRO: Modelo/Scaler para {data_ticker} não encontrado.")
                return None
            model = KerasLSTMWrapper.load_model(str(model_path), str(scaler_path))
            state = {"config": asset_config, "strategy": StrategyClass(), "model": model}
            self.asset_states[data_ticker] = state
            self.log_message(f"Recursos para {data_ticker} carregados.")
            return state
        except Exception as e:
            self.log_message(f"ERRO: Falha ao carregar {data_ticker}: {e}")
            logging.error(f"Falha ao carregar {data_ticker}", exc_info=True)
            return None

    # --- Criação de Widgets ---
    def _create_asset_widgets(self):
        # Limpa frames
        for widget in self.asset_selection_frame.winfo_children(): widget.destroy()
        for widget in self.market_data_frame.winfo_children(): widget.destroy()
        self.market_data_labels.clear()
        self.checkbox_vars.clear()
        self.timeframe_comboboxes.clear()

        # Cabeçalhos Monitor de Mercado
        headers = ["Ativo", "Abertura", "Máxima", "Mínima", "Último", "Médio", "Variação %"]
        for col, header in enumerate(headers):
            lbl = ttk.Label(self.market_data_frame, text=header, font=('Arial', 10, 'bold'))
            lbl.grid(row=0, column=col, padx=5, pady=2, sticky="w")

        # Linhas para cada ativo no Monitor
        for row_idx, asset_config in enumerate(self.assets_config, start=1):
            data_ticker = asset_config['ticker']
            order_ticker = asset_config['live_trading'].get('ticker_order', data_ticker)
            asset_labels = {}
            lbl_ticker = ttk.Label(self.market_data_frame, text=order_ticker, width=15)
            lbl_ticker.grid(row=row_idx, column=0, padx=5, pady=2, sticky="w")
            asset_labels['ticker'] = lbl_ticker
            for col_idx, key in enumerate(['open', 'high', 'low', 'last', 'avg', 'var'], start=1):
                lbl_data = ttk.Label(self.market_data_frame, text="-", width=12, anchor="e")
                lbl_data.grid(row=row_idx, column=col_idx, padx=5, pady=2, sticky="e")
                asset_labels[key] = lbl_data
            self.market_data_labels[order_ticker] = asset_labels

            # Checkbox e Combobox para Simulação
            asset_sim_frame = ttk.Frame(self.asset_selection_frame)
            asset_sim_frame.pack(side=tk.LEFT, padx=10, pady=2)

            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(asset_sim_frame, text=data_ticker, variable=var)
            chk.pack(side=tk.LEFT, padx=(0, 5))
            self.checkbox_vars[data_ticker] = var

            # Opções de Timeframe
            configured_tf = asset_config['live_trading']['timeframe_str']
            tf_options = ["M5", "M15", "H1", "D1"]
            if configured_tf not in tf_options:
                tf_options.append(configured_tf)
            tf_options = sorted(list(set(tf_options))) # Garante ordem e unicidade

            tf_combo = ttk.Combobox(asset_sim_frame, values=tf_options, width=5, state="readonly")
            tf_combo.set(configured_tf) # Pré-seleciona o configurado
            tf_combo.pack(side=tk.LEFT)
            self.timeframe_comboboxes[data_ticker] = tf_combo


    # --- Lógica de Atualização de Dados de Mercado ---
    def _start_market_data_updates(self):
        """Inicia a thread para atualizar os dados de mercado."""
        self.market_data_running = True
        self.market_data_thread = threading.Thread(target=self._update_market_data_loop, daemon=True)
        self.market_data_thread.start()

    def _update_market_data_loop(self):
        """Loop que busca e atualiza os dados de mercado e o timer."""
        while self.market_data_running:
            try:
                # Atualiza o Timer
                current_countdown = self.refresh_countdown.get()
                if self.auto_refresh_var.get():
                    if current_countdown <= 0:
                        self._fetch_and_update_market_data() # Busca dados
                        self.refresh_countdown.set(60) # Reseta timer
                    else:
                        self.refresh_countdown.set(current_countdown - 1)
                    timer_text = f"Próxima atualização em: {self.refresh_countdown.get()}s"
                else:
                    timer_text = "Auto Refresh: OFF"

                self.after(0, self.timer_label.config, {"text": timer_text})

            except Exception as e:
                logging.error(f"Erro no loop de atualização: {e}")

            time.sleep(1) # Loop roda a cada segundo

    def _manual_refresh(self):
        """Força a atualização dos dados de mercado e reseta o timer."""
        self.log_message("Atualização manual solicitada...")
        # Executa em thread para não travar
        refresh_thread = threading.Thread(target=self._fetch_and_update_market_data, daemon=True)
        refresh_thread.start()
        self.refresh_countdown.set(60) # Reseta timer

    def _fetch_and_update_market_data(self):
        """Busca os dados de mercado para todos os ativos e atualiza a GUI."""
        if not self._connect_mt5(): return # Garante conexão

        for order_ticker, labels in self.market_data_labels.items():
            try:
                rates = mt5.copy_rates_from_pos(order_ticker, mt5.TIMEFRAME_D1, 0, 1)
                tick = mt5.symbol_info_tick(order_ticker)

                if rates is not None and len(rates) > 0 and tick:
                    last_rate = rates[0]
                    o, h, l, c = last_rate['open'], last_rate['high'], last_rate['low'], last_rate['close']
                    last_price = tick.last
                    avg_price = (h + l) / 2
                    variation = ((last_price / o) - 1) * 100 if o > 0 else 0
                    var_color = "green" if variation >= 0 else "red"
                    var_text = f"{variation:+.2f}%"

                    # Atualiza GUI (agendado para a thread principal)
                    self.after(0, labels['open'].config, {"text": f"{o:.2f}"})
                    self.after(0, labels['high'].config, {"text": f"{h:.2f}"})
                    self.after(0, labels['low'].config, {"text": f"{l:.2f}"})
                    self.after(0, labels['last'].config, {"text": f"{last_price:.2f}"})
                    self.after(0, labels['avg'].config, {"text": f"{avg_price:.2f}"})
                    self.after(0, labels['var'].config, {"text": var_text, "foreground": var_color})
            except Exception as e:
                logging.warning(f"Erro ao buscar dados para {order_ticker}: {e}")
                # Limpa labels em caso de erro
                self.after(0, lambda lbls=labels: [lbl.config(text="-") for key, lbl in lbls.items() if key != 'ticker'])
        mt5.shutdown() # Desconecta após buscar todos os dados

    # --- Lógica de Simulação ---
    def _trigger_simulation(self):
        """Inicia a simulação de ciclo único para os ativos selecionados."""
        selected_tickers = [ticker for ticker, var in self.checkbox_vars.items() if var.get()]
        if not selected_tickers:
            self.log_message("Nenhum ativo selecionado para simulação.")
            return

        # Coleta os timeframes selecionados para os ativos
        selected_timeframes = { ticker: self.timeframe_comboboxes[ticker].get()
                                for ticker in selected_tickers if ticker in self.timeframe_comboboxes }

        self.log_message(f"Iniciando simulação para: {', '.join(selected_tickers)}")
        sim_thread = threading.Thread(target=self._run_simulation_thread,
                                      args=(selected_tickers, selected_timeframes), # Passa timeframes
                                      daemon=True)
        sim_thread.start()

    def _run_simulation_thread(self, tickers_to_simulate, selected_timeframes):
        """Lógica da simulação executada em uma thread separada."""
        if not self._connect_mt5():
             self.after(0, self.log_message, "ERRO: Não foi possível conectar ao MT5 para simulação.")
             return

        for data_ticker in tickers_to_simulate:
            state = self._load_single_asset_model(data_ticker)
            if not state: continue

            asset_config = state['config']
            live_config = asset_config['live_trading']
            order_ticker = live_config.get('ticker_order', data_ticker)
            # Usa o timeframe SELECIONADO pelo usuário
            timeframe_str = selected_timeframes.get(data_ticker, live_config['timeframe_str'])
            mt5_timeframe = self._get_mt5_timeframe_from_string(timeframe_str)

            self.after(0, self.log_message, f"--- Simulando {data_ticker} ({timeframe_str}) ---")

            try:
                # 1. Buscar dados
                latest_data = self.provider.get_latest_rates(data_ticker, 300, mt5_timeframe)
                if latest_data.empty:
                    self.after(0, self.log_message, f"Não foi possível obter dados para {data_ticker}.")
                    continue
                last_candle_time = latest_data.index[-1].strftime('%Y-%m-%d %H:%M:%S')

                # 2. Gerar features
                featured_data = state["strategy"].define_features(latest_data)
                X_live = featured_data[state["strategy"].get_feature_names()].dropna()
                if X_live.empty:
                    self.after(0, self.log_message, f"Dados insuficientes para features em {data_ticker}.")
                    continue

                # 3. Gerar sinal
                signal = state["model"].predict(X_live)[-1]
                signal_text = 'COMPRA' if signal == 1 else 'VENDA'

                # 4. Obter preço e indicadores para log
                suggested_price, price_source = 0.0, "N/A"
                symbol_info = mt5.symbol_info_tick(order_ticker)
                if symbol_info and symbol_info.ask > 0 and symbol_info.bid > 0:
                    suggested_price = symbol_info.ask if signal == 1 else symbol_info.bid
                    price_source = "Tick"
                elif not latest_data.empty:
                    suggested_price = latest_data['close'].iloc[-1]
                    price_source = "Último Fechamento"

                # Pega indicadores do último candle
                last_indicators = featured_data.iloc[-1]
                ma_values = {}
                ma_keys = ['sma_9', 'ema_21', 'ema_50', 'ema_200'] # Adaptar se nomes mudarem
                for key in ma_keys:
                    if key in last_indicators and pd.notna(last_indicators[key]):
                        ma_values[key] = f"{last_indicators[key]:.2f}"
                    else:
                         ma_values[key] = "N/A" # Caso não calculado ainda

                # 5. Logar a sugestão completa
                log_msg = (
                    f"SINAL {data_ticker} ({timeframe_str}): {signal_text}\n"
                    f"  Preço Sugerido: {suggested_price:.2f} (Fonte: {price_source})\n"
                    f"  Ref. Candle: {last_candle_time}\n"
                    f"  Indicadores: SMA9={ma_values['sma_9']} | EMA21={ma_values['ema_21']} | EMA50={ma_values['ema_50']} | EMA200={ma_values['ema_200']}\n"
                    f"  Ticker Ordem: {order_ticker}"
                )
                self.after(0, self.log_message, log_msg)

            except Exception as e:
                log_err = f"Erro ao simular {data_ticker}: {e}"
                logging.error(log_err, exc_info=True)
                self.after(0, self.log_message, log_err)

        mt5.shutdown()
        self.after(0, self.log_message, "--- Simulação Concluída ---")


    # --- Função de Fechamento ---
    def _on_closing(self):
        """Handler para quando a janela da GUI é fechada."""
        logging.info("Fechando dashboard...")
        self.market_data_running = False # Para a thread de cotações
        if self.market_data_thread and self.market_data_thread.is_alive():
             self.market_data_thread.join(timeout=1.0) # Espera thread terminar
        mt5.shutdown()
        self.destroy()

if __name__ == "__main__":
    app = TradingDashboard()
    app.mainloop()