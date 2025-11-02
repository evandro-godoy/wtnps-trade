# src/gui/unified_dashboard.py
import sys
import yaml
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pytz
import time # <<< ADICIONADO IMPORT TIME
import tkinter as tk
from tkinter import ttk, messagebox, font as tkFont
from collections import deque
import csv # Para salvar o log
import MetaTrader5 as mt5 # <<< ADICIONADO IMPORT MT5
from threading import Thread
from queue import Queue, Empty

# Adiciona a raiz do projeto ao path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Importa engines DEPOIS de ajustar o path
from src.live_trader import LiveTrader # Usado apenas para type hinting e stop
from src.simulation.engine import SimulationEngine

# Configuração do Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s')
logger = logging.getLogger(__name__) # Usa logger em vez de log

class UnifiedDashboard(tk.Tk):
    """ Interface Gráfica Unificada para Simulação e Live Trading. """
    def __init__(self, config_path="configs/main.yaml"):
        super().__init__()
        self.title("WTNPS Trade - Unified Dashboard")
        self.geometry("1200x750")

        self.config_path = config_path
        self.config = self._load_config()
        if self.config is None: self.destroy(); return

        # Timezone único e padrão: UTC
        self.local_tz = pytz.utc
        logger.info("Dashboard usando timezone: UTC")

        self.assets_config_list = self.config.get('assets', [])
        self.all_asset_tickers = [cfg.get('ticker') for cfg in self.assets_config_list if cfg.get('ticker')]
        # Filtra tickers que têm config de live trading e estão habilitados nela
        self.live_asset_tickers_config = {
            cfg['ticker']: cfg.get('live_trading', {})
            for cfg in self.assets_config_list
            if cfg.get('ticker') and cfg.get('live_trading', {}).get('enabled', False)
        }
        self.live_asset_tickers = list(self.live_asset_tickers_config.keys()) # Apenas os tickers habilitados para live

        self.market_data_auto_refresh = tk.BooleanVar(value=True)
        self.auto_refresh_job_id = None
        self.refresh_interval_ms = 60 * 1000 # 1 minuto

        self.last_results = deque(maxlen=2)
        self.all_results_log = []

        self.asset_widgets = {}
        self.queue = Queue()

        # --- Motores ---
        self.trader_engine: LiveTrader | None = None # Hinting
        self.simulation_engine: SimulationEngine | None = None
        self.is_trader_initialized = False
        self.is_simulation_engine_initialized = False
        
        # Flag para saber se o monitoramento live está ativo
        self.is_live_monitoring_active = False

        self._setup_styles()
        self._create_widgets()

        # --- Inicialização dos Motores em Threads Separadas ---
        logger.info("Iniciando thread de inicialização do LiveTrader...")
        Thread(target=self._initialize_trader_engine, daemon=True).start()
        logger.info("Iniciando thread de inicialização do SimulationEngine...")
        Thread(target=self._initialize_simulation_engine, daemon=True).start()

        self.after(100, self._process_queue) # Inicia processador de fila da GUI
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Inicia o auto-refresh do monitor de mercado se habilitado
        # if self.market_data_auto_refresh.get():
        #     self._start_auto_refresh()
        # self._update_refresh_status_label()

    def _load_config(self):
        """Carrega configuração YAML."""
        logger.info(f"Carregando config: {self.config_path}")
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f: return yaml.safe_load(f)
        except FileNotFoundError: logger.error(f"Config '{self.config_path}' não encontrado."); messagebox.showerror("Erro", f"'{self.config_path}' não encontrado."); return None
        except yaml.YAMLError as e: logger.error(f"Erro YAML '{self.config_path}': {e}"); messagebox.showerror("Erro", f"Erro config '{self.config_path}':\n{e}"); return None

    def _setup_styles(self):
        """Define estilos Ttk."""
        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        # Cores personalizadas
        self.bg_color="#2E2E2E"; self.fg_color="#E0E0E0"; self.frame_bg="#3C3C3C"; self.entry_bg="#555555"
        self.buy_color="lime green"; self.sell_color="red"; self.hold_color="orange"
        self.status_ok_color="deep sky blue"; self.status_err_color="red"; self.status_warn_color="gold"
        self.configure(bg=self.bg_color)
        self.style.configure(".", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 9))
        self.style.configure("TFrame", background=self.frame_bg); self.style.configure("TLabel", background=self.frame_bg, foreground=self.fg_color)
        self.style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"), padding=(0,5,0,5))
        self.style.configure("CardTitle.TLabel", font=("Segoe UI", 10, "bold"))
        self.style.configure("TButton", background="#555555", foreground=self.fg_color, padding=5); self.style.map("TButton", background=[('active','#666666')])
        self.style.configure("TEntry", fieldbackground=self.entry_bg, foreground=self.fg_color, insertbackground=self.fg_color)
        self.style.configure("TCombobox", fieldbackground=self.entry_bg, foreground=self.fg_color, selectbackground=self.entry_bg, arrowcolor=self.fg_color)
        self.style.map('TCombobox', fieldbackground=[('readonly', self.entry_bg)], foreground=[('readonly', self.fg_color)])
        self.style.configure("Treeview", background=self.entry_bg, fieldbackground=self.entry_bg, foreground=self.fg_color); self.style.configure("Treeview.Heading", background="#444444", foreground=self.fg_color, font=("Segoe UI", 9, "bold")); self.style.map("Treeview.Heading", background=[('active','#555555')])
        self.style.configure("TCheckbutton", background=self.frame_bg, foreground=self.fg_color); self.style.map("TCheckbutton", indicatorcolor=[('selected', self.buy_color)], background=[('active', self.frame_bg)])
        self.style.configure("Buy.TLabel", foreground=self.buy_color, background=self.frame_bg, font=("Segoe UI", 9, "bold"))
        self.style.configure("Sell.TLabel", foreground=self.sell_color, background=self.frame_bg, font=("Segoe UI", 9, "bold"))
        self.style.configure("Hold.TLabel", foreground=self.hold_color, background=self.frame_bg, font=("Segoe UI", 9))
        self.style.configure("Error.TLabel", foreground=self.status_err_color, background=self.frame_bg, font=("Segoe UI", 9, "bold"))
        self.style.configure("Status.OK.TLabel", foreground=self.status_ok_color, background=self.bg_color)
        self.style.configure("Status.Warn.TLabel", foreground=self.status_warn_color, background=self.bg_color)
        self.style.configure("Status.Error.TLabel", foreground=self.status_err_color, background=self.bg_color)
        self.style.configure("Status.Off.TLabel", foreground="grey", background=self.bg_color)


    def _initialize_trader_engine(self):
        """(Thread) Instancia LiveTrader e aguarda sua init interna."""
        logger.info("Thread Init Trader: Iniciando...")
        try:
            self.trader_engine = LiveTrader(config_path=self.config_path, callback=self.queue.put)
            # Espera a thread de inicialização *interna* do LiveTrader
            if hasattr(self.trader_engine, '_init_thread') and self.trader_engine._init_thread:
                logger.info("Thread Init Trader: Aguardando inicialização interna do LiveTrader...")
                self.trader_engine._init_thread.join() # Espera aqui
            # Verifica o estado APÓS a inicialização interna terminar
            self.is_trader_initialized = self.trader_engine.is_trader_initialized # Pega flag do engine
            if self.is_trader_initialized: logger.info("Thread Init Trader: LiveTrader inicializado.")
            else: logger.error("Thread Init Trader: LiveTrader falhou na inicialização (ver logs anteriores).")
        except Exception as e:
            logger.critical(f"Falha CRÍTICA ao instanciar/aguardar LiveTrader: {e}", exc_info=True)
            self.is_trader_initialized = False
            try: self.queue.put({"type": "status", "asset": "GLOBAL", "message": "Live CRÍTICO", "color": "red"})
            except Exception: pass # Ignora erro se a fila falhar aqui
        finally: logger.info("Thread Init Trader: Finalizada.")


    def _initialize_simulation_engine(self):
        """(Thread) Instancia SimulationEngine."""
        logger.info("Thread Init Sim: Iniciando...")
        try:
            self.simulation_engine = SimulationEngine(config_path=self.config_path)
            # Tenta pré-carregar recursos do primeiro ativo (se houver)
            first_ticker = next(iter(self.all_asset_tickers), None)
            if first_ticker and self.simulation_engine:
                 logger.info(f"Thread Init Sim: Pré-carregando recursos para {first_ticker}...")
                 res = self.simulation_engine._load_asset_resources(first_ticker)
                 if not res or 'error' in res:
                      logger.warning(f"Falha ao pré-carregar recursos para {first_ticker} no SimulationEngine.")
                      # Não impede a inicialização, mas loga
            self.is_simulation_engine_initialized = True
            logger.info("Thread Init Sim: SimulationEngine instanciado.")
            self.queue.put({"type": "status_sim", "message": "Simulador Pronto", "color": "blue"})
        except Exception as e:
            logger.critical(f"Falha CRÍTICA ao instanciar SimulationEngine: {e}", exc_info=True)
            self.is_simulation_engine_initialized = False
            self.queue.put({"type": "status_sim", "message": "Erro Simulador", "color": "red"})
        finally: logger.info("Thread Init Sim: Finalizada.")


    def _create_widgets(self):
        """Cria componentes visuais."""
        # --- Layout Principal ---
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=3)

        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

        # --- Componentes ---
        header = ttk.Frame(main_frame, style="TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(header, text="WTNPS Unified Dashboard", style="Header.TLabel").pack(side=tk.LEFT, padx=5)


        self.global_status_label = ttk.Label(header, text="Inicializando...", anchor=tk.E, style="Status.Warn.TLabel")
        self.global_status_label.pack(side=tk.RIGHT, padx=5)
        
        controls_frame = ttk.Frame(main_frame, padding=10)
        controls_frame.grid(row=1, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        controls_frame.rowconfigure(2, weight=1)
        controls_frame.columnconfigure(0, weight=1)
        self._create_simulation_controls(controls_frame)
        self._create_live_controls(controls_frame)
        monitor_results_frame = ttk.Frame(main_frame)
        monitor_results_frame.grid(row=1, column=1, rowspan=2, sticky="nsew")
        monitor_results_frame.rowconfigure(0, weight=1)
        monitor_results_frame.rowconfigure(1, weight=0)
        monitor_results_frame.columnconfigure(0, weight=1)
        self._create_market_monitor(monitor_results_frame)
        self._create_results_display(monitor_results_frame)

    def _create_simulation_controls(self, parent):
        """Cria controles de simulação."""
        frame = ttk.LabelFrame(parent, text=" Market Replay (Simulação) ", padding=10); frame.grid(row=0, column=0, sticky="new", pady=(0, 10))
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Ativo:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.sim_asset_var = tk.StringVar(); self.sim_asset_combo = ttk.Combobox(frame, textvariable=self.sim_asset_var, values=self.all_asset_tickers, width=12, state="readonly")
        if self.all_asset_tickers: self.sim_asset_combo.current(0)
        self.sim_asset_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=3)
        ttk.Label(frame, text="Timeframe:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        timeframes = ["M1", "M5", "M15", "M30", "H1", "D1"]; self.sim_tf_var = tk.StringVar(value="M5"); self.sim_tf_combo = ttk.Combobox(frame, textvariable=self.sim_tf_var, values=timeframes, width=8, state="readonly")
        self.sim_tf_combo.grid(row=1, column=1, sticky="w", padx=5, pady=3)
        ttk.Label(frame, text="Data/Hora (UTC):").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        now_local_str = datetime.now(self.local_tz).strftime("%Y-%m-%d %H:%M"); self.sim_datetime_var = tk.StringVar(value=now_local_str); self.sim_datetime_entry = ttk.Entry(frame, textvariable=self.sim_datetime_var, width=20)
        self.sim_datetime_entry.grid(row=2, column=1, sticky="w", padx=5, pady=3); ttk.Label(frame, text="YYYY-MM-DD HH:MM:SS", font=("Segoe UI", 7)).grid(row=3, column=1, sticky="w", padx=5)
        self.sim_button = ttk.Button(frame, text="Executar Simulação", command=self._run_simulation_click); self.sim_button.grid(row=4, column=0, columnspan=2, pady=(10, 5))
        self.sim_status_label = ttk.Label(frame, text="Simulador: Aguardando...", anchor=tk.CENTER); self.sim_status_label.grid(row=5, column=0, columnspan=2, pady=(0, 5))


    def _create_live_controls(self, parent):
        """Cria controles de live trading."""
        frame = ttk.LabelFrame(parent, text=" Live Trading ", padding=10); frame.grid(row=1, column=0, sticky="new")
        frame.columnconfigure(0, weight=1)
        self.live_start_button = ttk.Button(frame, text="INICIAR Monitoramento", command=self._start_live_click); self.live_start_button.grid(row=0, column=0, pady=5)
        self.live_stop_button = ttk.Button(frame, text="PARAR Monitoramento", command=self._stop_live_click, state=tk.DISABLED); self.live_stop_button.grid(row=1, column=0, pady=5)
        self.live_status_label = ttk.Label(frame, text="Live: Desligado", anchor=tk.CENTER); self.live_status_label.grid(row=2, column=0, pady=(10, 5))


    def _create_market_monitor(self, parent):
        """Cria seção do Monitor de Mercado."""
        frame = ttk.LabelFrame(parent, text=" Monitor de Mercado ", padding=10); frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        frame.columnconfigure(0, weight=1); frame.rowconfigure(1, weight=1)
        controls_frame = ttk.Frame(frame, style="TFrame"); controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.refresh_check = ttk.Checkbutton(controls_frame, text="Auto Refresh (1 min)", variable=self.market_data_auto_refresh, command=self._toggle_auto_refresh); self.refresh_check.pack(side=tk.LEFT, padx=5)
        self.refresh_button = ttk.Button(controls_frame, text="Atualizar Agora", command=self._manual_refresh_click); self.refresh_button.pack(side=tk.LEFT, padx=5)
        self.refresh_status_label = ttk.Label(controls_frame, text="...", anchor=tk.E); self.refresh_status_label.pack(side=tk.RIGHT, padx=5)
        cols = ("Ticker", "Preço Atual", "Hora (UTC)", "Bid", "Ask", "Volume"); self.market_tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode="browse")
        for col in cols: self.market_tree.heading(col, text=col); self.market_tree.column(col, anchor=tk.W if col=="Ticker" else tk.CENTER, width=110, stretch=tk.NO if col=="Ticker" else tk.YES) # Ajusta ancoragem e stretch
        self.market_tree.grid(row=1, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.market_tree.yview); self.market_tree.configure(yscrollcommand=tree_scroll.set); tree_scroll.grid(row=1, column=1, sticky="ns")
        self._populate_market_monitor_placeholder()


    def _create_results_display(self, parent):
        """Cria seção dos últimos resultados."""
        frame = ttk.LabelFrame(parent, text=" Últimas Execuções ", padding=10); frame.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        self.result_label_1 = ttk.Label(frame, text="Resultado 1: ---", wraplength=1000, justify=tk.LEFT); self.result_label_1.grid(row=0, column=0, sticky="w", pady=2)
        self.result_label_2 = ttk.Label(frame, text="Resultado 2: ---", wraplength=1000, justify=tk.LEFT); self.result_label_2.grid(row=1, column=0, sticky="w", pady=2)


    # --- Funções de Controle ---

    def _run_simulation_click(self):

        """Inicia a execução da simulação em uma thread."""
        if not self.is_simulation_engine_initialized or not self.simulation_engine:
             messagebox.showerror("Erro", "Motor de Simulação não inicializado.") 
             return
        
        asset = self.sim_asset_var.get()
        tf = self.sim_tf_var.get() 
        dt_str = self.sim_datetime_var.get()

        if not asset: 
            messagebox.showwarning("Atenção", "Selecione um ativo.") 
            return
        
        try: 
            dt_utc_naive = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except ValueError: 
            messagebox.showerror("Erro", f"Formato Data/Hora inválido: {dt_str}") 
            return
        
        # Converte para aware em UTC
        try: 
            dt_utc_aware = pytz.utc.localize(dt_utc_naive)
        except (pytz.exceptions.NonExistentTimeError, pytz.exceptions.AmbiguousTimeError) as e:
            messagebox.showerror("Erro Fuso Horário", f"Data/Hora inválida ou ambígua: {e}")
            return

        logger.info(f"Solicitando simulação: {asset} @ {tf} em {dt_utc_aware}")
        self.sim_status_label.config(text="Simulando...", foreground=self.hold_color)
        self.sim_button.config(state=tk.DISABLED)
        
        Thread(target=self._execute_simulation_thread, args=(asset, tf, dt_utc_aware), daemon=True).start()


    def _execute_simulation_thread(self, asset, tf, dt_utc_aware):
        """(Thread) Executa simulação e envia resultado para fila."""
        # Garante que o engine existe antes de chamar
        if self.simulation_engine:
            try:
                result = self.simulation_engine.run_simulation_cycle(asset, tf, dt_utc_aware)
                self.queue.put({"type": "sim_result", "data": result})
            except Exception as e:
                logger.error(f"Erro thread simulação {asset}: {e}", exc_info=True)
                self.queue.put({"type": "sim_result", "data": {"error": f"Erro interno simulação: {e}"}})
        else:
             logger.error("SimulationEngine não disponível para executar simulação.")
             self.queue.put({"type": "sim_result", "data": {"error": "Motor de Simulação indisponível."}})


    def _start_live_click(self):
        """Solicita o início do monitoramento live."""
        if not self.is_trader_initialized: messagebox.showwarning("Atenção", "LiveTrader não inicializado."); return
        if self.is_live_monitoring_active: logger.warning("Monitoramento Live já ativo."); return # Previne start duplo
        if not self.live_asset_tickers: messagebox.showinfo("Informação", "Nenhum ativo habilitado para Live."); return

        logger.info("Botão INICIAR LIVE clicado.")
        # Desabilita botão Imediatamente para feedback
        self.live_start_button.config(state=tk.DISABLED)
        self.live_status_label.config(text="Live: Iniciando...")
        # Chama o start do engine (que roda em background)
        if self.trader_engine: self.trader_engine.start()
        # O estado dos botões e label será atualizado pelo callback do engine


    def _stop_live_click(self):
        """Solicita a parada do monitoramento live."""
        if not self.is_trader_initialized or not self.trader_engine: return # Não faz nada se não inicializado
        if not self.is_live_monitoring_active: logger.warning("Monitoramento Live já parado."); return # Previne stop duplo

        logger.info("Botão PARAR LIVE clicado.")
        self.live_stop_button.config(state=tk.DISABLED) # Desabilita imediatamente
        self.live_status_label.config(text="Live: Parando...")
        self.trader_engine.stop() # Chama o stop (bloqueante ou não, dependendo da implementação)
        # O estado dos botões e label será atualizado pelo callback do engine


    def _toggle_auto_refresh(self):
        """Ativa/Desativa o auto refresh."""
        if self.market_data_auto_refresh.get(): self._start_auto_refresh()
        else: self._stop_auto_refresh()
        self._update_refresh_status_label()


    def _manual_refresh_click(self):
        """Força atualização do monitor."""
        logger.info("Botão ATUALIZAR MONITOR clicado.")
        # Cancela qualquer job pendente para evitar duas atualizações seguidas
        self._stop_auto_refresh()
        self._update_market_monitor()
        # Reagenda se o auto-refresh estiver ligado
        if self.market_data_auto_refresh.get(): self._start_auto_refresh(immediate=False) # Não executa imediatamente de novo
        self._update_refresh_status_label()


    def _start_auto_refresh(self, immediate=True):
        """Agenda/Reagenda auto-refresh."""
        self._stop_auto_refresh() # Garante que não haja jobs duplicados
        if immediate: self._update_market_monitor() # Executa uma vez agora
        # Agenda a próxima execução
        self.auto_refresh_job_id = self.after(self.refresh_interval_ms, self._start_auto_refresh)
        logger.debug(f"Auto Refresh agendado (Job: {self.auto_refresh_job_id})")


    def _stop_auto_refresh(self):
        """Cancela auto-refresh."""
        if self.auto_refresh_job_id:
            logger.debug(f"Cancelando Auto Refresh (Job: {self.auto_refresh_job_id})")
            self.after_cancel(self.auto_refresh_job_id)
            self.auto_refresh_job_id = None


    def _update_refresh_status_label(self):
        """Atualiza label de status do refresh."""
        is_on = self.market_data_auto_refresh.get()
        status = "Auto Refresh: ON" if is_on else "Auto Refresh: OFF"
        # Adiciona hora da última atualização se disponível
        last_update = getattr(self, '_last_monitor_update_time', None)
        if last_update: status += f" | Última: {last_update.strftime('%H:%M:%S')}"
        self.refresh_status_label.config(text=status)


    # --- MÉTODO PARA ATUALIZAR MONITOR DE MERCADO ---
    def _update_market_monitor(self):
        """Busca dados de tick via MT5 e atualiza a Treeview."""
        logger.debug("Atualizando Monitor de Mercado...")

        # Verifica se o trader engine e o provider MT5 estão disponíveis
        mt5_conn_ok = False
        provider = None
        # Acessa o provider de forma segura
        if self.trader_engine and hasattr(self.trader_engine, '_lock'):
             with self.trader_engine._lock:
                  provider = self.trader_engine.mt5_provider
                  if provider and provider.is_connected():
                       mt5_conn_ok = True
        elif not self.is_trader_initialized: # Se ainda não inicializou, tenta conectar aqui
             if mt5.initialize():
                  mt5_conn_ok = True
             else:
                  logger.warning("MT5 não conectado para atualizar monitor.")
        elif self.is_trader_initialized and not mt5_conn_ok: # Se inicializou mas perdeu conexão
             logger.warning("MT5 desconectado. Tentando reconectar para monitor...")
             # Tenta reconectar através do engine se ele existir
             if self.trader_engine and hasattr(self.trader_engine, '_initialize_mt5'):
                  if self.trader_engine._initialize_mt5():
                       with self.trader_engine._lock: provider = self.trader_engine.mt5_provider
                       if provider and provider.is_connected(): mt5_conn_ok = True
                  else: logger.error("Falha ao reconectar MT5 para monitor.")
             elif not self.trader_engine: # Se não tem engine, tenta direto
                  if mt5.initialize(): mt5_conn_ok = True


        if not mt5_conn_ok:
            logger.warning("Não foi possível conectar ao MT5 para atualizar o monitor.")
            # Limpa a tabela ou mostra mensagem de erro? Limpar por enquanto.
            for item in self.market_tree.get_children(): self.market_tree.delete(item)
            self._last_monitor_update_time = datetime.now(self.local_tz) # Marca tentativa
            self._update_refresh_status_label()
            # Reagenda se auto-refresh estiver ligado, para tentar de novo depois
            if self.market_data_auto_refresh.get() and not self.auto_refresh_job_id:
                 self.auto_refresh_job_id = self.after(self.refresh_interval_ms, self._start_auto_refresh)
            return

        # Busca ticks para os ativos configurados para LIVE TRADING
        # Usa os tickers definidos em live_trading.ticker_order
        updated_rows = {}
        for asset_symbol in self.live_asset_tickers:
            live_cfg = self.live_asset_tickers_config.get(asset_symbol, {})
            ticker_to_fetch = live_cfg.get('ticker_order', asset_symbol) # Usa ticker_order se definido
            tick = None
            try:
                tick = mt5.symbol_info_tick(ticker_to_fetch)
            except Exception as e:
                logger.warning(f"Erro ao buscar tick para {ticker_to_fetch}: {e}")
                tick = None # Garante que tick é None em caso de erro

            if tick and tick.time > 0: # Verifica se o tick é válido
                # Converte timestamp do tick para datetime UTC
                tick_time_utc = datetime.fromtimestamp(tick.time, tz=pytz.utc)
                time_str = tick_time_utc.strftime("%H:%M:%S")

                # Determina preço atual (ex: último negociado ou média bid/ask)
                current_price = tick.last if tick.last > 0 else (tick.bid + tick.ask) / 2
                volume = tick.volume # Volume do último tick

                # Formata os dados para a tabela
                # ("Ticker", "Preço Atual", "Hora (UTC)", "Bid", "Ask", "Volume")
                row_data = (
                    asset_symbol, # Mostra o ticker principal (WDO$, WIN$)
                    f"{current_price:.2f}", # Ajuste a precisão se necessário
                    time_str,
                    f"{tick.bid:.2f}",
                    f"{tick.ask:.2f}",
                    f"{volume:.0f}" # Volume como inteiro
                )
                updated_rows[asset_symbol] = row_data
            else:
                 # Mantém dados antigos ou mostra 'Erro'? Por ora, marca como 'Inválido'
                 updated_rows[asset_symbol] = (asset_symbol, "Inválido", "---", "---", "---", "---")


        # Atualiza a Treeview
        items_in_tree = {self.market_tree.item(item, "values")[0]: item for item in self.market_tree.get_children()}

        for ticker, row_data in updated_rows.items():
             item_id = items_in_tree.get(ticker)
             if item_id: # Atualiza linha existente
                  self.market_tree.item(item_id, values=row_data)
             else: # Insere nova linha (caso algum ativo não estivesse antes)
                  tag = 'even' if len(self.market_tree.get_children()) % 2 == 0 else 'odd'
                  self.market_tree.insert("", tk.END, values=row_data, tags=(tag,))

        # Remove linhas da treeview que não estão mais na lista de ativos live (improvável, mas seguro)
        live_set = set(self.live_asset_tickers)
        for ticker_in_tree, item_id in items_in_tree.items():
             if ticker_in_tree not in live_set:
                  self.market_tree.delete(item_id)

        # Atualiza timestamp da última atualização e label
        self._last_monitor_update_time = datetime.now(self.local_tz)
        self._update_refresh_status_label()
        logger.debug("Monitor de Mercado atualizado.")

        # Reagenda o próximo auto-refresh APENAS SE ele foi chamado pelo 'after'
        # e não manualmente, e se o auto-refresh ainda está ativo.
        # A lógica em _start_auto_refresh já cuida disso.


    def _populate_market_monitor_placeholder(self):
         """Adiciona linhas iniciais vazias."""
         # Limpa antes de popular
         for item in self.market_tree.get_children(): self.market_tree.delete(item)
         # Adiciona placeholders para ativos LIVE
         for ticker in self.live_asset_tickers:
             tag = 'even' if len(self.market_tree.get_children()) % 2 == 0 else 'odd'
             self.market_tree.insert("", tk.END, values=(ticker, "Carregando...", "...", "...", "...", "..."), tags=(tag,))
         # Configura cores alternadas
         self.market_tree.tag_configure('even', background='#505050', foreground='white')
         self.market_tree.tag_configure('odd', background='#454545', foreground='white')


    def _add_result_to_display(self, result_dict):
        """Adiciona resultado (Sim ou Live) ao display e log."""
        if not result_dict or not isinstance(result_dict, dict): return # Ignora inválido

        # Adiciona tipo (Simulação/Live) se não existir
        if "type" not in result_dict: result_dict["type"] = "Desconhecido"

        # Garante timestamp para o log
        log_entry = result_dict.copy()
        log_entry["log_timestamp"] = datetime.now(self.local_tz).isoformat()

        self.all_results_log.append(log_entry) # Guarda cópia com timestamp
        self.last_results.append(result_dict) # Guarda original para display

        results = list(self.last_results)
        prec = result_dict.get('price_precision', 2) # Usa precisão do ativo se disponível

        def format_res(res):
            price_str = f"{res.get('current_price','?'):.{prec}f}" if isinstance(res.get('current_price'), (int, float)) else "?"
            sl_str = f"{res.get('stop_loss','?'):.{prec}f}" if isinstance(res.get('stop_loss'), (int, float)) else "N/A"
            tp_str = f"{res.get('take_profit','?'):.{prec}f}" if isinstance(res.get('take_profit'), (int, float)) else "N/A"
            return f"[{res.get('datetime','')}] ({res.get('type','?')}) {res.get('asset','?')}/{res.get('timeframe','?')}: Sinal={res.get('final_signal','?')}, P={price_str}, SL={sl_str}, TP={tp_str}, Pos={res.get('position','---')}"

        res1_str = format_res(results[-1]) if len(results) > 0 else "---"
        self.result_label_1.config(text=f"Recente: {res1_str}")
        self._color_result_label(self.result_label_1, results[-1].get('final_signal') if len(results) > 0 else None)

        res2_str = format_res(results[-2]) if len(results) > 1 else "---"
        self.result_label_2.config(text=f"Anterior: {res2_str}")
        self._color_result_label(self.result_label_2, results[-2].get('final_signal') if len(results) > 1 else None)

    def _color_result_label(self, label, signal):
         """Aplica estilo ao label de resultado baseado no sinal."""
         if signal == "COMPRA": label.config(style="Buy.TLabel")
         elif signal == "VENDA": label.config(style="Sell.TLabel")
         elif signal == "ERRO_IA" or signal == "ERRO": label.config(style="Error.TLabel")
         else: label.config(style="Hold.TLabel") # HOLD ou ---


    def _save_log_to_csv(self):
        """Salva log completo em CSV."""
        if not self.all_results_log: logger.info("Nenhum resultado para salvar."); return
        log_dir = Path("logs"); log_dir.mkdir(exist_ok=True)
        filename = log_dir / f"unified_dashboard_log_{datetime.now():%Y%m%d_%H%M%S}.csv"
        try:
            # Pega cabeçalhos do último registro (mais provável ter todas as chaves)
            # Adiciona colunas para dicts serializados
            headers = list(self.all_results_log[-1].keys())
            if 'indicators' in headers: headers.remove('indicators'); headers.append('indicators_json')
            if 'setup_details' in headers: headers.remove('setup_details'); headers.append('setup_details_json')
            if 'log_timestamp' not in headers: headers.insert(0, 'log_timestamp') # Garante timestamp

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
                writer.writeheader()
                for row in self.all_results_log:
                     row_copy = row.copy()
                     # Serializa dicts aninhados
                     if isinstance(row_copy.get('indicators'), dict): row_copy['indicators_json'] = str(row_copy.pop('indicators'))
                     if isinstance(row_copy.get('setup_details'), dict): row_copy['setup_details_json'] = str(row_copy.pop('setup_details'))
                     writer.writerow(row_copy)
            logger.info(f"Log de resultados salvo em: {filename}")
        except ImportError: logger.error("Módulo 'csv' não encontrado para salvar log."); messagebox.showerror("Erro", "Módulo 'csv' não disponível.")
        except Exception as e: logger.error(f"Erro ao salvar log CSV: {e}", exc_info=True); messagebox.showerror("Erro", f"Erro ao salvar log:\n{e}")

    def _process_queue(self):
        """Processa eventos da fila da GUI."""
        try:
            while True:
                msg = self.queue.get_nowait()
                msg_type = msg.get("type")

                if msg_type == "update": self._update_asset_card(msg.get("asset"), msg)
                elif msg_type == "position": self._update_asset_position(msg.get("asset"), msg)
                elif msg_type == "status": self._update_status_label(msg.get("asset"), msg.get("message"), msg.get("color"))
                elif msg_type == "status_sim": self.sim_status_label.config(text=msg.get("message", "??"), foreground=self.style.lookup(f"{msg.get('color','grey').title()}.TLabel", "foreground", default=self.fg_color))
                elif msg_type == "sim_result": self._add_result_to_display(msg.get("data")); self.sim_button.config(state=tk.NORMAL) # Reativa botão pós-simulação
                else: logger.warning(f"Mensagem desconhecida na fila: {msg}")

        except Empty: pass # Fila vazia
        except Exception as e: logger.warning(f"Erro processar fila GUI: {e}", exc_info=True)
        finally: self.after(100, self._process_queue) # Reagenda


    def _update_asset_card(self, asset_symbol, data):
        """Atualiza card de ativo live."""
        if not asset_symbol or asset_symbol not in self.asset_widgets: return
        widgets = self.asset_widgets[asset_symbol]
        prec = self.asset_resources.get(asset_symbol, {}).get('price_precision', 2)
        price_str = f"{data.get('price','N/A'):.{prec}f}" if isinstance(data.get('price'),(float,int)) else 'N/A'
        widgets["price"].config(text=price_str)
        widgets["datetime"].config(text=f"{data.get('datetime', '---')}")
        ai = data.get("ai_signal","N/A"); widgets["ai_signal"].config(text=ai); self._update_label_color(widgets["ai_signal"], ai)
        valid = data.get("setup_valid"); widgets["setup_valid"].config(text=("SIM" if valid else "NÃO") if isinstance(valid, bool) else "N/A"); widgets["setup_valid"].config(style="Buy.TLabel" if valid else "Sell.TLabel" if valid is False else "Hold.TLabel")
        final = data.get("final_signal","N/A"); widgets["final_signal"].config(text=final); self._update_label_color(widgets["final_signal"], final)
        # Adiciona resultado ao log/display
        data['type'] = 'Live' # Marca como resultado live
        data['position'] = data.get('position', '---') # Garante que posição está no dict
        self._add_result_to_display(data)

    def _update_asset_position(self, asset_symbol, data):
        """Atualiza display de posição."""
        if not asset_symbol or asset_symbol not in self.asset_widgets: return
        widgets = self.asset_widgets[asset_symbol]
        status = data.get("status", "---"); price = data.get("price")
        prec = self.asset_resources.get(asset_symbol, {}).get('price_precision', 2)
        price_str = f"{price:.{prec}f}" if isinstance(price,(float,int)) else "?"

        if status == "Comprado": style = "PositionBuy.TLabel"; text = f"COMPRADO @ {price_str}"
        elif status == "Vendido": style = "PositionSell.TLabel"; text = f"VENDIDO @ {price_str}"
        else: style = "PositionFlat.TLabel"; text = f"POSIÇÃO: {status}" # Mostra status (ex: Fechado(SL))
        widgets["position"].config(text=text, style=style)

    def _update_status_label(self, asset_symbol, message, color_name):
        """Atualiza labels de status (global ou card)."""
        color_map = {"red": self.sell_color, "green": self.buy_color, "blue": self.status_ok_color, "orange": self.hold_color, "grey": "grey"}
        color = color_map.get(color_name, self.fg_color)
        if asset_symbol == "GLOBAL":
            self.global_status_label.config(text=message or "??", foreground=color)
            # Atualiza estado dos botões live baseado no status global
            if message == "Monitorando...":
                 self.is_live_monitoring_active = True
                 self.live_start_button.config(state=tk.DISABLED)
                 self.live_stop_button.config(state=tk.NORMAL)
                 self.live_status_label.config(text="Live: ATIVO", foreground=self.buy_color)
            elif message in ["Parado", "Vazio", "Erro MT5", "Falha Init/MT5", "Live CRÍTICO"]:
                 self.is_live_monitoring_active = False
                 self.live_start_button.config(state=tk.NORMAL)
                 self.live_stop_button.config(state=tk.DISABLED)
                 status_text = "Live: Desligado" if message=="Parado" else f"Live: {message}"
                 status_color = self.fg_color if message=="Parado" else color
                 self.live_status_label.config(text=status_text, foreground=status_color)

        elif asset_symbol in self.asset_widgets:
            self.asset_widgets[asset_symbol]["status"].config(text=message or "??", foreground=color)

    def _on_closing(self):
        """Chamado ao fechar a janela."""
        logger.info("Fechando dashboard...")
        if messagebox.askokcancel("Sair", "Deseja fechar? O monitoramento será interrompido e o log salvo."):
            # Para o auto-refresh imediatamente
            self._stop_auto_refresh()

            # Para o LiveTrader (se iniciado)
            # Verifica se a engine foi instanciada antes de chamar stop
            if self.trader_engine:
                logger.info("Solicitando parada do LiveTrader...")
                self.trader_engine.stop() # stop() agora espera as threads

            # Salva o log ANTES de fechar o SimulationEngine (que pode fechar conexão MT5)
            self._save_log_to_csv()

            # Fecha engine de simulação
            if self.simulation_engine and hasattr(self.simulation_engine, 'close'):
                 logger.info("Fechando SimulationEngine...")
                 self.simulation_engine.close()

            # Espera um pouco se necessário (time.sleep é ok aqui no fechamento)
            # time.sleep(0.5) # <<< CORRIGIDO USO DO TIME

            logger.info("Encerrando aplicação GUI.")
            # Desconecta MT5 explicitamente se ainda estiver conectado (fallback)
            if mt5.terminal_info():
                 logger.info("Desconectando MT5 (fallback)...")
                 mt5.shutdown()
            self.destroy()

# --- Bloco Principal ---
if __name__ == "__main__":
    # Garante inicialização MT5 para buscar ticks no monitor ANTES do LiveTrader
    if not mt5.initialize():
        logger.error("Falha ao inicializar MT5 globalmente. Monitor de Mercado pode não funcionar.")
        # Decide se continua ou aborta. Continuar pode ser ok se só usar simulação.
        # messagebox.showerror("Erro MT5", "Não foi possível conectar ao MetaTrader 5.")
        # sys.exit(1) # Aborta

    app = UnifiedDashboard()
    app.mainloop()
    # Garante desligamento MT5 ao sair do loop principal
    if mt5.terminal_info():
        logger.info("Desligando MT5 ao sair...")
        mt5.shutdown()