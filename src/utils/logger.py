import logging
import os
from datetime import datetime

def setup_logging(log_file_prefix='log'):
    """
    Configura o sistema de logging para salvar em arquivo e exibir no console.
    
    O nome do arquivo de log incluirá o prefixo e um timestamp.
    """
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Gerar nome do arquivo de log com prefixo e data/hora
    log_filename = f"{log_file_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_filepath = os.path.join(log_dir, log_filename)

    # Remove handlers existentes para evitar duplicação (útil em re-execuções)
    for handler in logging.root.handlers[:]:
        handler.close()
        logging.root.removeHandler(handler)

    # Configura o logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_filepath), # Salva no arquivo
            logging.StreamHandler()            # Exibe no console
        ]
    )
    logging.info(f"Logging configurado. Salvando em: {log_filepath}")