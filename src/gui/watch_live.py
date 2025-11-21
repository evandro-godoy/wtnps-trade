import sys
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ReloadHandler(FileSystemEventHandler):
    def __init__(self, target_file):
        self.target_file = target_file
        self.process = None
        self.start_process()

    def start_process(self):
        """Inicia o script da interface."""
        if self.process:
            self.process.kill() # Fecha a janela anterior
        
        print(f"⚡ Iniciando/Reiniciando {self.target_file}...")
        # Abre o design_ui.py como um novo processo
        self.process = subprocess.Popen([sys.executable, self.target_file])

    def on_modified(self, event):
        """Detecta quando o arquivo foi salvo."""
        if event.src_path.endswith(self.target_file):
            self.start_process()

if __name__ == "__main__":
    TARGET_FILE = "src/gui/monitor_ui.py" # O arquivo que você quer editar
    
    event_handler = ReloadHandler(TARGET_FILE)
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.start()

    print(f"👀 Monitorando alterações em {TARGET_FILE}. Pressione Ctrl+C para sair.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if event_handler.process:
            event_handler.process.kill()
    observer.join()