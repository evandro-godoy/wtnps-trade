import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, PADY, PADX, W, E, N, S
import threading
import time
import pandas as pd
from datetime import datetime
import queue

# --- Importações dos módulos do seu projeto ---
# Estas são suposições baseadas na estrutura de pastas.
# Ajuste os caminhos de importação se a estrutura for diferente.
try:
    from src.data_handler.provider import DataProvider
    from src.simulation.engine import SimulationEngine
    from src.live_trader import LiveTrader
    # Assumindo que as estratégias podem ser carregadas ou listadas
    # from src.strategies.base import BaseStrategy 
except ImportError:
    messagebox.showerror("Erro de Importação", 
                         "Não foi possível importar os módulos principais (DataProvider, SimulationEngine, LiveTrader). "
                         "Verifique se o PYTHONPATH está correto ou execute a partir da raiz do projeto.")
    # Em um cenário real, poderíamos ter fallbacks ou fechar a app
    # Para este exemplo, definiremos classes dummy para permitir que a GUI carregue
    class DataProvider:
        def get_market_data(self, asset):
            return f"Erro: DataProvider não carregado.\nAtivo: {asset}\nHora: {datetime.now()}"

    class SimulationEngine:
        def __init__(self, *args, **kwargs): self.stop_event = threading.Event()
        def run(self): 
            while not self.stop_event.is_set(): time.sleep(1)
            return {"timestamp": datetime.now(), "module": "Simulation", "status": "Engine não carregado"}
        def stop(self): self.stop_event.set()

    class LiveTrader:
        def __init__(self, *args, **kwargs): self.stop_event = threading.Event()
        def run(self): 
            while not self.stop_event.is_set(): time.sleep(1)
            return {"timestamp": datetime.now(), "module": "LiveTrade", "status": "Trader não carregado"}
        def stop(self): self.stop_event.set()


class UnifiedDashboard(tk.Tk):
    """
    Dashboard unificado para gerenciamento dos módulos de Simulação e Live Trading.
    """

    def __init__(self):
        super().__init__()
        self.title("Unified Trading Dashboard (Simulação & Live)")
        self.geometry("1000x700")

        # --- Estado da Aplicação ---
        self.all_executions_data = []  # Para o log .csv
        self.execution_queue = queue.Queue() # Fila para resultados thread-safe
        self.auto_refresh_running = threading.Event()
        self.simulation_running = threading.Event()
        self.live_trade_running = threading.Event()

        # --- Threads ---
        self.auto_refresh_thread = None
        self.simulation_thread = None
        self.live_trade_thread = None

        # --- Módulos de Backend ---
        # Instanciamos os provedores aqui para que possam ser usados pela GUI
        self.data_provider = DataProvider()
        self.simulation_engine = None # Será instanciado ao iniciar a simulação
        self.live_trader = None       # Será instanciado ao iniciar o live trade

        # --- Configuração da GUI ---
        self.create_widgets()
        
        # --- Protocolo de Fechamento ---
        # Garante que os logs sejam salvos e as threads finalizadas
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Inicia o processador da fila de resultados
        self.process_execution_queue()

    def create_widgets(self):
        """
Cria e organiza os principais frames e widgets da aplicação.
        """
        # --- Configuração do Layout Principal (Grid) ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1) # Monitor de Mercado
        self.grid_rowconfigure(1, weight=2) # Módulos (Sim/Live)
        self.grid_rowconfigure(2, weight=2) # Resultados

        # --- Frame 1: Monitor de Mercado ---
        monitor_frame = ttk.LabelFrame(self, text="Monitor de Mercado", padding=(10, 5))
        monitor_frame.grid(row=0, column=0, columnspan=2, sticky=(N, S, E, W), padx=10, pady=5)
        monitor_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(monitor_frame, text="Ativo:").grid(row=0, column=0, sticky=W, padx=5)
        self.asset_var = tk.StringVar(value="WDO$") # Ativo padrão
        self.asset_entry = ttk.Entry(monitor_frame, textvariable=self.asset_var, width=10)
        self.asset_entry.grid(row=0, column=1, sticky=W, padx=5)

        self.monitor_text = scrolledtext.ScrolledText(monitor_frame, height=5, wrap=tk.WORD, state='disabled')
        self.monitor_text.grid(row=1, column=0, columnspan=4, sticky=(E, W), padx=5, pady=5)

        self.manual_refresh_btn = ttk.Button(monitor_frame, text="Refresh Manual", command=self.update_market_data)
        self.manual_refresh_btn.grid(row=0, column=2, padx=5)

        self.auto_refresh_check = ttk.Checkbutton(monitor_frame, text="Auto-Refresh (1 min)", command=self.toggle_auto_refresh)
        self.auto_refresh_check.grid(row=0, column=3, padx=5, sticky=E)

        # --- Frame 2: Módulos de Execução ---
        modules_frame = ttk.Frame(self)
        modules_frame.grid(row=1, column=0, columnspan=2, sticky=(N, S, E, W), padx=5, pady=5)
        modules_frame.grid_columnconfigure(0, weight=1)
        modules_frame.grid_columnconfigure(1, weight=1)

        # --- Sub-Frame 2a: Simulação ---
        sim_frame = ttk.LabelFrame(modules_frame, text="Módulo de Simulação", padding=(10, 5))
        sim_frame.grid(row=0, column=0, sticky=(N, S, E, W), padx=5)
        sim_frame.grid_columnconfigure(1, weight=1)
        
        # (Inputs de simulação: Datas, Estratégia, etc.)
        ttk.Label(sim_frame, text="Data Início:").grid(row=0, column=0, sticky=W, padx=PADX, pady=PADY)
        self.sim_start_date = ttk.Entry(sim_frame, width=12); self.sim_start_date.grid(row=0, column=1, sticky=W)
        self.sim_start_date.insert(0, "YYYY-MM-DD")
        
        ttk.Label(sim_frame, text="Data Fim:").grid(row=1, column=0, sticky=W, padx=PADX, pady=PADY)
        self.sim_end_date = ttk.Entry(sim_frame, width=12); self.sim_end_date.grid(row=1, column=1, sticky=W)
        self.sim_end_date.insert(0, "YYYY-MM-DD")
        
        ttk.Label(sim_frame, text="Estratégia:").grid(row=2, column=0, sticky=W, padx=PADX, pady=PADY)
        self.sim_strategy = ttk.Combobox(sim_frame, values=["LSTM", "RandomForest", "SentimentLSTM"]); 
        self.sim_strategy.grid(row=2, column=1, sticky=(W,E))
        self.sim_strategy.set("LSTM") # Valor Padrão

        self.sim_status_label = ttk.Label(sim_frame, text="Status: Desligado", foreground="red")
        self.sim_status_label.grid(row=3, column=0, columnspan=2, sticky=W, padx=PADX, pady=10)

        self.sim_toggle_btn = ttk.Button(sim_frame, text="Iniciar Simulação", command=self.toggle_simulation)
        self.sim_toggle_btn.grid(row=4, column=0, columnspan=2, sticky=(E, W), pady=5)

        # --- Sub-Frame 2b: Live Trading ---
        live_frame = ttk.LabelFrame(modules_frame, text="Módulo de Live Trading", padding=(10, 5))
        live_frame.grid(row=0, column=1, sticky=(N, S, E, W), padx=5)
        live_frame.grid_columnconfigure(1, weight=1)

        # (Inputs de Live Trade: Estratégia, Volume, etc.)
        ttk.Label(live_frame, text="Volume:").grid(row=0, column=0, sticky=W, padx=PADX, pady=PADY)
        self.live_volume = ttk.Entry(live_frame, width=12); self.live_volume.grid(row=0, column=1, sticky=W)
        self.live_volume.insert(0, "1")

        ttk.Label(live_frame, text="Estratégia:").grid(row=1, column=0, sticky=W, padx=PADX, pady=PADY)
        self.live_strategy = ttk.Combobox(live_frame, values=["LSTM", "RandomForest", "SentimentLSTM"]); 
        self.live_strategy.grid(row=1, column=1, sticky=(W,E))
        self.live_strategy.set("LSTM") # Valor Padrão

        self.live_status_label = ttk.Label(live_frame, text="Status: Desligado", foreground="red")
        self.live_status_label.grid(row=3, column=0, columnspan=2, sticky=W, padx=PADX, pady=10)

        self.live_toggle_btn = ttk.Button(live_frame, text="Iniciar Live Trade", command=self.toggle_live_trade)
        self.live_toggle_btn.grid(row=4, column=0, columnspan=2, sticky=(E, W), pady=5)


        # --- Frame 3: Resultados da Execução ---
        results_frame = ttk.LabelFrame(self, text="Resultados (Últimas 2 Execuções)", padding=(10, 5))
        results_frame.grid(row=2, column=0, columnspan=2, sticky=(N, S, E, W), padx=10, pady=5)
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(0, weight=1)

        self.results_text = scrolledtext.ScrolledText(results_frame, height=10, wrap=tk.WORD, state='disabled')
        self.results_text.grid(row=0, column=0, sticky=(N, S, E, W))

    # --- Lógica do Monitor de Mercado ---

    def toggle_auto_refresh(self):
        """
Inicia ou para o loop de auto-refresh em uma thread separada.
        """
        if self.auto_refresh_check.instate(['selected']):
            self.auto_refresh_running.set()
            self.auto_refresh_thread = threading.Thread(target=self._auto_refresh_loop, daemon=True)
            self.auto_refresh_thread.start()
            self.manual_refresh_btn.config(state='disabled')
        else:
            self.auto_refresh_running.clear()
            self.manual_refresh_btn.config(state='normal')

    def _auto_refresh_loop(self):
        """
Loop de thread que dispara a atualização de dados a cada 60 segundos.
        """
        while self.auto_refresh_running.is_set():
            self.update_market_data(from_auto_refresh=True)
            time.sleep(60) # Espera 1 minuto

    def update_market_data(self, from_auto_refresh=False):
        """
Dispara a busca de dados do mercado em uma thread para não bloquear a GUI.
        """
        if not from_auto_refresh:
            # Se for manual, desativa o botão para evitar cliques duplos
            self.manual_refresh_btn.config(state='disabled')
        
        # A busca de dados (rede/disco) deve ser em thread
        fetch_thread = threading.Thread(target=self._fetch_market_data_thread, daemon=True)
        fetch_thread.start()

    def _fetch_market_data_thread(self):
        """
Thread worker que realmente busca os dados.
        """
        try:
            asset = self.asset_var.get()
            # Chamada ao seu módulo de dados
            data = self.data_provider.get_market_data(asset) 
            # Formata os dados para exibição (ex: último preço, variação)
            # Exemplo simples:
            display_data = f"Ativo: {asset}\nÚltima Atualização: {datetime.now().strftime('%H:%M:%S')}\nDados: {data}"
        except Exception as e:
            display_data = f"Erro ao buscar dados para {asset}:\n{e}"
        
        # Envia a atualização de volta para a thread principal da GUI
        self.after(0, self._update_monitor_text, display_data)

    def _update_monitor_text(self, display_data):
        """
Atualiza o widget de texto do monitor (executado na thread da GUI).
        """
        self.monitor_text.config(state='normal')
        self.monitor_text.delete(1.0, tk.END)
        self.monitor_text.insert(tk.END, display_data)
        self.monitor_text.config(state='disabled')
        
        # Reativa o botão de refresh manual se não estiver em modo auto
        if not self.auto_refresh_running.is_set():
            self.manual_refresh_btn.config(state='normal')

    # --- Lógica da Simulação ---

    def toggle_simulation(self):
        """
Inicia ou para a thread de simulação.
        """
        if self.simulation_running.is_set():
            # --- PARAR SIMULAÇÃO ---
            if self.simulation_engine:
                self.simulation_engine.stop() # Requer que o engine tenha um método stop()
            self.simulation_running.clear()
            self.sim_toggle_btn.config(text="Iniciar Simulação", state='disabled') # Desabilita até a thread confirmar
            self.sim_status_label.config(text="Status: Parando...", foreground="orange")
        else:
            # --- INICIAR SIMULAÇÃO ---
            try:
                # Coleta e validação de parâmetros
                params = {
                    "start_date": self.sim_start_date.get(),
                    "end_date": self.sim_end_date.get(),
                    "strategy_name": self.sim_strategy.get(),
                    "asset": self.asset_var.get()
                    # Adicione outros parâmetros necessários
                }
                # TODO: Adicionar validação de datas e outros campos
                
                self.simulation_running.set()
                self.sim_toggle_btn.config(text="Parar Simulação")
                self.sim_status_label.config(text="Status: Executando...", foreground="green")
                
                # Inicia a thread de simulação
                self.simulation_thread = threading.Thread(
                    target=self._run_simulation_thread, 
                    args=(params,), 
                    daemon=True
                )
                self.simulation_thread.start()
                
            except Exception as e:
                messagebox.showerror("Erro na Simulação", f"Não foi possível iniciar: {e}")
                self.sim_status_label.config(text="Status: Erro", foreground="red")

    def _run_simulation_thread(self, params):
        """
Thread worker que executa a simulação.
        """
        try:
            # Instancia o motor com os parâmetros e o evento de parada
            self.simulation_engine = SimulationEngine(
                params=params, 
                stop_event=self.simulation_running
            )
            # O método run() do engine deve periodicamente checar o stop_event
            result = self.simulation_engine.run() 
            
            if self.simulation_running.is_set():
                # Simulação concluída (sem ser parada)
                status = "Concluída"
            else:
                # Simulação foi parada pelo usuário
                status = "Parada"
                result = {"status": "Parado pelo usuário"}

        except Exception as e:
            result = {"status": "Erro na execução", "error": str(e)}
            status = "Erro"
        
        # Prepara o dicionário de resultado para o log
        log_entry = {
            "timestamp": datetime.now(),
            "module": "Simulation",
            "params": params,
            "status": status,
            "result": result 
        }
        
        # Envia o resultado para a fila (thread-safe)
        self.execution_queue.put(log_entry)
        
        # Sinaliza o fim da execução (se não foi parada)
        self.simulation_running.clear()
        
        # Atualiza a GUI na thread principal
        self.after(0, self._on_simulation_finish, status)

    def _on_simulation_finish(self, status):
        """
Callback para atualizar a GUI quando a simulação termina.
        """
        self.sim_toggle_btn.config(text="Iniciar Simulação", state='normal')
        if status == "Concluída":
            self.sim_status_label.config(text="Status: Concluída", foreground="blue")
        elif status == "Parada":
            self.sim_status_label.config(text="Status: Desligado", foreground="red")
        elif status == "Erro":
            self.sim_status_label.config(text="Status: Erro na Execução", foreground="red")
        
        self.simulation_thread = None

    # --- Lógica do Live Trading ---

    def toggle_live_trade(self):
        """
Inicia ou para a thread de live trading.
        """
        if self.live_trade_running.is_set():
            # --- PARAR LIVE TRADE ---
            if self.live_trader:
                self.live_trader.stop() # Requer que o trader tenha um método stop()
            self.live_trade_running.clear()
            self.live_toggle_btn.config(text="Iniciar Live Trade", state='disabled')
            self.live_status_label.config(text="Status: Desconectando...", foreground="orange")
        else:
            # --- INICIAR LIVE TRADE ---
            try:
                params = {
                    "volume": int(self.live_volume.get()),
                    "strategy_name": self.live_strategy.get(),
                    "asset": self.asset_var.get()
                }

                self.live_trade_running.set()
                self.live_toggle_btn.config(text="Parar Live Trade")
                self.live_status_label.config(text="Status: Conectado", foreground="green")

                self.live_trade_thread = threading.Thread(
                    target=self._run_live_trade_thread, 
                    args=(params,), 
                    daemon=True
                )
                self.live_trade_thread.start()

            except Exception as e:
                messagebox.showerror("Erro no Live Trade", f"Não foi possível iniciar: {e}")
                self.live_status_label.config(text="Status: Erro", foreground="red")

    def _run_live_trade_thread(self, params):
        """
Thread worker que executa o live trading.
        """
        try:
            self.live_trader = LiveTrader(
                params=params, 
                stop_event=self.live_trade_running,
                execution_queue=self.execution_queue # Permite que o live trader reporte trades
            )
            # O método run() do LiveTrader deve ser um loop que checa o stop_event
            self.live_trader.run()
            
            status = "Desconectado"
            result = {"status": "Desconectado pelo usuário"}

        except Exception as e:
            result = {"status": "Erro fatal", "error": str(e)}
            status = "Erro"
        
        # Log de encerramento do módulo
        log_entry = {
            "timestamp": datetime.now(),
            "module": "LiveTrade_Session",
            "params": params,
            "status": status,
            "result": result
        }
        self.execution_queue.put(log_entry)
        
        self.live_trade_running.clear()
        self.after(0, self._on_live_trade_finish, status)

    def _on_live_trade_finish(self, status):
        """
Callback para atualizar a GUI quando o live trading termina.
        """
        self.live_toggle_btn.config(text="Iniciar Live Trade", state='normal')
        if status == "Erro":
            self.live_status_label.config(text="Status: Erro", foreground="red")
        else:
            self.live_status_label.config(text="Status: Desligado", foreground="red")
            
        self.live_trade_thread = None

    # --- Gerenciamento de Resultados e Fechamento ---

    def process_execution_queue(self):
        """
Verifica a fila de resultados e atualiza a GUI.
        """
        try:
            while True:
                # Obtém o resultado da fila (thread-safe)
                log_entry = self.execution_queue.get_nowait()
                
                # Adiciona ao log completo
                self.all_executions_data.append(log_entry)
                
                # Atualiza a exibição na tela (apenas os 2 últimos)
                self.update_results_display()
                
        except queue.Empty:
            # A fila está vazia, agenda a próxima verificação
            self.after(100, self.process_execution_queue)

    def update_results_display(self):
        """
Atualiza o painel de resultados com as 2 últimas entradas.
        """
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)
        
        # Pega os 2 últimos, ou menos se não houver 2
        last_two_results = self.all_executions_data[-2:]
        
        for entry in last_two_results:
            # Formatação simples (pode ser melhorada)
            self.results_text.insert(tk.END, f"--- {entry['timestamp']} | Módulo: {entry['module']} ---\n")
            self.results_text.insert(tk.END, f"Status: {entry['status']}\n")
            self.results_text.insert(tk.END, f"Parâmetros: {entry.get('params', 'N/A')}\n")
            self.results_text.insert(tk.END, f"Resultado: {entry.get('result', 'N/A')}\n\n")
            
        self.results_text.config(state='disabled')
        self.results_text.see(tk.END) # Rola para o final

    def on_close(self):
        """
Executado ao fechar a janela (clicar no 'X').
        """
        if messagebox.askokcancel("Sair", "Deseja fechar o dashboard? Os logs de execução serão salvos."):
            # 1. Sinaliza para todas as threads pararem
            self.auto_refresh_running.clear()
            self.simulation_running.clear()
            self.live_trade_running.clear()
            
            if self.live_trader:
                self.live_trader.stop()
            if self.simulation_engine:
                self.simulation_engine.stop()
                
            # 2. Salva o log completo em CSV
            try:
                if self.all_executions_data:
                    df = pd.DataFrame(self.all_executions_data)
                    # Normaliza colunas aninhadas (params, result) se necessário
                    # Para simplificar, vamos salvar como está (pode ter dicts)
                    # df = pd.json_normalize(self.all_executions_data) # Opção mais robusta
                    
                    filename = f"execution_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    df.to_csv(filename, index=False, sep=';', decimal=',')
                    print(f"Log salvo em: {filename}")
                else:
                    print("Nenhuma execução para salvar.")
                    
            except Exception as e:
                print(f"Erro ao salvar o log CSV: {e}")
                messagebox.showerror("Erro de Log", f"Não foi possível salvar o log: {e}")

            # 3. Fecha a janela
            self.destroy()

# --- Ponto de Entrada ---
if __name__ == "__main__":
    try:
        app = UnifiedDashboard()
        app.mainloop()
    except Exception as e:
        # Um "catch-all" final para erros de inicialização
        messagebox.showerror("Erro Fatal de Inicialização", 
                             f"A aplicação não pôde ser iniciada:\n{e}\n\n"
                             "Verifique as dependências e a configuração.")