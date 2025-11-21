#!/usr/bin/env python
# run_monitor_gui.py

"""
Script de execução da Interface Gráfica do Monitor em Tempo Real.

Este script inicializa e executa a GUI do monitor que controla o
RealTimeMonitor e exibe alertas de trading em tempo real.

Uso:
    poetry run python run_monitor_gui.py

Controles:
    - Botão "INICIAR MONITORAMENTO": Inicia o monitor em background
    - Botão "PARAR MONITORAMENTO": Para o monitor graciosamente
    - Botão "Limpar Logs": Remove todos os logs da tela
    - Fechar janela: Para o monitor (se rodando) e encerra

Requisitos:
    - Modelo treinado em models/
    - MetaTrader 5 aberto e logado
    - Configuração válida em configs/main.yaml
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
sys.path.insert(0, str(Path(__file__).parent))

from src.gui.monitor_ui import main


if __name__ == "__main__":
    main()
