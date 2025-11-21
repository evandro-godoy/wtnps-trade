# src/live/monitor_engine.py

import time
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from pathlib import Path
import yaml
import MetaTrader5 as mt5
from typing import Optional

from src.data_handler.provider import MetaTraderProvider
from src.strategies.lstm_volatility import LSTMVolatilityStrategy
from src.analysis.context_analyzer import MarketContextAnalyzer

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


class RealTimeMonitor:
    """
    Motor de Monitoramento em Tempo Real para geração de alertas ML.
    
    Monitora o mercado em loop infinito, processando novos candles conforme
    são formados e gerando alertas baseados no modelo LSTM de volatilidade.
    
    Attributes:
        ticker (str): Símbolo do ativo a monitorar (ex: "WDO$")
        timeframe (int): Timeframe MT5 para monitoramento (ex: mt5.TIMEFRAME_M5)
        timeframe_str (str): String do timeframe (ex: "M5")
        threshold_alert (float): Probabilidade mínima para gerar ALERTA (>65%)
        threshold_log (float): Probabilidade mínima para gerar LOG (>55%)
        buffer_size (int): Quantidade de candles no buffer histórico
        buffer_df (pd.DataFrame): Buffer com dados OHLCV
        provider (MetaTraderProvider): Provedor de dados MT5
        strategy (LSTMVolatilityStrategy): Estratégia ML carregada
        model_path_prefix (str): Caminho base para carregar modelo/scaler
    """
    
    def __init__(
        self,
        ticker: str = "WDO$",
        timeframe_str: str = "M5",
        threshold_alert: float = 0.65,
        threshold_log: float = 0.55,
        buffer_size: int = 500,
        config_path: str = "configs/main.yaml",
        ui_callback: Optional[callable] = None
    ):
        """
        Inicializa o monitor em tempo real.
        
        Args:
            ticker: Símbolo do ativo
            timeframe_str: Timeframe em string ("M5", "M15", etc.)
            threshold_alert: Probabilidade para gerar alerta (default: 0.65)
            threshold_log: Probabilidade para gerar log (default: 0.55)
            buffer_size: Quantidade de velas no buffer histórico
            config_path: Caminho para o arquivo de configuração
            ui_callback: Função de callback para atualização de UI (opcional)
        """
        logger.info("=" * 80)
        logger.info("INICIALIZANDO REAL-TIME MONITOR")
        logger.info("=" * 80)
        
        self.ticker = ticker
        self.timeframe_str = timeframe_str
        self.timeframe = self._get_mt5_timeframe(timeframe_str)
        self.threshold_alert = threshold_alert
        self.threshold_log = threshold_log
        self.buffer_size = buffer_size
        self.buffer_df: Optional[pd.DataFrame] = None
        self.ui_callback = ui_callback
        self.running = False
        
        # Inicializa analisador de contexto técnico
        logger.info("Inicializando MarketContextAnalyzer...")
        self.context_analyzer = MarketContextAnalyzer(
            ema_fast=9,
            sma_fast=20,
            sma_slow=50,
            sma_lookback=200,
            rsi_period=14,
            lookback_levels=20,
            strong_candle_threshold=0.65
        )
        logger.info("✓ Analisador de contexto inicializado")
        
        # Carrega configuração
        logger.info(f"Carregando configuração de: {config_path}")
        self.config = self._load_config(config_path)
        
        # Inicializa provider MT5
        logger.info("Inicializando MetaTrader 5 Provider...")
        self.provider = MetaTraderProvider()
        if not self.provider.is_connected():
            raise ConnectionError("Falha ao conectar ao MetaTrader 5. Verifique se o terminal está aberto e logado.")
        logger.info("✓ MT5 conectado com sucesso")
        
        # Inicializa e carrega a estratégia
        logger.info("Carregando estratégia LSTMVolatilityStrategy...")
        self.strategy = self._load_strategy()
        logger.info("✓ Estratégia carregada com sucesso")
        
        # Carrega modelo treinado
        logger.info("Carregando modelo ML treinado...")
        self.model_path_prefix = self._get_model_path()
        self.strategy.model = LSTMVolatilityStrategy.load(self.model_path_prefix)
        logger.info(f"✓ Modelo carregado de: {self.model_path_prefix}")
        
        logger.info(f"""
Configurações do Monitor:
  - Ticker: {self.ticker}
  - Timeframe: {self.timeframe_str}
  - Threshold Alerta: {self.threshold_alert * 100:.0f}%
  - Threshold Log: {self.threshold_log * 100:.0f}%
  - Buffer Size: {self.buffer_size} candles
  - Lookback LSTM: {self.strategy.lookback} períodos
        """)
        
        logger.info("=" * 80)
    
    def _load_config(self, config_path: str) -> dict:
        """Carrega o arquivo de configuração YAML."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return config
    
    def _get_mt5_timeframe(self, tf_str: str) -> int:
        """Converte string de timeframe para constante MT5."""
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
        
        tf_constant = tf_map.get(tf_str.upper())
        if tf_constant is None:
            raise ValueError(f"Timeframe inválido: {tf_str}. Válidos: {list(tf_map.keys())}")
        
        return tf_constant
    
    def _load_strategy(self) -> LSTMVolatilityStrategy:
        """Carrega a estratégia a partir da configuração."""
        # Busca configuração do ativo
        asset_config = None
        for asset in self.config.get('assets', []):
            if asset.get('ticker') == self.ticker:
                asset_config = asset
                break
        
        if not asset_config:
            raise ValueError(f"Configuração não encontrada para ticker: {self.ticker}")
        
        # Busca estratégia LSTM
        strategy_config = None
        for strat in asset_config.get('strategies', []):
            if strat.get('name') == 'LSTMVolatilityStrategy':
                strategy_config = strat
                break
        
        if not strategy_config:
            raise ValueError(f"LSTMVolatilityStrategy não encontrada para {self.ticker}")
        
        # Extrai parâmetros
        params = strategy_config.get('strategy_params', {})
        
        # Cria instância da estratégia
        strategy = LSTMVolatilityStrategy(
            lookback=params.get('lookback', 96),
            lstm_units=params.get('lstm_units', 64),
            dropout_rate=params.get('dropout_rate', 0.2),
            epochs=params.get('epochs', 30),
            batch_size=params.get('batch_size', 128),
            target_period=params.get('target_period', 5),
            volatility_multiplier=params.get('volatility_multiplier', 3.0)
        )
        
        return strategy
    
    def _get_model_path(self) -> str:
        """Retorna o caminho base para carregar o modelo."""
        model_dir = self.config.get('global_settings', {}).get('model_directory', 'models')
        model_prefix = f"{self.ticker}_{self.strategy.__class__.__name__}_{self.timeframe_str}_prod"
        return str(Path(model_dir) / model_prefix)
    
    def _warm_up(self):
        """
        Aquece o buffer com dados históricos.
        Busca as últimas buffer_size velas do MT5 para inicializar o sistema.
        """
        logger.info(f"WARM-UP: Buscando {self.buffer_size} velas históricas (apenas fechadas)...")
        
        # Busca dados históricos (provider já retorna apenas candles fechados)
        data = self.provider.get_latest_candles(
            ticker=self.ticker,
            timeframe=self.timeframe,
            count=self.buffer_size
        )
        
        if data.empty:
            raise RuntimeError(f"Falha ao buscar dados históricos para {self.ticker}")
        
        # Valida colunas obrigatórias
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required_cols if col not in data.columns]
        if missing:
            raise ValueError(f"Colunas faltando nos dados: {missing}")
        
        self.buffer_df = data[required_cols].copy()
        
        logger.info(f"✓ Buffer inicializado com {len(self.buffer_df)} candles")
        logger.info(f"  Período: {self.buffer_df.index[0]} até {self.buffer_df.index[-1]}")
    
    def _process_new_candle(self):
        """
        Processa o candle mais recente e gera alertas se necessário.
        
        Fluxo:
        1. Calcula features usando a estratégia
        2. Calcula EMA(20) para filtro de tendência
        3. Executa predição do modelo LSTM
        4. Verifica thresholds e gera logs/alertas conforme probabilidade
        """
        try:
            # 1. Calcula features
            features_df = self.strategy.define_features(self.buffer_df.copy())
            
            # Verifica se há dados suficientes após calcular features
            if len(features_df) < self.strategy.lookback + 10:
                logger.warning(f"Dados insuficientes após calcular features: {len(features_df)} linhas")
                return
            
            # 2. Calcula EMA(20) para filtro de tendência
            if 'ema_20' not in features_df.columns:
                features_df['ema_20'] = features_df['close'].ewm(span=20, adjust=False).mean()
            
            # 3. Prepara dados para predição (últimas lookback + margem linhas)
            lookback = self.strategy.lookback
            features_subset = features_df.tail(lookback + 20)  # Margem extra para criar sequências
            
            # Seleciona apenas as features esperadas pelo modelo
            feature_cols = self.strategy.get_feature_names()
            missing_features = [col for col in feature_cols if col not in features_subset.columns]
            if missing_features:
                logger.error(f"Features faltando: {missing_features}")
                return
            
            X_input = features_subset[feature_cols]
            
            # 4. Executa predição
            proba = self.strategy.model.predict_proba(X_input)
            
            if len(proba) == 0:
                logger.warning("Nenhuma predição gerada (sequências insuficientes)")
                return
            
            # Pega a última predição (mais recente)
            prob_class1 = proba[-1, 1]  # Probabilidade da classe 1 (explosão de volatilidade)
            
            # 5. Obtém dados do último candle
            last_candle = self.buffer_df.iloc[-1]
            current_time = self.buffer_df.index[-1]
            current_price = last_candle['close']
            ema_20 = features_df['ema_20'].iloc[-1]
            
            # 6. Determina direção baseada em tendência (EMA)
            direction = "CALL" if current_price > ema_20 else "PUT"
            
            # 7. Análise de Contexto Técnico
            context = self.context_analyzer.analyze(self.buffer_df)
            
            # 8. Validação do sinal com contexto técnico
            signal_valid, validation_reason = self.context_analyzer.validate_signal(
                ml_direction=direction,
                context=context,
                require_trend_alignment=False  # Não exige alinhamento estrito (apenas alerta)
            )
            
            # 9. Gera logs/alertas conforme probabilidade
            prob_pct = prob_class1 * 100
            
            # Prepara dados para callback de UI (sempre envia dados do último candle)
            if self.ui_callback:
                # Dados completos do último candle para UI (inclui contexto técnico)
                candle_data = {
                    'timestamp': current_time,
                    'open': last_candle['open'],
                    'high': last_candle['high'],
                    'low': last_candle['low'],
                    'close': current_price,
                    'volume': last_candle['volume'],
                    'probability': prob_pct,
                    'direction': direction,
                    'ema_20': ema_20,
                    'sma_fast': context.get('sma_fast'),
                    # Contexto técnico
                    'trend': context['trend'],
                    'trend_strength': context['trend_strength'],
                    'rsi': context['rsi'],
                    'rsi_condition': context['rsi_condition'],
                    'support': context['support'],
                    'resistance': context['resistance'],
                    'pattern': context['pattern'],
                    'signal_valid': signal_valid,
                    'validation_reason': validation_reason,
                }
                
                if prob_class1 > self.threshold_alert:
                    # ALERTA CRÍTICO - Mensagem enriquecida
                    candle_data['type'] = 'ALERT'
                    target = context['resistance'] if direction == 'CALL' else context['support']
                    validation_icon = "✅" if signal_valid else "⚠️"
                    candle_data['message'] = (
                        f"{validation_icon} SINAL {direction} ({prob_pct:.1f}%) | "
                        f"Tendência: {context['trend']} ({context['trend_strength']}) | "
                        f"Padrão: {context['pattern']} | "
                        f"Alvo: {target:.2f}"
                    )
                    self.ui_callback(candle_data)
                elif prob_class1 > self.threshold_log:
                    # LOG INFORMATIVO
                    candle_data['type'] = 'INFO'
                    candle_data['message'] = (
                        f"📊 Prob. Moderada ({prob_pct:.1f}%) | "
                        f"Tendência: {context['trend']} | "
                        f"RSI: {context['rsi']:.0f} ({context['rsi_condition']})"
                    )
                    self.ui_callback(candle_data)
                else:
                    # TICK normal (sem alerta)
                    candle_data['type'] = 'TICK'
                    candle_data['message'] = f"Candle processado | Tendência: {context['trend']}"
                    self.ui_callback(candle_data)
            
            # Logs no console (enriquecidos com contexto)
            if prob_class1 > self.threshold_alert:
                # ALERTA CRÍTICO (>65%)
                target = context['resistance'] if direction == 'CALL' else context['support']
                validation_status = "VALIDADO" if signal_valid else "NÃO VALIDADO"
                logger.critical(
                    f"🚨 ALERTA DE VOLATILIDADE 🚨 | "
                    f"Hora: {current_time.strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"Probabilidade: {prob_pct:.2f}% | "
                    f"Direção: {direction} | "
                    f"Preço: {current_price:.2f} | "
                    f"Tendência: {context['trend']} ({context['trend_strength']}) | "
                    f"RSI: {context['rsi']:.0f} ({context['rsi_condition']}) | "
                    f"Padrão: {context['pattern']} | "
                    f"EMA9: {context['ema_fast']:.2f} | SMA20: {context.get('sma_fast', 0):.2f} | SMA50: {context['sma_slow']:.2f} | "
                    f"Suporte: {context['support']:.2f} | "
                    f"Resistência: {context['resistance']:.2f} | "
                    f"Alvo: {target:.2f} | "
                    f"Status: {validation_status}"
                )
                if not signal_valid:
                    logger.warning(f"⚠️ Motivo da não validação: {validation_reason}")
            elif prob_class1 > self.threshold_log:
                # LOG INFORMATIVO (55-65%)
                logger.info(
                    f"📊 Probabilidade Moderada | "
                    f"Hora: {current_time.strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"Probabilidade: {prob_pct:.2f}% | "
                    f"Preço: {current_price:.2f} | "
                    f"Tendência: {context['trend']} | "
                    f"RSI: {context['rsi']:.0f} | EMA9: {context['ema_fast']:.2f} | SMA20: {context.get('sma_fast', 0):.2f} | SMA50: {context['sma_slow']:.2f}"
                )
            
        except Exception as e:
            logger.error(f"Erro ao processar candle: {e}", exc_info=True)
    
    def _reconnect_mt5(self) -> bool:
        """
        Tenta reconectar ao MT5 em caso de falha.
        
        Returns:
            bool: True se reconexão bem-sucedida, False caso contrário
        """
        logger.warning("Tentando reconectar ao MT5...")
        
        # Shutdown e reinit
        mt5.shutdown()
        time.sleep(2)
        
        self.provider = MetaTraderProvider()
        
        if self.provider.is_connected():
            logger.info("✓ Reconexão ao MT5 bem-sucedida")
            return True
        else:
            logger.error("✗ Falha na reconexão ao MT5")
            return False
    
    def _wait_for_next_candle(self):
        """
        Sincroniza com o próximo fechamento de candle.
        
        Para M5: aguarda até HH:M0, HH:M5, HH:M10, etc. + 5 segundos de buffer.
        """
        now = datetime.now()
        
        # Calcula minutos para próximo candle M5
        if self.timeframe_str == "M5":
            interval_minutes = 5
        elif self.timeframe_str == "M15":
            interval_minutes = 15
        elif self.timeframe_str == "M30":
            interval_minutes = 30
        elif self.timeframe_str == "H1":
            interval_minutes = 60
        else:
            # Fallback para outros timeframes
            interval_minutes = 5
        
        # Calcula próximo múltiplo
        current_minute = now.minute
        next_minute = ((current_minute // interval_minutes) + 1) * interval_minutes
        
        # Calcula próximo horário (pode rolar para próxima hora)
        next_time = now.replace(second=0, microsecond=0)
        next_time = next_time.replace(minute=0) + timedelta(minutes=next_minute)
        
        # Adiciona buffer de 5 segundos
        next_time += timedelta(seconds=5)
        
        # Calcula tempo de espera
        wait_seconds = (next_time - now).total_seconds()
        
        if wait_seconds > 0:
            logger.info(f"Aguardando próximo candle... ({wait_seconds:.0f}s até {next_time.strftime('%H:%M:%S')})")
            time.sleep(wait_seconds)
    
    def stop(self):
        """
        Para o loop de monitoramento.
        Define self.running = False para sair do loop graciosamente.
        """
        logger.info("Solicitação de parada recebida...")
        self.running = False
    
    def start(self):
        """
        Inicia o loop de monitoramento em tempo real.
        
        Loop controlado por self.running que:
        1. Aguarda fechamento do próximo candle
        2. Busca novo candle do MT5
        3. Atualiza buffer (append + drop old)
        4. Processa candle e gera alertas
        
        Interrompível via stop() ou Ctrl+C (KeyboardInterrupt).
        """
        logger.info("=" * 80)
        logger.info("INICIANDO MONITORAMENTO EM TEMPO REAL")
        logger.info("=" * 80)
        
        # Define flag de execução
        self.running = True
        
        # Warm-up inicial
        self._warm_up()
        
        logger.info(f"""
Monitor configurado e pronto!
Pressione Ctrl+C para interromper.
        """)
        logger.info("=" * 80)
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        try:
            while self.running:
                try:
                    # 1. Sincroniza com próximo candle
                    self._wait_for_next_candle()
                    
                    # 2. Verifica conexão MT5
                    if not self.provider.is_connected():
                        logger.warning("Conexão MT5 perdida. Tentando reconectar...")
                        if not self._reconnect_mt5():
                            consecutive_errors += 1
                            if consecutive_errors >= max_consecutive_errors:
                                logger.critical(f"Máximo de erros consecutivos atingido ({max_consecutive_errors}). Encerrando.")
                                break
                            time.sleep(10)
                            continue
                    
                    # 3. Busca último candle fechado (não o em formação)
                    new_data = self.provider.get_latest_candles(
                        ticker=self.ticker,
                        timeframe=self.timeframe,
                        count=1
                    )
                    
                    if new_data.empty:
                        logger.warning("Nenhum dado retornado do MT5. Pulando ciclo.")
                        consecutive_errors += 1
                        continue
                    
                    # 4. Atualiza buffer (append + mantém tamanho fixo)
                    new_candle = new_data.iloc[-1:]
                    self.buffer_df = pd.concat([self.buffer_df, new_candle])
                    
                    # Remove candles antigos para manter exatamente buffer_size
                    if len(self.buffer_df) > self.buffer_size:
                        self.buffer_df = self.buffer_df.iloc[-self.buffer_size:]
                    
                    logger.debug(f"Buffer atualizado: {len(self.buffer_df)} candles (último: {self.buffer_df.index[-1]})")
                    
                    # 5. Processa novo candle
                    self._process_new_candle()
                    
                    # Reset contador de erros em caso de sucesso
                    consecutive_errors = 0
                    
                except KeyboardInterrupt:
                    # Propaga para o handler externo
                    raise
                    
                except Exception as e:
                    logger.error(f"Erro no ciclo de monitoramento: {e}", exc_info=True)
                    consecutive_errors += 1
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.critical(f"Máximo de erros consecutivos atingido ({max_consecutive_errors}). Encerrando.")
                        break
                    
                    # Aguarda antes de tentar novamente
                    time.sleep(30)
        
        except KeyboardInterrupt:
            logger.info("\n" + "=" * 80)
            logger.info("Interrupção detectada (Ctrl+C)")
            logger.info("Encerrando monitor...")
        
        finally:
            # Cleanup
            self.running = False
            logger.info("Fechando conexão MT5...")
            self.provider.close_connection()
            mt5.shutdown()
            logger.info("=" * 80)
            logger.info("MONITOR ENCERRADO")
            logger.info("=" * 80)
