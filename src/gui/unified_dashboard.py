# src/gui/unified_dashboard.py

import sys
import yaml
import logging
from pathlib import Path
from datetime import datetime, timedelta, time
import pytz # Para lidar com timezones no futuro
import tkinter as tk
from tkinter import ttk, messagebox, font as tkFont
from collections import deque # Para guardar os últimos resultados

# Adiciona a raiz do projeto ao path para importações futuras
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# --- Configuração do Logging (Básico por enquanto) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s')
logger = logging.getLogger(__name__)

class UnifiedDashboard(tk.Tk):
    """
    Nova Interface Gráfica Unificada para Simulação e Live Trading.
    Etapa 1: Layout e Controles Visuais.
    """
    def __init__(self, config_path="configs/main.yaml"):
        super().__init__()
        self.title("WTNPS Trade - Unified Dashboard")
        # Ajusta o tamanho inicial se necessário
        self.geometry("1200x750")

        # --- Carregamento de Config ---
        self.config_path = config_path
        self.config = self._load_config()
        if self.config is None:
             self.destroy(); return # Fecha se o config falhar

        # --- Fuso Horário ---
        try:
            tz_str = self.config.get('global_settings', {}).get('local_timezone', 'America/Sao_Paulo')
            self.local_tz = pytz.timezone(tz_str)
        except pytz.UnknownTimeZoneError:
            logger.warning(f"Timezone '{tz_str}' não encontrado, usando UTC.")
            self.local_tz = pytz.utc

        # --- Estado da Interface ---
        self.assets_config_list = self.config.get('assets', [])
        self.all_asset_tickers = [cfg.get('ticker') for cfg in self.assets_config_list if cfg.get('ticker')]
        self.live_asset_tickers = [cfg.get('ticker') for cfg in self.assets_config_list if cfg.get('ticker') and cfg.get('live_trading', {}).get('enabled', False)]

        self.market_data_auto_refresh = tk.BooleanVar(value=True) # Controla auto refresh
        self.auto_refresh_job_id = None # ID para cancelar o job do 'after'
        self.refresh_interval_ms = 60 * 1000 # 1 minuto

        # Guarda os 2 últimos resultados (simulação ou live)
        self.last_results = deque(maxlen=2)
        # Lista para guardar TODOS os resultados para salvar em CSV
        self.all_results_log = []

        # --- Inicialização da GUI ---
        self._setup_styles()
        self._create_widgets()
        self._update_refresh_status_label() # Atualiza label inicial do refresh

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _load_config(self):
        """Carrega o arquivo de configuração YAML."""
        logger.info(f"Carregando config: {self.config_path}")
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Config '{self.config_path}' não encontrado.")
            messagebox.showerror("Erro", f"Arquivo '{self.config_path}' não encontrado.")
            return None
        except yaml.YAMLError as e:
            logger.error(f"Erro ao ler YAML '{self.config_path}': {e}")
            messagebox.showerror("Erro", f"Erro ao ler '{self.config_path}':\n{e}")
            return None

    def _setup_styles(self):
        """Define estilos Ttk."""
        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        # Cores (similar ao dashboard anterior)
        self.bg_color = "#2E2E2E"; self.fg_color = "#E0E0E0"
        self.frame_bg = "#3C3C3C"; self.entry_bg = "#555555"
        self.buy_color = "green"; self.sell_color = "red"; self.hold_color = "orange"
        self.status_ok_color = "lightblue"; self.status_err_color = "red"; self.status_warn_color = "yellow"

        self.configure(bg=self.bg_color)

        # Estilos Ttk
        self.style.configure(".", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 9))
        self.style.configure("TFrame", background=self.frame_bg)
        self.style.configure("TLabel", background=self.frame_bg, foreground=self.fg_color)
        self.style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"), padding=(0, 5, 0, 5))
        self.style.configure("CardTitle.TLabel", font=("Segoe UI", 10, "bold"))
        self.style.configure("TButton", background="#555555", foreground=self.fg_color, padding=5)
        self.style.map("TButton", background=[('active', '#666666')])
        self.style.configure("TEntry", fieldbackground=self.entry_bg, foreground=self.fg_color, insertbackground=self.fg_color)
        self.style.configure("TCombobox", fieldbackground=self.entry_bg, foreground=self.fg_color, selectbackground=self.entry_bg, arrowcolor=self.fg_color)
        self.style.map('TCombobox', fieldbackground=[('readonly', self.entry_bg)], foreground=[('readonly', self.fg_color)])
        self.style.configure("Treeview", background=self.entry_bg, fieldbackground=self.entry_bg, foreground=self.fg_color)
        self.style.configure("Treeview.Heading", background="#444444", foreground=self.fg_color, font=("Segoe UI", 9, "bold"))
        self.style.map("Treeview.Heading", background=[('active', '#555555')])
        self.style.configure("TCheckbutton", background=self.frame_bg, foreground=self.fg_color)
        self.style.map("TCheckbutton", indicatorcolor=[('selected', self.buy_color)], background=[('active', self.frame_bg)])

        # Estilos específicos para sinais e status
        self.style.configure("Buy.TLabel", foreground=self.buy_color, background=self.frame_bg, font=("Segoe UI", 9, "bold"))
        self.style.configure("Sell.TLabel", foreground=self.sell_color, background=self.frame_bg, font=("Segoe UI", 9, "bold"))
        self.style.configure("Hold.TLabel", foreground=self.hold_color, background=self.frame_bg, font=("Segoe UI", 9))
        self.style.configure("Error.TLabel", foreground=self.status_err_color, background=self.frame_bg, font=("Segoe UI", 9, "bold"))
        self.style.configure("Status.OK.TLabel", foreground=self.status_ok_color, background=self.bg_color)
        self.style.configure("Status.Warn.TLabel", foreground=self.status_warn_color, background=self.bg_color)
        self.style.configure("Status.Error.TLabel", foreground=self.status_err_color, background=self.bg_color)
        self.style.configure("Status.Off.TLabel", foreground="grey", background=self.bg_color)

    def _create_widgets(self):
        """Cria os componentes visuais da interface."""

        # --- Frame Principal ---
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1) # Coluna dos controles
        main_frame.columnconfigure(1, weight=3) # Coluna do monitor e resultados
        main_frame.rowconfigure(1, weight=1) # Linha do monitor expande
        main_frame.rowconfigure(2, weight=1) # Linha dos resultados expande

        # --- Header ---
        header = ttk.Frame(main_frame, style="TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(header, text="WTNPS Unified Dashboard", style="Header.TLabel").pack(side=tk.LEFT, padx=5)
        self.global_status_label = ttk.Label(header, text="Inicializando...", anchor=tk.E, style="Status.Warn.TLabel")
        self.global_status_label.pack(side=tk.RIGHT, padx=5)

        # --- Coluna Esquerda: Controles ---
        controls_frame = ttk.Frame(main_frame, padding=10)
        controls_frame.grid(row=1, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        controls_frame.rowconfigure(0, weight=0) # Simulação
        controls_frame.rowconfigure(1, weight=0) # Live
        controls_frame.rowconfigure(2, weight=1) # Espaço
        controls_frame.columnconfigure(0, weight=1)

        self._create_simulation_controls(controls_frame)
        self._create_live_controls(controls_frame)

        # --- Coluna Direita: Monitor e Resultados ---
        monitor_results_frame = ttk.Frame(main_frame)
        monitor_results_frame.grid(row=1, column=1, rowspan=2, sticky="nsew")
        monitor_results_frame.rowconfigure(0, weight=1) # Monitor
        monitor_results_frame.rowconfigure(1, weight=0) # Resultados
        monitor_results_frame.columnconfigure(0, weight=1)

        self._create_market_monitor(monitor_results_frame)
        self._create_results_display(monitor_results_frame)

    def _create_simulation_controls(self, parent):
        """Cria a seção de controles para o Market Replay."""
        frame = ttk.LabelFrame(parent, text=" Market Replay (Simulação) ", padding=10)
        frame.grid(row=0, column=0, sticky="new", pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        # Labels e Entradas
        ttk.Label(frame, text="Ativo:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.sim_asset_var = tk.StringVar()
        self.sim_asset_combo = ttk.Combobox(frame, textvariable=self.sim_asset_var, values=self.all_asset_tickers, width=12, state="readonly")
        if self.all_asset_tickers: self.sim_asset_combo.current(0)
        self.sim_asset_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=3)

        ttk.Label(frame, text="Timeframe:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        timeframes = ["M1", "M5", "M15", "M30", "H1", "D1"] # Ajuste conforme necessário
        self.sim_tf_var = tk.StringVar(value="M5")
        self.sim_tf_combo = ttk.Combobox(frame, textvariable=self.sim_tf_var, values=timeframes, width=8, state="readonly")
        self.sim_tf_combo.grid(row=1, column=1, sticky="w", padx=5, pady=3)

        ttk.Label(frame, text="Data/Hora (Local):").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        now_local_str = datetime.now(self.local_tz).strftime("%Y-%m-%d %H:%M:00")
        self.sim_datetime_var = tk.StringVar(value=now_local_str)
        self.sim_datetime_entry = ttk.Entry(frame, textvariable=self.sim_datetime_var, width=20)
        self.sim_datetime_entry.grid(row=2, column=1, sticky="w", padx=5, pady=3)
        ttk.Label(frame, text="YYYY-MM-DD HH:MM:SS", font=("Segoe UI", 7)).grid(row=3, column=1, sticky="w", padx=5)

        # Botão e Status
        self.sim_button = ttk.Button(frame, text="Executar Simulação", command=self._run_simulation_click)
        self.sim_button.grid(row=4, column=0, columnspan=2, pady=(10, 5))
        self.sim_status_label = ttk.Label(frame, text="Simulador: Pronto", anchor=tk.CENTER)
        self.sim_status_label.grid(row=5, column=0, columnspan=2, pady=(0, 5))

    def _create_live_controls(self, parent):
        """Cria a seção de controles para o Live Trading."""
        frame = ttk.LabelFrame(parent, text=" Live Trading ", padding=10)
        frame.grid(row=1, column=0, sticky="new")
        frame.columnconfigure(0, weight=1) # Centraliza botões/labels

        # Botões
        self.live_start_button = ttk.Button(frame, text="INICIAR Monitoramento", command=self._start_live_click)
        self.live_start_button.grid(row=0, column=0, pady=5)

        self.live_stop_button = ttk.Button(frame, text="PARAR Monitoramento", command=self._stop_live_click, state=tk.DISABLED)
        self.live_stop_button.grid(row=1, column=0, pady=5)

        # Status
        self.live_status_label = ttk.Label(frame, text="Live: Desligado", anchor=tk.CENTER)
        self.live_status_label.grid(row=2, column=0, pady=(10, 5))

    def _create_market_monitor(self, parent):
        """Cria a seção do Monitor de Mercado."""
        frame = ttk.LabelFrame(parent, text=" Monitor de Mercado ", padding=10)
        frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1) # Faz a Treeview expandir

        # Controles de Refresh
        controls_frame = ttk.Frame(frame, style="TFrame") # Frame sem borda
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        self.refresh_check = ttk.Checkbutton(controls_frame, text="Auto Refresh (1 min)", variable=self.market_data_auto_refresh, command=self._toggle_auto_refresh)
        self.refresh_check.pack(side=tk.LEFT, padx=5)

        self.refresh_button = ttk.Button(controls_frame, text="Atualizar Agora", command=self._manual_refresh_click)
        self.refresh_button.pack(side=tk.LEFT, padx=5)

        self.refresh_status_label = ttk.Label(controls_frame, text="Auto Refresh: ON", anchor=tk.E)
        self.refresh_status_label.pack(side=tk.RIGHT, padx=5)

        # Tabela (Treeview)
        cols = ("Ticker", "Preço Atual", "Hora Local", "Bid", "Ask", "Volume") # Adicione mais se necessário
        self.market_tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode="browse")
        for col in cols:
            self.market_tree.heading(col, text=col)
            self.market_tree.column(col, anchor=tk.CENTER, width=100) # Ajuste larguras

        self.market_tree.grid(row=1, column=0, sticky="nsew")

        # Scrollbar para a Treeview
        tree_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.market_tree.yview)
        self.market_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.grid(row=1, column=1, sticky="ns")

        # Populando inicialmente (Placeholder) - A lógica real virá depois
        self._populate_market_monitor_placeholder()

    def _create_results_display(self, parent):
        """Cria a seção para exibir os 2 últimos resultados."""
        frame = ttk.LabelFrame(parent, text=" Últimas Execuções ", padding=10)
        frame.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        # Usaremos Labels para simplicidade, mas um Text ou Treeview seria mais flexível
        self.result_label_1 = ttk.Label(frame, text="Resultado 1: ---", wraplength=1000, justify=tk.LEFT)
        self.result_label_1.grid(row=0, column=0, sticky="w", pady=2)

        self.result_label_2 = ttk.Label(frame, text="Resultado 2: ---", wraplength=1000, justify=tk.LEFT)
        self.result_label_2.grid(row=1, column=0, sticky="w", pady=2)

    # --- Funções de Controle (Placeholders) ---

    def _run_simulation_click(self):
        """Placeholder para botão 'Executar Simulação'."""
        asset = self.sim_asset_var.get()
        tf = self.sim_tf_var.get()
        dt_str = self.sim_datetime_var.get()
        logger.info(f"Botão SIMULAR clicado: Ativo={asset}, TF={tf}, DataHora={dt_str}")
        self.sim_status_label.config(text="Simulando...")
        # Aqui virá a chamada ao SimulationEngine em uma thread
        # Exemplo de como adicionar resultado (para teste):
        dummy_result = { "type": "Simulação", "datetime": dt_str, "asset": asset, "timeframe": tf, "final_signal": "COMPRA",
                         "current_price": 123.45, "stop_loss": 122.00, "take_profit": 125.00, "position":"---" }
        self._add_result_to_display(dummy_result)
        self.sim_status_label.config(text="Simulação Concluída")


    def _start_live_click(self):
        """Placeholder para botão 'INICIAR Monitoramento'."""
        logger.info("Botão INICIAR LIVE clicado.")
        self.live_status_label.config(text="Live: Iniciando...")
        self.live_start_button.config(state=tk.DISABLED)
        self.live_stop_button.config(state=tk.NORMAL)
        # Aqui virá a chamada a self.trader_engine.start()
        # Exemplo de como adicionar resultado (para teste):
        dummy_result = { "type": "Live", "datetime": datetime.now(self.local_tz).strftime("%Y-%m-%d %H:%M:%S"),
                         "asset": "WDO$", "timeframe": "M5", "final_signal": "VENDA",
                         "current_price": 5432.1, "stop_loss": 5440.0, "take_profit": 5400.0, "position":"Vendido @ 5432.1" }
        self._add_result_to_display(dummy_result)
        self.live_status_label.config(text="Live: Monitorando...")


    def _stop_live_click(self):
        """Placeholder para botão 'PARAR Monitoramento'."""
        logger.info("Botão PARAR LIVE clicado.")
        self.live_status_label.config(text="Live: Parando...")
        self.live_start_button.config(state=tk.NORMAL)
        self.live_stop_button.config(state=tk.DISABLED)
        # Aqui virá a chamada a self.trader_engine.stop()
        self.live_status_label.config(text="Live: Desligado")


    def _toggle_auto_refresh(self):
        """Ativa/Desativa o auto refresh do monitor."""
        is_on = self.market_data_auto_refresh.get()
        logger.info(f"Toggle Auto Refresh clicado: {'ON' if is_on else 'OFF'}")
        if is_on:
            self._start_auto_refresh()
        else:
            self._stop_auto_refresh()
        self._update_refresh_status_label()

    def _manual_refresh_click(self):
        """Placeholder para o botão 'Atualizar Agora'."""
        logger.info("Botão ATUALIZAR AGORA (Monitor) clicado.")
        self._update_market_monitor() # Chama a função de atualização

    def _start_auto_refresh(self):
        """Agenda a próxima atualização automática."""
        if self.auto_refresh_job_id: # Cancela job anterior se existir
            self.after_cancel(self.auto_refresh_job_id)

        # Chama a atualização e re-agenda
        self._update_market_monitor()
        self.auto_refresh_job_id = self.after(self.refresh_interval_ms, self._start_auto_refresh)
        logger.debug(f"Auto Refresh agendado (Job ID: {self.auto_refresh_job_id})")


    def _stop_auto_refresh(self):
        """Cancela a atualização automática."""
        if self.auto_refresh_job_id:
            logger.debug(f"Cancelando Auto Refresh (Job ID: {self.auto_refresh_job_id})")
            self.after_cancel(self.auto_refresh_job_id)
            self.auto_refresh_job_id = None

    def _update_refresh_status_label(self):
        """Atualiza o label de status do auto refresh."""
        status = "Auto Refresh: ON" if self.market_data_auto_refresh.get() else "Auto Refresh: OFF"
        self.refresh_status_label.config(text=status)

    def _update_market_monitor(self):
        """Placeholder para atualizar os dados da Treeview."""
        logger.info("Atualizando Monitor de Mercado (Placeholder)...")
        # Limpa a tabela atual
        for item in self.market_tree.get_children():
            self.market_tree.delete(item)

        # --- Aqui virá a lógica para buscar dados reais (ex: Ticks MT5) ---
        # Adiciona dados dummy por enquanto
        now_str = datetime.now(self.local_tz).strftime("%H:%M:%S")
        dummy_data = [
            ("WDO$", f"5432.10", now_str, "5432.00", "5432.50", "15k"),
            ("WIN$", f"128765", now_str, "128760", "128770", "150k"),
        ]
        for item in dummy_data:
             # Aplica tag de cor baseado no ticker (exemplo)
             tag = 'even' if len(self.market_tree.get_children()) % 2 == 0 else 'odd'
             self.market_tree.insert("", tk.END, values=item, tags=(tag,))

        # Configura cores alternadas (exemplo)
        self.market_tree.tag_configure('even', background='#505050', foreground='white')
        self.market_tree.tag_configure('odd', background='#454545', foreground='white')

        # Atualiza o label "Last Update"
        last_update_time = datetime.now(self.local_tz).strftime("%H:%M:%S")
        status_text = f"{'Auto Refresh: ON' if self.market_data_auto_refresh.get() else 'Auto Refresh: OFF'} | Última: {last_update_time}"
        self.refresh_status_label.config(text=status_text)


    def _populate_market_monitor_placeholder(self):
         """Adiciona linhas iniciais vazias ou com 'Carregando...'."""
         for ticker in self.live_asset_tickers: # Usa apenas ativos live aqui
             self.market_tree.insert("", tk.END, values=(ticker, "Carregando...", "...", "...", "...", "..."), tags=('odd' if len(self.market_tree.get_children()) % 2 else 'even',))

    def _add_result_to_display(self, result_dict):
        """Adiciona um novo resultado (Sim ou Live) ao display e ao log."""
        # Adiciona ao log completo
        self.all_results_log.append(result_dict)

        # Adiciona à deque para display (sobrescreve o mais antigo se cheio)
        self.last_results.append(result_dict)

        # Atualiza os labels na GUI
        results_to_display = list(self.last_results) # Pega cópia

        # Formata Resultado 1 (o mais recente)
        if len(results_to_display) > 0:
            res1 = results_to_display[-1] # Pega o último adicionado
            res1_str = f"[{res1.get('datetime', '')}] ({res1.get('type', '?')}) {res1.get('asset', '?')}@{res1.get('timeframe', '?')}: Sinal={res1.get('final_signal', '?')}, Preço={res1.get('current_price', '?')}, SL={res1.get('stop_loss', '?')}, TP={res1.get('take_profit', '?')}, Pos={res1.get('position', '?')}"
            self.result_label_1.config(text=f"Recente: {res1_str}")
        else:
            self.result_label_1.config(text="Resultado 1: ---")

        # Formata Resultado 2 (o anterior)
        if len(results_to_display) > 1:
            res2 = results_to_display[-2] # Pega o penúltimo
            res2_str = f"[{res2.get('datetime', '')}] ({res2.get('type', '?')}) {res2.get('asset', '?')}@{res2.get('timeframe', '?')}: Sinal={res2.get('final_signal', '?')}, Preço={res2.get('current_price', '?')}, SL={res2.get('stop_loss', '?')}, TP={res2.get('take_profit', '?')}, Pos={res2.get('position', '?')}"
            self.result_label_2.config(text=f"Anterior: {res2_str}")
        else:
            self.result_label_2.config(text="Resultado 2: ---")


    def _save_log_to_csv(self):
        """Salva o log completo de resultados em um arquivo CSV."""
        if not self.all_results_log:
            logger.info("Nenhum resultado para salvar no log CSV.")
            return

        log_dir = Path("logs") # Define diretório de logs
        log_dir.mkdir(exist_ok=True) # Cria se não existir
        filename = log_dir / f"unified_dashboard_log_{datetime.now():%Y%m%d_%H%M%S}.csv"

        try:
            import csv # Importa apenas quando necessário
            # Extrai cabeçalhos do primeiro registro (assume consistência)
            headers = list(self.all_results_log[0].keys())
            # Garante que colunas complexas sejam tratadas (ex: indicators, setup_details)
            headers = [h for h in headers if not isinstance(self.all_results_log[0][h], (dict, list))] + \
                      ['indicators_json', 'setup_details_json'] # Salva dicts como JSON string

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers, extrasaction='ignore') # Ignora chaves extras
                writer.writeheader()
                for row_dict in self.all_results_log:
                     # Converte dicts internos para JSON string
                     row_to_write = row_dict.copy()
                     if 'indicators' in row_to_write and isinstance(row_to_write['indicators'], dict):
                          row_to_write['indicators_json'] = str(row_to_write.pop('indicators')) # Converte para string simples
                     if 'setup_details' in row_to_write and isinstance(row_to_write['setup_details'], dict):
                          row_to_write['setup_details_json'] = str(row_to_write.pop('setup_details'))

                     writer.writerow(row_to_write)
            logger.info(f"Log de resultados salvo em: {filename}")
        except Exception as e:
            logger.error(f"Erro ao salvar log CSV em {filename}: {e}", exc_info=True)
            messagebox.showerror("Erro ao Salvar Log", f"Não foi possível salvar o arquivo CSV:\n{e}")

    def _on_closing(self):
        """Chamado ao fechar a janela."""
        logger.info("Fechando dashboard...")
        if messagebox.askokcancel("Sair", "Deseja fechar o dashboard? O monitoramento será interrompido e o log salvo."):
            self._stop_live_click() # Tenta parar o LiveTrader (se estiver rodando)
            self._stop_auto_refresh() # Para o refresh do monitor

            # Espera um pouco para a thread do LiveTrader tentar parar
            self.update() # Processa eventos pendentes
            time.sleep(1) # Pequena pausa

            # Salva o log
            self._save_log_to_csv()

            # Fecha engine de simulação (importante para fechar conexão MT5 se ele a usou)
            if self.simulation_engine and hasattr(self.simulation_engine, 'close'):
                 logger.info("Fechando SimulationEngine...")
                 self.simulation_engine.close()

            # Fecha a janela
            logger.info("Encerrando aplicação GUI.")
            self.destroy()

# --- Bloco Principal ---
if __name__ == "__main__":
    app = UnifiedDashboard()
    # Define status inicial (opcional)
    app.global_status_label.config(text="Pronto.", style="Status.OK.TLabel")
    app.mainloop()