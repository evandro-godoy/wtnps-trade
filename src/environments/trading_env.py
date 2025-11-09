# src/environments/trading_env.py
"""
Ambiente de treinamento customizado para Deep Reinforcement Learning.
Este ambiente consome dados do MetaTraderProvider e implementa a lógica de
State, Action e Reward baseada em log returns (FinancialTradingasaGameDRL.pdf).
"""

import numpy as np
import pandas as pd
import logging
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


class TradingEnv:
    """
    Ambiente de trading customizado.
    
    Ações (Action Space):
        0: VENDA (Short)
        1: HOLD (Neutro/Cash)
        2: COMPRA (Long)
    
    Estado (State):
        - Market features: log returns, volume, indicadores técnicos
        - Position feature: one-hot encoding da posição atual [venda, hold, compra]
    
    Recompensa (Reward):
        - Log return do portfólio baseado em PnL e custos de transação
        - Equação inspirada em FinancialTradingasaGameDRL.pdf (Eq. 1 e 3)
    """
    
    def __init__(self, ticker: str, strategy_config: Dict[str, Any], provider):
        """
        Inicializa o ambiente de trading.
        
        Args:
            ticker: Símbolo do ativo (ex: 'WDO$', 'WIN$')
            strategy_config: Dicionário de configuração da estratégia (de strategies[] no main.yaml)
            provider: Instância do BaseDataProvider (ex: MetaTraderProvider)
        """
        self.ticker = ticker
        self.strategy_config = strategy_config
        self.provider = provider
        
        # Define espaço de ação: 0=Venda, 1=Hold, 2=Compra
        self.action_space = [0, 1, 2]
        self.num_actions = len(self.action_space)
        
        # Extrai parâmetros de configuração da estratégia
        self.trading_rules = strategy_config.get('training_trading_rules', {})
        
        # Custos de transação (stop_loss_pct como proxy)
        self.transaction_cost_pct = self.trading_rules.get('stop_loss_pct', 0.001)  # 0.1% default
        
        # Carrega dados históricos completos
        logger.info(f"Carregando dados históricos para {self.ticker}...")
        self._load_historical_data()
        
        # Calcula features de estado (market features)
        logger.info(f"Calculando features de mercado para {self.ticker}...")
        self._calculate_market_features()
        
        # Estado interno do ambiente
        self.current_step = 0
        self.current_position = 1  # Inicia em HOLD
        self.portfolio_value = 1.0  # Valor nocional inicial (para log returns)
        
        # Dimensão do estado
        self.state_dim = len(self._get_state())
        
        logger.info(f"TradingEnv inicializado: {self.ticker}, Steps={len(self.market_features_df)}, StateDim={self.state_dim}")
    
    def _load_historical_data(self):
        """Carrega todos os dados históricos usando o provider."""
        data_config = self.strategy_config['data']
        start_date = data_config['start_date']
        end_date = data_config['end_date']
        timeframe = data_config['timeframe_model']

        mt5_timeframe_obj = self.provider._get_mt5_timeframe(timeframe)

        if mt5_timeframe_obj is None:
            logger.info(f"Timeframe '{timeframe}' inválido para MT5 no ativo {self.ticker}. Utilizando D1.")
            mt5_timeframe_obj = self.provider._get_mt5_timeframe('D1')

        # Usa o provider para obter dados
        self.raw_data = self.provider.get_data(
            ticker=self.ticker,
            start_date=start_date,
            end_date=end_date,
            timeframe=mt5_timeframe_obj
        )
        
        if self.raw_data is None or len(self.raw_data) == 0:
            raise ValueError(f"Nenhum dado histórico obtido para {self.ticker}")
        
        logger.info(f"Dados carregados: {len(self.raw_data)} candles de {start_date} a {end_date}")
    
    def _calculate_market_features(self):
        """
        Calcula features de mercado usando indicadores técnicos (pandas_ta).
        
        Features:
        - ema_9: Exponential Moving Average (9 períodos)
        - sma_20: Simple Moving Average (20 períodos)
        - sma_200: Simple Moving Average (200 períodos)
        - dist_sma_20: Distância normalizada para SMA 20
        - dist_sma_200: Distância normalizada para SMA 200
        - atr: Average True Range normalizado (volatilidade)
        """
        import pandas_ta as ta
        
        df = self.raw_data.copy()
        
        # --- Novas Features usando pandas_ta ---
        
        # 1. EMA 9
        df['ema_9'] = ta.ema(df['close'], length=9)
        
        # 2. SMA 20
        df['sma_20'] = ta.sma(df['close'], length=20)
        
        # 3. SMA 200
        df['sma_200'] = ta.sma(df['close'], length=200)
        
        # 4. Distância (normalizada) para a SMA 20
        df['dist_sma_20'] = (df['close'] - df['sma_20']) / df['close']
        
        # 5. Distância (normalizada) para a SMA 200
        df['dist_sma_200'] = (df['close'] - df['sma_200']) / df['close']
        
        # 6. ATR (Volatilidade Normalizada)
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['atr'] = atr / df['close']  # Normaliza o ATR pelo preço
        
        # Lista de nomes das novas features
        self.market_feature_names = [
            'ema_9', 'sma_20', 'sma_200', 
            'dist_sma_20', 'dist_sma_200', 'atr'
        ]
        
        # Normaliza as features baseadas em preço (exceto distâncias e ATR que já são relativos)
        price_features = ['ema_9', 'sma_20', 'sma_200']
        for col in price_features:
            df[col] = (df[col] / df['close']) - 1  # Normaliza pelo preço de fechamento
        
        # Remove NaN (primeiras linhas sem dados suficientes)
        df = df.dropna()
        
        # Armazena DataFrame com features + preços originais
        self.market_features_df = df
        
        # Extrai apenas as features para o estado
        self.market_features_only = df[self.market_feature_names].values
        
        # Armazena preços de fechamento para cálculo de PnL
        self.prices = df['close'].values
        
        logger.info(f"Features calculadas: {len(self.market_features_only)} steps, {len(self.market_feature_names)} features")
    
    def _get_state(self) -> np.ndarray:
        """
        Retorna o vetor de estado atual.
        
        State = [market_features, position_feature]
        - market_features: features de mercado (log returns, volatilidade, etc.)
        - position_feature: one-hot encoding da posição [venda, hold, compra]
        
        Returns:
            np.array: Vetor de estado completo
        """
        # Market features do step atual
        market_features = self.market_features_only[self.current_step]
        
        # Position feature (one-hot encoding)
        # Posição 0=Venda: [1,0,0], 1=Hold: [0,1,0], 2=Compra: [0,0,1]
        position_feature = np.zeros(3, dtype=np.float32)
        position_feature[self.current_position] = 1.0
        
        # Concatena ambos
        state = np.concatenate([market_features, position_feature])
        
        return state.astype(np.float32)
    
    def reset(self) -> np.ndarray:
        """
        Reseta o ambiente para o estado inicial.
        
        Returns:
            np.array: Estado inicial
        """
        self.current_step = 0
        self.current_position = 1  # HOLD
        self.portfolio_value = 1.0
        
        return self._get_state()
    
    def step(self, action: int) -> Tuple[Optional[np.ndarray], float, bool]:
        """
        Executa uma ação no ambiente e retorna o próximo estado, recompensa e flag de término.
        
        Lógica de Recompensa (baseada em FinancialTradingasaGameDRL.pdf):
        - reward = log( (portfolio_value_new) / (portfolio_value_old) )
        - portfolio_value_new = portfolio_value_old * (1 + pnl - transaction_cost)
        
        Args:
            action: Ação a ser executada (0=Venda, 1=Hold, 2=Compra)
        
        Returns:
            Tupla (next_state, reward, done)
            - next_state: Próximo estado (ou None se done=True)
            - reward: Recompensa obtida
            - done: Se o episódio terminou
        """
        # Valida ação
        if action not in self.action_space:
            raise ValueError(f"Ação inválida: {action}. Ações válidas: {self.action_space}")
        
        # --- Calcula Recompensa (Reward) ---
        
        # Preço atual e próximo
        current_price = self.prices[self.current_step]
        next_step = self.current_step + 1
        
        if next_step >= len(self.prices):
            # Fim dos dados
            return None, 0.0, True
        
        next_price = self.prices[next_step]
        
        # PnL baseado na POSIÇÃO ANTERIOR (mantida até agora)
        # Posição 0=Venda (short): lucra se preço cai
        # Posição 1=Hold: sem PnL
        # Posição 2=Compra (long): lucra se preço sobe
        price_return = (next_price - current_price) / current_price
        
        if self.current_position == 0:  # VENDA (short)
            pnl = -price_return  # Inverte o retorno
        elif self.current_position == 1:  # HOLD
            pnl = 0.0
        else:  # self.current_position == 2 (COMPRA/long)
            pnl = price_return
        
        # Custo de transação (Equação 3 do paper: só paga se mudar posição)
        transaction_cost = 0.0
        if action != self.current_position:
            # Muda posição: paga custo
            transaction_cost = self.transaction_cost_pct
        
        # Novo valor do portfólio (aplicando PnL e custo)
        portfolio_value_new = self.portfolio_value * (1 + pnl - transaction_cost)
        
        # Recompensa = log return do portfólio (Equação 1)
        # Usa np.clip para evitar log de valores <= 0 (proteção contra falhas)
        reward = np.log(np.clip(portfolio_value_new / self.portfolio_value, 1e-10, None))
        
        # Atualiza portfólio
        self.portfolio_value = portfolio_value_new
        
        # --- Atualiza Estado Interno ---
        self.current_position = action  # Nova posição após a ação
        self.current_step = next_step
        
        # Verifica se chegou ao fim
        done = self.current_step >= len(self.market_features_only) - 1
        
        # Log de debug a cada 1000 steps (evita spam)
        if self.current_step % 1000 == 0:
            logger.debug(
                f"Step {self.current_step}/{len(self.market_features_only)}, "
                f"Position: {self.current_position}, Reward: {reward:.6f}, "
                f"Portfolio: {self.portfolio_value:.4f}"
            )
        
        # Próximo estado
        if done:
            next_state = None
            logger.debug(f"Episódio finalizado no step {self.current_step}")
        else:
            next_state = self._get_state()
        
        return next_state, reward, done
    
    def get_feature_names(self) -> list:
        """
        Retorna os nomes das features de mercado.
        Útil para debug e compatibilidade com DRLStrategy.
        """
        return self.market_feature_names
