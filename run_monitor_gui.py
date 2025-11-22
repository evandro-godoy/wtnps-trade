#!/usr/bin/env python
# run_monitor_gui.py

"""
Script de execução da Interface Gráfica do Monitor em Tempo Real.

Suporta dois modos de operação:

1. LIVE TRADING (padrão):
   poetry run python run_monitor_gui.py --mode live

2. REPLAY HISTÓRICO:
   poetry run python run_monitor_gui.py --mode replay --ticker WDO$ --date 2025-11-20 --time 09:00 --timeframe M5 --speed 2.0

Argumentos:
    --mode: 'live' (padrão) ou 'replay'
    --ticker: Símbolo do ativo (padrão: WDO$)
    --date: Data para replay no formato YYYY-MM-DD (padrão: ontem)
    --time: Hora de início UTC no formato HH:MM (padrão: 09:00)
    --timeframe: Timeframe (M1, M5, M15, etc) (padrão: M5)
    --speed: Multiplicador de velocidade (0.5 - 10.0) (padrão: 1.0)

Exemplos:
    # Modo live
    poetry run python run_monitor_gui.py
    
    # Replay 2x speed do dia 20/11
    poetry run python run_monitor_gui.py --mode replay --date 2025-11-20 --speed 2.0
    
    # Replay WIN$ em M15
    poetry run python run_monitor_gui.py --mode replay --ticker WIN$ --timeframe M15
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Adiciona o diretório raiz ao path para imports
sys.path.insert(0, str(Path(__file__).parent))

from src.gui.monitor_ui import main


def parse_arguments():
    """Parse argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description='Monitor em Tempo Real - WTNPS Trade',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--mode',
        choices=['live', 'replay'],
        default='live',
        help='Modo de operação: live (tempo real) ou replay (histórico)'
    )
    
    parser.add_argument(
        '--ticker',
        default='WDO$',
        help='Símbolo do ativo (ex: WDO$, WIN$)'
    )
    
    parser.add_argument(
        '--date',
        default=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
        help='Data para replay (YYYY-MM-DD). Padrão: ontem'
    )
    
    parser.add_argument(
        '--time',
        default='09:00',
        help='Hora de início UTC para replay (HH:MM). Padrão: 09:00'
    )
    
    parser.add_argument(
        '--timeframe',
        default='M5',
        choices=['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'],
        help='Timeframe dos candles. Padrão: M5'
    )
    
    parser.add_argument(
        '--speed',
        type=float,
        default=1.0,
        help='Velocidade do replay (0.5 a 10.0). Padrão: 1.0'
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    
    # Monta configuração de replay
    replay_config = {
        'ticker': args.ticker,
        'start_date': args.date,
        'start_time': args.time,
        'timeframe': args.timeframe,
        'speed': args.speed
    }
    
    # Executa GUI com modo e configuração
    main(mode=args.mode, replay_config=replay_config)
