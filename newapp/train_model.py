# newapp/train_model.py
"""ML Model Training Script for newapp.

Adapts legacy train_model.py to use newapp architecture:
- HybridDataLoader for data fetching (DB-first + provider fallback)
- SQLAlchemy models and repositories for persistence
- Saves models to newapp/models/ directory
- Stores training metrics in wtnps-trade.db

Maintains legacy business logic and model architecture unchanged.
"""
import sys
import os
import json
import base64
import io
import time
from datetime import datetime
from pathlib import Path
import logging

import yaml
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.model_selection import train_test_split

# Add project root to path for absolute imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from newapp.src.data_handler.hybrid_data_loader import get_default_provider
from newapp.src.database.db import get_db
from newapp.src.database.repository import TrainingRunRepository
from newapp.src.strategies.base import BaseStrategy

# Configuração básica do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')
logger = logging.getLogger(__name__)

# Diretório de relatórios
REPORTS_DIR = Path('newapp/reports/models')
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def compute_classification_metrics(y_true, y_pred) -> dict:
    """Computa métricas de classificação e matriz de confusão.
    
    Args:
        y_true: True labels (can be Series or ndarray)
        y_pred: Predicted labels (can be Series or ndarray)
        
    Returns:
        Dict with metrics and confusion matrix
    """
    # Convert to numpy arrays if needed
    if hasattr(y_true, 'values'):
        y_true = y_true.values
    if hasattr(y_pred, 'values'):
        y_pred = y_pred.values
    
    # Flatten arrays
    y_true = np.asarray(y_true).flatten()
    y_pred = np.asarray(y_pred).flatten()
    
    if len(y_true) == 0 or len(y_pred) == 0:
        return {
            'accuracy': None, 'precision': None, 'recall': None, 'f1': None,
            'confusion_matrix': {'tn': 0, 'fp': 0, 'fn': 0, 'tp': 0}, 'samples': 0
        }
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    return {
        'accuracy': float(acc),
        'precision': float(prec),
        'recall': float(rec),
        'f1': float(f1),
        'confusion_matrix': {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
        'samples': int(len(y_true))
    }


def feature_statistics(train_df: pd.DataFrame, test_df: pd.DataFrame) -> dict:
    """Coleta estatísticas simples (mean/std/min/max) para cada feature."""
    stats = {}
    for col in train_df.columns:
        if col not in test_df.columns:
            continue
        stats[col] = {
            'train_mean': float(train_df[col].mean()),
            'test_mean': float(test_df[col].mean()),
            'train_std': float(train_df[col].std()),
            'test_std': float(test_df[col].std()),
            'train_min': float(train_df[col].min()),
            'test_min': float(test_df[col].min()),
            'train_max': float(train_df[col].max()),
            'test_max': float(test_df[col].max())
        }
    return stats


def class_distribution(y) -> dict:
    """Retorna distribuição de classes (contagem e percentual).
    
    Args:
        y: Labels (can be Series or ndarray)
        
    Returns:
        Dict with counts, percents, and total
    """
    # Convert to numpy array if needed
    if hasattr(y, 'values'):
        y = y.values
    y = np.asarray(y).flatten()
    
    if len(y) == 0:
        return {'counts': {}, 'percents': {}, 'total': 0}
    unique, counts = np.unique(y, return_counts=True)
    total = counts.sum()
    counts_dict = {int(k): int(v) for k, v in zip(unique, counts)}
    perc_dict = {int(k): float(v / total * 100) for k, v in zip(unique, counts)}
    return {'counts': counts_dict, 'percents': perc_dict, 'total': int(total)}


def save_reports(asset_symbol: str, strategy_name: str, timeframe_str: str, model_obj, report_payload: dict, history: dict,
                 train_probs: np.ndarray = None, y_train_aligned: np.ndarray = None,
                 test_probs: np.ndarray = None, y_test_aligned: np.ndarray = None):
    """Salva relatórios JSON, TXT e HTML para o modelo."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_name = f"{asset_symbol}_{strategy_name}_{timeframe_str}_{timestamp}"
    json_path = REPORTS_DIR / f"{base_name}.json"
    txt_path = REPORTS_DIR / f"{base_name}.txt"
    html_path = REPORTS_DIR / f"{base_name}.html"

    # JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report_payload, f, indent=2, ensure_ascii=False)
    logger.info(f"Relatório JSON salvo: {json_path}")

    # TXT (resumo rápido)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"Relatório de Treino - {asset_symbol}/{strategy_name}/{timeframe_str} - {timestamp}\n")
        f.write("=" * 80 + "\n")
        f.write("Métricas Treino:\n")
        train_m = report_payload['metrics']['train']
        f.write(f"  Acurácia: {train_m['accuracy']:.2%}\n")
        f.write(f"  Precisão: {train_m['precision']:.2%}\n")
        f.write(f"  Recall: {train_m['recall']:.2%}\n")
        f.write(f"  F1: {train_m['f1']:.4f}\n")
        f.write("Métricas Teste:\n")
        test_m = report_payload['metrics']['test']
        f.write(f"  Acurácia: {test_m['accuracy']:.2%}\n")
        f.write(f"  Precisão: {test_m['precision']:.2%}\n")
        f.write(f"  Recall: {test_m['recall']:.2%}\n")
        f.write(f"  F1: {test_m['f1']:.4f}\n")
        f.write("\nDistribuição Classes (Treino): " + str(report_payload['class_distribution']['train']) + "\n")
        f.write("Distribuição Classes (Teste): " + str(report_payload['class_distribution']['test']) + "\n")
        f.write("=" * 80 + "\nFim do Relatório TXT\n")
    logger.info(f"Relatório TXT salvo: {txt_path}")

    # Gráfico de perdas (loss/val_loss) em PNG base64
    loss_img_b64 = ''
    if history:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(history.get('loss', []), label='loss')
        if 'val_loss' in history:
            ax.plot(history.get('val_loss', []), label='val_loss')
        ax.set_title('Curva de Perda por Época')
        ax.set_xlabel('Época')
        ax.set_ylabel('Perda')
        ax.legend()
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        loss_img_b64 = base64.b64encode(buf.read()).decode('utf-8')

    # Gerar gráfico de curva Precision/Recall vs Threshold
    pr_img_b64 = ''
    if train_probs is not None and y_train_aligned is not None and len(train_probs) == len(y_train_aligned):
        thresholds = np.linspace(0.05, 0.95, 19)
        prec_train = []
        rec_train = []
        prec_test = []
        rec_test = []
        for th in thresholds:
            train_pred_th = (train_probs >= th).astype(int)
            m_train = compute_classification_metrics(y_train_aligned, train_pred_th)
            prec_train.append(m_train['precision'] if m_train['precision'] is not None else 0)
            rec_train.append(m_train['recall'] if m_train['recall'] is not None else 0)
            if test_probs is not None and y_test_aligned is not None and len(test_probs) == len(y_test_aligned):
                test_pred_th = (test_probs >= th).astype(int)
                m_test = compute_classification_metrics(y_test_aligned, test_pred_th)
                prec_test.append(m_test['precision'] if m_test['precision'] is not None else 0)
                rec_test.append(m_test['recall'] if m_test['recall'] is not None else 0)

        fig_pr, ax_pr = plt.subplots(figsize=(7, 4))
        ax_pr.plot(thresholds, prec_train, label='Train Precision', color='tab:blue')
        ax_pr.plot(thresholds, rec_train, label='Train Recall', color='tab:orange')
        if prec_test:
            ax_pr.plot(thresholds, prec_test, '--', label='Test Precision', color='tab:blue', alpha=0.6)
        if rec_test:
            ax_pr.plot(thresholds, rec_test, '--', label='Test Recall', color='tab:orange', alpha=0.6)
        ax_pr.set_xlabel('Threshold')
        ax_pr.set_ylabel('Score')
        ax_pr.set_title('Curva Precision/Recall vs Threshold')
        ax_pr.grid(alpha=0.3)
        ax_pr.legend()
        buf_pr = io.BytesIO()
        fig_pr.tight_layout()
        fig_pr.savefig(buf_pr, format='png')
        plt.close(fig_pr)
        buf_pr.seek(0)
        pr_img_b64 = base64.b64encode(buf_pr.read()).decode('utf-8')

    # Gerar matriz de confusão visual (train e teste)
    cm_img_b64 = ''
    cm_test_img_b64 = ''
    for split_name, probs, y_vals, container in [
        ('Train', train_probs, y_train_aligned, 'train'),
        ('Test', test_probs, y_test_aligned, 'test')
    ]:
        if probs is not None and y_vals is not None and len(probs) == len(y_vals) and len(y_vals) > 0:
            preds_split = (probs >= 0.5).astype(int)
            cm_vals = confusion_matrix(y_vals, preds_split)
            fig_cm, ax_cm = plt.subplots(figsize=(4, 3))
            sns.heatmap(cm_vals, annot=True, fmt='d', cmap='Blues', cbar=False, ax=ax_cm)
            ax_cm.set_title(f'Matriz de Confusão {split_name} (th=0.5)')
            ax_cm.set_xlabel('Predito')
            ax_cm.set_ylabel('Real')
            buf_cm = io.BytesIO()
            fig_cm.tight_layout()
            fig_cm.savefig(buf_cm, format='png')
            plt.close(fig_cm)
            buf_cm.seek(0)
            b64_img = base64.b64encode(buf_cm.read()).decode('utf-8')
            if split_name == 'Train':
                cm_img_b64 = b64_img
            else:
                cm_test_img_b64 = b64_img

    # HTML detalhado
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write("<html><head><meta charset='utf-8'><title>Modelo " + asset_symbol + "/" + strategy_name + "/" + timeframe_str + "</title>\n")
        f.write("<style>body{font-family:Arial; margin:20px;} table{border-collapse:collapse;} th,td{border:1px solid #ccc;padding:4px;} th{background:#f0f0f0;} .section{margin-top:30px;} .metric-box{display:flex;gap:20px;} .metric{padding:10px;border:1px solid #ddd;border-radius:4px;background:#fafafa;} </style></head><body>")
        f.write(f"<h1>Relatório de Treinamento - {asset_symbol} / {strategy_name} / {timeframe_str}</h1>")
        f.write(f"<p>Timestamp: {timestamp}</p>")
        # Métricas comparativas
        f.write("<div class='section'><h2>Métricas de Classificação</h2><div class='metric-box'>")
        for split in ['train', 'test']:
            m = report_payload['metrics'][split]
            f.write(f"<div class='metric'><h3>{split.capitalize()}</h3>Acc: {m['accuracy']:.2%}<br>Prec: {m['precision']:.2%}<br>Rec: {m['recall']:.2%}<br>F1: {m['f1']:.4f}</div>")
        f.write("</div></div>")
        # Distribuição de classes
        f.write("<div class='section'><h2>Distribuição de Classes</h2><table><tr><th>Split</th><th>Classe</th><th>Count</th><th>%</th></tr>")
        for split in ['train', 'test']:
            dist = report_payload['class_distribution'][split]
            for cls, cnt in dist['counts'].items():
                f.write(f"<tr><td>{split}</td><td>{cls}</td><td>{cnt}</td><td>{dist['percents'][cls]:.2f}%</td></tr>")
        f.write("</table></div>")
        # Feature stats
        f.write("<div class='section'><h2>Estatísticas de Features (amostra)</h2><table><tr><th>Feature</th><th>Train Mean</th><th>Test Mean</th><th>Train Std</th><th>Test Std</th></tr>")
        for i, (feat, vals) in enumerate(report_payload['feature_stats'].items()):
            if i >= 10:
                break
            f.write(f"<tr><td>{feat}</td><td>{vals['train_mean']:.5f}</td><td>{vals['test_mean']:.5f}</td><td>{vals['train_std']:.5f}</td><td>{vals['test_std']:.5f}</td></tr>")
        f.write("</table></div>")
        # Confusion matrices
        f.write("<div class='section'><h2>Matrizes de Confusão</h2><table><tr><th>Split</th><th>TN</th><th>FP</th><th>FN</th><th>TP</th></tr>")
        for split in ['train', 'test']:
            cm = report_payload['metrics'][split]['confusion_matrix']
            f.write(f"<tr><td>{split}</td><td>{cm['tn']}</td><td>{cm['fp']}</td><td>{cm['fn']}</td><td>{cm['tp']}</td></tr>")
        f.write("</table></div>")
        # Loss chart
        if loss_img_b64:
            f.write(f"<div class='section'><h2>Curva de Perda</h2><img src='data:image/png;base64,{loss_img_b64}' style='max-width:600px;'></div>")
        # Precision/Recall Curve
        if pr_img_b64:
            f.write(f"<div class='section'><h2>Curva Precision/Recall</h2><img src='data:image/png;base64,{pr_img_b64}' style='max-width:700px;'></div>")
        # Confusion Matrices Visual
        if cm_img_b64:
            f.write(f"<div class='section'><h2>Matriz de Confusão (Train)</h2><img src='data:image/png;base64,{cm_img_b64}' style='max-width:400px;'></div>")
        if cm_test_img_b64:
            f.write(f"<div class='section'><h2>Matriz de Confusão (Test)</h2><img src='data:image/png;base64,{cm_test_img_b64}' style='max-width:400px;'></div>")
        f.write("<div class='section'><h2>Metadados</h2><pre>" + json.dumps(report_payload['meta'], indent=2, ensure_ascii=False) + "</pre></div>")
        f.write("</body></html>")
    logger.info(f"Relatório HTML salvo: {html_path}")


def train_all_models(config_path: str = 'newapp/configs/main.yaml'):
    """Carrega configs, busca dados via HybridDataLoader, treina e salva modelos no newapp."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Config não encontrado: {config_path}")
        return
    except yaml.YAMLError as e:
        logger.error(f"Erro ao ler YAML: {e}")
        return

    global_settings = config.get('global_settings', {})
    models_dir = Path(global_settings.get('model_directory', 'newapp/models'))
    models_dir.mkdir(parents=True, exist_ok=True)

    # Database session for storing training metrics
    db = next(get_db())

    for asset_config in config.get('assets', []):
        asset_symbol = asset_config.get('ticker')
        if not asset_symbol:
            logger.warning("Ativo sem ticker definido, pulando...")
            continue

        if not asset_config.get('enabled', True):
            logger.info(f"Ativo {asset_symbol} desabilitado, pulando...")
            continue

        strategies_list = asset_config.get('strategies', [])
        if not strategies_list:
            logger.warning(f"Nenhuma estratégia configurada para {asset_symbol}, pulando...")
            continue

        for strategy_config in strategies_list:
            strategy_name = strategy_config.get('name')
            strategy_module = strategy_config.get('module')
            data_config = strategy_config.get('data', {})
            strategy_params = strategy_config.get('strategy_params', {})

            if not strategy_name or not strategy_module:
                logger.warning(f"Estratégia sem nome ou módulo em {asset_symbol}, pulando...")
                continue

            logger.info(f"\n{'=' * 80}")
            logger.info(f"Iniciando treino: {asset_symbol} / {strategy_name}")
            logger.info(f"{'=' * 80}\n")

            start_time = time.time()

            # --- 1. Importar classe de estratégia dinamicamente ---
            try:
                strategy_module_path = f"newapp.src.strategies.{strategy_module}"
                strategy_class_obj = __import__(strategy_module_path, fromlist=[strategy_name])
                StrategyClass = getattr(strategy_class_obj, strategy_name)
            except (ImportError, AttributeError) as e:
                logger.error(f"Erro ao importar estratégia {strategy_name} de {strategy_module}: {e}")
                continue

            # --- 2. Instanciar estratégia ---
            try:
                strategy_instance: BaseStrategy = StrategyClass(**strategy_params)
            except Exception as e:
                logger.error(f"Erro ao instanciar {strategy_name} com params {strategy_params}: {e}")
                continue

            # --- 3. Buscar dados usando HybridDataLoader ---
            start_date_str = data_config.get('start_date', '2022-01-01')
            end_date_str = data_config.get('end_date', datetime.now().strftime('%Y-%m-%d'))
            timeframe_str = data_config.get('timeframe_model', 'M5')

            try:
                start_dt = pd.to_datetime(start_date_str)
                end_dt = pd.to_datetime(end_date_str)
            except Exception as e:
                logger.error(f"Erro ao parsear datas {start_date_str} - {end_date_str}: {e}")
                continue

            logger.info(f"Buscando dados via HybridDataLoader: {asset_symbol} {timeframe_str} ({start_date_str} a {end_date_str})")
            try:
                provider = get_default_provider()
                data_df = provider.get_data(
                    ticker=asset_symbol,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    timeframe=timeframe_str
                )
            except Exception as e:
                logger.error(f"Erro ao buscar dados para {asset_symbol}: {e}")
                continue

            if data_df.empty:
                logger.warning(f"DataFrame vazio para {asset_symbol}, pulando...")
                continue

            logger.info(f"Dados carregados: {len(data_df)} candles")

            # --- 4. Gerar features ---
            logger.info("Gerando features...")
            try:
                data_with_features = strategy_instance.define_features(data_df)
            except Exception as e:
                logger.error(f"Erro ao gerar features: {e}")
                continue

            # --- 5. Gerar target ---
            logger.info("Gerando target...")
            try:
                target_series = strategy_instance.define_target(data_with_features)
            except Exception as e:
                logger.error(f"Erro ao gerar target: {e}")
                continue

            # --- 6. Preparar features e target ---
            feature_names = strategy_instance.get_feature_names()
            logger.info(f"Features utilizadas ({len(feature_names)}): {feature_names[:5]}...")

            # Alinhar índices (remover NaNs do target)
            valid_idx = target_series.notna()
            X = data_with_features.loc[valid_idx, feature_names]
            y = target_series.loc[valid_idx]

            logger.info(f"Amostras válidas após limpeza: {len(X)}")

            if len(X) < 100:
                logger.warning(f"Dados insuficientes para treino ({len(X)} amostras), pulando...")
                continue

            # --- 7. Train/Test Split ---
            test_size = 0.2
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, shuffle=False)
            logger.info(f"Train: {len(X_train)} amostras, Test: {len(X_test)} amostras")

            # --- 8. Instanciar modelo ---
            logger.info("Instanciando modelo...")
            try:
                model = strategy_instance.define_model()
            except Exception as e:
                logger.error(f"Erro ao definir modelo: {e}")
                continue

            # --- 9. Treinar modelo ---
            logger.info("Iniciando treinamento...")
            try:
                model.fit(X_train, y_train)
            except Exception as e:
                logger.error(f"Erro durante treinamento: {e}")
                continue

            training_duration = time.time() - start_time
            logger.info(f"Treinamento concluído em {training_duration:.2f}s")

            # --- 10. Avaliar modelo ---
            logger.info("Avaliando modelo...")
            try:
                y_train_pred = model.predict(X_train)
                y_test_pred = model.predict(X_test)
                y_train_proba = model.predict_proba(X_train)[:, 1] if hasattr(model, 'predict_proba') else None
                y_test_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else None
            except Exception as e:
                logger.error(f"Erro ao gerar predições: {e}")
                continue

            # Align y_train/y_test with predictions (LSTM uses sequences, reducing sample count)
            # Extract lookback from strategy params to calculate alignment
            lookback = strategy_params.get('lookback', 108)
            
            # For LSTM models, predictions start after lookback period
            # Align y_train and y_test by slicing from lookback onwards
            y_train_aligned = y_train.iloc[lookback:].reset_index(drop=True) if len(y_train_pred) < len(y_train) else y_train
            y_test_aligned = y_test.iloc[lookback:].reset_index(drop=True) if len(y_test_pred) < len(y_test) else y_test
            
            # Ensure exact length match (handle edge cases)
            if len(y_train_aligned) > len(y_train_pred):
                y_train_aligned = y_train_aligned.iloc[:len(y_train_pred)]
            if len(y_test_aligned) > len(y_test_pred):
                y_test_aligned = y_test_aligned.iloc[:len(y_test_pred)]
            
            logger.info(f"Amostras alinhadas - Train: {len(y_train_aligned)} vs {len(y_train_pred)}, Test: {len(y_test_aligned)} vs {len(y_test_pred)}")

            # Metrics (using aligned targets)
            train_metrics = compute_classification_metrics(y_train_aligned, y_train_pred)
            test_metrics = compute_classification_metrics(y_test_aligned, y_test_pred)
            train_dist = class_distribution(y_train_aligned)
            test_dist = class_distribution(y_test_aligned)
            feat_stats = feature_statistics(X_train, X_test)

            logger.info(f"Train - Acc: {train_metrics['accuracy']:.2%}, Prec: {train_metrics['precision']:.2%}, Rec: {train_metrics['recall']:.2%}, F1: {train_metrics['f1']:.4f}")
            logger.info(f"Test  - Acc: {test_metrics['accuracy']:.2%}, Prec: {test_metrics['precision']:.2%}, Rec: {test_metrics['recall']:.2%}, F1: {test_metrics['f1']:.4f}")

            # --- 11. Salvar modelo ---
            model_path_prefix = models_dir / f"{asset_symbol}_{strategy_name}_{timeframe_str}_prod"
            logger.info(f"Salvando modelo em: {model_path_prefix}")
            try:
                strategy_instance.save(model, str(model_path_prefix))
            except Exception as e:
                logger.error(f"Erro ao salvar modelo: {e}")
                continue

            # --- 12. Extrair histórico de treino (loss) ---
            history = {}
            if hasattr(model, 'last_history') and model.last_history:
                history = model.last_history
                logger.info(f"Histórico de treino capturado: {len(history.get('loss', []))} épocas")

            # --- 13. Salvar relatórios ---
            report_payload = {
                'meta': {
                    'asset': asset_symbol,
                    'strategy': strategy_name,
                    'timeframe': timeframe_str,
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'train_samples': len(X_train),
                    'test_samples': len(X_test),
                    'training_duration_seconds': training_duration,
                    'strategy_params': strategy_params
                },
                'metrics': {
                    'train': train_metrics,
                    'test': test_metrics
                },
                'class_distribution': {
                    'train': train_dist,
                    'test': test_dist
                },
                'feature_stats': feat_stats
            }

            save_reports(
                asset_symbol, strategy_name, timeframe_str, model, report_payload, history,
                y_train_proba, y_train_aligned.values if hasattr(y_train_aligned, 'values') else y_train_aligned,
                y_test_proba, y_test_aligned.values if hasattr(y_test_aligned, 'values') else y_test_aligned
            )

            # --- 14. Salvar métricas no database ---
            logger.info("Salvando métricas no database...")
            try:
                TrainingRunRepository.save_training_run(
                    db=db,
                    symbol=asset_symbol,
                    strategy_name=strategy_name,
                    timeframe_str=timeframe_str,
                    start_date=start_dt,
                    end_date=end_dt,
                    model_path_prefix=str(model_path_prefix),
                    train_metrics=train_metrics,
                    test_metrics=test_metrics,
                    class_distribution={'train': train_dist, 'test': test_dist},
                    strategy_params=json.dumps(strategy_params),
                    feature_stats=json.dumps(feat_stats),
                    loss_history=json.dumps(history.get('loss', [])) if history else None,
                    val_loss_history=json.dumps(history.get('val_loss', [])) if history else None,
                    total_epochs=len(history.get('loss', [])) if history else None,
                    training_duration_seconds=training_duration
                )
                logger.info("Métricas salvas no database com sucesso!")
            except Exception as e:
                logger.error(f"Erro ao salvar métricas no database: {e}")

            logger.info(f"✅ Modelo {asset_symbol}/{strategy_name}/{timeframe_str} treinado e salvo com sucesso!\n")

    db.close()
    logger.info("\n" + "=" * 80)
    logger.info("🎉 Treinamento de todos os modelos concluído!")
    logger.info("=" * 80)


if __name__ == "__main__":
    train_all_models()
