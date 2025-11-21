# src/gui/monitor_ui.py

"""
Interface Gráfica para o Monitor de Trading em Tempo Real.

Utiliza tkinter para criar uma GUI moderna que controla o RealTimeMonitor
e exibe alertas/logs em tempo real de forma thread-safe.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import queue
import logging
from datetime import datetime
from pathlib import Path
import sys

# Adiciona o diretório raiz ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.live.monitor_engine import RealTimeMonitor

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


class MonitorApp:
    """
    Aplicação GUI para controle e visualização do Monitor em Tempo Real.
    
    Features:
    - Header com informações do ativo (Ticker, Preço, Timeframe, Status)
    - Botão Start/Stop para controlar o monitor
    - Treeview com logs/alertas ordenados por data (mais recentes no topo)
    - Destaque visual para alertas de alta probabilidade
    - Comunicação thread-safe entre monitor e UI via Queue
    """
    
    def __init__(self, root):
        """
        Inicializa a aplicação GUI.
        
        Args:
            root: Janela raiz do tkinter
        """
        self.root = root
        self.root.title("WTNPS-TRADE - Monitor em Tempo Real")
        self.root.geometry("1400x750")
        self.root.resizable(True, True)
        
        # Configurações do monitor
        self.ticker = "WDO$"
        self.timeframe = "M5"
        self.threshold_alert = 0.65
        self.threshold_log = 0.55
        self.buffer_size = 500
        
        # Estado da aplicação
        self.monitor = None
        self.monitor_thread = None
        self.is_running = False
        self.last_candle = {
            'timestamp': None,
            'open': 0.0,
            'high': 0.0,
            'low': 0.0,
            'close': 0.0,
            'volume': 0
        }
        
        # Queue para comunicação thread-safe
        self.update_queue = queue.Queue()
        
        # Janela de buffer (inicialmente None)
        self.buffer_window = None
        
        # Configura estilos
        self._setup_styles()
        
        # Constrói interface
        self._build_ui()
        
        # Inicia polling da queue
        self._poll_queue()
        
        logger.info("Interface GUI inicializada")
    
    def _setup_styles(self):
        """Configura estilos visuais do ttk."""
        style = ttk.Style()
        style.theme_use('clam')  # Tema moderno
        
        # Estilo para botão Start
        style.configure(
            'Start.TButton',
            font=('Segoe UI', 12, 'bold'),
            padding=10,
            background='#28a745',
            foreground='white'
        )
        
        # Estilo para botão Stop
        style.configure(
            'Stop.TButton',
            font=('Segoe UI', 12, 'bold'),
            padding=10,
            background='#dc3545',
            foreground='white'
        )
        
        # Estilo para Treeview
        style.configure(
            'Monitor.Treeview',
            font=('Segoe UI', 10),
            rowheight=30
        )
        style.configure(
            'Monitor.Treeview.Heading',
            font=('Segoe UI', 10, 'bold'),
            background='#343a40',
            foreground='white'
        )
    
    def _build_ui(self):
        """Constrói a interface gráfica completa."""
        # Container principal
        main_container = ttk.Frame(self.root, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configura grid weights para expansão
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(2, weight=1)
        
        # === HEADER ===
        self._build_header(main_container)
        
        # === CONTROLES ===
        self._build_controls(main_container)
        
        # === ÁREA DE LOGS/ALERTAS ===
        self._build_logs_area(main_container)
    
    def _build_header(self, parent):
        """
        Constrói o header com informações do ativo.
        
        Exibe: Ticker, Timeframe, Dados do Último Candle (Hora UTC + OHLC)
        """
        header_frame = ttk.LabelFrame(parent, text="Informações do Ativo", padding="10")
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Container para dados do ativo
        info_container = ttk.Frame(header_frame)
        info_container.pack(fill=tk.X)
        
        # === TICKER ===
        ticker_frame = ttk.Frame(info_container)
        ticker_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(
            ticker_frame,
            text="Ticker:",
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W)
        
        self.ticker_label = ttk.Label(
            ticker_frame,
            text=self.ticker,
            font=('Segoe UI', 18, 'bold'),
            foreground='#007bff'
        )
        self.ticker_label.pack(anchor=tk.W)
        
        # === TIMEFRAME ===
        tf_frame = ttk.Frame(info_container)
        tf_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(
            tf_frame,
            text="Timeframe:",
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W)
        
        self.timeframe_label = ttk.Label(
            tf_frame,
            text=self.timeframe,
            font=('Segoe UI', 18, 'bold'),
            foreground='#6c757d'
        )
        self.timeframe_label.pack(anchor=tk.W)
        
        # === DADOS DO ÚLTIMO CANDLE ===
        candle_frame = ttk.Frame(info_container)
        candle_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(
            candle_frame,
            text="Último Candle (UTC):",
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W)
        
        # Container horizontal para OHLC
        ohlc_container = ttk.Frame(candle_frame)
        ohlc_container.pack(anchor=tk.W)
        
        # Hora
        self.candle_time_label = ttk.Label(
            ohlc_container,
            text="--:--:--",
            font=('Segoe UI', 14, 'bold'),
            foreground='#28a745'
        )
        self.candle_time_label.pack(side=tk.LEFT, padx=(0, 15))
        
        # OHLC
        ohlc_data_frame = ttk.Frame(ohlc_container)
        ohlc_data_frame.pack(side=tk.LEFT)
        
        self.ohlc_label = ttk.Label(
            ohlc_data_frame,
            text="O: ---- | H: ---- | L: ---- | C: ----",
            font=('Segoe UI', 11),
            foreground='#495057'
        )
        self.ohlc_label.pack()
    
    def _build_controls(self, parent):
        """
        Constrói área de controles.
        
        Botão Start/Stop com indicador de status (semáforo) ao lado.
        """
        controls_frame = ttk.Frame(parent, padding="10")
        controls_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Container esquerdo para botão Start/Stop e Status
        left_controls = ttk.Frame(controls_frame)
        left_controls.pack(side=tk.LEFT)
        
        # Botão Start/Stop
        self.start_stop_btn = ttk.Button(
            left_controls,
            text="▶ INICIAR MONITORAMENTO",
            command=self._toggle_monitor,
            style='Start.TButton',
            width=30
        )
        self.start_stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Canvas para círculo do semáforo
        self.status_canvas = tk.Canvas(
            left_controls,
            width=30,
            height=30,
            bg='#f0f0f0',
            highlightthickness=0
        )
        self.status_canvas.pack(side=tk.LEFT, padx=5)
        
        # Desenha círculo vermelho (parado)
        self.status_indicator = self.status_canvas.create_oval(
            5, 5, 25, 25,
            fill='#dc3545',
            outline='#6c757d',
            width=2
        )
        
        # Botão de Ver Buffer (lado direito)
        right_controls = ttk.Frame(controls_frame)
        right_controls.pack(side=tk.RIGHT)
        
        buffer_btn = ttk.Button(
            right_controls,
            text="📊 Ver Buffer",
            command=self._show_buffer_window,
            width=15
        )
        buffer_btn.pack(side=tk.RIGHT, padx=5)
    
    def _build_logs_area(self, parent):
        """
        Constrói área de logs/alertas com Treeview.
        
        Colunas: Data/Hora (UTC), Tipo, Preço, Probabilidade, Mensagem
        Botão Limpar Logs no canto inferior direito.
        """
        logs_frame = ttk.LabelFrame(parent, text="Logs e Alertas", padding="10")
        logs_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configura grid
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)
        
        # Container com scrollbars
        tree_container = ttk.Frame(logs_frame)
        tree_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_container, orient="vertical")
        hsb = ttk.Scrollbar(tree_container, orient="horizontal")
        
        # Treeview
        self.logs_tree = ttk.Treeview(
            tree_container,
            columns=('datetime', 'type', 'price', 'probability', 'message'),
            show='headings',
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            style='Monitor.Treeview'
        )
        
        # Configura scrollbars
        vsb.config(command=self.logs_tree.yview)
        hsb.config(command=self.logs_tree.xview)
        
        # Grid do Treeview
        self.logs_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Configura colunas
        self.logs_tree.heading('datetime', text='Data/Hora (UTC)')
        self.logs_tree.heading('type', text='Tipo')
        self.logs_tree.heading('price', text='Preço')
        self.logs_tree.heading('probability', text='Probabilidade ML')
        self.logs_tree.heading('message', text='Mensagem')
        
        # Larguras das colunas
        self.logs_tree.column('datetime', width=180, anchor=tk.W)
        self.logs_tree.column('type', width=100, anchor=tk.CENTER)
        self.logs_tree.column('price', width=120, anchor=tk.E)
        self.logs_tree.column('probability', width=140, anchor=tk.E)
        self.logs_tree.column('message', width=400, anchor=tk.W)
        
        # Tags para formatação de linhas
        self.logs_tree.tag_configure('ALERT', background='#fff3cd', foreground='#856404')
        self.logs_tree.tag_configure('INFO', background='#d1ecf1', foreground='#0c5460')
        self.logs_tree.tag_configure('TICK', background='#ffffff', foreground='#6c757d')
        
        # Botão Limpar Logs no canto inferior direito
        clear_logs_frame = ttk.Frame(logs_frame)
        clear_logs_frame.grid(row=1, column=0, sticky=tk.E, pady=(5, 0))
        
        clear_btn = ttk.Button(
            clear_logs_frame,
            text="🗑 Limpar Logs",
            command=self._clear_logs,
            width=15
        )
        clear_btn.pack(side=tk.RIGHT)
    
    def _toggle_monitor(self):
        """
        Alterna entre iniciar e parar o monitor.
        
        Inicia o monitor em thread separada ou solicita parada.
        """
        if not self.is_running:
            # Iniciar monitor
            self._start_monitor()
        else:
            # Parar monitor
            self._stop_monitor()
    
    def _start_monitor(self):
        """Inicia o monitor em thread separada."""
        try:
            logger.info("Iniciando monitor...")
            
            # Atualiza UI
            self.is_running = True
            self.start_stop_btn.config(
                text="■ PARAR MONITORAMENTO",
                style='Stop.TButton'
            )
            # Atualiza semáforo para verde
            self.status_canvas.itemconfig(self.status_indicator, fill='#28a745')
            
            # Cria instância do monitor com callback
            self.monitor = RealTimeMonitor(
                ticker=self.ticker,
                timeframe_str=self.timeframe,
                threshold_alert=self.threshold_alert,
                threshold_log=self.threshold_log,
                buffer_size=self.buffer_size,
                ui_callback=self._on_monitor_update
            )
            
            # Inicia monitor em thread separada
            self.monitor_thread = threading.Thread(
                target=self._run_monitor,
                daemon=True
            )
            self.monitor_thread.start()
            
            logger.info("Monitor iniciado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar monitor: {e}", exc_info=True)
            messagebox.showerror(
                "Erro",
                f"Falha ao iniciar monitor:\n{str(e)}\n\nVerifique se o MT5 está aberto e logado."
            )
            self._reset_ui_state()
    
    def _run_monitor(self):
        """Executa o loop do monitor (roda em thread separada)."""
        try:
            self.monitor.start()
        except Exception as e:
            logger.error(f"Erro no monitor: {e}", exc_info=True)
            self.update_queue.put({
                'action': 'error',
                'message': str(e)
            })
        finally:
            self.update_queue.put({'action': 'stopped'})
    
    def _stop_monitor(self):
        """Para o monitor."""
        try:
            logger.info("Parando monitor...")
            
            if self.monitor:
                self.monitor.stop()
            
            # Aguarda thread finalizar (com timeout)
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5)
            
            self._reset_ui_state()
            
            logger.info("Monitor parado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao parar monitor: {e}", exc_info=True)
            messagebox.showerror("Erro", f"Falha ao parar monitor:\n{str(e)}")
    
    def _reset_ui_state(self):
        """Reseta estado da UI para parado."""
        self.is_running = False
        self.start_stop_btn.config(
            text="▶ INICIAR MONITORAMENTO",
            style='Start.TButton'
        )
        # Atualiza semáforo para vermelho
        self.status_canvas.itemconfig(self.status_indicator, fill='#dc3545')
    
    def _on_monitor_update(self, data: dict):
        """
        Callback chamado pelo monitor quando há nova atualização.
        
        Adiciona dados à queue para processamento thread-safe.
        
        Args:
            data: Dicionário com dados do evento (type, timestamp, price, etc.)
        """
        self.update_queue.put({
            'action': 'update',
            'data': data
        })
    
    def _poll_queue(self):
        """
        Polling da queue de atualizações.
        
        Processa eventos da queue e atualiza UI (thread-safe).
        Executado periodicamente via root.after.
        """
        try:
            # Processa todos os eventos pendentes na queue
            while True:
                try:
                    event = self.update_queue.get_nowait()
                    
                    if event['action'] == 'update':
                        self._process_update(event['data'])
                    elif event['action'] == 'stopped':
                        self._reset_ui_state()
                    elif event['action'] == 'error':
                        messagebox.showerror(
                            "Erro no Monitor",
                            f"Erro durante monitoramento:\n{event['message']}"
                        )
                        self._reset_ui_state()
                    
                except queue.Empty:
                    break
        
        except Exception as e:
            logger.error(f"Erro ao processar queue: {e}", exc_info=True)
        
        finally:
            # Reagenda polling (100ms)
            self.root.after(100, self._poll_queue)
    
    def _process_update(self, data: dict):
        """
        Processa atualização do monitor e atualiza UI.
        
        Args:
            data: Dicionário com dados do evento
        """
        try:
            # Atualiza dados do último candle no header
            if 'open' in data and 'high' in data and 'low' in data and 'close' in data:
                self.last_candle['open'] = data['open']
                self.last_candle['high'] = data['high']
                self.last_candle['low'] = data['low']
                self.last_candle['close'] = data['close']
                self.last_candle['volume'] = data.get('volume', 0)
                self.last_candle['timestamp'] = data.get('timestamp')
                
                # Atualiza hora do candle (UTC)
                timestamp = data.get('timestamp', datetime.now())
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                
                # Formata hora UTC (HH:MM:SS)
                time_str = timestamp.strftime('%H:%M:%S')
                self.candle_time_label.config(text=time_str)
                
                # Formata OHLC
                o = self.last_candle['open']
                h = self.last_candle['high']
                l = self.last_candle['low']
                c = self.last_candle['close']
                
                ohlc_text = f"O: {o:.2f} | H: {h:.2f} | L: {l:.2f} | C: {c:.2f}"
                self.ohlc_label.config(text=ohlc_text)
            
            # Formata data/hora para o log (UTC no formato DD/MM/YYYY HH:MM:SS)
            timestamp = data.get('timestamp', datetime.now())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            datetime_str = timestamp.strftime('%d/%m/%Y %H:%M:%S')
            
            # Formata tipo
            event_type = data.get('type', 'TICK')
            
            # Formata preço
            price = data.get('close', data.get('price', 0.0))
            price_str = f"R$ {price:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
            
            # Formata probabilidade
            probability = data.get('probability', 0.0)
            prob_str = f"{probability:.2f}%"
            
            # Mensagem
            message = data.get('message', '')
            
            # Adiciona ao Treeview (no topo - índice 0)
            self.logs_tree.insert(
                '',
                0,  # Índice 0 = topo
                values=(datetime_str, event_type, price_str, prob_str, message),
                tags=(event_type,)
            )
            
            # Limita número de linhas (máximo 1000)
            children = self.logs_tree.get_children()
            if len(children) > 1000:
                # Remove linhas antigas (do final)
                for item in children[1000:]:
                    self.logs_tree.delete(item)
            
            # Auto-scroll para o topo (mostra evento mais recente)
            if children:
                self.logs_tree.see(children[0])
        
        except Exception as e:
            logger.error(f"Erro ao processar atualização: {e}", exc_info=True)
    
    def _clear_logs(self):
        """Limpa todos os logs do Treeview."""
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)
        logger.info("Logs limpos")
    
    def _show_buffer_window(self):
        """Abre janela modal para exibir o buffer de dados."""
        if not self.monitor or not hasattr(self.monitor, 'buffer_df'):
            messagebox.showinfo(
                "Buffer Indisponível",
                "O monitor ainda não foi iniciado ou não possui dados em buffer."
            )
            return
        
        if self.monitor.buffer_df is None or self.monitor.buffer_df.empty:
            messagebox.showinfo(
                "Buffer Vazio",
                "O buffer de dados está vazio."
            )
            return
        
        # Fecha janela anterior se existir
        if self.buffer_window and self.buffer_window.winfo_exists():
            self.buffer_window.destroy()
        
        # Cria nova janela
        self.buffer_window = tk.Toplevel(self.root)
        self.buffer_window.title("Buffer de Dados - Último 500 Candles")
        self.buffer_window.geometry("900x600")
        
        # Frame container
        container = ttk.Frame(self.buffer_window, padding="10")
        container.pack(fill=tk.BOTH, expand=True)
        
        # Label informativo
        info_label = ttk.Label(
            container,
            text=f"Total de registros: {len(self.monitor.buffer_df)}",
            font=('Segoe UI', 10, 'bold')
        )
        info_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Frame para Treeview
        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        
        # Treeview
        buffer_tree = ttk.Treeview(
            tree_frame,
            columns=('timestamp', 'open', 'high', 'low', 'close', 'volume'),
            show='headings',
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )
        
        vsb.config(command=buffer_tree.yview)
        hsb.config(command=buffer_tree.xview)
        
        # Grid
        buffer_tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.E, tk.W))
        
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Configura colunas
        buffer_tree.heading('timestamp', text='Timestamp (UTC)')
        buffer_tree.heading('open', text='Open')
        buffer_tree.heading('high', text='High')
        buffer_tree.heading('low', text='Low')
        buffer_tree.heading('close', text='Close')
        buffer_tree.heading('volume', text='Volume')
        
        buffer_tree.column('timestamp', width=180, anchor=tk.W)
        buffer_tree.column('open', width=120, anchor=tk.E)
        buffer_tree.column('high', width=120, anchor=tk.E)
        buffer_tree.column('low', width=120, anchor=tk.E)
        buffer_tree.column('close', width=120, anchor=tk.E)
        buffer_tree.column('volume', width=100, anchor=tk.E)
        
        # Popula dados (ordem reversa - mais recentes primeiro)
        df = self.monitor.buffer_df
        for idx in reversed(df.index):
            row = df.loc[idx]
            timestamp_str = idx.strftime('%Y-%m-%d %H:%M:%S')
            
            buffer_tree.insert(
                '',
                'end',
                values=(
                    timestamp_str,
                    f"{row['open']:.2f}",
                    f"{row['high']:.2f}",
                    f"{row['low']:.2f}",
                    f"{row['close']:.2f}",
                    int(row.get('volume', 0))
                )
            )
        
        # Botão fechar
        close_btn = ttk.Button(
            container,
            text="Fechar",
            command=self.buffer_window.destroy,
            width=15
        )
        close_btn.pack(pady=(10, 0))
    
    def run(self):
        """Inicia o loop principal da GUI."""
        logger.info("Iniciando loop principal da GUI")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.mainloop()
    
    def _on_closing(self):
        """Manipula fechamento da janela."""
        if self.is_running:
            if messagebox.askokcancel("Sair", "Monitor está rodando. Deseja parar e sair?"):
                self._stop_monitor()
                # Fecha janela de buffer se existir
                if self.buffer_window and self.buffer_window.winfo_exists():
                    self.buffer_window.destroy()
                self.root.destroy()
        else:
            # Fecha janela de buffer se existir
            if self.buffer_window and self.buffer_window.winfo_exists():
                self.buffer_window.destroy()
            self.root.destroy()


def main():
    """Função principal para executar a GUI."""
    root = tk.Tk()
    app = MonitorApp(root)
    app.run()


if __name__ == "__main__":
    main()
