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
        # Define o fuso horário local (para B3)
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
        self.assets = [
            asset['ticker'] for asset in self.config.get('assets', []) 
            if asset.get('enabled', True) and asset.get('live_trading', {}).get('enabled', False)
        ]
        self.asset_widgets = {} # Dicionário para guardar os widgets de cada ativo
        self.queue = Queue() # Fila para comunicação das threads com a GUI
        
        # --- Motores ---
        self.trader_engine = None # Será o LiveTrader (para dados ao vivo e execução)
        self.simulation_engine = None # Será o SimulationEngine (para market replay)
        
        self.is_trader_initialized = False
        self.is_simulation_engine_initialized = False

        # --- Inicialização da GUI ---
        self._setup_styles()
        self._create_widgets()
        
        # --- Inicialização dos Motores ---
        # Inicia o LiveTrader (para dados ao vivo) em uma thread
        log.info("Iniciando thread de inicialização do LiveTrader...")
        Thread(target=self._initialize_trader_engine, daemon=True).start()
        
        # Inicia o SimulationEngine (para market replay) em outra thread
        log.info("Iniciando thread de inicialização do SimulationEngine...")
        Thread(target=self._initialize_simulation_engine, daemon=True).start()

        # Inicia o processador da fila de eventos
        self.after(100, self._process_queue)
        
        # Protocolo de fechamento
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_styles(self):
        """Define os estilos da Ttk."""
        self.style = ttk.Style(self)
        self.style.theme_use('clam') # Tema moderno
        
        # Cores
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
        
        # Estilos Ttk
        self.style.configure("TFrame", background=self.frame_bg)
        self.style.configure("TLabel", background=self.frame_bg, foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        self.style.configure("TButton", background="#555555", foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.map("TButton", background=[('active', '#666666')])
        self.style.configure("TEntry", fieldbackground=self.entry_bg, foreground=self.fg_color, insertbackground=self.fg_color)
        self.style.configure("TCombobox", fieldbackground=self.entry_bg, foreground=self.fg_color, selectbackground=self.entry_bg)
        
        # Estilos de Labels coloridos
        self.style.configure("Buy.TLabel", foreground=self.buy_color, font=("Segoe UI", 11, "bold"))
        self.style.configure("Sell.TLabel", foreground=self.sell_color, font=("Segoe UI", 11, "bold"))
        self.style.configure("Hold.TLabel", foreground=self.hold_color, font=("Segoe UI", 11, "bold"))
        self.style.configure("PositionBuy.TLabel", foreground="white", background=self.buy_color, font=("Segoe UI", 10, "bold"))
        self.style.configure("PositionSell.TLabel", foreground="white", background=self.sell_color, font=("Segoe UI", 10, "bold"))
        self.style.configure("PositionFlat.TLabel", foreground=self.fg_color, background=self.frame_bg, font=("Segoe UI", 10))

    def _initialize_trader_engine(self):
        """(Thread) Instancia e inicializa o LiveTrader."""
        log.info("Thread _initialize_trader_engine: Iniciando...")
        try:
            # 1. Instancia o LiveTrader (isso inicia a _init_thread interna dele)
            self.trader_engine = LiveTrader(config_path=self.config_path, callback=self.queue.put)
            
            # 2. **CORREÇÃO:** Aguarda a thread de inicialização interna do LiveTrader terminar
            if hasattr(self.trader_engine, '_init_thread') and self.trader_engine._init_thread is not None:
                self.trader_engine._init_thread.join() # Espera a thread terminar
            
            # 3. Verifica se a inicialização foi bem-sucedida (ex: se o provider está conectado)
            if self.trader_engine.mt5_provider and self.trader_engine.mt5_provider.is_connected():
                self.is_trader_initialized = True
                log.info("Thread _initialize_trader_engine: LiveTrader inicializado com sucesso.")
                # Envia mensagem para a GUI (opcional, já que o LiveTrader envia seu próprio status)
                # self.queue.put({"type": "status", "asset": "GLOBAL", "message": "Live OK", "color": "green"})
            else:
                 self.is_trader_initialized = False
                 log.error("Thread _initialize_trader_engine: LiveTrader falhou na inicialização (MT5 não conectado).")
                 self.queue.put({"type": "status", "asset": "GLOBAL", "message": "Live Erro", "color": "red"})

        except Exception as e:
            log.critical(f"Falha crítica ao instanciar LiveTrader: {e}", exc_info=True)
            self.is_trader_initialized = False
            self.queue.put({"type": "status", "asset": "GLOBAL", "message": "Live CRÍTICO", "color": "red"})
        log.info("Thread _initialize_trader_engine: Finalizada.")


    def _initialize_simulation_engine(self):
        """(Thread) Instancia o SimulationEngine."""
        log.info("Thread _initialize_simulation_engine: Iniciando...")
        try:
            self.simulation_engine = SimulationEngine(config_path=self.config_path)
            self.is_simulation_engine_initialized = True
            log.info("Thread _initialize_simulation_engine: SimulationEngine inicializado com sucesso.")
            # Atualiza status na GUI
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
        
        main_frame.rowconfigure(1, weight=1) # Permite que a área de ativos expanda
        main_frame.columnconfigure(0, weight=1)

        # --- Header Frame (Simulação) ---
        header_frame = ttk.Frame(main_frame, padding=10, style="TFrame")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        ttk.Label(header_frame, text="Market Replay (Simulação)", style="Header.TLabel").pack(side=tk.LEFT, padx=(0, 20))
        
        # Ativo
        ttk.Label(header_frame, text="Ativo:").pack(side=tk.LEFT, padx=5)
        self.sim_asset_var = tk.StringVar(value=self.assets[0] if self.assets else "")
        self.sim_asset_combo = ttk.Combobox(header_frame, textvariable=self.sim_asset_var, values=self.assets, width=8)
        self.sim_asset_combo.pack(side=tk.LEFT, padx=5)
        
        # Timeframe
        timeframes = ["M1", "M5", "M15", "M30", "H1", "D1"]
        ttk.Label(header_frame, text="TF:").pack(side=tk.LEFT, padx=5)
        self.sim_tf_var = tk.StringVar(value="M5")
        self.sim_tf_combo = ttk.Combobox(header_frame, textvariable=self.sim_tf_var, values=timeframes, width=5)
        self.sim_tf_combo.pack(side=tk.LEFT, padx=5)

        # Data/Hora
        default_time = (datetime.now(self.local_tz) - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        ttk.Label(header_frame, text="Data/Hora (Local):").pack(side=tk.LEFT, padx=5)
        self.sim_datetime_var = tk.StringVar(value=default_time.strftime("%Y-%m-%d %H:%M:%S"))
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

        # Canvas e Scrollbar
        canvas = tk.Canvas(assets_canvas_frame, bg=self.bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(assets_canvas_frame, orient="vertical", command=canvas.yview)
        
        # Frame rolável dentro do Canvas
        self.scrollable_frame = ttk.Frame(canvas, style="TFrame")
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
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

        # --- Cria os widgets para cada ativo no frame rolável ---
        self._create_asset_widgets(self.scrollable_frame)

    def _create_asset_widgets(self, parent):
        """Cria um 'card' para cada ativo monitorado."""
        
        # Define as colunas do "grid" de cards
        num_columns = 3 # Quantos cards por linha
        
        for i, asset_symbol in enumerate(self.assets):
            row = i // num_columns
            col = i % num_columns
            
            card = ttk.Frame(parent, padding=10, relief=tk.RIDGE, borderwidth=1, style="TFrame")
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            # Configuração do grid interno do card (3 colunas)
            card.columnconfigure(1, weight=1) # Coluna do meio expande

            widgets = {}
            
            # --- Linha 1: Título e Status ---
            widgets["title"] = ttk.Label(card, text=asset_symbol, style="Header.TLabel")
            widgets["title"].grid(row=0, column=0, sticky="w", columnspan=2)
            
            widgets["status"] = ttk.Label(card, text="Aguardando...", anchor=tk.E)
            widgets["status"].grid(row=0, column=2, sticky="e")

            # --- Linha 2: Timeframe e Posição ---
            live_config = self.config['assets'][i].get('live_trading', {}) # CUIDADO: Assumindo mesma ordem
            tf = live_config.get('timeframe_str', 'N/A')
            widgets["tf"] = ttk.Label(card, text=f"TF: {tf}")
            widgets["tf"].grid(row=1, column=0, sticky="w")
            
            widgets["position"] = ttk.Label(card, text="POSIÇÃO: ---", style="PositionFlat.TLabel", anchor=tk.E)
            widgets["position"].grid(row=1, column=1, columnspan=2, sticky="e")

            # --- Linha 3: Preço ---
            ttk.Label(card, text="Preço:").grid(row=2, column=0, sticky="w", pady=(10, 0))
            widgets["price"] = ttk.Label(card, text="N/A", font=("Segoe UI", 11, "bold"))
            widgets["price"].grid(row=2, column=1, sticky="w", columnspan=2, pady=(10, 0))

            # --- Linha 4: Sinal IA ---
            ttk.Label(card, text="Sinal IA:").grid(row=3, column=0, sticky="w")
            widgets["ai_signal"] = ttk.Label(card, text="N/A", style="Hold.TLabel")
            widgets["ai_signal"].grid(row=3, column=1, sticky="w", columnspan=2)

            # --- Linha 5: Setup ---
            ttk.Label(card, text="Setup OK?").grid(row=4, column=0, sticky="w")
            widgets["setup_valid"] = ttk.Label(card, text="N/A", style="Hold.TLabel")
            widgets["setup_valid"].grid(row=4, column=1, sticky="w", columnspan=2)

            # --- Linha 6: Sinal Final ---
            ttk.Label(card, text="Sinal Final:").grid(row=5, column=0, sticky="w")
            widgets["final_signal"] = ttk.Label(card, text="N/A", style="Hold.TLabel")
            widgets["final_signal"].grid(row=5, column=1, sticky="w", columnspan=2)
            
            # --- Linha 7: Última Atualização ---
            widgets["datetime"] = ttk.Label(card, text="---", font=("Segoe UI", 8))
            widgets["datetime"].grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

            self.asset_widgets[asset_symbol] = widgets

    def _start_trader(self):
        """Inicia o motor de trading ao vivo."""
        if not self.is_trader_initialized:
            messagebox.showwarning("Atenção", "O motor LiveTrader ainda não foi inicializado (ou falhou). Verifique a conexão MT5.")
            return
            
        log.info("Comando INICIAR recebido.")
        self.trader_engine.start() # Chama o start() do LiveTrader
        
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.global_status_label.config(text="Monitoramento ATIVO.", foreground=self.buy_color)

    def _stop_trader(self):
        """Para o motor de trading ao vivo."""
        log.info("Comando PARAR recebido.")
        if self.trader_engine:
            self.trader_engine.stop() # Chama o stop() do LiveTrader
            
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.global_status_label.config(text="Monitoramento PARADO.", foreground=self.hold_color)

    def _run_simulation(self):
        """Executa um ciclo do SimulationEngine."""
        if not self.is_simulation_engine_initialized:
             messagebox.showerror("Erro", "O Motor de Simulação não está pronto.")
             return
             
        asset = self.sim_asset_var.get()
        tf = self.sim_tf_var.get()
        datetime_str = self.sim_datetime_var.get()
        
        try:
            # Converte a string de data/hora para um objeto datetime LOCAL
            dt_local = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            # Associa o fuso horário local
            dt_local_aware = self.local_tz.localize(dt_local)
        except Exception as e:
            messagebox.showerror("Erro de Formato", f"Data/Hora inválida: {e}\nUse o formato YYYY-MM-DD HH:MM:SS")
            return
            
        log.info(f"Executando simulação para {asset} @ {tf} em {dt_local_aware}")
        
        try:
            # O SimulationEngine lida com a conversão UTC interna
            result = self.simulation_engine.run_simulation_cycle(asset, tf, dt_local_aware)
            
            # Exibe o resultado em uma nova janela (Toplevel)
            self._show_simulation_result(result)
            
        except Exception as e:
            log.error(f"Erro ao executar simulação: {e}", exc_info=True)
            messagebox.showerror("Erro na Simulação", f"Falha ao executar ciclo:\n{e}")

    def _show_simulation_result(self, result):
        """Mostra o resultado da simulação em uma janela popup."""
        if result.get("error"):
            messagebox.showerror("Erro na Simulação", result["error"])
            return

        win = tk.Toplevel(self)
        win.title(f"Resultado Simulação: {result.get('asset')} @ {result.get('datetime')}")
        win.configure(bg=self.bg_color)
        
        frame = ttk.Frame(win, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        row = 0
        # Exibe os resultados principais
        for key, value in result.items():
            if key == "indicators" or key == "setup_details": continue # Pula complexos
            
            ttk.Label(frame, text=f"{key.replace('_', ' ').title()}:", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="e", padx=5, pady=2)
            lbl = ttk.Label(frame, text=str(value), wraplength=400)
            lbl.grid(row=row, column=1, sticky="w", padx=5, pady=2)
            
            if key == "final_signal":
                 self._update_label_color(lbl, value) # Colore o sinal final
            
            row += 1
            
        # Exibe Detalhes do Setup
        ttk.Label(frame, text="Detalhes Setup:", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        setup_details_str = "\n".join([f" - {k}: {v}" for k, v in result.get("setup_details", {}).items()])
        if not setup_details_str: setup_details_str = "N/A"
        ttk.Label(frame, text=setup_details_str, wraplength=400).grid(row=row, column=1, sticky="w", padx=5, pady=5)
        row += 1

        # Exibe Indicadores
        ttk.Label(frame, text="Indicadores:", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="ne", padx=5, pady=5)
        indicators_str = "\n".join([f" - {k}: {v}" for k, v in result.get("indicators", {}).items()])
        if not indicators_str: indicators_str = "N/A"
        ttk.Label(frame, text=indicators_str, wraplength=400).grid(row=row, column=1, sticky="w", padx=5, pady=5)


    def _process_queue(self):
        """Processa eventos da fila (vindas das threads)."""
        try:
            while True:
                msg = self.queue.get_nowait()
                
                if msg["type"] == "update":
                    self._update_asset_card(msg["asset"], msg)
                elif msg["type"] == "position":
                    self._update_asset_position(msg["asset"], msg)
                elif msg["type"] == "status":
                    self._update_status_label(msg["asset"], msg["message"], msg["color"])
                elif msg["type"] == "status_sim":
                    self.sim_status_label.config(text=msg["message"], foreground=self.style.lookup(f"{msg['color'].title()}.TLabel", "foreground", default=self.fg_color))


        except Empty:
            pass # Fila vazia, normal
        except Exception as e:
            log.warning(f"Erro ao processar fila da GUI: {e}", exc_info=True)
        finally:
            # Reagenda a verificação
            self.after(100, self._process_queue)

    def _update_asset_card(self, asset_symbol, data):
        """Atualiza um card de ativo com novos dados."""
        if asset_symbol not in self.asset_widgets:
            return
            
        widgets = self.asset_widgets[asset_symbol]
        
        widgets["price"].config(text=f"{data.get('price', 'N/A')}")
        widgets["datetime"].config(text=f"Atualizado: {data.get('datetime', '---')}")
        
        # Sinal IA
        ai_signal = data.get("ai_signal", "N/A")
        widgets["ai_signal"].config(text=ai_signal)
        self._update_label_color(widgets["ai_signal"], ai_signal)
        
        # Setup Válido
        setup_valid = data.get("setup_valid", None)
        if setup_valid is True:
            widgets["setup_valid"].config(text="SIM", style="Buy.TLabel") # Verde
        elif setup_valid is False:
            widgets["setup_valid"].config(text="NÃO", style="Sell.TLabel") # Vermelho
        else:
            widgets["setup_valid"].config(text="N/A", style="Hold.TLabel") # Laranja

        # Sinal Final
        final_signal = data.get("final_signal", "N/A")
        widgets["final_signal"].config(text=final_signal)
        self._update_label_color(widgets["final_signal"], final_signal)
        
        # (Opcional) Tooltip para detalhes do setup
        setup_details = data.get("setup_details", {})
        if setup_details:
             tooltip_text = "\n".join([f"{k}: {v}" for k, v in setup_details.items()])
             # (Aqui entraria a lógica para adicionar/atualizar um tooltip)
             pass


    def _update_label_color(self, label_widget, text_value):
        """Muda o estilo do label baseado no texto (COMPRA, VENDA, HOLD)."""
        if text_value == "COMPRA":
            label_widget.config(style="Buy.TLabel")
        elif text_value == "VENDA":
            label_widget.config(style="Sell.TLabel")
        else: # HOLD ou N/A
            label_widget.config(style="Hold.TLabel")

    def _update_asset_position(self, asset_symbol, data):
        """Atualiza o display de posição de um ativo."""
        if asset_symbol not in self.asset_widgets:
            return
            
        widgets = self.asset_widgets[asset_symbol]
        status = data.get("status", "---")
        
        if status == "Comprado":
            widgets["position"].config(text=f"COMPRADO @ {data.get('price', 'N/A')}", style="PositionBuy.TLabel")
        elif status == "Vendido":
            widgets["position"].config(text=f"VENDIDO @ {data.get('price', 'N/A')}", style="PositionSell.TLabel")
        else: # Fechado, Flat, ---
            widgets["position"].config(text="POSIÇÃO: ---", style="PositionFlat.TLabel")

    def _update_status_label(self, asset_symbol, message, color_name):
        """Atualiza os labels de status (global ou do card)."""
        
        # Mapeia nome da cor para cor real
        color_map = {
            "red": self.sell_color, "green": self.buy_color,
            "blue": self.status_ok_color, "orange": self.hold_color,
            "grey": self.fg_color
        }
        color = color_map.get(color_name, self.fg_color)
        
        if asset_symbol == "GLOBAL":
            self.global_status_label.config(text=message, foreground=color)
        elif asset_symbol in self.asset_widgets:
            self.asset_widgets[asset_symbol]["status"].config(text=message, foreground=color)

    def _on_closing(self):
        """Chamado quando a janela é fechada."""
        log.info("Fechando dashboard...")
        if messagebox.askokcancel("Sair", "Deseja fechar o dashboard? O monitoramento (se ativo) será interrompido."):
            
            # Para a thread do LiveTrader
            if self.trader_engine:
                log.info("Solicitando parada do LiveTrader...")
                self.trader_engine.stop()
            
            # Para a thread do SimulationEngine (se houver o que parar)
            if self.simulation_engine:
                 if hasattr(self.simulation_engine, 'close'):
                      log.info("Fechando SimulationEngine...")
                      self.simulation_engine.close()

            log.info("Encerrando aplicação.")
            self.destroy()

if __name__ == "__main__":
    app = LiveTraderDashboard()
    app.mainloop()