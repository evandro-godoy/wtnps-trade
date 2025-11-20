# src/backtest_engine/backtest_lstm_volatility.py
"""
Mecanismo de Backtest para LSTMVolatilityStrategy.
Executa backtesting detalhado com métricas de performance e geração de relatórios.

Adequações:
- Ajuste de import path para permitir execução direta (`python src/backtest_engine/backtest_lstm_volatility.py`).
- Tratamento do typo em config (`strategie_name` vs `strategy_name`).
- Threshold e parâmetros de trade (capital, stop, take) agora são lidos de `configs/main.yaml` em `assets[].backtesting` quando disponíveis.
- Otimização de threshold é executada apenas se não houver `threshold` definido no bloco `backtesting`.
- Payoff médio (avg_win_r) derivado de `take_profit_pct / stop_loss_pct` quando ambos disponíveis.
- Uso consistente do tamanho das sequências (probabilidades/predictions alinhados ao lookback).
- Validações adicionais de consistência de arrays antes do cálculo de métricas.
 - Relatórios gerados: JSON, TXT e agora HTML (human readable) com métricas, trades e parâmetros.
"""

import sys
from pathlib import Path

# Garante que o diretório raiz do projeto esteja no sys.path para permitir `import src.*`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
import yaml
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json
import importlib
from src.data_handler import provider as data_provider_module
from sklearn.metrics import (
    accuracy_score, 
    precision_score, 
    recall_score, 
    f1_score,
    confusion_matrix, 
    classification_report
)

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Engine de backtesting para estratégias LSTM de volatilidade.
    """
    
    def __init__(self, config_path: str = 'configs/main.yaml'):
        """
        Inicializa o engine de backtest.
        
        Args:
            config_path: Caminho para arquivo de configuração YAML
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.results = {}
        self.trades = []
        
    def _load_config(self) -> dict:
        """Carrega configurações do arquivo YAML."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuração carregada de {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Erro ao carregar config: {e}")
            raise
    
    def run_backtest(
        self,
        ticker: str,
        predictions: np.ndarray,
        probabilities: np.ndarray,
        actual_targets: np.ndarray,
        prices: pd.DataFrame,
        threshold: float = 3.0,
        trade_params: Optional[Dict] = None,
        min_signals: Optional[int] = None,
        market_close_hour: int = 17,
        max_holding_candles: Optional[int] = None
    ) -> Dict:
        """
        Executa o backtest com as predições do modelo.
        
        Args:
            ticker: Símbolo do ativo
            predictions: Predições binárias do modelo (0 ou 1)
            probabilities: Probabilidades de explosão (0 a 1)
            actual_targets: Targets reais (ground truth)
            prices: DataFrame com dados OHLCV
            threshold: Limiar de probabilidade para entrada
            trade_params: Parâmetros de trade derivados do config (capital, stop, take, payoff)
            
        Returns:
            Dicionário com resultados do backtest
        """
        logger.info(f"=== Iniciando Backtest para {ticker} ===")
        logger.info(f"Threshold: {threshold:.2f}")
        # Sanidade dos tamanhos
        if len(probabilities) != len(actual_targets):
            logger.warning(
                f"Comprimento de probabilidades ({len(probabilities)}) diferente de targets ({len(actual_targets)}). Ajustando para mínimo comum."
            )
            min_len = min(len(probabilities), len(actual_targets))
            probabilities = probabilities[:min_len]
            actual_targets = actual_targets[:min_len]
            if len(predictions) != min_len:
                predictions = predictions[:min_len]

        logger.info(f"Períodos analisados (sequências válidas): {len(probabilities)}")
        
        # Aplicar threshold nas probabilidades (com ajuste dinâmico para garantir mínimo de sinais)
        y_pred_threshold = (probabilities > threshold).astype(int).flatten()
        if min_signals is not None:
            original_threshold = threshold
            step = 0.05
            while np.sum(y_pred_threshold == 1) < min_signals and threshold > 0.05:
                threshold = max(0.05, threshold - step)
                y_pred_threshold = (probabilities > threshold).astype(int).flatten()
            if threshold != original_threshold:
                logger.info(f"Threshold ajustado dinamicamente de {original_threshold:.2f} para {threshold:.2f} visando mínimo de {min_signals} sinais.")
        
        # Métricas de classificação
        metrics = self._calculate_metrics(actual_targets, y_pred_threshold)
        
        # Simular trades em formato Day Trade com controle de posição
        trade_results = self._simulate_daytrade_positions(
            signals=y_pred_threshold,
            prices=prices,
            stop_loss_pct=trade_params.get('stop_loss_pct') if trade_params else None,
            take_profit_pct=trade_params.get('take_profit_pct') if trade_params else None,
            initial_capital=trade_params.get('initial_capital') if trade_params else None,
            market_close_hour=market_close_hour,
            max_holding_candles=max_holding_candles
        )
        
        # Consolidar resultados
        results = {
            'ticker': ticker,
            'threshold': threshold,
            'period': {
                'start': prices.index[0].strftime('%Y-%m-%d %H:%M'),
                'end': prices.index[-1].strftime('%Y-%m-%d %H:%M'),
                'total_candles': len(probabilities)
            },
            'classification_metrics': metrics,
            'trading_performance': trade_results,
            'trade_params': trade_params if trade_params else {},
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        self.results = results
        return results
    
    def _calculate_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict:
        """Calcula métricas de classificação."""
        # Garantir que arrays são 1D
        y_true = y_true.flatten()
        y_pred = y_pred.flatten()
        
        # Métricas básicas
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        
        # Matriz de confusão
        cm = confusion_matrix(y_true, y_pred)
        
        # True/False Positives/Negatives
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
        
        # Distribuição de classes
        total_samples = len(y_true)
        class_distribution = {
            'calm_actual': int(np.sum(y_true == 0)),
            'explosion_actual': int(np.sum(y_true == 1)),
            'calm_predicted': int(np.sum(y_pred == 0)),
            'explosion_predicted': int(np.sum(y_pred == 1))
        }
        
        metrics = {
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'confusion_matrix': {
                'true_negatives': int(tn),
                'false_positives': int(fp),
                'false_negatives': int(fn),
                'true_positives': int(tp)
            },
            'class_distribution': class_distribution,
            'total_samples': total_samples
        }
        
        logger.info(f"Accuracy: {accuracy:.2%}")
        logger.info(f"Precision (Win Rate): {precision:.2%}")
        logger.info(f"Recall (Coverage): {recall:.2%}")
        logger.info(f"F1 Score: {f1:.4f}")
        
        return metrics
    
    def _simulate_trades(
        self,
        signals: np.ndarray,
        actual_targets: np.ndarray,
        prices: pd.DataFrame,
        ticker: str,
        avg_win: float = 2.0,
        avg_loss: float = -1.0,
        initial_capital: Optional[float] = None,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None
    ) -> Dict:
        """
        Simula execução de trades baseado nos sinais.
        
        Args:
            signals: Sinais de entrada (1 = entra, 0 = fica fora)
            actual_targets: Targets reais (1 = explosão aconteceu, 0 = calmo)
            prices: DataFrame com preços
            ticker: Símbolo do ativo
            avg_win: Ganho médio esperado em R (risk units)
            avg_loss: Perda média esperada em R
            
        Returns:
            Dicionário com resultados de trading
        """
        logger.info("Simulando trades...")
        
        # Contar trades
        total_signals = int(np.sum(signals == 1))
        winning_trades = int(np.sum((signals == 1) & (actual_targets == 1)))
        losing_trades = int(np.sum((signals == 1) & (actual_targets == 0)))
        
        # Resultados financeiros (em unidades de risco R)
        total_return_r = (winning_trades * avg_win) + (losing_trades * avg_loss)
        
        # Win rate
        win_rate = winning_trades / total_signals if total_signals > 0 else 0
        
        # Expectativa matemática
        expectancy = total_return_r / total_signals if total_signals > 0 else 0
        
        # Profit factor
        gross_profit = winning_trades * avg_win
        gross_loss = abs(losing_trades * avg_loss)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Registrar trades individuais (simplificado)
        self.trades = []
        indices_signals = np.where(signals == 1)[0]
        
        for idx in indices_signals:
            if idx < len(actual_targets):
                result = 'WIN' if actual_targets[idx] == 1 else 'LOSS'
                pnl_r = avg_win if result == 'WIN' else avg_loss
                
                trade = {
                    'index': int(idx),
                    'timestamp': prices.index[idx].strftime('%Y-%m-%d %H:%M') if idx < len(prices) else 'N/A',
                    'signal': 'EXPLOSION_ENTRY',
                    'result': result,
                    'pnl_r': float(pnl_r)
                }
                self.trades.append(trade)
        
        # Capital e retorno monetário (se parâmetros fornecidos)
        monetary_return = None
        final_capital = None
        if initial_capital is not None and stop_loss_pct is not None:
            risk_unit_value = initial_capital * stop_loss_pct
            monetary_return = total_return_r * risk_unit_value
            final_capital = initial_capital + monetary_return
        
        results = {
            'total_signals': total_signals,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': float(win_rate),
            'total_return_r': float(total_return_r),
            'expectancy_r': float(expectancy),
            'profit_factor': float(profit_factor),
            'avg_win_r': float(avg_win),
            'avg_loss_r': float(avg_loss),
            'initial_capital': float(initial_capital) if initial_capital is not None else None,
            'final_capital': float(final_capital) if final_capital is not None else None,
            'monetary_return': float(monetary_return) if monetary_return is not None else None,
            'stop_loss_pct': float(stop_loss_pct) if stop_loss_pct is not None else None,
            'take_profit_pct': float(take_profit_pct) if take_profit_pct is not None else None,
            'trades_log': self.trades[:10]  # Primeiros 10 trades como amostra
        }
        
        logger.info(f"Total de Sinais: {total_signals}")
        logger.info(f"Trades Vencedores: {winning_trades}")
        logger.info(f"Trades Perdedores: {losing_trades}")
        logger.info(f"Win Rate: {win_rate:.2%}")
        logger.info(f"Retorno Total: {total_return_r:.2f}R")
        logger.info(f"Expectativa: {expectancy:.2f}R por trade")
        logger.info(f"Profit Factor: {profit_factor:.2f}")
        
        return results

    def _simulate_daytrade_positions(
        self,
        signals: np.ndarray,
        prices: pd.DataFrame,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        initial_capital: Optional[float] = None,
        market_close_hour: int = 17,
        max_holding_candles: Optional[int] = None
    ) -> Dict:
        """Simula execução Day Trade com controle de posição e regras adicionais.

        Regras:
        - Abre posição LONG quando signal == 1 e nenhuma posição aberta e hora < market_close_hour.
        - Força flat diário: fecha no candle cujo hour >= market_close_hour.
        - Se dia muda e posição continua aberta (timezone desalinhado), força saída OVERNIGHT_FORCE no último candle do dia anterior.
        - Stop / Take conforme percentuais; prioridade STOP antes de TAKE.
        - Max holding: força saída 'MAX_HOLDING' se excede max_holding_candles.
        - Calcula PnL em R com base no stop quando disponível.
        """
        logger.info("Simulando Day Trade com controle de posição...")
        self.trades = []
        open_pos = None
        risk_unit_value = initial_capital * stop_loss_pct if (initial_capital is not None and stop_loss_pct) else None
        prev_ts = None

        if len(signals) != len(prices):
            min_len = min(len(signals), len(prices))
            signals = signals[:min_len]
            prices = prices.iloc[:min_len]

        for i, (ts, row) in enumerate(prices.iterrows()):
            hour = ts.hour
            signal = signals[i]

            # Overnight force close if date changed and position still open
            if open_pos and prev_ts is not None and ts.date() != prev_ts.date():
                prev_close = prices.loc[prev_ts, 'close'] if prev_ts in prices.index else open_pos['entry_price']
                pnl_r = (prev_close - open_pos['entry_price']) / (open_pos['entry_price'] - open_pos['stop_price']) if open_pos['stop_price'] else 0.0
                trade = {
                    'day': prev_ts.date().isoformat(),
                    'entry_time': open_pos['entry_time'].strftime('%Y-%m-%d %H:%M'),
                    'exit_time': prev_ts.strftime('%Y-%m-%d %H:%M'),
                    'entry_price': float(open_pos['entry_price']),
                    'exit_price': float(prev_close),
                    'stop_price': float(open_pos['stop_price']) if open_pos['stop_price'] else None,
                    'take_profit_price': float(open_pos['take_profit_price']) if open_pos['take_profit_price'] else None,
                    'exit_reason': 'OVERNIGHT_FORCE',
                    'holding_period_candles': (i - 1) - open_pos['entry_index'] + 1,
                    'pnl_r': float(pnl_r),
                }
                if risk_unit_value is not None:
                    trade['pnl_monetary'] = float(pnl_r * risk_unit_value)
                trade['result'] = 'WIN' if pnl_r > 0 else ('LOSS' if pnl_r < 0 else 'FLAT')
                self.trades.append(trade)
                open_pos = None

            # Market close enforcement
            if open_pos and hour >= market_close_hour:
                exit_price = row['close']
                pnl_r = (exit_price - open_pos['entry_price']) / (open_pos['entry_price'] - open_pos['stop_price']) if open_pos['stop_price'] else 0.0
                trade = {
                    'day': ts.date().isoformat(),
                    'entry_time': open_pos['entry_time'].strftime('%Y-%m-%d %H:%M'),
                    'exit_time': ts.strftime('%Y-%m-%d %H:%M'),
                    'entry_price': float(open_pos['entry_price']),
                    'exit_price': float(exit_price),
                    'stop_price': float(open_pos['stop_price']) if open_pos['stop_price'] else None,
                    'take_profit_price': float(open_pos['take_profit_price']) if open_pos['take_profit_price'] else None,
                    'exit_reason': 'MARKET_CLOSE',
                    'holding_period_candles': i - open_pos['entry_index'] + 1,
                    'pnl_r': float(pnl_r),
                }
                if risk_unit_value is not None:
                    trade['pnl_monetary'] = float(pnl_r * risk_unit_value)
                trade['result'] = 'WIN' if pnl_r > 0 else ('LOSS' if pnl_r < 0 else 'FLAT')
                self.trades.append(trade)
                open_pos = None
                prev_ts = ts
                continue

            # Open position
            if open_pos is None and signal == 1 and hour < market_close_hour:
                entry_price = row['close']
                stop_price = entry_price * (1 - stop_loss_pct) if stop_loss_pct else None
                take_profit_price = entry_price * (1 + take_profit_pct) if take_profit_pct else None
                open_pos = {
                    'entry_time': ts,
                    'entry_price': entry_price,
                    'stop_price': stop_price,
                    'take_profit_price': take_profit_price,
                    'entry_index': i
                }
                prev_ts = ts
                continue

            # Manage open position
            if open_pos:
                high = row['high']
                low = row['low']
                exit_reason = None
                exit_price = None
                stop_hit = open_pos['stop_price'] is not None and low <= open_pos['stop_price']
                take_hit = open_pos['take_profit_price'] is not None and high >= open_pos['take_profit_price']

                if stop_hit:
                    exit_reason = 'STOP'
                    exit_price = open_pos['stop_price']
                elif take_hit:
                    exit_reason = 'TAKE_PROFIT'
                    exit_price = open_pos['take_profit_price']

                # Max holding enforcement
                if exit_reason is None and max_holding_candles is not None:
                    holding = i - open_pos['entry_index'] + 1
                    if holding >= max_holding_candles:
                        exit_reason = 'MAX_HOLDING'
                        exit_price = row['close']

                if exit_reason:
                    if open_pos['stop_price']:
                        pnl_r = (exit_price - open_pos['entry_price']) / (open_pos['entry_price'] - open_pos['stop_price'])
                    else:
                        if take_profit_pct and stop_loss_pct and exit_reason == 'TAKE_PROFIT':
                            pnl_r = take_profit_pct / stop_loss_pct
                        elif exit_reason == 'STOP':
                            pnl_r = -1.0 if stop_loss_pct else 0.0
                        else:
                            pnl_r = 0.0
                    trade = {
                        'day': ts.date().isoformat(),
                        'entry_time': open_pos['entry_time'].strftime('%Y-%m-%d %H:%M'),
                        'exit_time': ts.strftime('%Y-%m-%d %H:%M'),
                        'entry_price': float(open_pos['entry_price']),
                        'exit_price': float(exit_price),
                        'stop_price': float(open_pos['stop_price']) if open_pos['stop_price'] else None,
                        'take_profit_price': float(open_pos['take_profit_price']) if open_pos['take_profit_price'] else None,
                        'exit_reason': exit_reason,
                        'holding_period_candles': i - open_pos['entry_index'] + 1,
                        'pnl_r': float(pnl_r),
                    }
                    if risk_unit_value is not None:
                        trade['pnl_monetary'] = float(pnl_r * risk_unit_value)
                    trade['result'] = 'WIN' if pnl_r > 0 else ('LOSS' if pnl_r < 0 else 'FLAT')
                    self.trades.append(trade)
                    open_pos = None

            prev_ts = ts

        # Final close if still open
        if open_pos:
            last_ts = prices.index[-1]
            exit_price = prices.iloc[-1]['close']
            if open_pos['stop_price']:
                pnl_r = (exit_price - open_pos['entry_price']) / (open_pos['entry_price'] - open_pos['stop_price'])
            else:
                pnl_r = 0.0
            trade = {
                'day': last_ts.date().isoformat(),
                'entry_time': open_pos['entry_time'].strftime('%Y-%m-%d %H:%M'),
                'exit_time': last_ts.strftime('%Y-%m-%d %H:%M'),
                'entry_price': float(open_pos['entry_price']),
                'exit_price': float(exit_price),
                'stop_price': float(open_pos['stop_price']) if open_pos['stop_price'] else None,
                'take_profit_price': float(open_pos['take_profit_price']) if open_pos['take_profit_price'] else None,
                'exit_reason': 'DATA_END',
                'holding_period_candles': len(prices) - open_pos['entry_index'],
                'pnl_r': float(pnl_r),
            }
            if risk_unit_value is not None:
                trade['pnl_monetary'] = float(pnl_r * risk_unit_value)
            trade['result'] = 'WIN' if pnl_r > 0 else ('LOSS' if pnl_r < 0 else 'FLAT')
            self.trades.append(trade)

        # Aggregations
        total_signals = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t['result'] == 'WIN')
        losing_trades = sum(1 for t in self.trades if t['result'] == 'LOSS')
        total_return_r = sum(t['pnl_r'] for t in self.trades)
        win_rate = winning_trades / total_signals if total_signals > 0 else 0.0
        expectancy = total_return_r / total_signals if total_signals > 0 else 0.0
        gross_profit_r = sum(t['pnl_r'] for t in self.trades if t['pnl_r'] > 0)
        gross_loss_r = abs(sum(t['pnl_r'] for t in self.trades if t['pnl_r'] < 0))
        profit_factor = gross_profit_r / gross_loss_r if gross_loss_r > 0 else 0.0

        daily_stats: Dict[str, Dict[str, float]] = {}
        for t in self.trades:
            d = t['day']
            if d not in daily_stats:
                daily_stats[d] = {'trades': 0, 'wins': 0, 'losses': 0, 'pnl_r': 0.0, 'pnl_monetary': 0.0}
            daily_stats[d]['trades'] += 1
            if t['result'] == 'WIN':
                daily_stats[d]['wins'] += 1
            elif t['result'] == 'LOSS':
                daily_stats[d]['losses'] += 1
            daily_stats[d]['pnl_r'] += t['pnl_r']
            if 'pnl_monetary' in t:
                daily_stats[d]['pnl_monetary'] += t['pnl_monetary']

        monetary_return = None
        final_capital = None
        if initial_capital is not None and stop_loss_pct is not None:
            monetary_return = total_return_r * risk_unit_value if risk_unit_value is not None else None
            final_capital = initial_capital + monetary_return if monetary_return is not None else None

        exit_reason_counts: Dict[str, int] = {}
        for t in self.trades:
            exit_reason_counts[t['exit_reason']] = exit_reason_counts.get(t['exit_reason'], 0) + 1
        avg_holding = float(np.mean([t['holding_period_candles'] for t in self.trades])) if self.trades else 0.0

        return {
            'total_signals': total_signals,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': float(win_rate),
            'total_return_r': float(total_return_r),
            'expectancy_r': float(expectancy),
            'profit_factor': float(profit_factor),
            'avg_win_r': float(gross_profit_r / winning_trades) if winning_trades > 0 else 0.0,
            'avg_loss_r': float(-gross_loss_r / losing_trades) if losing_trades > 0 else 0.0,
            'avg_holding_candles': avg_holding,
            'exit_reason_counts': exit_reason_counts,
            'initial_capital': float(initial_capital) if initial_capital is not None else None,
            'final_capital': float(final_capital) if final_capital is not None else None,
            'monetary_return': float(monetary_return) if monetary_return is not None else None,
            'stop_loss_pct': float(stop_loss_pct) if stop_loss_pct is not None else None,
            'take_profit_pct': float(take_profit_pct) if take_profit_pct is not None else None,
            'trades_log': self.trades[:10],
            'daily_stats': daily_stats,
            'full_trades': self.trades
        }
    
    def optimize_threshold(
        self,
        probabilities: np.ndarray,
        actual_targets: np.ndarray,
        prices: pd.DataFrame,
        ticker: str,
        thresholds: Optional[List[float]] = None
    ) -> Tuple[float, pd.DataFrame]:
        """
        Otimiza o threshold de entrada testando diferentes valores.
        
        Args:
            probabilities: Probabilidades do modelo
            actual_targets: Targets reais
            prices: DataFrame com preços
            ticker: Símbolo do ativo
            thresholds: Lista de thresholds a testar (default: 0.50 a 0.95)
            
        Returns:
            Tupla com (melhor_threshold, dataframe_resultados)
        """
        if thresholds is None:
            thresholds = np.arange(0.50, 0.96, 0.05)
        
        logger.info(f"=== Otimizando Threshold para {ticker} ===")
        logger.info(f"Testando {len(thresholds)} thresholds diferentes...")
        
        results = []
        
        for thresh in thresholds:
            y_pred = (probabilities > thresh).astype(int).flatten()
            precision = precision_score(actual_targets, y_pred, zero_division=0)
            recall = recall_score(actual_targets, y_pred, zero_division=0)
            total_signals = int(np.sum(y_pred == 1))
            winning_trades = int(np.sum((y_pred == 1) & (actual_targets == 1)))
            losing_trades = int(np.sum((y_pred == 1) & (actual_targets == 0)))
            total_return = (winning_trades * 2.0) + (losing_trades * -1.0)
            results.append({
                'Threshold': f"{thresh:.2f}",
                'Precision (%)': f"{precision*100:.1f}",
                'Recall (%)': f"{recall*100:.1f}",
                'Total_Signals': total_signals,
                'Wins': winning_trades,
                'Losses': losing_trades,
                'Return_R': float(total_return)
            })
        
        df_results = pd.DataFrame(results)
        best_idx = df_results['Return_R'].idxmax()
        best_threshold = float(df_results.loc[best_idx, 'Threshold'])
        logger.info(f"Melhor Threshold: {best_threshold:.2f}")
        logger.info(f"Retorno com melhor threshold: {df_results.loc[best_idx, 'Return_R']:.2f}R")
        return best_threshold, df_results
    
    def generate_report(
        self,
        output_dir: str = 'reports/backtest'
    ) -> str:
        """
        Gera relatório detalhado do backtest em JSON e TXT.
        
        Args:
            output_dir: Diretório de saída dos relatórios
            
        Returns:
            Path do arquivo de relatório gerado
        """
        if not self.results:
            logger.warning("Nenhum resultado de backtest disponível para gerar relatório.")
            return ""
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        ticker = self.results['ticker']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        json_file = output_path / f"backtest_{ticker}_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        logger.info(f"Relatório JSON salvo em: {json_file}")
        
        txt_file = output_path / f"backtest_{ticker}_{timestamp}.txt"
        self._generate_text_report(txt_file)
        logger.info(f"Relatório TXT salvo em: {txt_file}")
        return str(txt_file)
    
    def _generate_text_report(self, filepath: Path):
        """Gera relatório em formato texto legível."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"RELATÓRIO DE BACKTEST - {self.results['ticker']}\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Período: {self.results['period']['start']} até {self.results['period']['end']}\n")
            f.write(f"Total de Candles: {self.results['period']['total_candles']}\n")
            f.write(f"Threshold Utilizado: {self.results['threshold']:.2f}\n")
            f.write(f"Data do Backtest: {self.results['timestamp']}\n\n")
            f.write("-" * 80 + "\n")
            f.write("MÉTRICAS DE CLASSIFICAÇÃO\n")
            f.write("-" * 80 + "\n")
            cm = self.results['classification_metrics']
            f.write(f"Acurácia: {cm['accuracy']:.2%}\n")
            f.write(f"Precisão (Win Rate): {cm['precision']:.2%}\n")
            f.write(f"Recall (Cobertura): {cm['recall']:.2%}\n")
            f.write(f"F1-Score: {cm['f1_score']:.4f}\n\n")
            f.write("Matriz de Confusão:\n")
            conf = cm['confusion_matrix']
            f.write(f"  True Negatives (Calmo corretamente identificado): {conf['true_negatives']}\n")
            f.write(f"  False Positives (Falso alarme de explosão): {conf['false_positives']}\n")
            f.write(f"  False Negatives (Explosão não detectada): {conf['false_negatives']}\n")
            f.write(f"  True Positives (Explosão corretamente identificada): {conf['true_positives']}\n\n")
            dist = cm['class_distribution']
            f.write("Distribuição de Classes:\n")
            for cls, count in dist.items():
                f.write(f"  Classe {cls}: {count}\n")
            f.write("\n")
            perf = self.results.get('trading_performance', {})
            f.write("-" * 80 + "\n")
            f.write("PERFORMANCE DE TRADING (DAY TRADE)\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total Trades: {perf.get('total_signals', 0)}\n")
            f.write(f"Winning Trades: {perf.get('winning_trades', 0)}\n")
            f.write(f"Losing Trades: {perf.get('losing_trades', 0)}\n")
            f.write(f"Win Rate: {perf.get('win_rate', 0):.2%}\n")
            f.write(f"Retorno Total (R): {perf.get('total_return_r', 0):.2f}R\n")
            f.write(f"Expectativa por Trade (R): {perf.get('expectancy_r', 0):.2f}R\n")
            f.write(f"Profit Factor: {perf.get('profit_factor', 0):.2f}\n")
            f.write(f"Payoff Médio: Win = {perf.get('avg_win_r',0):.2f}R | Loss = {perf.get('avg_loss_r',0):.2f}R\n")
            if perf.get('avg_holding_candles') is not None:
                f.write(f"Média Holding (candles): {perf.get('avg_holding_candles',0):.1f}\n")
            erc = perf.get('exit_reason_counts', {})
            if erc:
                f.write("Motivos de Saída:\n")
                for reason, count in erc.items():
                    f.write(f"  {reason}: {count}\n")
            if perf.get('initial_capital') is not None:
                f.write(f"Capital Inicial: {perf.get('initial_capital'):.2f}\n")
            if perf.get('final_capital') is not None:
                f.write(f"Capital Final: {perf.get('final_capital'):.2f}\n")
            if perf.get('monetary_return') is not None:
                f.write(f"Retorno Monetário: {perf.get('monetary_return'):.2f}\n")
            if perf.get('stop_loss_pct') is not None and perf.get('take_profit_pct') is not None:
                f.write(f"Stop Loss %: {perf.get('stop_loss_pct'):.4f} | Take Profit %: {perf.get('take_profit_pct'):.4f}\n")
            f.write("\nAmostra de Trades:\n")
            for trade in self.trades[:10]:
                if 'timestamp' in trade:
                    f.write(f"  {trade['timestamp']} | {trade['signal']} | {trade['result']} | PnL: {trade['pnl_r']:.2f}R\n")
                    continue
                f.write(
                    f"  Entry: {trade.get('entry_time')} | Exit: {trade.get('exit_time')} | Reason: {trade.get('exit_reason')} | EP: {trade.get('entry_price'):.2f} | XP: {trade.get('exit_price'):.2f} | PnL(R): {trade.get('pnl_r',0):.2f} | Result: {trade.get('result')}\n"
                )
            f.write("\n" + "=" * 80 + "\n")
            f.write("FIM DO RELATÓRIO\n")
            f.write("=" * 80 + "\n")

    def generate_html_report(self, output_dir: str = 'reports/backtest') -> str:
        """Gera relatório em HTML detalhado (human readable) do backtest.

        Inclui:
        - Metadados (ticker, período, threshold, timestamp)
        - Métricas de classificação (tabela)
        - Matriz de confusão
        - Distribuição de classes
        - Parâmetros de trade utilizados
        - Performance de trading (win rate, expectancy, profit factor, capital)
        - Log completo de trades simulados
        - Observações metodológicas
        """
        if not self.results:
            logger.warning("Nenhum resultado para gerar HTML.")
            return ""

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        ticker = self.results['ticker']
        timestamp_file = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file = output_path / f"backtest_{ticker}_{timestamp_file}.html"

        r = self.results
        cm = r['classification_metrics']
        tp = r['trading_performance']
        trade_params = r.get('trade_params', {})
        conf = cm['confusion_matrix']
        dist = cm['class_distribution']

        # Monta tabela detalhada de trades agrupados por dia
        full_trades = r['trading_performance'].get('full_trades', [])
        daily_stats = r['trading_performance'].get('daily_stats', {})
        daily_sections = []
        for day, stats in sorted(daily_stats.items()):
            day_trades = [t for t in full_trades if t['day'] == day]
            rows = []
            for t in day_trades:
                stop_str = f"{t['stop_price']:.2f}" if t.get('stop_price') is not None else ""
                take_str = f"{t['take_profit_price']:.2f}" if t.get('take_profit_price') is not None else ""
                pnl_m_str = f"{t['pnl_monetary']:.2f}" if t.get('pnl_monetary') is not None else ""
                rows.append(
                    "<tr>" +
                    f"<td>{t['entry_time']}</td>" +
                    f"<td>{t['exit_time']}</td>" +
                    f"<td>{t['exit_reason']}</td>" +
                    f"<td>{t['entry_price']:.2f}</td>" +
                    f"<td>{stop_str}</td>" +
                    f"<td>{take_str}</td>" +
                    f"<td>{t['exit_price']:.2f}</td>" +
                    f"<td>{t['holding_period_candles']}</td>" +
                    f"<td>{t['pnl_r']:.2f}R</td>" +
                    f"<td>{pnl_m_str}</td>" +
                    f"<td>{t['result']}</td>" +
                    "</tr>"
                )
            table_html = (
                f"<h3>Dia {day} - Trades (PnL R={stats['pnl_r']:.2f}, Monetário={stats.get('pnl_monetary', 0):.2f})</h3>" +
                "<table class='table'>" +
                "<thead><tr><th>Entrada</th><th>Saída</th><th>Motivo Saída</th><th>Preço Entrada</th><th>Stop</th><th>Take</th><th>Preço Saída</th><th>Candles</th><th>PnL (R)</th><th>PnL Monetário</th><th>Resultado</th></tr></thead><tbody>" +
                "".join(rows) + "</tbody></table>"
            )
            daily_sections.append(table_html)
        trades_table_html = "".join(daily_sections)

        # CSS simples embutido
        css = """
        body {font-family: Arial, sans-serif; margin:24px; color:#222;}
        h1,h2,h3 {margin: 0 0 12px;}
        .section {margin-top:32px;}
        .meta-box {display:flex; flex-wrap:wrap; gap:16px;}
        .meta {background:#f5f5f5; padding:10px 14px; border-radius:6px; border:1px solid #ddd; min-width:220px;}
        table.table {border-collapse: collapse; width:100%; margin-top:12px;}
        table.table th, table.table td {border:1px solid #ccc; padding:6px 8px; font-size:13px; text-align:left;}
        table.table th {background:#fafafa;}
        .kpi-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px;}
        .kpi {background:#ffffff; border:1px solid #ddd; border-radius:6px; padding:10px;}
        .footer {margin-top:40px; font-size:12px; color:#666;}
        code {background:#eee; padding:2px 4px; border-radius:4px;}
        .tag {display:inline-block; background:#004d7a; color:#fff; padding:2px 6px; font-size:11px; border-radius:4px; margin-right:6px;}
        """

        # HTML
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write("<html><head><meta charset='utf-8'><title>Backtest " + ticker + "</title>")
            f.write(f"<style>{css}</style></head><body>")
            f.write(f"<h1>Relatório de Backtest - {ticker}</h1>")
            f.write("<div class='meta-box'>")
            f.write(f"<div class='meta'><strong>Período Início:</strong><br>{r['period']['start']}</div>")
            f.write(f"<div class='meta'><strong>Período Fim:</strong><br>{r['period']['end']}</div>")
            f.write(f"<div class='meta'><strong>Total Candles:</strong><br>{r['period']['total_candles']}</div>")
            f.write(f"<div class='meta'><strong>Threshold:</strong><br>{r['threshold']:.2f}</div>")
            f.write(f"<div class='meta'><strong>Timestamp Execução:</strong><br>{r['timestamp']}</div>")
            if trade_params:
                f.write(f"<div class='meta'><strong>Parâmetros Trade:</strong><br>" + ", ".join([f"{k}={v}" for k,v in trade_params.items()]) + "</div>")
            f.write("</div>")

            # Métricas de Classificação
            f.write("<div class='section'><h2>Métricas de Classificação</h2>")
            f.write("<div class='kpi-grid'>")
            f.write(f"<div class='kpi'><h3>Acurácia</h3><p>{cm['accuracy']:.2%}</p></div>")
            f.write(f"<div class='kpi'><h3>Precisão</h3><p>{cm['precision']:.2%}</p></div>")
            f.write(f"<div class='kpi'><h3>Recall</h3><p>{cm['recall']:.2%}</p></div>")
            f.write(f"<div class='kpi'><h3>F1-Score</h3><p>{cm['f1_score']:.4f}</p></div>")
            f.write("</div>")
            f.write("<h3>Matriz de Confusão</h3>")
            f.write("<table class='table'><thead><tr><th>TN</th><th>FP</th><th>FN</th><th>TP</th></tr></thead><tbody>")
            f.write(f"<tr><td>{conf['true_negatives']}</td><td>{conf['false_positives']}</td><td>{conf['false_negatives']}</td><td>{conf['true_positives']}</td></tr>")
            f.write("</tbody></table>")
            f.write("<h3>Distribuição de Classes</h3>")
            f.write("<table class='table'><thead><tr><th>Tipo</th><th>Calmo</th><th>Explosão</th></tr></thead><tbody>")
            f.write(f"<tr><td>Real</td><td>{dist['calm_actual']}</td><td>{dist['explosion_actual']}</td></tr>")
            f.write(f"<tr><td>Predito</td><td>{dist['calm_predicted']}</td><td>{dist['explosion_predicted']}</td></tr>")
            f.write("</tbody></table>")
            f.write("</div>")

            # Performance Trading
            f.write("<div class='section'><h2>Performance de Trading</h2>")
            perf_rows = [
                ("Total Sinais", tp['total_signals']),
                ("Trades Vencedores", tp['winning_trades']),
                ("Trades Perdedores", tp['losing_trades']),
                ("Win Rate", f"{tp['win_rate']:.2%}"),
                ("Retorno Total (R)", f"{tp['total_return_r']:.2f}"),
                ("Expectativa (R/trade)", f"{tp['expectancy_r']:.2f}"),
                ("Profit Factor", f"{tp['profit_factor']:.2f}"),
                ("Payoff Médio Win", f"{tp['avg_win_r']:.2f}R"),
                ("Payoff Médio Loss", f"{tp['avg_loss_r']:.2f}R"),
            ]
            if tp.get('avg_holding_candles') is not None:
                perf_rows.append(("Média Holding (candles)", f"{tp['avg_holding_candles']:.1f}"))
            if tp.get('initial_capital') is not None:
                perf_rows.append(("Capital Inicial", f"{tp['initial_capital']:.2f}"))
            if tp.get('final_capital') is not None:
                perf_rows.append(("Capital Final", f"{tp['final_capital']:.2f}"))
            if tp.get('monetary_return') is not None:
                perf_rows.append(("Retorno Monetário", f"{tp['monetary_return']:.2f}"))
            if tp.get('stop_loss_pct') is not None and tp.get('take_profit_pct') is not None:
                perf_rows.append(("Stop/Take (%)", f"SL={tp['stop_loss_pct']:.4f} TP={tp['take_profit_pct']:.4f}"))
            if tp.get('exit_reason_counts'):
                reasons_summary = ", ".join([f"{k}={v}" for k,v in tp['exit_reason_counts'].items()])
                perf_rows.append(("Saídas", reasons_summary))
            f.write("<table class='table'><thead><tr><th>Métrica</th><th>Valor</th></tr></thead><tbody>")
            for k,v in perf_rows:
                f.write(f"<tr><td>{k}</td><td>{v}</td></tr>")
            f.write("</tbody></table>")
            f.write("</div>")

            # Trades detalhados por dia
            f.write("<div class='section'><h2>Trades Simulados (Day Trade)</h2>")
            if trades_table_html:
                f.write(trades_table_html)
            else:
                f.write("<p>Nenhum trade registrado.</p>")
            f.write("</div>")

            # Observações
            f.write("<div class='section'><h2>Observações</h2>")
            f.write("<p>Este relatório resume o processo de backtest da estratégia LSTM de volatilidade. Os sinais são gerados a partir de probabilidades acima do threshold definido. Os parâmetros de trade refletem configurações em <code>configs/main.yaml</code>. Ajuste o período, threshold e regras de trade para refinar resultados.</p>")
            f.write("<p>Importante: Os ganhos/perdas em R (risk units) são calculados usando payoff estimado. Resultados monetários dependem da relação entre o stop_loss_pct e capital inicial.</p>")
            f.write("</div>")

            f.write("<div class='footer'>Relatório gerado em " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + " | Engine LSTMVolatility Backtest</div>")
            f.write("</body></html>")

        logger.info(f"Relatório HTML detalhado salvo em: {html_file}")
        return str(html_file)


def main():

    # Função principal para executar backtest standalone.


    config_path = 'configs/main.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    asset_config = None

    for asset in config.get('assets', []):
        if asset.get('enabled', False) and asset.get('backtesting', {}).get('enabled', False):
            asset_config = asset
            break

    if not asset_config:
        logger.error("Nenhum ativo com backtesting habilitado encontrado no config.")
        sys.exit(1)

    ticker = asset_config['ticker']
    backtest_cfg = asset_config['backtesting']

    strategy_name = backtest_cfg.get('strategy_name') or backtest_cfg.get('strategie_name')
    if not strategy_name:
        logger.error("Campo 'strategy_name'/'strategie_name' ausente na seção backtesting do config.")
        sys.exit(1)

    logger.info(f"Executando backtest para {ticker} com estratégia {strategy_name}")

    strategy_config = None
    for strat in asset_config.get('strategies', []):
        if strat['name'] == strategy_name:
            strategy_config = strat
            break

    if not strategy_config:
        logger.error(f"Estratégia {strategy_name} não encontrada para {ticker}.")
        sys.exit(1)

    provider_name = strategy_config.get('provider', 'MetaTrader5')
    data_provider = data_provider_module.get_provider_instance(provider_name)

    timeframe_str = backtest_cfg['timeframe_str']
    mt5_timeframe = data_provider._get_mt5_timeframe(timeframe_str)

    logger.info(f"Buscando dados de {backtest_cfg['start_date']} a {backtest_cfg['end_date']}...")
    
    market_data = data_provider.get_data(
        ticker=ticker,
        start_date=backtest_cfg['start_date'],
        end_date=backtest_cfg['end_date'],
        timeframe=mt5_timeframe
    )

    if market_data.empty:
        logger.error("Nenhum dado obtido para backtest.")
        sys.exit(1)

    logger.info(f"Dados obtidos: {len(market_data)} candles")



    strategy_module_name = strategy_config.get('module')
    strategy_class_name = strategy_config.get('name')
    timeframe_str = backtest_cfg.get('timeframe_str', '')

    try:
        strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
        StrategyClass = getattr(strategy_module, strategy_class_name)
        strategy_params = strategy_config.get('strategy_params', {})
        strategy_instance = StrategyClass(**strategy_params)
    except Exception as e:
        logger.error(f"Erro ao carregar estratégia: {e}")
        sys.exit(1)

    models_dir = Path(config.get('global_settings', {}).get('model_directory', 'models'))
    model_prefix = str(models_dir / f"{ticker}_{strategy_class_name}_{timeframe_str}_prod")
    logger.info(f"Carregando modelo de {model_prefix}...")

    try:
        model = strategy_instance.load(model_prefix)
    except Exception as e:
        logger.error(f"Erro ao carregar modelo: {e}")
        sys.exit(1)




    df_features = strategy_instance.define_features(market_data)
    target = strategy_instance.define_target(df_features)
    feature_names = strategy_instance.get_feature_names()
    X = df_features[feature_names].iloc[:len(target)]
    y = target.values
    logger.info("Executando predições...")

    predictions = model.predict(X)

    if predictions.size == 0:
        logger.error("Modelo retornou predições vazias. Verifique se há dados suficientes após o lookback.")
        sys.exit(1)

    X_scaled = model.scaler.transform(X.values)
    from src.strategies.lstm_volatility import create_sequences
    X_seq, _ = create_sequences(X_scaled, np.zeros(len(X_scaled)), model.lookback)
    probabilities = model.model.predict(X_seq, verbose=0).flatten()
    y_aligned = y[model.lookback:]
    prices_aligned = market_data.iloc[model.lookback:model.lookback+len(y_aligned)]
    if len(probabilities) != len(y_aligned):
        logger.warning(
            f"Probabilidades ({len(probabilities)}) e y_aligned ({len(y_aligned)}) desalinhados. Ajustando para mínimo comum." 
        )
        min_len = min(len(probabilities), len(y_aligned))
        probabilities = probabilities[:min_len]
        y_aligned = y_aligned[:min_len]
        predictions = predictions[:min_len]
    engine = BacktestEngine(config_path)
    trade_params_cfg = {}
    if 'trading_initial_capital' in backtest_cfg:
        trade_params_cfg['initial_capital'] = backtest_cfg.get('trading_initial_capital')
    if 'stop_loss_pct' in backtest_cfg and 'take_profit_pct' in backtest_cfg:
        sl = backtest_cfg.get('stop_loss_pct')
        tpct = backtest_cfg.get('take_profit_pct')
        if sl and sl > 0:
            trade_params_cfg['avg_win_r'] = tpct / sl
            trade_params_cfg['avg_loss_r'] = -1.0
        trade_params_cfg['stop_loss_pct'] = sl
        trade_params_cfg['take_profit_pct'] = tpct
    configured_threshold = backtest_cfg.get('threshold')
    df_opt = None
    if configured_threshold is None:
        best_threshold, df_opt = engine.optimize_threshold(
            probabilities,
            y_aligned,
            prices_aligned,
            ticker
        )
        configured_threshold = best_threshold
    else:
        logger.info(f"Usando threshold definido em config: {configured_threshold:.2f}")

    min_signals = backtest_cfg.get('min_signals')
    max_holding_candles = backtest_cfg.get('max_holding_candles')
    market_close_hour = backtest_cfg.get('market_close_hour', 17)

    results = engine.run_backtest(
        ticker=ticker,
        predictions=predictions,
        probabilities=probabilities,
        actual_targets=y_aligned,
        prices=prices_aligned,
        threshold=configured_threshold,
        trade_params=trade_params_cfg if trade_params_cfg else None,
        min_signals=min_signals,
        market_close_hour=market_close_hour,
        max_holding_candles=max_holding_candles
    )

    report_path = engine.generate_report()
    html_report_path = engine.generate_html_report()

    logger.info(f"=== Backtest Concluído ===")
    logger.info(f"Relatório TXT/JSON salvo em: {report_path}")
    logger.info(f"Relatório HTML salvo em: {html_report_path}")
    
    if df_opt is not None:
        print("\n" + "="*80)
        print("OTIMIZAÇÃO DE THRESHOLD")
        print("="*80)
        print(df_opt.to_string(index=False))
        print("="*80 + "\n")
    else:
        print("\nThreshold do config utilizado diretamente sem otimização.\n")


if __name__ == "__main__":
    main()
