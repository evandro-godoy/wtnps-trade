# train_drl_model.py
"""
Script de treinamento para agentes Deep Reinforcement Learning (DRL).

Este script:
1. Carrega a configuração de um ativo do configs/main.yaml
2. Instancia o ambiente de trading customizado (TradingEnv)
3. Cria e treina um agente DDQN
4. Salva o modelo treinado usando a DRLStrategy

Uso:
    poetry run python train_drl_model.py

O script pedirá o ticker do ativo a ser treinado.
"""
import os
import yaml
import logging
from pathlib import Path
from time import time
import pandas as pd
import numpy as np
import re
from tensorflow import keras
from collections import deque

# --- NOVAS IMPORTAÇÕES ---
# Importações necessárias para o novo logger e a função de finalização
import shutil
import glob
from src.utils.logger import setup_logging
from src.reporting.plot import plot_training_stats
# -------------------------

# Imports do projeto
from src.environments.trading_env import TradingEnv
from src.agents.drl_agent import DDQNAgent
from src.data_handler.provider import get_provider_instance
from src.strategies.drl_strategy import DRLStrategy

# --- CONFIGURAÇÃO DE LOGGING ANTIGA REMOVIDA ---
# O logging.basicConfig() que estava aqui foi removido
# e substituído pela chamada setup_logging() dentro da main().


def load_config(config_path: str = 'configs/main.yaml') -> dict:
    """Carrega o arquivo de configuração YAML."""
    # (O logger é obtido dentro da 'main' agora)
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def get_ticker_input(available_tickers: list) -> str:
    """Solicita ao usuário que escolha um ticker da lista."""
    logger = logging.getLogger(__name__)
    print("Ativos disponíveis no config:")
    for i, ticker in enumerate(available_tickers, 1):
        print(f"  {i}. {ticker}")
    
    while True:
        try:
            choice = input(f"Escolha o número do ativo para treinar (1-{len(available_tickers)}): ")
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(available_tickers):
                selected_ticker = available_tickers[choice_idx]
                logger.info(f"Ticker selecionado: {selected_ticker}")
                return selected_ticker
            else:
                print("Escolha inválida. Tente novamente.")
        except ValueError:
            print("Entrada inválida. Por favor, insira um número.")

def save_checkpoint(agent, path: str):
    """Salva o checkpoint do modelo do agente."""
    try:
        agent.save(path)
        logging.info(f"Checkpoint salvo em: {path}")
    except Exception as e:
        logging.error(f"Erro ao salvar checkpoint: {e}")

# --- NOVA FUNÇÃO ADICIONADA ---
def finalize_training(config: dict, strategy_name: str, ticker: str):
    """
    Finaliza o treinamento: identifica o melhor modelo (ou o último, se
    interrompido) e o promove para produção.
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("FINALIZANDO E SELECIONANDO MELHOR MODELO")
    logger.info("=" * 80)

    # --- 1. Definir Caminhos ---
    base_name = f"{ticker}${strategy_name}"
    model_dir = config['paths']['models_dir']
    report_dir = config['paths']['reports_dir']

    stats_file_path = os.path.join(model_dir, f"{base_name}_training_stats.csv")
    prod_model_path = os.path.join(model_dir, f"{base_name}_prod_drl.keras")
    plot_file_path = os.path.join(report_dir, f"{base_name}_training_report.html")

    best_checkpoint_path = None
    stats_df = None

    # --- 2. Lógica de Seleção ---
    
    # CENÁRIO 1: Treino concluído (arquivo de log existe)
    if os.path.exists(stats_file_path):
        logger.info("Analisando arquivo de estatísticas (CSV) para encontrar o melhor episódio.")
        try:
            stats_df = pd.read_csv(stats_file_path)
            if stats_df.empty:
                logger.warning("Arquivo de estatísticas está vazio.")
            else:
                # Encontra o índice da MAIOR recompensa média de 100 episódios
                best_episode_idx = stats_df['reward_ma_100'].idxmax()
                best_stats = stats_df.loc[best_episode_idx]
                best_episode = int(best_stats['episode'])
                best_reward = best_stats['reward_ma_100']

                logger.info(f"  Melhor episódio (pelo log): {best_episode} (Reward MA 100: {best_reward:.4f})")
                
                checkpoint_name = f"{base_name}_checkpoint_ep{best_episode}_drl.keras"
                best_checkpoint_path = os.path.join(model_dir, checkpoint_name)

        except Exception as e:
            logger.error(f"Erro ao ler ou analisar o arquivo de estatísticas: {e}")

    # CENÁRIO 2: Treino interrompido (Log não existe ou falhou)
    if best_checkpoint_path is None or not os.path.exists(best_checkpoint_path):
        if not os.path.exists(stats_file_path): # Se o log não existia, loga o aviso
            logger.warning(f"Arquivo de estatísticas '{stats_file_path}' não encontrado ou vazio.")
        
        logger.info("Procurando pelo ÚLTIMO checkpoint salvo...")
        
        checkpoint_pattern = os.path.join(model_dir, f"{base_name}_checkpoint_ep*_drl.keras")
        checkpoints = glob.glob(checkpoint_pattern)
        
        if not checkpoints:
            logger.error("Nenhum arquivo de checkpoint encontrado. Não é possível gerar o modelo de produção.")
            return
        
        # Encontra o checkpoint com o maior número de episódio
        latest_episode = -1
        latest_checkpoint_path = None
        for cp_path in checkpoints:
            match = re.search(r'_ep(\d+)_drl\.keras$', cp_path)
            if match:
                episode_num = int(match.group(1))
                if episode_num > latest_episode:
                    latest_episode = episode_num
                    latest_checkpoint_path = cp_path
        
        if latest_checkpoint_path:
            best_checkpoint_path = latest_checkpoint_path
            logger.info(f"  Melhor modelo (pelo último checkpoint): Episódio {latest_episode}")
        else:
            logger.error("Checkpoints encontrados, mas não foi possível extrair números de episódios.")
            return

    # --- 3. Promover o Melhor Checkpoint para Produção ---
    if best_checkpoint_path and os.path.exists(best_checkpoint_path):
        try:
            shutil.copy(best_checkpoint_path, prod_model_path)
            logger.info(f"Modelo de produção salvo: {prod_model_path}")
        except Exception as e:
            logger.error(f"Falha ao copiar o melhor checkpoint para produção: {e}")
    else:
        logger.warning(f"Checkpoint selecionado ({best_checkpoint_path}) não foi encontrado. O modelo de produção não foi atualizado.")

    # --- 4. Gerar Gráfico de Treinamento (se o log existiu) ---
    if stats_df is not None and not stats_df.empty:
        try:
            plot_training_stats(stats_df, plot_file_path)
            logger.info(f"Relatório gráfico de treinamento salvo em: {plot_file_path}")
        except Exception as e:
            logger.error(f"Falha ao gerar o gráfico de treinamento: {e}")
    else:
        logger.info("Pulando geração de gráfico (sem dados de estatísticas).")
# -------------------------


# --- FUNÇÃO print_summary() REMOVIDA ---
# (A função print_summary(..) que estava aqui foi removida)
# -------------------------


def main():
    # --- LÓGICA DE LOGGING ATUALIZADA ---
    # Configura o logging centralizado
    setup_logging(log_file_prefix='train_drl_model')
    logger = logging.getLogger(__name__)
    # -------------------------

    start_time = time()
    
    config = load_config()
    models_dir = config['paths']['models_dir']
    Path(models_dir).mkdir(parents=True, exist_ok=True)

    available_tickers = [
        asset for asset in config['assets'] 
        if config['assets'][asset].get('enabled', False) and 
           'DRLStrategy' in config['assets'][asset].get('strategies', [])
    ]
    
    if not available_tickers:
        logger.error("Nenhum ativo habilitado para DRLStrategy encontrado no 'main.yaml'.")
        return

    ticker_input = get_ticker_input(available_tickers)
    
    asset_config = config['assets'][ticker_input]
    strategy_name = 'DRLStrategy' # Nome fixo para este script
    strategy_config = config['strategies'][strategy_name]
    provider_name = asset_config['provider']
    provider_config = config['providers'][provider_name]

    logger.info(f"Usando estratégia: {strategy_name}")
    logger.info(f"  Provider: {provider_name}")
    logger.info(f"  Dados: {provider_config['data_range']['train_start']} a {provider_config['data_range']['train_end']}")
    logger.info(f"  Timeframe: {provider_config['timeframe']}")

    # 1. Carregar Dados
    logger.info("Conectando ao provider...")
    provider = get_provider_instance(config, provider_name)
    
    logger.info(f"Carregando dados históricos para {ticker_input}...")
    market_data = provider.load_data(
        ticker=ticker_input,
        start_date=provider_config['data_range']['train_start'],
        end_date=provider_config['data_range']['train_end'],
        timeframe=provider_config['timeframe']
    )
    
    # 2. Criar Ambiente
    logger.info("Criando ambiente de trading...")
    env = TradingEnv(
        market_data=market_data,
        config=config,
        **strategy_config.get('environment', {})
    )
    logger.info(f"Ambiente criado: {env.total_steps} steps, state_dim={env.state_dim}")

    # 3. Criar Agente
    logger.info("Criando agente DDQN...")
    agent_config = strategy_config.get('agent', {})
    agent = DDQNAgent(
        state_dim=env.state_dim,
        num_actions=env.action_space.n,
        config=agent_config
    )
    
    # 4. Carregar Checkpoint (se existir)
    start_episode = 1
    epsilon = agent_config.get('epsilon_start', 1.0)
    
    # Define o padrão do checkpoint
    checkpoint_base_name = f"{ticker_input}_{strategy_name}_checkpoint"
    prod_model_name = f"{ticker_input}_{strategy_name}_prod_drl.keras"
    stats_name = f"{ticker_input}_{strategy_name}_training_stats.csv"
    stats_path = Path(models_dir) / stats_name

    # Encontra o checkpoint mais recente
    checkpoint_files = list(Path(models_dir).glob(f"{checkpoint_base_name}_ep*.keras"))
    if checkpoint_files:
        latest_checkpoint = max(checkpoint_files, key=lambda p: int(re.search(r'_ep(\d+)_drl\.keras$', str(p)).group(1)))
        
        match = re.search(r'_ep(\d+)_drl\.keras$', str(latest_checkpoint))
        if match:
            try:
                start_episode = int(match.group(1)) + 1
                agent.load(str(latest_checkpoint))
                logger.info(f"Checkpoint carregado: {latest_checkpoint}")
                
                # Ajustar epsilon
                epsilon_min = agent_config.get('epsilon_min', 0.01)
                epsilon_decay_episodes = agent_config.get('epsilon_linear_decay_episodes', 80)
                
                if start_episode > epsilon_decay_episodes:
                    epsilon = epsilon_min
                else:
                    epsilon = agent_config.get('epsilon_start', 1.0) - (start_episode * (
                        (agent_config.get('epsilon_start', 1.0) - epsilon_min) / epsilon_decay_episodes
                    ))
                
                epsilon = max(epsilon_min, epsilon) # Garante
                
                logger.info(f"Treinamento continuará a partir do episódio {start_episode}")
                logger.info(f"Epsilon ajustado para: {epsilon:.4f}")
                
            except Exception as e:
                logger.error(f"Erro ao carregar checkpoint: {e}. Começando do zero.")
                start_episode = 1
                epsilon = agent_config.get('epsilon_start', 1.0)
    else:
        logger.info("Nenhum checkpoint encontrado. Iniciando novo treinamento.")

    # 5. Loop de Treinamento
    training_config = strategy_config.get('training', {})
    num_episodes = training_config.get('episodes', 100)
    batch_size = agent_config.get('batch_size', 32)
    checkpoint_interval = training_config.get('checkpoint_freq', 10)
    
    # Histórico para médias móveis
    rewards_history = deque(maxlen=100)
    nav_history = deque(maxlen=100)
    
    # Abre o arquivo de stats (ou cria se não existir)
    file_exists = stats_path.exists()
    with open(stats_path, 'a', buffering=1) as stats_file:
        if not file_exists:
            stats_file.write("episode,reward,steps,epsilon,nav,reward_ma_10,reward_ma_100,nav_ma_10,nav_ma_100\n")
        
        try:
            for episode in range(start_episode, start_episode + num_episodes):
                logger.info(f"--- Iniciando Episódio {episode}/{start_episode + num_episodes - 1} ---")
                state = env.reset()
                done = False
                total_reward = 0
                step = 0
                
                while not done:
                    action = agent.act(state, epsilon)
                    next_state, reward, done, _, info = env.step(action)
                    agent.remember(state, action, reward, next_state, done)
                    state = next_state
                    total_reward += reward
                    step += 1
                
                # Treinamento (replay)
                if len(agent.replay_buffer) > batch_size:
                    agent.replay(batch_size)
                
                # Decaimento do Epsilon
                epsilon_min = agent_config.get('epsilon_min', 0.01)
                epsilon_decay_episodes = agent_config.get('epsilon_linear_decay_episodes', 80)
                
                if episode <= epsilon_decay_episodes:
                     epsilon = agent_config.get('epsilon_start', 1.0) - (episode * (
                        (agent_config.get('epsilon_start', 1.0) - epsilon_min) / epsilon_decay_episodes
                    ))
                else:
                    # Decaimento exponencial após o linear
                    epsilon *= agent_config.get('epsilon_exponential_decay', 0.99)
                
                epsilon = max(epsilon_min, epsilon) # Garante
                
                # Atualizar target network
                if episode % agent_config.get('tau', 10) == 0:
                    agent.update_target_model()
                    
                # Logging e Stats
                nav = info.get('nav', 0)
                rewards_history.append(total_reward)
                nav_history.append(nav)
                
                reward_ma_10 = np.mean(list(rewards_history)[-10:])
                reward_ma_100 = np.mean(rewards_history)
                nav_ma_10 = np.mean(list(nav_history)[-10:])
                nav_ma_100 = np.mean(nav_history)
                
                logger.info(f"Episode {episode} | Reward: {total_reward:.4f} | "
                             f"Avg(100): {reward_ma_100:.4f} | Avg(10): {reward_ma_10:.4f} | "
                             f"Epsilon: {epsilon:.4f} | Steps: {step} | NAV: {nav:.4f}")

                # Salva stats
                stats_file.write(f"{episode},{total_reward},{step},{epsilon},{nav},{reward_ma_10},{reward_ma_100},{nav_ma_10},{nav_ma_100}\n")
                
                # Salva Checkpoint
                if checkpoint_interval > 0 and episode % checkpoint_interval == 0:
                    checkpoint_path = Path(models_dir) / f"{checkpoint_base_name}_ep{episode}_drl.keras"
                    save_checkpoint(agent, str(checkpoint_path))
            
            logger.info("Treinamento concluído.")

        except KeyboardInterrupt:
            logger.warning("Treinamento interrompido pelo usuário.")
            # --- CHAMADA DE FINALIZAÇÃO (EM CASO DE INTERRUPÇÃO) ---
            finalize_training(config, strategy_name, ticker_input)
            return # Sai da função

    # --- CHAMADA DE FINALIZAÇÃO (SUCESSO) ---
    # Substitui o print_summary
    finalize_training(config, strategy_name, ticker_input)


if __name__ == "__main__":
    main()