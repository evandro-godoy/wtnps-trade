# src/live/replay_engine.py

"""
Motor de Replay de Mercado - Simulação de Dados Históricos.

Utiliza SimulationEngine para processar dados históricos em modo replay,
permitindo controle de velocidade, pausa/resume e navegação temporal.
"""

import logging
import threading
import time
import pytz
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable, Dict
import pandas as pd

from src.simulation.engine import SimulationEngine
from src.data_handler.provider import MetaTraderProvider

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


class ReplayEngine:
    """
    Motor de Replay para simulação de mercado com dados históricos.
    
    Wraps SimulationEngine para fornecer controle temporal:
    - Play/Pause/Step (manual)
    - Controle de velocidade (0.5x - 10x)
    - Pre-fetching de dados com callback de progresso
    - Compatibilidade com interface de RealTimeMonitor
    
    Attributes:
        ticker (str): Símbolo do ativo
        start_date (str): Data inicial (YYYY-MM-DD)
        end_date (str): Data final (YYYY-MM-DD)
        start_time (str): Hora inicial UTC (HH:MM)
        timeframe_str (str): Timeframe ("M5", "M15", etc)
        speed_multiplier (float): Multiplicador de velocidade
        running (bool): Flag de execução
        paused (bool): Flag de pausa
        current_time (datetime): Timestamp atual do replay
        simulation_engine (SimulationEngine): Engine de simulação
    """
    
    def __init__(
        self,
        ticker: str = "WDO$",
        start_date: str = "2025-11-20",
        end_date: str = "2025-11-21",
        start_time: str = "09:00",
        timeframe_str: str = "M5",
        buffer_size: int = 500,
        speed_multiplier: float = 1.0,
        config_path: str = "configs/main.yaml",
        ui_callback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None
    ):
        """
        Inicializa o motor de replay.
        
        Args:
            ticker: Símbolo do ativo
            start_date: Data inicial (YYYY-MM-DD)
            end_date: Data final (YYYY-MM-DD)
            start_time: Hora inicial UTC (HH:MM)
            timeframe_str: Timeframe ("M5", "M15", etc)
            buffer_size: Tamanho do buffer para SimulationEngine
            speed_multiplier: Velocidade de replay (0.5 a 10.0)
            config_path: Caminho para arquivo de configuração
            ui_callback: Função de callback para UI
            progress_callback: Função de callback para progresso
        """
        logger.info("=" * 80)
        logger.info("INICIALIZANDO REPLAY ENGINE")
        logger.info("=" * 80)
        
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.start_time = start_time
        self.timeframe_str = timeframe_str
        self.buffer_size = buffer_size
        self.speed_multiplier = max(0.1, min(10.0, speed_multiplier))
        self.config_path = config_path
        self.ui_callback = ui_callback
        self.progress_callback = progress_callback
        
        # Estado do replay
        self.running = False
        self.paused = False
        self.current_time = None
        self.end_time = None
        self.replay_thread = None
        
        # Mapeamento de timeframe para timedelta
        self.timeframe_deltas = {
            "M1": timedelta(minutes=1),
            "M5": timedelta(minutes=5),
            "M15": timedelta(minutes=15),
            "M30": timedelta(minutes=30),
            "H1": timedelta(hours=1),
            "H4": timedelta(hours=4),
            "D1": timedelta(days=1),
            "W1": timedelta(weeks=1),
            "MN1": timedelta(days=30)
        }
        
        self.candle_interval = self.timeframe_deltas.get(timeframe_str)
        if not self.candle_interval:
            raise ValueError(f"Timeframe inválido: {timeframe_str}")
        
        # Inicializa SimulationEngine
        logger.info("Inicializando SimulationEngine...")
        self.simulation_engine = SimulationEngine(config_path=config_path)
        logger.info("✓ SimulationEngine inicializado")
        
        # Inicializa provider para pre-fetching
        logger.info("Inicializando MetaTrader Provider...")
        self.provider = MetaTraderProvider()
        if not self.provider.is_connected():
            raise RuntimeError("Falha ao conectar ao MetaTrader 5")
        logger.info("✓ MT5 conectado")
        
        # Pre-fetch dados históricos
        self._prefetch_data()
        
        logger.info(f"""
Configurações do Replay:
  - Ticker: {self.ticker}
  - Período: {self.start_date} {self.start_time} até {self.end_date}
  - Timeframe: {self.timeframe_str}
  - Velocidade: {self.speed_multiplier}x
  - Candles disponíveis: {len(self.historical_data) if hasattr(self, 'historical_data') else 0}
        """)
        
        logger.info("=" * 80)
    
    def _prefetch_data(self):
        """Pre-carrega dados históricos do período completo."""
        logger.info(f"Pre-fetching dados de {self.start_date} até {self.end_date}...")
        
        try:
            # Monta datetime de início e fim
            start_dt_str = f"{self.start_date} {self.start_time}:00"
            end_dt_str = f"{self.end_date} 23:59:59"
            
            # Converte timeframe para constante MT5
            import MetaTrader5 as mt5
            tf_map = {
                "M1": mt5.TIMEFRAME_M1,
                "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15,
                "M30": mt5.TIMEFRAME_M30,
                "H1": mt5.TIMEFRAME_H1,
                "H4": mt5.TIMEFRAME_H4,
                "D1": mt5.TIMEFRAME_D1,
                "W1": mt5.TIMEFRAME_W1,
                "MN1": mt5.TIMEFRAME_MN1
            }
            timeframe_mt5 = tf_map.get(self.timeframe_str)
            
            # Busca dados
            self.historical_data = self.provider.get_data(
                ticker=self.ticker,
                start_date=start_dt_str,
                end_date=end_dt_str,
                timeframe=timeframe_mt5
            )
            
            if self.historical_data is None or len(self.historical_data) == 0:
                raise ValueError(f"Nenhum dado histórico encontrado para {self.ticker} no período especificado")
            
            logger.info(f"✓ {len(self.historical_data)} candles carregados")
            
            # Define timestamps de início e fim do replay
            self.current_time = self.historical_data.index[0]
            self.end_time = self.historical_data.index[-1]
            
            logger.info(f"  Período: {self.current_time} até {self.end_time}")
            
        except Exception as e:
            logger.error(f"Erro ao pre-carregar dados: {e}")
            raise
    
    def start(self):
        """Inicia replay em modo contínuo (play)."""
        if self.running:
            logger.warning("Replay já está em execução")
            return
        
        logger.info("Iniciando replay em modo contínuo...")
        self.running = True
        self.paused = False
        
        # Executa em thread separada
        self.replay_thread = threading.Thread(target=self._run_replay, daemon=True)
        self.replay_thread.start()
    
    def _run_replay(self):
        """Loop principal do replay (executado em thread)."""
        logger.info("Loop de replay iniciado")
        
        candle_count = 0
        total_candles = len(self.historical_data)
        
        try:
            while self.running and self.current_time <= self.end_time:
                # Verifica pausa
                while self.paused and self.running:
                    time.sleep(0.1)
                
                if not self.running:
                    break
                
                # Processa candle atual
                result = self.step()
                
                if result is None:
                    break
                
                candle_count += 1
                
                # Callback de progresso
                if self.progress_callback and candle_count % 10 == 0:
                    self.progress_callback(candle_count, total_candles)
                
                # Sleep baseado na velocidade
                sleep_time = self._calculate_sleep_time()
                time.sleep(sleep_time)
            
            # Replay finalizado
            logger.info(f"Replay finalizado: {candle_count} candles processados")
            self.running = False
            
            # Callback de progresso final
            if self.progress_callback:
                self.progress_callback(total_candles, total_candles)
            
        except Exception as e:
            logger.error(f"Erro no loop de replay: {e}", exc_info=True)
            self.running = False
    
    def _calculate_sleep_time(self) -> float:
        """Calcula tempo de sleep baseado no timeframe e velocidade."""
        # Tempo base em segundos (para simular tempo real)
        base_seconds = self.candle_interval.total_seconds()
        
        # Ajusta pela velocidade (velocidade maior = sleep menor)
        adjusted_seconds = base_seconds / self.speed_multiplier
        
        # Limita a um mínimo razoável (0.01s = 10ms)
        return max(0.01, adjusted_seconds)
    
    def step(self) -> Optional[Dict]:
        """
        Avança um candle manualmente.
        
        Returns:
            Dict com dados do candle processado ou None se fim do replay
        """
        if self.current_time > self.end_time:
            logger.info("Fim do replay alcançado")
            return None
        
        try:
            # Executa simulação para o timestamp atual
            result = self.simulation_engine.run_simulation_cycle(
                asset_symbol=self.ticker,
                timeframe_str=self.timeframe_str,
                target_datetime_local=self.current_time
            )
            
            # Converte resultado para formato de candle_data
            candle_data = self._convert_result_to_candle_data(result)
            
            # Callback para UI
            if self.ui_callback and candle_data:
                self.ui_callback(candle_data)
            
            # Avança para próximo candle
            self.current_time += self.candle_interval
            
            return candle_data
            
        except Exception as e:
            logger.error(f"Erro ao processar step em {self.current_time}: {e}", exc_info=True)
            return None
    
    def _convert_result_to_candle_data(self, result: Dict) -> Optional[Dict]:
        """
        Converte resultado do SimulationEngine para formato de candle_data.
        
        Args:
            result: Resultado de run_simulation_cycle()
        
        Returns:
            Dict no formato esperado pela UI (compatível com RealTimeMonitor)
        """
        if not result or result.get('ai_signal') is None:
            return None
        
        try:
            # Extrai dados do resultado
            ai_signal = result.get('ai_signal', 'HOLD')
            setup_valid = result.get('setup_valid', False)
            final_decision = result.get('final_decision', 'HOLD')
            price = result.get('price', 0.0)
            
            # Indicadores
            indicators = result.get('indicators', {})
            
            # Determina probabilidade (simulada baseada em setup)
            probability = 0.70 if setup_valid else 0.50
            
            # Determina direção (CALL/PUT baseado em sinal)
            if ai_signal == 'COMPRA':
                direction = 'CALL'
            elif ai_signal == 'VENDA':
                direction = 'PUT'
            else:
                direction = 'HOLD'
            
            # Determina tipo de mensagem
            if probability >= 0.65 and setup_valid:
                msg_type = 'ALERT'
            elif probability >= 0.55:
                msg_type = 'INFO'
            else:
                msg_type = 'TICK'
            
            # Monta mensagem
            if msg_type == 'ALERT':
                message = f"🚨 ALERTA {direction} ({probability*100:.1f}%) | Sinal: {ai_signal} | Setup: {'✅ Válido' if setup_valid else '❌ Inválido'} | Preço: {price:.2f}"
            elif msg_type == 'INFO':
                message = f"📊 Sinal {direction} ({probability*100:.1f}%) | {ai_signal} | Preço: {price:.2f}"
            else:
                message = f"Tick | Preço: {price:.2f}"
            
            # Busca dados OHLC do candle atual do historical_data
            if self.current_time in self.historical_data.index:
                candle = self.historical_data.loc[self.current_time]
                open_price = candle.get('open', price)
                high_price = candle.get('high', price)
                low_price = candle.get('low', price)
                close_price = candle.get('close', price)
                volume = candle.get('volume', 0)
            else:
                open_price = high_price = low_price = close_price = price
                volume = 0
            
            # Monta candle_data no formato esperado
            candle_data = {
                'timestamp': self.current_time,
                'open': float(open_price),
                'high': float(high_price),
                'low': float(low_price),
                'close': float(close_price),
                'volume': int(volume),
                'probability': probability * 100,
                'direction': direction,
                'ema_20': indicators.get('ema_20', 0.0),
                'sma_20': indicators.get('sma_20', 0.0),
                'sma_50': indicators.get('sma_50', 0.0),
                'trend': indicators.get('trend', 'LATERAL'),
                'trend_strength': indicators.get('trend_strength', 'FRACA'),
                'rsi': indicators.get('rsi', 50.0),
                'rsi_condition': indicators.get('rsi_condition', 'NEUTRO'),
                'support': indicators.get('support', 0.0),
                'resistance': indicators.get('resistance', 0.0),
                'pattern': indicators.get('pattern', 'NEUTRO'),
                'signal_valid': setup_valid,
                'validation_reason': result.get('validation_reason', ''),
                'type': msg_type,
                'message': message
            }
            
            return candle_data
            
        except Exception as e:
            logger.error(f"Erro ao converter resultado: {e}", exc_info=True)
            return None
    
    def pause(self):
        """Pausa o replay."""
        if not self.running:
            logger.warning("Replay não está em execução")
            return
        
        self.paused = True
        logger.info("Replay pausado")
    
    def resume(self):
        """Resume o replay após pausa."""
        if not self.running:
            logger.warning("Replay não está em execução")
            return
        
        self.paused = False
        logger.info("Replay resumido")
    
    def set_speed(self, multiplier: float):
        """
        Altera a velocidade do replay.
        
        Args:
            multiplier: Multiplicador de velocidade (0.1 a 10.0)
        """
        self.speed_multiplier = max(0.1, min(10.0, multiplier))
        logger.info(f"Velocidade alterada para {self.speed_multiplier}x")
    
    def stop(self):
        """Para o replay completamente."""
        logger.info("Parando replay...")
        self.running = False
        self.paused = False
        
        # Aguarda thread terminar
        if self.replay_thread and self.replay_thread.is_alive():
            self.replay_thread.join(timeout=5.0)
        
        logger.info("Replay parado")
    
    def is_connected(self) -> bool:
        """Verifica se o provider está conectado (compatibilidade com RealTimeMonitor)."""
        return self.provider.is_connected()
