import yaml
import logging
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import pytz
import MetaTrader5 as mt5

# --- ALTERAÇÃO IMPORTANTE ---
# 1. Define explicitamente o backend gráfico para o Matplotlib antes de importar o pyplot.
# Isso garante que ele saiba como desenhar uma janela.
import matplotlib
matplotlib.use('TkAgg')
# --- FIM DA ALTERAÇÃO ---

import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Configuração do logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class MarketReplayEngine:
    """
    Motor de replay de mercado que busca dados de tick do MetaTrader 5,
    agrega-os em candles e exibe um gráfico animado.
    """

    def __init__(self, ticker: str, replay_date_str: str):
        self.ticker = ticker
        self.replay_date = datetime.strptime(replay_date_str, "%Y-%m-%d")
        self.ticks_df = None
        self.fig, self.ax = None, None

        timezone = pytz.timezone("Etc/UTC")
        self.start_time_utc = timezone.localize(self.replay_date)
        self.end_time_utc = timezone.localize(
            self.replay_date + timedelta(days=1) - timedelta(seconds=1)
        )
        self.current_sim_time = self.start_time_utc

    def _fetch_tick_data(self) -> bool:
        """Busca todos os dados de tick para o dia do replay."""
        logging.info(f"Conectando ao MetaTrader 5 para buscar dados de tick...")
        if not mt5.initialize():
            logging.error(f"Falha na inicialização do MT5: {mt5.last_error()}")
            return False

        logging.info(f"Buscando ticks para {self.ticker} em {self.replay_date.date()}...")
        ticks = mt5.copy_ticks_range(
            self.ticker, self.start_time_utc, self.end_time_utc, mt5.COPY_TICKS_ALL
        )
        mt5.shutdown()

        if ticks is None or len(ticks) == 0:
            logging.error(f"Nenhum dado de tick encontrado para {self.ticker} na data especificada.")
            return False

        self.ticks_df = pd.DataFrame(ticks)
        self.ticks_df["time"] = pd.to_datetime(self.ticks_df["time"], unit="s", utc=True)
        self.ticks_df.set_index("time", inplace=True)
        logging.info(f"{len(self.ticks_df)} ticks carregados com sucesso.")
        return True

    def _update_plot(self, frame):
        """Função chamada a cada intervalo de animação para atualizar o gráfico."""
        self.current_sim_time += timedelta(seconds=30)

        if self.current_sim_time > self.end_time_utc:
            logging.info("\nFim do dia de replay. Fechando o gráfico...")
            plt.close(self.fig)
            return

        current_ticks = self.ticks_df[self.ticks_df.index <= self.current_sim_time]
        if current_ticks.empty:
            return

        candles_m5 = current_ticks["last"].resample("5min").ohlc().dropna()
        if candles_m5.empty:
            return

        candles_m5["sma9"] = candles_m5["close"].rolling(window=9).mean()
        candles_m5["ema21"] = candles_m5["close"].ewm(span=21, adjust=False).mean()
        candles_m5["ema50"] = candles_m5["close"].ewm(span=50, adjust=False).mean()
        candles_m5["ema200"] = candles_m5["close"].ewm(span=200, adjust=False).mean()

        self.ax.clear()

        addplots = [
            mpf.make_addplot(candles_m5["sma9"], color="red"),
            mpf.make_addplot(candles_m5["ema21"], color="blue"),
            mpf.make_addplot(candles_m5["ema50"], color="orange"),
            mpf.make_addplot(candles_m5["ema200"], color="black"),
        ]

        mpf.plot(
            candles_m5,
            type="candle",
            style=self.chart_style,
            ax=self.ax,
            addplot=addplots,
            update_width_config=dict(candle_linewidth=1.5),
        )

        last_candle = candles_m5.iloc[-1]
        self.ax.set_title(
            f"Replay de Mercado - {self.ticker} (M5) - Simulado até: {self.current_sim_time.strftime('%H:%M:%S')}"
        )
        print(
            f"\rSim Time: {self.current_sim_time.strftime('%H:%M:%S')} | "
            f"Último Candle: O={last_candle.open:.2f} H={last_candle.high:.2f} L={last_candle.low:.2f} C={last_candle.close:.2f}",
            end="",
        )

    def run_replay(self):
        """Inicia e executa o motor de replay."""
        if not self._fetch_tick_data():
            return

        logging.info("Dados de tick carregados. Configurando o gráfico...")

        self.chart_style = mpf.make_mpf_style(
            base_mpf_style="default",
            marketcolors=mpf.make_marketcolors(up="g", down="r", inherit=True),
            gridstyle="-",
            facecolor="white",
        )
        
        self.fig, self.ax = plt.subplots(figsize=(15, 7))
        self.fig.suptitle(f"Replay de Mercado para {self.ticker}", fontsize=16)
        
        logging.info("Gráfico configurado. Iniciando a animação...")

        ani = FuncAnimation(
            self.fig, self._update_plot, interval=200, save_count=1000
        )
        
        logging.info("Mostrando o gráfico. A janela deve aparecer agora...")
        plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Motor de Replay de Mercado com MetaTrader 5.")
    parser.add_argument("--ticker", required=True, type=str, help="O ticker do ativo para o replay (ex: 'WIN$').")
    parser.add_argument("--date", required=True, type=str, help="A data para o replay no formato 'YYYY-MM-DD'.")
    args = parser.parse_args()

    with open("configs/main.yaml", "r") as file:
        config = yaml.safe_load(file)
    
    configured_tickers = [asset['ticker'] for asset in config['assets']]
    if args.ticker not in configured_tickers:
        print(f"Erro: Ticker '{args.ticker}' não encontrado na lista de ativos em configs/main.yaml.")
        exit()

    engine = MarketReplayEngine(ticker=args.ticker, replay_date_str=args.date)
    engine.run_replay()