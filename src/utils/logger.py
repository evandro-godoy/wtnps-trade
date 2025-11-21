# src/utils/logger.py
import logging
import os
import sys
from datetime import datetime

def setup_logging(log_file_prefix: str = 'log') -> None:
    """
    Configura o sistema de logging para salvar em arquivo e exibir no console.
    
    O nome do arquivo de log incluirá o prefixo e um timestamp.
    """
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Gerar nome do arquivo de log com prefixo e data/hora
    log_filename = f"{log_file_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_filepath = os.path.join(log_dir, log_filename)

    # Remove handlers existentes para evitar duplicação
    for handler in logging.root.handlers[:]:
        handler.close()
        logging.root.removeHandler(handler)

    # Configura o logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(log_filepath), # Salva no arquivo
            logging.StreamHandler(sys.stdout)  # Exibe no console
        ]
    )
    logging.info(f"Logging configurado. Salvando em: {log_filepath}")


def get_logger(name: str = 'wtnps') -> logging.Logger:
    """Retorna um logger configurado. Garante configuração única.

    Se nenhum handler estiver presente no root, invoca setup_logging.
    """
    if not logging.getLogger().handlers:
        setup_logging('log')
    return logging.getLogger(name)

# Exporta instância padrão utilizada pelo projeto
if not logging.getLogger().handlers:
    setup_logging('log')
logger: logging.Logger = logging.getLogger('wtnps')

__all__ = ['setup_logging', 'get_logger', 'logger']