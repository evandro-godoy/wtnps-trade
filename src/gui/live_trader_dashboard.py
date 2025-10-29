# src/gui/live_trader_dashboard.py

import sys
import yaml
import logging
from pathlib import Path
from datetime import datetime, time, timedelta
import pytz
from queue import Queue, Empty
from threading import Thread

import tkinter as tk
from tkinter import ttk, messagebox, font as tkFont

# Adiciona a raiz do projeto ao path para importações
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.live_trader import LiveTrader # Importa a classe LiveTrader
from src.simulation.engine import SimulationEngine # Importa o SimulationEngine

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s')
log = logging.getLogger(__name__)

class LiveTraderDashboard(tk.Tk):
    """
    Interface gráfica (GUI) principal para o Live Trader, combinando
    o monitoramento ao vivo com a capacidade de simulação "market replay".
    """
    def __init__(self, config_path="configs/main.yaml"):
        super().__init__()
        self.title("WTNPS Trade - Live Trader Dashboard")
        self.geometry("1400x800")

        # --- Configuração de Fuso Horário ---
        try:
            self.local_tz = pytz.timezone('America/Sao_Paulo')
        except pytz.UnknownTimeZoneError:
            log.warning("Timezone 'America/Sao_Paulo' não encontrado, usando UTC.")
            self.local_tz = pytz.utc
        self.utc_tz = pytz.utc

        # --- Carregamento de Config ---
        self.config_path = config_path
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            log.critical(f"Erro fatal ao carregar config: {e}")
            messagebox.showerror("Erro de Configuração", f"Não foi possível carregar 'configs/main.yaml'.\n{e}")
            self.destroy()
            return

        # --- Estado da Aplicação ---
        # Filtra assets que estão habilitados E têm configuração de live_trading habilitada
        self.assets = [
            asset['ticker'] for asset in self.config.get('assets', [])
            if asset.get('enabled', True) and asset.get('live_trading', {}).get('enabled', False)
        ]
        if not self.assets:
             log.warning("Nenhum ativo habilitado para Live Trading no 'configs/main.yaml'. O dashboard pode ficar vazio.")
             # Opcional: Mostrar um aviso na GUI
             # messagebox.showwarning("Aviso", "Nenhum ativo configurado e habilitado para Live Trading.")

        self.asset_widgets = {}
        self.queue = Queue()

        # --- Motores ---
        self.trader_engine = None
        self.simulation_engine = None
        self.is_trader_initialized = False
        self.is_simulation_engine_initialized = False

        # --- Inicialização da GUI ---
        self._setup_styles()
        self._create_widgets()

        # --- Inicialização dos Motores em Threads Separadas ---
        log.info("Iniciando thread de inicialização do LiveTrader...")
        Thread(target=self._initialize_trader_engine, daemon=True).start()
        log.info("Iniciando thread de inicialização do SimulationEngine...")
        Thread(target=self._initialize_simulation_engine, daemon=True).start()

        self.after(100, self._process_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_styles(self):
        """Define os estilos da Ttk."""
        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        # Cores (mantido igual)
        self.bg_color = "#2E2E2E"
        self.fg_color = "#E0E0E0"
        self.frame_bg = "#3C3C3C"
        self.entry_bg = "#555555"
        self.buy_color = "green"
        self.sell_color = "red"
        self.hold_color = "orange"
        self.status_ok_color = "blue"
        self.status_err_color = "red"

        self.configure(bg=self.bg_color)

        # Estilos Ttk (mantido igual)
        self.style.configure("TFrame", background=self.frame_bg)
        self.style.configure("TLabel", background=self.frame_bg, foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        self.style.configure("TButton", background="#555555", foreground=self.fg_color, font=("Segoe UI", 10), padding=5)
        self.style.map("TButton", background=[('active', '#666666')])
        self.style.configure("TEntry", fieldbackground=self.entry_bg, foreground=self.fg_color, insertbackground=self.fg_color)
        self.style.configure("TCombobox", fieldbackground=self.entry_bg, foreground=self.fg_color, selectbackground=self.entry_bg, arrowcolor=self.fg_color)
        self.style.map('TCombobox', fieldbackground=[('readonly', self.entry_bg)], foreground=[('readonly', self.fg_color)])

        # Estilos de Labels coloridos (mantido igual)
        self.style.configure("Buy.TLabel", foreground=self.buy_color, background=self.frame_bg, font=("Segoe UI", 11, "bold"))
        self.style.configure("Sell.TLabel", foreground=self.sell_color, background=self.frame_bg, font=("Segoe UI", 11, "bold"))
        self.style.configure("Hold.TLabel", foreground=self.hold_color, background=self.frame_bg, font=("Segoe UI", 11, "bold"))
        self.style.configure("PositionBuy.TLabel", foreground="white", background=self.buy_color, font=("Segoe UI", 10, "bold"), padding=2)
        self.style.configure("PositionSell.TLabel", foreground="white", background=self.sell_color, font=("Segoe UI", 10, "bold"), padding=2)
        self.style.configure("PositionFlat.TLabel", foreground=self.fg_color, background=self.frame_bg, font=("Segoe UI", 10), padding=2)


    def _initialize_trader_engine(self):
        """(Thread) Instancia o LiveTrader e aguarda sua inicialização interna."""
        log.info("Thread _initialize_trader_engine: Iniciando...")
        try:
            # 1. Instancia o LiveTrader (dispara a thread _init_thread interna)
            self.trader_engine = LiveTrader(config_path=self.config_path, callback=self.queue.put)

            # 2. **CORREÇÃO:** Espera a thread de inicialização interna do LiveTrader terminar
            if hasattr(self.trader_engine, '_init_thread') and self.trader_engine._init_thread is not None:
                log.info("Thread _initialize_trader_engine: Aguardando inicialização interna do LiveTrader...")
                self.trader_engine._init_thread.join() # Aguarda o fim da thread
                log.info("Thread _initialize_trader_engine: Inicialização interna do LiveTrader concluída.")

            # 3. Verifica o estado após a inicialização interna
            # Verifica se o provider foi criado e está conectado
            if self.trader_engine and self.trader_engine.mt5_provider and self.trader_engine.mt5_provider.is_connected():
                 # Verifica se algum ativo foi carregado com sucesso
                 # Acessa asset_resources com lock para segurança
                 with self.trader_engine._lock:
                      successful_assets = [k for k, v in self.trader_engine.asset_resources.items() if v and 'error' not in v]

                 if successful_assets:
                      self.is_trader_initialized = True
                      log.info(f"Thread _initialize_trader_engine: LiveTrader inicializado com sucesso para {len(successful_assets)} ativo(s).")
                      # A própria thread do LiveTrader já envia status "Iniciado" e "Pronto"
                 else:
                      self.is_trader_initialized = False # Considera falha se nenhum ativo carregou
                      log.error("Thread _initialize_trader_engine: LiveTrader inicializado, mas nenhum ativo foi carregado com sucesso.")
                      self.queue.put({"type": "status", "asset": "GLOBAL", "message": "Erro Carga Ativos", "color": "red"})

            else:
                 self.is_trader_initialized = False
                 log.error("Thread _initialize_trader_engine: LiveTrader falhou na inicialização (provavelmente erro na conexão MT5).")
                 # A própria thread do LiveTrader já deve ter enviado o erro "Erro MT5"
                 # self.queue.put({"type": "status", "asset": "GLOBAL", "message": "Live Erro MT5", "color": "red"})

        except Exception as e:
            log.critical(f"Falha crítica ao instanciar ou aguardar LiveTrader: {e}", exc_info=True)
            self.is_trader_initialized = False
            # Garante que uma mensagem de erro seja enviada para a GUI
            try:
                self.queue.put({"type": "status", "asset": "GLOBAL", "message": "Live CRÍTICO", "color": "red"})
            except Exception as qe:
                log.error(f"Erro ao enviar status CRÍTICO para a fila: {qe}")
        finally:
            log.info("Thread _initialize_trader_engine: Finalizada.")


    def _initialize_simulation_engine(self):
        """(Thread) Instancia o SimulationEngine."""
        log.info("Thread _initialize_simulation_engine: Iniciando...")
        try:
            self.simulation_engine = SimulationEngine(config_path=self.config_path)
            # Tenta carregar recursos para verificar se está funcional
            # Pega o primeiro ativo da lista geral (mesmo que não habilitado para live)
            first_asset_cfg = next(iter(self.config.get('assets', [])), None)
            if first_asset_cfg and first_asset_cfg.get('ticker'):
                 self.simulation_engine._load_asset_resources(first_asset_cfg['ticker']) # Pré-carrega um
            self.is_simulation_engine_initialized = True
            log.info("Thread _initialize_simulation_engine: SimulationEngine instanciado.")
            self.queue.put({"type": "status_sim", "message": "Simulador Pronto", "color": "blue"})
        except Exception as e:
            log.critical(f"Falha crítica ao instanciar SimulationEngine: {e}", exc_info=True)
            self.is_simulation_engine_initialized = False
            self.queue.put({"type": "status_sim", "message": "Erro Simulador", "color": "red"})
        log.info("Thread _initialize_simulation_engine: Finalizada.")


    def _create_widgets(self):
        """Cria os componentes da interface gráfica."""
        # --- Main Frame ---
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # --- Header Frame (Simulação) ---
        header_frame = ttk.Frame(main_frame, padding=10, style="TFrame")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(header_frame, text="Market Replay (Simulação)", style="Header.TLabel").pack(side=tk.LEFT, padx=(0, 20))

        # Ativo para Simulação (usa todos os assets do config, não só os live)
        all_assets_tickers = [a.get('ticker', f'idx_{i}') for i, a in enumerate(self.config.get('assets', []))]
        ttk.Label(header_frame, text="Ativo:").pack(side=tk.LEFT, padx=5)
        self.sim_asset_var = tk.StringVar(value=all_assets_tickers[0] if all_assets_tickers else "")
        self.sim_asset_combo = ttk.Combobox(header_frame, textvariable=self.sim_asset_var, values=all_assets_tickers, width=10, state="readonly")
        self.sim_asset_combo.pack(side=tk.LEFT, padx=5)

        # Timeframe
        timeframes = ["M1", "M5", "M15", "M30", "H1", "D1"] # Adicione outros se necessário
        ttk.Label(header_frame, text="TF:").pack(side=tk.LEFT, padx=5)
        self.sim_tf_var = tk.StringVar(value="M5")
        self.sim_tf_combo = ttk.Combobox(header_frame, textvariable=self.sim_tf_var, values=timeframes, width=5, state="readonly")
        self.sim_tf_combo.pack(side=tk.LEFT, padx=5)

        # Data/Hora
        default_time_str = (datetime.now(self.local_tz) - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:00") # Pega 15min atrás
        ttk.Label(header_frame, text="Data/Hora (Local):").pack(side=tk.LEFT, padx=5)
        self.sim_datetime_var = tk.StringVar(value=default_time_str)
        self.sim_datetime_entry = ttk.Entry(header_frame, textvariable=self.sim_datetime_var, width=20)
        self.sim_datetime_entry.pack(side=tk.LEFT, padx=5)

        # Botão Simular
        self.sim_button = ttk.Button(header_frame, text="Simular Ponto", command=self._run_simulation)
        self.sim_button.pack(side=tk.LEFT, padx=10)

        # Status da Simulação
        self.sim_status_label = ttk.Label(header_frame, text="Aguardando Simulador...", style="TLabel")
        self.sim_status_label.pack(side=tk.LEFT, padx=10)


        # --- Ativos Frame (Live) ---
        assets_canvas_frame = ttk.Frame(main_frame)
        assets_canvas_frame.grid(row=1, column=0, sticky="nsew")
        assets_canvas_frame.columnconfigure(0, weight=1)
        assets_canvas_frame.rowconfigure(0, weight=1)

        canvas = tk.Canvas(assets_canvas_frame, bg=self.bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(assets_canvas_frame, orient="vertical", command=canvas.yview)

        self.scrollable_frame = ttk.Frame(canvas, style="TFrame")
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=1300) # Define largura inicial
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Footer Frame (Controles Globais) ---
        footer_frame = ttk.Frame(main_frame, padding=10)
        footer_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self.start_button = ttk.Button(footer_frame, text="INICIAR MONITORAMENTO", command=self._start_trader)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(footer_frame, text="PARAR MONITORAMENTO", command=self._stop_trader, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.global_status_label = ttk.Label(footer_frame, text="Aguardando inicialização do LiveTrader...", width=50)
        self.global_status_label.pack(side=tk.LEFT, padx=20, fill=tk.X, expand=True)

        # --- Cria os widgets para cada ativo LIVE no frame rolável ---
        # Usa self.assets (filtrado na inicialização)
        if self.assets:
             self._create_asset_widgets(self.scrollable_frame)
        else:
             # Mostra mensagem se nenhum ativo live estiver configurado
             ttk.Label(self.scrollable_frame, text="Nenhum ativo habilitado para Live Trading.",
                       style="Header.TLabel", foreground="orange").pack(pady=20)


    def _create_asset_widgets(self, parent):
        """Cria um 'card' para cada ativo LIVE monitorado."""
        num_columns = 3
        
        # Usa self.assets (já filtrado para live)
        asset_configs_live = {
             asset_cfg['ticker']: asset_cfg 
             for asset_cfg in self.config.get('assets', []) 
             if asset_cfg.get('ticker') in self.assets
        }

        for i, asset_symbol in enumerate(self.assets):
            row = i // num_columns
            col = i % num_columns

            card = ttk.Frame(parent, padding=10, relief=tk.RIDGE, borderwidth=1, style="TFrame")
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            parent.columnconfigure(col, weight=1) # Faz colunas expandirem

            card.columnconfigure(1, weight=1)

            widgets = {}

            # Linha 1: Título e Status
            widgets["title"] = ttk.Label(card, text=asset_symbol, style="Header.TLabel")
            widgets["title"].grid(row=0, column=0, sticky="w", columnspan=2)
            widgets["status"] = ttk.Label(card, text="Carregando...", anchor=tk.E)
            widgets["status"].grid(row=0, column=2, sticky="e")

            # Linha 2: Timeframe e Posição
            asset_cfg = asset_configs_live.get(asset_symbol, {})
            live_config = asset_cfg.get('live_trading', {})
            tf = live_config.get('timeframe_str', 'N/A')
            widgets["tf"] = ttk.Label(card, text=f"TF: {tf}")
            widgets["tf"].grid(row=1, column=0, sticky="w")
            widgets["position"] = ttk.Label(card, text="POSIÇÃO: ---", style="PositionFlat.TLabel", anchor=tk.E)
            widgets["position"].grid(row=1, column=1, columnspan=2, sticky="e")

            # Linha 3: Preço
            ttk.Label(card, text="Preço:").grid(row=2, column=0, sticky="w", pady=(10, 0))
            widgets["price"] = ttk.Label(card, text="N/A", font=("Segoe UI", 11, "bold"))
            widgets["price"].grid(row=2, column=1, sticky="w", columnspan=2, pady=(10, 0))

            # Linha 4: Sinal IA
            ttk.Label(card, text="Sinal IA:").grid(row=3, column=0, sticky="w")
            widgets["ai_signal"] = ttk.Label(card, text="N/A", style="Hold.TLabel")
            widgets["ai_signal"].grid(row=3, column=1, sticky="w", columnspan=2)

            # Linha 5: Setup
            ttk.Label(card, text="Setup OK?").grid(row=4, column=0, sticky="w")
            widgets["setup_valid"] = ttk.Label(card, text="N/A", style="Hold.TLabel")
            widgets["setup_valid"].grid(row=4, column=1, sticky="w", columnspan=2)

            # Linha 6: Sinal Final
            ttk.Label(card, text="Sinal Final:").grid(row=5, column=0, sticky="w")
            widgets["final_signal"] = ttk.Label(card, text="N/A", style="Hold.TLabel")
            widgets["final_signal"].grid(row=5, column=1, sticky="w", columnspan=2)

            # Linha 7: Última Atualização
            widgets["datetime"] = ttk.Label(card, text="---", font=("Segoe UI", 8))
            widgets["datetime"].grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

            self.asset_widgets[asset_symbol] = widgets

    def _start_trader(self):
        """Inicia o motor de trading ao vivo."""
        if not self.is_trader_initialized:
            messagebox.showwarning("Atenção", "O motor LiveTrader ainda não foi inicializado (ou falhou).")
            return
            
        if not self.assets:
             messagebox.showinfo("Informação", "Nenhum ativo habilitado para Live Trading.")
             return

        # Verifica se a thread já está rodando
        if self.trader_engine and hasattr(self.trader_engine, '_run_thread') and self.trader_engine._run_thread and self.trader_engine._run_thread.is_alive():
             log.warning("Monitoramento já está ativo.")
             return

        log.info("Comando INICIAR recebido.")
        # O start agora apenas inicia a thread _run_monitor_thread
        if self.trader_engine:
            self.trader_engine.start() # Chama o start() do LiveTrader
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            # Status global será atualizado pelo callback do LiveTrader
        else:
             log.error("Tentativa de iniciar trader sem engine instanciado.")

    def _stop_trader(self):
        """Para o motor de trading ao vivo."""
        log.info("Comando PARAR recebido.")
        if self.trader_engine:
            self.trader_engine.stop() # Chama o stop() do LiveTrader
            
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        # Status global será atualizado pelo callback do LiveTrader

    def _run_simulation(self):
        """Executa um ciclo do SimulationEngine."""
        if not self.is_simulation_engine_initialized or not self.simulation_engine:
             messagebox.showerror("Erro", "O Motor de Simulação não está pronto.")
             return

        asset = self.sim_asset_var.get()
        tf = self.sim_tf_var.get()
        datetime_str = self.sim_datetime_var.get()

        if not asset:
             messagebox.showwarning("Atenção", "Selecione um ativo para simular.")
             return

        try:
            dt_local = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            dt_local_aware = self.local_tz.localize(dt_local)
        except Exception as e:
            messagebox.showerror("Erro de Formato", f"Data/Hora inválida: {e}\nUse YYYY-MM-DD HH:MM:SS")
            return

        log.info(f"Executando simulação para {asset} @ {tf} em {dt_local_aware}")
        self.sim_status_label.config(text="Simulando...", foreground=self.hold_color)
        self.sim_button.config(state=tk.DISABLED) # Desabilita botão durante simulação

        # Executa a simulação em uma thread separada para não travar a GUI
        Thread(target=self._execute_simulation_thread, args=(asset, tf, dt_local_aware), daemon=True).start()

    def _execute_simulation_thread(self, asset, tf, dt_local_aware):
        """(Thread) Executa a simulação e envia resultado para a fila."""
        try:
            result = self.simulation_engine.run_simulation_cycle(asset, tf, dt_local_aware)
            self.queue.put({"type": "sim_result", "data": result})
        except Exception as e:
            log.error(f"Erro ao executar simulação na thread: {e}", exc_info=True)
            self.queue.put({"type": "sim_result", "data": {"error": f"Erro interno: {e}"}})


    def _show_simulation_result(self, result):
        """Mostra o resultado da simulação em uma janela popup."""
        # Reativa o botão de simulação
        self.sim_button.config(state=tk.NORMAL)

        if not result or result.get("error"):
            error_msg = result.get("error", "Erro desconhecido na simulação.")
            messagebox.showerror("Erro na Simulação", error_msg)
            self.sim_status_label.config(text="Falha na Simulação", foreground=self.sell_color)
            return

        self.sim_status_label.config(text="Simulação Concluída", foreground=self.buy_color)

        win = tk.Toplevel(self)
        win.title(f"Resultado Simulação: {result.get('asset')} @ {result.get('datetime')}")
        win.configure(bg=self.bg_color)
        win.geometry("600x600") # Tamanho da janela

        # Frame principal com scrollbar
        main_sim_frame = ttk.Frame(win)
        main_sim_frame.pack(fill=tk.BOTH, expand=True)
        sim_canvas = tk.Canvas(main_sim_frame, bg=self.bg_color, highlightthickness=0)
        sim_scrollbar = ttk.Scrollbar(main_sim_frame, orient="vertical", command=sim_canvas.yview)
        sim_scrollable_frame = ttk.Frame(sim_canvas, style="TFrame", padding=15)

        sim_scrollable_frame.bind("<Configure>", lambda e: sim_canvas.configure(scrollregion=sim_canvas.bbox("all")))
        sim_canvas.create_window((0, 0), window=sim_scrollable_frame, anchor="nw")
        sim_canvas.configure(yscrollcommand=sim_scrollbar.set)

        sim_canvas.pack(side="left", fill="both", expand=True)
        sim_scrollbar.pack(side="right", fill="y")

        # --- Conteúdo da Janela ---
        row = 0
        bold_font = tkFont.Font(font=("Segoe UI", 10, "bold"))

        # Exibe os resultados principais
        main_results = {k: v for k, v in result.items() if k not in ["indicators", "setup_details"]}
        for key, value in main_results.items():
            ttk.Label(sim_scrollable_frame, text=f"{key.replace('_', ' ').title()}:", font=bold_font).grid(row=row, column=0, sticky="ne", padx=5, pady=3)
            # Formata floats com precisão definida
            display_value = f"{value:.{self.asset_resources.get(result.get('asset'), {}).get('price_precision', 2)}f}" if isinstance(value, float) else str(value)
            
            lbl = ttk.Label(sim_scrollable_frame, text=display_value, wraplength=350, anchor="w")
            lbl.grid(row=row, column=1, sticky="nw", padx=5, pady=3)
            
            # Colore sinais
            if key in ["ai_signal", "final_signal"]:
                 self._update_label_color(lbl, value)
            elif key == "setup_is_valid":
                 lbl.config(foreground=self.buy_color if value else self.sell_color)

            row += 1

        # Exibe Detalhes do Setup
        ttk.Label(sim_scrollable_frame, text="Detalhes Setup:", font=bold_font).grid(row=row, column=0, sticky="ne", padx=5, pady=5)
        setup_details = result.get("setup_details", {})
        setup_details_str = "\n".join([f"- {k}: {v}" for k, v in setup_details.items()]) if setup_details else "N/A"
        ttk.Label(sim_scrollable_frame, text=setup_details_str, wraplength=350, anchor="w").grid(row=row, column=1, sticky="nw", padx=5, pady=5)
        row += 1

        # Exibe Indicadores
        ttk.Label(sim_scrollable_frame, text="Indicadores:", font=bold_font).grid(row=row, column=0, sticky="ne", padx=5, pady=5)
        indicators = result.get("indicators", {})
        indicators_str = "\n".join([f"- {k}: {v}" for k, v in indicators.items()]) if indicators else "N/A"
        ttk.Label(sim_scrollable_frame, text=indicators_str, wraplength=350, anchor="w").grid(row=row, column=1, sticky="nw", padx=5, pady=5)
        row += 1

        # Ajusta largura da coluna de labels
        sim_scrollable_frame.columnconfigure(0, minsize=120)
        sim_scrollable_frame.columnconfigure(1, weight=1)


    def _process_queue(self):
        """Processa eventos da fila."""
        try:
            while True: # Processa todas as mensagens na fila
                msg = self.queue.get_nowait()

                if msg["type"] == "update":
                    self._update_asset_card(msg.get("asset"), msg)
                elif msg["type"] == "position":
                    self._update_asset_position(msg.get("asset"), msg)
                elif msg["type"] == "status":
                    self._update_status_label(msg.get("asset"), msg.get("message", "??"), msg.get("color", "grey"))
                elif msg["type"] == "status_sim":
                    self.sim_status_label.config(text=msg.get("message", "??"), foreground=self.style.lookup(f"{msg.get('color', 'grey').title()}.TLabel", "foreground", default=self.fg_color))
                elif msg["type"] == "sim_result": # Resultado da simulação chegou
                     self._show_simulation_result(msg.get("data"))

        except Empty:
            pass # Fila vazia
        except Exception as e:
            log.warning(f"Erro ao processar fila da GUI: {e}", exc_info=True)
        finally:
            self.after(100, self._process_queue) # Reagenda


    def _update_asset_card(self, asset_symbol, data):
        """Atualiza um card de ativo."""
        if not asset_symbol or asset_symbol not in self.asset_widgets: return
        widgets = self.asset_widgets[asset_symbol]

        price = data.get('price', 'N/A')
        precision = self.asset_resources.get(asset_symbol, {}).get('price_precision', 2)
        price_str = f"{price:.{precision}f}" if isinstance(price, (float, int)) else str(price)

        widgets["price"].config(text=price_str)
        widgets["datetime"].config(text=f"Atualizado: {data.get('datetime', '---')}")

        ai_signal = data.get("ai_signal", "N/A")
        widgets["ai_signal"].config(text=ai_signal)
        self._update_label_color(widgets["ai_signal"], ai_signal)

        setup_valid = data.get("setup_valid", None)
        widgets["setup_valid"].config(text=("SIM" if setup_valid else "NÃO") if isinstance(setup_valid, bool) else "N/A")
        widgets["setup_valid"].config(style="Buy.TLabel" if setup_valid else "Sell.TLabel" if setup_valid is False else "Hold.TLabel")

        final_signal = data.get("final_signal", "N/A")
        widgets["final_signal"].config(text=final_signal)
        self._update_label_color(widgets["final_signal"], final_signal)


    def _update_label_color(self, label_widget, text_value):
        """Muda o estilo do label baseado no texto."""
        style_map = {"COMPRA": "Buy.TLabel", "VENDA": "Sell.TLabel"}
        label_widget.config(style=style_map.get(text_value, "Hold.TLabel"))


    def _update_asset_position(self, asset_symbol, data):
        """Atualiza o display de posição."""
        if not asset_symbol or asset_symbol not in self.asset_widgets: return
        widgets = self.asset_widgets[asset_symbol]
        status = data.get("status", "---")
        price = data.get("price", "N/A")
        precision = self.asset_resources.get(asset_symbol, {}).get('price_precision', 2)
        price_str = f"{price:.{precision}f}" if isinstance(price, (float, int)) else str(price)

        if status == "Comprado":
            widgets["position"].config(text=f"COMPRADO @ {price_str}", style="PositionBuy.TLabel")
        elif status == "Vendido":
            widgets["position"].config(text=f"VENDIDO @ {price_str}", style="PositionSell.TLabel")
        else: # Fechado, Flat, ---
            widgets["position"].config(text="POSIÇÃO: ---", style="PositionFlat.TLabel")


    def _update_status_label(self, asset_symbol, message, color_name):
        """Atualiza labels de status."""
        color_map = { "red": self.sell_color, "green": self.buy_color, "blue": self.status_ok_color,
                      "orange": self.hold_color, "grey": self.fg_color }
        color = color_map.get(color_name, self.fg_color)

        if asset_symbol == "GLOBAL":
            self.global_status_label.config(text=message or "??", foreground=color)
        elif asset_symbol in self.asset_widgets:
            self.asset_widgets[asset_symbol]["status"].config(text=message or "??", foreground=color)


    def _on_closing(self):
        """Chamado quando a janela é fechada."""
        log.info("Fechando dashboard...")
        if messagebox.askokcancel("Sair", "Deseja fechar o dashboard? O monitoramento será interrompido."):
            
            # Sinaliza parada do LiveTrader (se existir e estiver rodando)
            if self.trader_engine and hasattr(self.trader_engine, '_run_thread') and self.trader_engine._run_thread and self.trader_engine._run_thread.is_alive():
                log.info("Solicitando parada do LiveTrader...")
                self.trader_engine.stop()
            # Se a thread de init ainda estiver rodando, sinaliza parada também
            elif self.trader_engine and hasattr(self.trader_engine, '_init_thread') and self.trader_engine._init_thread and self.trader_engine._init_thread.is_alive():
                 log.info("Sinalizando parada para thread de inicialização do LiveTrader...")
                 if hasattr(self.trader_engine, '_stop_event'): self.trader_engine._stop_event.set()

            # Fecha engine de simulação
            if self.simulation_engine and hasattr(self.simulation_engine, 'close'):
                 log.info("Fechando SimulationEngine...")
                 self.simulation_engine.close()

            log.info("Encerrando aplicação GUI.")
            self.destroy()

if __name__ == "__main__":
    app = LiveTraderDashboard()
    app.mainloop()