# train_model.py
import yaml
import logging
import json
import base64
import io
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import importlib
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

# Importa o MÓDULO provider
from src.data_handler import provider as data_provider_module
# Importa a classe base da estratégia para type hinting
from src.strategies.base import BaseStrategy

# Configuração básica do logging (stdout). FileHandlers serão adicionados por modelo.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Diretório de relatórios de modelos
REPORTS_DIR = Path('reports/models')
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def compute_classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Computa métricas de classificação e matriz de confusão."""
    y_true = y_true.flatten()
    y_pred = y_pred.flatten()
    if len(y_true) == 0 or len(y_pred) == 0:
        return {
            'accuracy': None, 'precision': None, 'recall': None, 'f1': None,
            'confusion_matrix': {'tn':0,'fp':0,'fn':0,'tp':0}, 'samples': 0
        }
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0,0,0,0)
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

def class_distribution(y: np.ndarray) -> dict:
    """Retorna distribuição de classes (contagem e percentual)."""
    if len(y) == 0:
        return {'counts': {}, 'percents': {}}
    unique, counts = np.unique(y, return_counts=True)
    total = counts.sum()
    counts_dict = {int(k): int(v) for k,v in zip(unique, counts)}
    perc_dict = {int(k): float(v/total*100) for k,v in zip(unique, counts)}
    return {'counts': counts_dict, 'percents': perc_dict, 'total': int(total)}

def save_reports(asset_symbol: str, strategy_name: str, model_obj, report_payload: dict, history: dict,
                 train_probs: np.ndarray = None, y_train_aligned: np.ndarray = None,
                 test_probs: np.ndarray = None, y_test_aligned: np.ndarray = None):
    """Salva relatórios JSON, TXT e HTML para o modelo.
    Inclui curva de precisão/recall por threshold e matriz de confusão visual.
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_name = f"{asset_symbol}_{strategy_name}_{timestamp}"
    json_path = REPORTS_DIR / f"{base_name}.json"
    txt_path = REPORTS_DIR / f"{base_name}.txt"
    html_path = REPORTS_DIR / f"{base_name}.html"

    # JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report_payload, f, indent=2, ensure_ascii=False)
    logger.info(f"Relatório JSON salvo: {json_path}")

    # TXT (human readable resumo rápido)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"Relatório de Treino - {asset_symbol}/{strategy_name} - {timestamp}\n")
        f.write("="*80 + "\n")
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
        f.write("Features Stats (amostra):\n")
        for i, (feat, vals) in enumerate(report_payload['feature_stats'].items()):
            if i >= 5: # limita no txt
                break
            f.write(f"  {feat}: train_mean={vals['train_mean']:.5f} test_mean={vals['test_mean']:.5f}\n")
        f.write("="*80 + "\nFim do Relatório TXT\n")
    logger.info(f"Relatório TXT salvo: {txt_path}")

    # Gráfico de perdas (loss/val_loss) em PNG base64
    loss_img_b64 = ''
    if history:
        fig, ax = plt.subplots(figsize=(6,4))
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

    # Gerar gráfico de curva Precision/Recall vs Threshold (train + teste se disponível)
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
        fig_pr, ax_pr = plt.subplots(figsize=(7,4))
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
            # Usa threshold 0.5 para matriz visual
            preds_split = (probs >= 0.5).astype(int)
            cm_vals = confusion_matrix(y_vals, preds_split)
            fig_cm, ax_cm = plt.subplots(figsize=(4,3))
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
        f.write("<html><head><meta charset='utf-8'><title>Modelo " + asset_symbol + "/" + strategy_name + "</title>\n")
        f.write("<style>body{font-family:Arial; margin:20px;} table{border-collapse:collapse;} th,td{border:1px solid #ccc;padding:4px;} th{background:#f0f0f0;} .section{margin-top:30px;} .metric-box{display:flex;gap:20px;} .metric{padding:10px;border:1px solid #ddd;border-radius:4px;background:#fafafa;} </style></head><body>")
        f.write(f"<h1>Relatório de Treinamento - {asset_symbol} / {strategy_name}</h1>")
        f.write(f"<p>Timestamp: {timestamp}</p>")
        # Métricas comparativas
        f.write("<div class='section'><h2>Métricas de Classificação</h2><div class='metric-box'>")
        for split in ['train','test']:
            m = report_payload['metrics'][split]
            f.write(f"<div class='metric'><h3>{split.title()}</h3>"
                    f"Acurácia: {m['accuracy']:.2%}<br>Precisão: {m['precision']:.2%}<br>Recall: {m['recall']:.2%}<br>F1: {m['f1']:.4f}</div>")
        f.write("</div></div>")
        # Distribuição de classes
        f.write("<div class='section'><h2>Distribuição de Classes</h2><table><tr><th>Split</th><th>Classe</th><th>Count</th><th>%</th></tr>")
        for split in ['train','test']:
            dist = report_payload['class_distribution'][split]
            for cls, cnt in dist['counts'].items():
                pct = dist['percents'].get(cls, 0.0)
                f.write(f"<tr><td>{split}</td><td>{cls}</td><td>{cnt}</td><td>{pct:.2f}%</td></tr>")
        f.write("</table></div>")
        # Feature stats
        f.write("<div class='section'><h2>Estatísticas de Features</h2><table><tr><th>Feature</th><th>Train Mean</th><th>Test Mean</th><th>Train Std</th><th>Test Std</th></tr>")
        for feat, vals in report_payload['feature_stats'].items():
            f.write(f"<tr><td>{feat}</td><td>{vals['train_mean']:.6f}</td><td>{vals['test_mean']:.6f}</td><td>{vals['train_std']:.6f}</td><td>{vals['test_std']:.6f}</td></tr>")
        f.write("</table></div>")
        # Confusion matrices
        f.write("<div class='section'><h2>Matrizes de Confusão</h2><table><tr><th>Split</th><th>TN</th><th>FP</th><th>FN</th><th>TP</th></tr>")
        for split in ['train','test']:
            cm = report_payload['metrics'][split]['confusion_matrix']
            f.write(f"<tr><td>{split}</td><td>{cm['tn']}</td><td>{cm['fp']}</td><td>{cm['fn']}</td><td>{cm['tp']}</td></tr>")
        f.write("</table></div>")
        # Loss chart
        if loss_img_b64:
            f.write("<div class='section'><h2>Curva de Perda</h2><img src='data:image/png;base64," + loss_img_b64 + "' alt='Loss Curve'></div>")
        # Precision/Recall Curve
        if pr_img_b64:
            f.write("<div class='section'><h2>Precision/Recall vs Threshold</h2><img src='data:image/png;base64," + pr_img_b64 + "' alt='PR Curve'></div>")
        # Confusion Matrices Visual
        if cm_img_b64:
            f.write("<div class='section'><h2>Matriz de Confusão Treino (Visual)</h2><img src='data:image/png;base64," + cm_img_b64 + "' alt='Train CM'></div>")
        if cm_test_img_b64:
            f.write("<div class='section'><h2>Matriz de Confusão Teste (Visual)</h2><img src='data:image/png;base64," + cm_test_img_b64 + "' alt='Test CM'></div>")
        f.write("<div class='section'><h2>Metadados</h2><pre>" + json.dumps(report_payload['meta'], indent=2, ensure_ascii=False) + "</pre></div>")
        f.write("</body></html>")
    logger.info(f"Relatório HTML salvo: {html_path}")

def get_model_logger(asset_symbol: str, strategy_name: str) -> logging.Logger:
    """Cria/retorna logger específico do modelo com FileHandler."""
    logger_name = f"model_{asset_symbol}_{strategy_name}"
    mdl_logger = logging.getLogger(logger_name)
    if not mdl_logger.handlers:
        fh = logging.FileHandler(REPORTS_DIR / f"{asset_symbol}_{strategy_name}.log", encoding='utf-8')
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        mdl_logger.addHandler(fh)
        mdl_logger.propagate = True
    return mdl_logger

# --- Função auxiliar para conversão de timeframe ---
def _get_mt5_timeframe_from_string(tf_str: str):
    """Converte string de timeframe para constante MT5."""
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
    }
    tf_constant = tf_map.get(tf_str.upper(), None)
    if tf_constant is None:
         logging.warning(f"Timeframe '{tf_str}' não mapeado ou inválido. Verifique o config.yaml.")
    return tf_constant

# --- Função principal de treino ---

def train_all_models(config_path: str = 'configs/main.yaml'):
    """
    Carrega configs, busca dados, treina e salva modelos
    para ativos configurados.
    """
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
    models_dir = Path(global_settings.get('models_directory', 'models'))
    models_dir.mkdir(parents=True, exist_ok=True)

    for asset_config in config.get('assets', []):
        asset_symbol = asset_config.get('ticker') # Usa o ticker como ID principal
        if not asset_symbol:
             logger.warning("Config de ativo sem 'ticker'. Pulando.")
             continue

        if not asset_config.get('enabled', True):
            logger.info(f"--- Ativo {asset_symbol} desabilitado. Pulando. ---")
            continue

        # --- Itera pelas estratégias do ativo ---
        strategies_list = asset_config.get('strategies', [])
        
        if not strategies_list:
            logger.warning(f"Nenhuma estratégia configurada para {asset_symbol}. Pulando.")
            continue
        
        for strategy_config in strategies_list:
            strategy_name = strategy_config.get('name')
            
            # Pula estratégias DRL (usam train_drl_model.py)
            if strategy_name == 'DRLStrategy':
                logger.info(f"--- Pulando {asset_symbol}/DRLStrategy (use train_drl_model.py) ---")
                continue
            
            logger.info(f"--- Iniciando treino para: {asset_symbol}/{strategy_name} ---")

            # --- Carregamento da Estratégia ---
            strategy_module_name = strategy_config.get('module')
            strategy_class_name = strategy_config.get('name')
            if not strategy_module_name or not strategy_class_name:
                logger.error(f"module/name não definido para {asset_symbol}/{strategy_name}. Pulando.")
                continue

            try:
                strategy_module = importlib.import_module(f"src.strategies.{strategy_module_name}")
                StrategyClass = getattr(strategy_module, strategy_class_name)
                # Passa parâmetros da estratégia do YAML, se existirem
                strategy_params = strategy_config.get('strategy_params', {})
                strategy_instance: BaseStrategy = StrategyClass(**strategy_params)
            except (ImportError, AttributeError, TypeError) as e:
                logger.error(f"Erro ao carregar estratégia {strategy_class_name}: {e}")
                continue

            # --- Obtenção de Dados ---
            data_provider_name = strategy_config.get('provider', 'MetaTrader5')
            train_cfg = strategy_config.get('data', {})
            # Ticker para buscar dados pode ser diferente do symbol principal
            ticker_data = train_cfg.get('ticker_data', asset_symbol) # Usa 'ticker_data' ou fallback para symbol

            # Verifica se as chaves essenciais existem
            required_data_keys = ['start_date', 'end_date', 'timeframe_model']
            if not all(k in train_cfg for k in required_data_keys):
                 logger.error(f"Config 'data' incompleta (faltando {', '.join(k for k in required_data_keys if k not in train_cfg)}) para {asset_symbol}/{strategy_name}. Pulando.")
                 continue

            data_provider = None
            try:
                data_provider = data_provider_module.get_provider_instance(data_provider_name)

                # Usa a chave 'timeframe_model' consistentemente
                tf_string = train_cfg['timeframe_model']
                logger.info(f"Buscando dados para {ticker_data} de {train_cfg['start_date']} a {train_cfg['end_date']} @ {tf_string}...")

                mt5_timeframe_obj = _get_mt5_timeframe_from_string(tf_string)

                if mt5_timeframe_obj is None and data_provider_name == 'MetaTrader5':
                    logger.error(f"Timeframe '{tf_string}' inválido para MT5 no ativo {asset_symbol}/{strategy_name}. Pulando.")
                    continue

                market_data = data_provider.get_data(
                    ticker=ticker_data,
                    start_date=train_cfg["start_date"],
                    end_date=train_cfg["end_date"],
                    timeframe=mt5_timeframe_obj if data_provider_name == 'MetaTrader5' else tf_string
                )

                if market_data.empty:
                    logger.warning(f"Nenhum dado retornado para {ticker_data}. Pulando.")
                    continue
                logger.info(f"Dados obtidos para {ticker_data}: {len(market_data)} registros.")

            except KeyError as e_key: # Captura KeyError específico
                logger.error(f"Erro ao acessar config de dados para {asset_symbol}/{strategy_name}: Chave '{e_key}' não encontrada.", exc_info=False)
                continue # Pula para a próxima estratégia
            except Exception as e:
                logger.error(f"Erro ao obter dados para {ticker_data} via {data_provider_name}: {e}", exc_info=True)
                continue
            finally:
                if data_provider and hasattr(data_provider, 'close_connection'):
                     try: data_provider.close_connection()
                     except Exception as e_close: logger.warning(f"Erro ao fechar conexão {data_provider_name}: {e_close}")

            # --- Preparação dos Dados ---
            try:
                logger.info(f"Definindo features para {asset_symbol}/{strategy_name}...")
                data_with_features = strategy_instance.define_features(market_data)

                logger.info(f"Definindo target para {asset_symbol}/{strategy_name}...")
                target = strategy_instance.define_target(data_with_features)

                feature_names = strategy_instance.get_feature_names()
                missing_features = [f for f in feature_names if f not in data_with_features.columns]
                if missing_features:
                     logger.error(f"Features ausentes para {asset_symbol}/{strategy_name}: {missing_features}. Verifique {strategy_class_name}.")
                     continue

                features = data_with_features[feature_names]
                combined = pd.concat([features, target.rename('target')], axis=1)
                combined.dropna(inplace=True)

                if combined.empty:
                    logger.warning(f"Sem dados restantes após NaNs para {ticker_data}. Pulando.")
                    continue

                X_full = combined[feature_names]
                y_full = combined['target']
                total_samples = len(X_full)
                test_size = max(1, int(total_samples * 0.2))
                train_size = total_samples - test_size
                X_train = X_full.iloc[:train_size]
                y_train = y_full.iloc[:train_size]
                X_test = X_full.iloc[train_size:]
                y_test = y_full.iloc[train_size:]
                logger.info(f"Split temporal realizado: treino={len(X_train)} teste={len(X_test)} (total={total_samples}).")

            except Exception as e:
                logger.error(f"Erro ao preparar dados para {ticker_data}/{strategy_name}: {e}", exc_info=True)
                continue

            # --- Definição e Treino ---
            try:
                logger.info(f"Definindo modelo via {strategy_class_name}...")
                production_model = strategy_instance.define_model()

                logger.info(f"Iniciando treino do modelo para {asset_symbol}/{strategy_name}...")
                production_model.fit(X_train, y_train)
                logger.info(f"Treino para {asset_symbol}/{strategy_name} concluído.")

            except Exception as e:
                logger.error(f"Erro definição/treino para {asset_symbol}/{strategy_name}: {e}", exc_info=True)
                continue

            # --- Salvamento ---
            try:
                # NOVO FORMATO: ticker_StrategyName_prod
                model_save_prefix = str(models_dir / f"{asset_symbol}_{strategy_class_name}_{tf_string}_prod")
                logger.info(f"Salvando modelo para {asset_symbol}/{strategy_name} -> {model_save_prefix}...")
                strategy_instance.save(production_model, model_save_prefix)
                logger.info(f"Modelo para {asset_symbol}/{strategy_name} salvo com sucesso.")

                # --- Avaliação Treino/Teste ---
                lookback = getattr(production_model, 'lookback', 0)
                # Predições treino (binárias) e probabilidades
                # Função auxiliar para probabilidades
                def _predict_probs(wrapper, X_df: pd.DataFrame):
                    if not isinstance(X_df, (pd.DataFrame, np.ndarray)) or len(X_df) == 0:
                        return np.array([])
                    X_vals = X_df.values if isinstance(X_df, pd.DataFrame) else X_df
                    X_scaled = wrapper.scaler.transform(X_vals)
                    y_dummy = np.zeros(len(X_scaled))
                    from src.strategies.lstm_volatility import create_sequences
                    X_seq, _ = create_sequences(X_scaled, y_dummy, wrapper.lookback)
                    if X_seq is None or len(X_seq) == 0:
                        return np.array([])
                    probs = wrapper.model.predict(X_seq, verbose=0).flatten()
                    return probs

                train_probs_full = _predict_probs(production_model, X_train)
                train_preds = (train_probs_full >= 0.5).astype(int) if len(train_probs_full) else production_model.predict(X_train)
                y_train_aligned = y_train.iloc[lookback:]
                train_probs_aligned = train_probs_full[:len(y_train_aligned)] if len(train_probs_full) > len(y_train_aligned) else train_probs_full
                train_preds_aligned = train_preds[:len(y_train_aligned)] if len(train_preds) > len(y_train_aligned) else train_preds
                # Predições teste
                test_probs_full = _predict_probs(production_model, X_test) if len(X_test) > lookback else np.array([])
                test_preds = (test_probs_full >= 0.5).astype(int) if len(test_probs_full) else np.array([])
                y_test_aligned = y_test.iloc[lookback:] if len(X_test) > lookback else np.array([])
                test_probs_aligned = test_probs_full[:len(y_test_aligned)] if len(test_probs_full) > len(y_test_aligned) else test_probs_full
                if isinstance(y_test_aligned, pd.Series):
                    y_test_aligned = y_test_aligned.values
                # Métricas
                train_metrics = compute_classification_metrics(y_train_aligned.values if isinstance(y_train_aligned, pd.Series) else y_train_aligned, train_preds_aligned)
                test_metrics = compute_classification_metrics(y_test_aligned, test_preds)

                # Feature stats
                feat_stats = feature_statistics(X_train, X_test)
                # Distribuição classes
                dist_train = class_distribution(y_train_aligned.values if isinstance(y_train_aligned, pd.Series) else y_train_aligned)
                dist_test = class_distribution(y_test_aligned)

                # Monta payload relatório
                report_payload = {
                    'asset': asset_symbol,
                    'strategy': strategy_name,
                    'timestamp': datetime.now().isoformat(),
                    'metrics': {
                        'train': train_metrics,
                        'test': test_metrics
                    },
                    'feature_stats': feat_stats,
                    'class_distribution': {
                        'train': dist_train,
                        'test': dist_test
                    },
                    'meta': {
                        'total_samples': total_samples,
                        'train_samples': int(len(X_train)),
                        'test_samples': int(len(X_test)),
                        'lookback': int(lookback),
                        'epochs': int(getattr(production_model, 'epochs', 0)),
                        'model_path_prefix': model_save_prefix
                    }
                }

                # Logger específico do modelo
                mdl_logger = get_model_logger(asset_symbol, strategy_name)
                mdl_logger.info(f"Resumo métricas treino: {train_metrics}")
                mdl_logger.info(f"Resumo métricas teste: {test_metrics}")
                mdl_logger.info(f"Distribuição treino: {dist_train}")
                mdl_logger.info(f"Distribuição teste: {dist_test}")
                mdl_logger.info(f"Features stats (primeiras 3): {dict(list(feat_stats.items())[:3])}")
                if hasattr(production_model, 'last_history') and production_model.last_history:
                    mdl_logger.info(f"Chaves histórico: {list(production_model.last_history.keys())}")
                    mdl_logger.info(f"Perda final: {production_model.last_history.get('loss', [None])[-1]}")

                # Salva relatórios
                save_reports(asset_symbol, strategy_name, production_model, report_payload, getattr(production_model, 'last_history', {}),
                             train_probs=train_probs_aligned, y_train_aligned=y_train_aligned.values if isinstance(y_train_aligned, pd.Series) else y_train_aligned,
                             test_probs=test_probs_aligned, y_test_aligned=y_test_aligned)

            except Exception as e:
                logger.error(f"Erro ao salvar modelo para {asset_symbol}/{strategy_name}: {e}", exc_info=True)
                continue

    logger.info("--- Treinamento de todos os modelos concluído. ---")


if __name__ == "__main__":
    train_all_models()