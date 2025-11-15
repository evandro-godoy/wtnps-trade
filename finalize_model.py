# finalize_model.py
"""
Script independente para finalizar o treinamento do DRL (Dummy Procedure).

Este script:
1. Carrega a configuração 'configs/main.yaml'.
2. Pergunta ao usuário qual Ticker finalizar.
3. Tenta ler o arquivo '_training_stats.csv' para encontrar o melhor episódio 
   (baseado na maior 'reward_ma_100').
4. Se o CSV não existir (indicando um treino interrompido), ele localiza
   o ÚLTIMO checkpoint (.keras) salvo.
5. Copia o checkpoint selecionado (o melhor ou o último) para o nome
   do arquivo de produção (ex: WDO$_DRLStrategy_prod_drl.keras).

Este script é 100% autônomo e não importa o 'train_drl_model.py'.
"""

# --- Importações Padrão Necessárias ---
import yaml
import logging
import os
import sys
from datetime import datetime
import pandas as pd
import re
import glob
import shutil
from pathlib import Path # Adicionado para consistência com os nomes de arquivo

# ==============================================================================
# SEÇÃO DE CÓDIGO DUPLICADO (Para Independência)
# ==============================================================================

def setup_logging(log_file_prefix='log'):
    """
    Configura o sistema de logging para salvar em arquivo e exibir no console.
    (Código duplicado para independência)
    """
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    log_filename = f"{log_file_prefix}_{datetime.now().strftime('%Y%m%d_%HM%S')}.log"
    log_filepath = os.path.join(log_dir, log_filename)

    # Remove handlers existentes para evitar duplicação
    for handler in logging.root.handlers[:]:
        handler.close()
        logging.root.removeHandler(handler)

    # Configura o logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(log_filepath),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info(f"Logging configurado. Salvando em: {log_filepath}")

def load_config(config_path: str = 'configs/main.yaml') -> dict:
    """
    Carrega o arquivo de configuração YAML.
    (Código duplicado do train_drl_model.py)
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Carregando configuração: {config_path}")
    if not os.path.exists(config_path):
        logger.error(f"Arquivo de configuração não encontrado em: {config_path}")
        return None
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def get_ticker_input(available_tickers: list) -> str:
    """
    Solicita ao usuário que escolha um ticker da lista.
    (Código duplicado do train_drl_model.py)
    """
    logger = logging.getLogger(__name__)
    print("Ativos disponíveis no config:")
    for i, ticker in enumerate(available_tickers, 1):
        print(f"  {i}. {ticker}")
    
    while True:
        try:
            choice = input(f"Escolha o número do ativo para FINALIZAR (1-{len(available_tickers)}): ")
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(available_tickers):
                selected_ticker = available_tickers[choice_idx]
                logger.info(f"Ticker selecionado: {selected_ticker}")
                return selected_ticker
            else:
                print("Escolha inválida. Tente novamente.")
        except ValueError:
            print("Entrada inválida. Por favor, insira um número.")

# ==============================================================================
# LÓGICA PRINCIPAL DE FINALIZAÇÃO
# ==============================================================================

def find_best_model(config: dict, strategy_name: str, ticker: str):
    """
    Lógica principal para encontrar o melhor checkpoint e copiá-lo para produção.
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info(f"Iniciando finalização para: {ticker} | {strategy_name}")
    logger.info("=" * 80)

    model_dir = config['paths']['models_dir']

    # --- Nomenclatura baseada no train_drl_model.py estável ---
    # O stats_path usa '$'
    stats_name = f"{ticker}${strategy_name}_training_stats.csv"
    stats_file_path = os.path.join(model_dir, stats_name)
    
    # O prod_model_name usa '_'
    prod_model_name = f"{ticker}_{strategy_name}_prod_drl.keras"
    prod_model_path = os.path.join(model_dir, prod_model_name)
    
    # O checkpoint_base_name usa '_'
    checkpoint_base_name = f"{ticker}_{strategy_name}_checkpoint"
    # ----------------------------------------------------------------

    best_checkpoint_path = None

    # --- CENÁRIO 1: Tentar ler o arquivo de estatísticas ---
    if os.path.exists(stats_file_path):
        logger.info(f"Analisando arquivo de estatísticas: {stats_file_path}")
        try:
            stats_df = pd.read_csv(stats_file_path)
            if stats_df.empty:
                logger.warning("Arquivo de estatísticas está vazio. Procurando último checkpoint.")
            else:
                # Encontra o índice (linha) da MAIOR recompensa média de 100 episódios
                best_episode_idx = stats_df['reward_ma_100'].idxmax()
                best_stats = stats_df.loc[best_episode_idx]
                best_episode = int(best_stats['episode'])
                best_reward = best_stats['reward_ma_100']

                logger.info(f"Melhor episódio (pelo log): {best_episode} (Reward MA 100: {best_reward:.4f})")
                
                checkpoint_name = f"{checkpoint_base_name}_ep{best_episode}_drl.keras"
                best_checkpoint_path = os.path.join(model_dir, checkpoint_name)

        except Exception as e:
            logger.error(f"Erro ao ler ou analisar o arquivo de estatísticas: {e}. Procurando último checkpoint.")
            best_checkpoint_path = None # Garante que caia no cenário 2

    # --- CENÁRIO 2: CSV não existe ou falhou (Treino interrompido) ---
    if best_checkpoint_path is None or not os.path.exists(best_checkpoint_path):
        if best_checkpoint_path is not None:
            # Isso acontece se o CSV foi lido, mas o .keras correspondente não foi encontrado
            logger.warning(f"Checkpoint do melhor episódio ({best_checkpoint_path}) não encontrado.")
        
        logger.info("Procurando pelo ÚLTIMO checkpoint salvo (maior número de episódio)...")
        
        checkpoint_pattern = os.path.join(model_dir, f"{checkpoint_base_name}_ep*_drl.keras")
        checkpoints = glob.glob(checkpoint_pattern)
        
        if not checkpoints:
            logger.error(f"Nenhum arquivo de checkpoint encontrado com o padrão: {checkpoint_pattern}")
            logger.error("Não é possível gerar o modelo de produção.")
            return

        # Encontra o checkpoint com o maior número de episódio
        latest_episode = -1
        latest_checkpoint_path = None
        for cp_path in checkpoints:
            # Extrai o número do episódio do nome do arquivo
            match = re.search(r'_ep(\d+)_drl\.keras$', cp_path)
            if match:
                episode_num = int(match.group(1))
                if episode_num > latest_episode:
                    latest_episode = episode_num
                    latest_checkpoint_path = cp_path
        
        if latest_checkpoint_path:
            best_checkpoint_path = latest_checkpoint_path
            logger.info(f"  Modelo selecionado (pelo último checkpoint): Episódio {latest_episode}")
        else:
            logger.error("Checkpoints encontrados, mas não foi possível extrair números de episódios.")
            return

    # --- 3. Promover (Copiar) o Melhor Checkpoint para Produção ---
    if best_checkpoint_path and os.path.exists(best_checkpoint_path):
        try:
            shutil.copy(best_checkpoint_path, prod_model_path)
            logger.info("=" * 80)
            logger.info(f"SUCESSO: Modelo de produção salvo em:")
            logger.info(f"{prod_model_path}")
            logger.info(f"(Copiado de: {best_checkpoint_path})")
            logger.info("=" * 80)
        except Exception as e:
            logger.error(f"Falha ao copiar o melhor checkpoint para produção: {e}")
    else:
        logger.warning(f"Checkpoint selecionado ({best_checkpoint_path}) não foi encontrado. O modelo de produção não foi atualizado.")


def main():
    """
    Função principal e independente para finalizar o modelo.
    """
    try:
        setup_logging(log_file_prefix='finalize_model')
        logger = logging.getLogger(__name__)

        config = load_config()
        if config is None:
            sys.exit(1)

        # Lógica duplicada de 'get_ticker_input'
        available_tickers = [
            asset for asset in config['assets'] 
            if config['assets'][asset].get('enabled', False) and 
            'DRLStrategy' in config['assets'][asset].get('strategies', [])
        ]
        
        if not available_tickers:
            logger.error("Nenhum ativo habilitado para DRLStrategy encontrado no 'main.yaml'.")
            return

        ticker_input = get_ticker_input(available_tickers)
        strategy_name = 'DRLStrategy' # Nome fixo
        
        # Executa a lógica de finalização
        find_best_model(config, strategy_name, ticker_input)

    except KeyboardInterrupt:
        logger.warning("Processo de finalização interrompido pelo usuário.")
    except Exception as e:
        logger.error(f"Erro fatal no script de finalização: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Script 'finalize_model.py' concluído.")
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)

if __name__ == "__main__":
    main()