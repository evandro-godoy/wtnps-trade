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
        trade_params: Optional[Dict] = None
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
        
        # Aplicar threshold nas probabilidades
        y_pred_threshold = (probabilities > threshold).astype(int).flatten()
        
        # Métricas de classificação
        metrics = self._calculate_metrics(actual_targets, y_pred_threshold)
        
        # Simular trades
        trade_results = self._simulate_trades(
            y_pred_threshold,
            actual_targets,
            prices,
            ticker,
            avg_win=trade_params.get('avg_win_r', 2.0) if trade_params else 2.0,
            avg_loss=trade_params.get('avg_loss_r', -1.0) if trade_params else -1.0,
            initial_capital=trade_params.get('initial_capital') if trade_params else None,
            stop_loss_pct=trade_params.get('stop_loss_pct') if trade_params else None,
            take_profit_pct=trade_params.get('take_profit_pct') if trade_params else None
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
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        self.results = results
        return results
    
    def _calculate_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict:
        """
        Calcula métricas de classificação.
        
        Args:
            y_true: Targets reais
            y_pred: Predições do modelo
            
        Returns:
            Dicionário com métricas
        """
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
            f.write(f"  Real: Calmo = {dist['calm_actual']}, Explosão = {dist['explosion_actual']}\n")
            f.write(f"  Predito: Calmo = {dist['calm_predicted']}, Explosão = {dist['explosion_predicted']}\n\n")
            f.write("-" * 80 + "\n")
            f.write("PERFORMANCE DE TRADING (Simulação)\n")
            f.write("-" * 80 + "\n")
            tp = self.results['trading_performance']
            f.write(f"Total de Sinais de Entrada: {tp['total_signals']}\n")
            f.write(f"Trades Vencedores: {tp['winning_trades']}\n")
            f.write(f"Trades Perdedores: {tp['losing_trades']}\n")
            f.write(f"Win Rate: {tp['win_rate']:.2%}\n\n")
            f.write(f"Retorno Total: {tp['total_return_r']:.2f}R\n")
            f.write(f"Expectativa por Trade: {tp['expectancy_r']:.2f}R\n")
            f.write(f"Profit Factor: {tp['profit_factor']:.2f}\n\n")
            f.write(f"Payoff Médio: Win = {tp['avg_win_r']:.2f}R, Loss = {tp['avg_loss_r']:.2f}R\n\n")
            if tp.get('initial_capital') is not None:
                f.write(f"Capital Inicial: {tp['initial_capital']:.2f}\n")
            if tp.get('final_capital') is not None:
                f.write(f"Capital Final: {tp['final_capital']:.2f}\n")
            if tp.get('monetary_return') is not None:
                f.write(f"Retorno Monetário: {tp['monetary_return']:.2f}\n")
            if tp.get('stop_loss_pct') is not None and tp.get('take_profit_pct') is not None:
                f.write(f"Stop Loss %: {tp['stop_loss_pct']:.4f} | Take Profit %: {tp['take_profit_pct']:.4f}\n\n")
            if tp['trades_log']:
                f.write("-" * 80 + "\n")
                f.write("AMOSTRA DE TRADES (Primeiros 10)\n")
                f.write("-" * 80 + "\n")
                for trade in tp['trades_log']:
                    f.write(f"  {trade['timestamp']} | {trade['signal']} | {trade['result']} | PnL: {trade['pnl_r']:.2f}R\n")
            f.write("\n" + "=" * 80 + "\n")
            f.write("FIM DO RELATÓRIO\n")
            f.write("=" * 80 + "\n")


def main():
    """
    Função principal para executar backtest standalone.
    """
    import importlib
    from src.data_handler import provider as data_provider_module
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
    strategy_module_name = strategy_config.get('module')
    strategy_class_name = strategy_config.get('name')
    try:
        strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
        StrategyClass = getattr(strategy_module, strategy_class_name)
        strategy_params = strategy_config.get('strategy_params', {})
        strategy_instance = StrategyClass(**strategy_params)
    except Exception as e:
        logger.error(f"Erro ao carregar estratégia: {e}")
        sys.exit(1)
    models_dir = Path(config.get('global_settings', {}).get('model_directory', 'models'))
    model_prefix = str(models_dir / f"{ticker}_{strategy_class_name}_prod")
    logger.info(f"Carregando modelo de {model_prefix}...")
    try:
        model = strategy_instance.load(model_prefix)
    except Exception as e:
        logger.error(f"Erro ao carregar modelo: {e}")
        sys.exit(1)
    provider_name = strategy_config.get('provider', 'MetaTrader5')
    data_provider = data_provider_module.get_provider_instance(provider_name)
    import MetaTrader5 as mt5
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
    }
    timeframe_str = backtest_cfg['timeframe_str']
    mt5_timeframe = tf_map.get(timeframe_str.upper())
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
    results = engine.run_backtest(
        ticker,
        predictions,
        probabilities,
        y_aligned,
        prices_aligned,
        threshold=configured_threshold,
        trade_params=trade_params_cfg if trade_params_cfg else None
    )
    report_path = engine.generate_report()
    logger.info(f"=== Backtest Concluído ===")
    logger.info(f"Relatório salvo em: {report_path}")
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
