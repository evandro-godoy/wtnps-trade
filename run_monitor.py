#!/usr/bin/env python
# run_monitor.py

"""
Script de execução do Monitor em Tempo Real.

Este script inicializa e executa o motor de monitoramento que analisa
o mercado em tempo real usando modelos ML treinados (LSTMVolatilityStrategy)
e gera alertas de trading baseados em probabilidades de explosão de volatilidade.

Uso:
    poetry run python run_monitor.py

Controles:
    - Ctrl+C: Interrompe graciosamente o monitoramento
    
Configuração:
    Edite os parâmetros abaixo ou use o arquivo configs/main.yaml
"""

import logging
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
sys.path.insert(0, str(Path(__file__).parent))

from src.live.monitor_engine import RealTimeMonitor


# ===================================================================
# CONFIGURAÇÕES DO MONITOR
# ===================================================================

TICKER = "WDO$"                    # Ativo a monitorar
TIMEFRAME = "M5"                   # Timeframe (M1, M5, M15, M30, H1, H4, D1)
THRESHOLD_ALERT = 0.65             # Probabilidade mínima para ALERTA (>65%)
THRESHOLD_LOG = 0.55               # Probabilidade mínima para LOG (>55%)
BUFFER_SIZE = 500                  # Quantidade de candles no buffer
CONFIG_PATH = "configs/main.yaml"  # Arquivo de configuração


# ===================================================================
# CONFIGURAÇÃO DE LOGGING
# ===================================================================

def setup_logging():
    """Configura o sistema de logging com formatação aprimorada."""
    
    # Formato detalhado com timestamp
    log_format = '%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Configuração do root logger
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout)  # Console output
        ]
    )
    
    # Define níveis específicos para módulos
    logging.getLogger('src.live.monitor_engine').setLevel(logging.INFO)
    logging.getLogger('src.data_handler.provider').setLevel(logging.WARNING)  # Reduz verbosidade do provider
    logging.getLogger('tensorflow').setLevel(logging.ERROR)  # Silencia TensorFlow warnings
    logging.getLogger('matplotlib').setLevel(logging.WARNING)


# ===================================================================
# FUNÇÃO PRINCIPAL
# ===================================================================

def main():
    """Função principal de execução do monitor."""
    
    # Configura logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("WTNPS-TRADE - REAL-TIME MONITORING SYSTEM")
    logger.info("=" * 80)
    
    try:
        # Cria instância do monitor
        monitor = RealTimeMonitor(
            ticker=TICKER,
            timeframe_str=TIMEFRAME,
            threshold_alert=THRESHOLD_ALERT,
            threshold_log=THRESHOLD_LOG,
            buffer_size=BUFFER_SIZE,
            config_path=CONFIG_PATH
        )
        
        # Inicia monitoramento (loop infinito)
        monitor.start()
        
    except FileNotFoundError as e:
        logger.error(f"Arquivo não encontrado: {e}")
        logger.error("Certifique-se de que o modelo foi treinado e existe em 'models/'")
        sys.exit(1)
        
    except ConnectionError as e:
        logger.error(f"Erro de conexão: {e}")
        logger.error("Verifique se o MetaTrader 5 está aberto e logado.")
        sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("\nMonitoramento interrompido pelo usuário.")
        sys.exit(0)
        
    except Exception as e:
        logger.critical(f"Erro crítico: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
