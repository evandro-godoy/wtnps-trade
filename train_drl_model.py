# train_drl_model.py
import os
import sys
import logging
import pandas as pd
from datetime import datetime
import shutil
import timeout_decorator
import yaml
import numpy as np
import glob
import re  # <--- Importado para extrair números dos arquivos

from src.data_handler.provider import DataHandler
from src.environments.trading_env import TradingEnv
from src.agents.drl_agent import DDQNAgent
from src.strategies.drl_strategy import DRLStrategy
from src.reporting.plot import plot_training_stats
from src.utils.logger import setup_logging

def load_config(config_path='configs/main.yaml'):
    """Carrega o arquivo de configuração YAML."""
    if not os.path.exists(config_path):
        logging.error(f"Arquivo de configuração não encontrado: {config_path}")
        sys.exit(1)
    with open(config_path, 'r') as file:
        return yaml.safe_load(config)

def setup_environment(config: dict, ticker: str) -> (TradingEnv, pd.DataFrame):
    """Configura e retorna o ambiente de trading e os dados."""
    logging.info("=" * 80)
    logging.info("Configurando Ambiente de Trading")
    logging.info("=" * 80)
    
    provider_config = config['providers']['MetaTrader5']
    data_handler = DataHandler(config)
    
    logging.info(f"Carregando dados históricos para {ticker}...")
    market_data = data_handler.load_data(
        ticker=ticker,
        provider_name='MetaTrader5',
        start_date=provider_config['data_range']['train_start'],
        end_date=provider_config['data_range']['train_end'],
        timeframe=provider_config['timeframe']
    )
    
    env = TradingEnv(
        market_data=market_data,
        config=config,
        **config['environment']
    )
    
    logging.info(f"Ambiente criado: {env.total_steps} steps, state_dim={env.state_dim}")
    return env, market_data

def setup_agent(config: dict, env: TradingEnv, model_dir: str, base_name: str) -> (DDQNAgent, int, float):
    """Configura o agente DDQN e carrega o checkpoint mais recente, se existir."""
    logging.info("=" * 80)
    logging.info("Configurando Agente DDQN")
    logging.info("=" * 80)

    agent_config = config['strategies']['DRLStrategy']['agent']
    
    agent = DDQNAgent(
        state_dim=env.state_dim,
        num_actions=env.action_space.n,
        config=agent_config
    )
    
    start_episode = 1
    epsilon = agent_config['epsilon_start']
    
    # --- Lógica de Carregamento de Checkpoint ---
    logging.info("Procurando por checkpoints...")
    checkpoint_pattern = os.path.join(model_dir, f"{base_name}_checkpoint_ep*_drl.keras")
    checkpoints = glob.glob(checkpoint_pattern)
    
    if checkpoints:
        latest_checkpoint = max(checkpoints, key=os.path.getctime)
        logging.info(f"Checkpoint encontrado: {latest_checkpoint}")
        
        try:
            episode_num_match = re.search(r'_ep(\d+)_drl\.keras$', latest_checkpoint)
            if episode_num_match:
                last_episode = int(episode_num_match.group(1))
                agent.load(latest_checkpoint)
                start_episode = last_episode + 1
                
                # Ajustar epsilon com base no episódio carregado
                epsilon_decay_episodes = agent_config.get('epsilon_linear_decay_episodes', 80)
                if start_episode > epsilon_decay_episodes:
                    epsilon = agent_config['epsilon_min']
                else:
                    epsilon = agent_config['epsilon_start'] - (start_episode * (
                        (agent_config['epsilon_start'] - agent_config['epsilon_min']) / epsilon_decay_episodes
                    ))
                
                epsilon = max(agent_config['epsilon_min'], epsilon) # Garante que não seja menor que o mínimo
                
                logging.info(f"Treinamento continuará do episódio {start_episode}")
                logging.info(f"Epsilon ajustado para: {epsilon:.4f}")
            else:
                logging.warning("Não foi possível extrair o número do episódio do checkpoint. Começando do zero.")
                
        except Exception as e:
            logging.error(f"Erro ao carregar checkpoint: {e}. Começando do zero.")
            start_episode = 1
            epsilon = agent_config['epsilon_start']
    else:
        logging.info("Nenhum checkpoint encontrado. Iniciando novo treinamento.")

    return agent, start_episode, epsilon

def run_training_loop(agent: DDQNAgent, env: TradingEnv, config: dict, 
                      start_episode: int, initial_epsilon: float,
                      stats_file_path: str, model_dir: str, base_name: str):
    """Executa o loop principal de treinamento do agente."""
    logging.info("=" * 80)
    logging.info("INICIANDO TREINAMENTO")
    logging.info("=" * 80)
    
    agent_config = config['strategies']['DRLStrategy']['agent']
    train_config = config['strategies']['DRLStrategy']['training']
    
    num_episodes = train_config['episodes']
    batch_size = agent_config['batch_size']
    epsilon = initial_epsilon
    
    # Prepara o arquivo de estatísticas (append se já existir)
    file_exists = os.path.isfile(stats_file_path)
    stats_file = open(stats_file_path, 'a', buffering=1) # 'a' para append, buffering=1 para line-buffered
    if not file_exists:
        stats_file.write("episode,reward,steps,epsilon,nav,reward_ma_10,reward_ma_100,nav_ma_10,nav_ma_100\n")

    # Listas para médias móveis
    rewards_history = []
    nav_history = []

    for episode in range(start_episode, num_episodes + 1):
        try:
            logging.info(f"--- Iniciando Episódio {episode}/{num_episodes} ---")
            
            @timeout_decorator.timeout(train_config['episode_timeout_seconds'])
            def run_episode():
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

                    if done:
                        return total_reward, step, info.get('nav', 0)
                
                # Este retorno só acontece se o loop terminar por 'done'
                return total_reward, step, info.get('nav', 0)

            total_reward, steps, nav = run_episode()

            # Lógica de "aquecimento" do buffer antes de treinar
            if len(agent.replay_buffer) > batch_size:
                logging.info(f"Episódio {episode}: Iniciando treinamento do agente (Buffer: {len(agent.replay_buffer)})...")
                agent.replay(batch_size)
            else:
                logging.info(f"Episódio {episode}: Buffer insuficiente ({len(agent.replay_buffer)}/{batch_size}). Pulando treinamento.")

            # Atualiza Epsilon (exemplo de decaimento linear)
            epsilon_decay_episodes = agent_config.get('epsilon_linear_decay_episodes', 80)
            if episode <= epsilon_decay_episodes:
                 epsilon = agent_config['epsilon_start'] - (episode * (
                    (agent_config['epsilon_start'] - agent_config['epsilon_min']) / epsilon_decay_episodes
                ))
            else:
                # Decaimento exponencial após o linear
                epsilon = max(agent_config['epsilon_min'], 
                              epsilon * agent_config.get('epsilon_exponential_decay', 0.99))

            # Atualiza a rede alvo (target network)
            if episode % agent_config.get('tau', 10) == 0:
                agent.update_target_model()

            # Logging e Estatísticas
            rewards_history.append(total_reward)
            nav_history.append(nav)
            
            # Calcula médias móveis
            reward_ma_10 = np.mean(rewards_history[-10:])
            reward_ma_100 = np.mean(rewards_history[-100:])
            nav_ma_10 = np.mean(nav_history[-10:])
            nav_ma_100 = np.mean(nav_history[-100:])

            logging.info(f"Episode {episode} | Reward: {total_reward:.4f} | "
                         f"Avg(100): {reward_ma_100:.4f} | Avg(10): {reward_ma_10:.4f} | "
                         f"Epsilon: {epsilon:.4f} | Steps: {steps} | NAV: {nav:.4f}")
            
            # Salva estatísticas no CSV
            stats_line = f"{episode},{total_reward},{steps},{epsilon},{nav},{reward_ma_10},{reward_ma_100},{nav_ma_10},{nav_ma_100}\n"
            stats_file.write(stats_line)

            # Salva Checkpoint
            if episode % train_config.get('checkpoint_freq', 10) == 0:
                save_checkpoint(agent, model_dir, base_name, episode)

        except timeout_decorator.TimeoutError:
            logging.warning(f"Episódio {episode} excedeu o timeout de {train_config['episode_timeout_seconds']}s. Passando para o próximo.")
            continue # Pula para o próximo episódio
        
        except KeyboardInterrupt:
            logging.warning("Treinamento interrompido pelo usuário.")
            break # Sai do loop
            
    stats_file.close()
    logging.info("Loop de treinamento concluído.")


def save_checkpoint(agent: DDQNAgent, model_dir: str, base_name: str, episode: int):
    """Salva o checkpoint do modelo do agente."""
    checkpoint_path = os.path.join(model_dir, f"{base_name}_checkpoint_ep{episode}_drl.keras")
    try:
        agent.save(checkpoint_path)
        logging.info(f"Checkpoint salvo: {checkpoint_path}")
    except Exception as e:
        logging.error(f"Erro ao salvar checkpoint: {e}")

def finalize_training(config: dict, strategy_name: str, ticker: str):
    """
    Finaliza o treinamento: identifica o melhor modelo (ou o último, se
    interrompido) e o promove para produção.
    """
    logging.info("=" * 80)
    logging.info("FINALIZANDO E SELECIONANDO MELHOR MODELO")
    logging.info("=" * 80)

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
        logging.info("Analisando arquivo de estatísticas (CSV) para encontrar o melhor episódio.")
        try:
            stats_df = pd.read_csv(stats_file_path)
            if stats_df.empty:
                logging.warning("Arquivo de estatísticas está vazio.")
            else:
                # Encontra o índice da MAIOR recompensa média de 100 episódios
                best_episode_idx = stats_df['reward_ma_100'].idxmax()
                best_stats = stats_df.loc[best_episode_idx]
                best_episode = int(best_stats['episode'])
                best_reward = best_stats['reward_ma_100']

                logging.info(f"  Melhor episódio (pelo log): {best_episode} (Reward MA 100: {best_reward:.4f})")
                
                checkpoint_name = f"{base_name}_checkpoint_ep{best_episode}_drl.keras"
                best_checkpoint_path = os.path.join(model_dir, checkpoint_name)

        except Exception as e:
            logging.error(f"Erro ao ler ou analisar o arquivo de estatísticas: {e}")

    # CENÁRIO 2: Treino interrompido (Log não existe ou falhou)
    if best_checkpoint_path is None or not os.path.exists(best_checkpoint_path):
        if not stats_df: # Se o log não existia, loga o aviso
            logging.warning(f"Arquivo de estatísticas '{stats_file_path}' não encontrado ou vazio.")
        
        logging.info("Procurando pelo ÚLTIMO checkpoint salvo...")
        
        checkpoint_pattern = os.path.join(model_dir, f"{base_name}_checkpoint_ep*_drl.keras")
        checkpoints = glob.glob(checkpoint_pattern)
        
        if not checkpoints:
            logging.error("Nenhum arquivo de checkpoint encontrado. Não é possível gerar o modelo de produção.")
            return
        
        # Encontra o checkpoint com o maior número de episódio
        latest_episode = -1
        for cp_path in checkpoints:
            match = re.search(r'_ep(\d+)_drl\.keras$', cp_path)
            if match:
                episode_num = int(match.group(1))
                if episode_num > latest_episode:
                    latest_episode = episode_num
                    best_checkpoint_path = cp_path
        
        if best_checkpoint_path:
            logging.info(f"  Melhor modelo (pelo último checkpoint): Episódio {latest_episode}")
        else:
            logging.error("Checkpoints encontrados, mas não foi possível extrair números de episódios.")
            return

    # --- 3. Promover o Melhor Checkpoint para Produção ---
    if os.path.exists(best_checkpoint_path):
        try:
            shutil.copy(best_checkpoint_path, prod_model_path)
            logging.info(f"Modelo de produção salvo: {prod_model_path}")
        except Exception as e:
            logging.error(f"Falha ao copiar o melhor checkpoint para produção: {e}")
    else:
        logging.warning(f"Checkpoint selecionado ({best_checkpoint_path}) não foi encontrado. O modelo de produção não foi atualizado.")

    # --- 4. Gerar Gráfico de Treinamento (se o log existiu) ---
    if stats_df is not None and not stats_df.empty:
        try:
            plot_training_stats(stats_df, plot_file_path)
            logging.info(f"Relatório gráfico de treinamento salvo em: {plot_file_path}")
        except Exception as e:
            logging.error(f"Falha ao gerar o gráfico de treinamento: {e}")
    else:
        logging.info("Pulando geração de gráfico (sem dados de estatísticas).")


def main(config_path='configs/main.yaml'):
    """Função principal para orquestrar o treinamento."""
    try:
        setup_logging()
        config = load_config(config_path)

        # Selecionar o ticker e estratégia (simplificado)
        # Em um app real, isso poderia vir de argumentos de linha de comando
        ticker = 'WDO$'
        strategy_config = config['strategies']['DRLStrategy']
        strategy_name = strategy_config['name']
        
        # --- 1. Setup do Ambiente ---
        env, market_data = setup_environment(config, ticker)
        
        # --- 2. Setup do Agente (com carregamento de checkpoint) ---
        model_dir = config['paths']['models_dir']
        base_name = f"{ticker}${strategy_name}"
        
        agent, start_episode, initial_epsilon = setup_agent(
            config, env, model_dir, base_name
        )
        
        # --- 3. Execução do Loop de Treino ---
        stats_file_path = os.path.join(model_dir, f"{base_name}_training_stats.csv")
        
        run_training_loop(
            agent=agent,
            env=env,
            config=config,
            start_episode=start_episode,
            initial_epsilon=initial_epsilon,
            stats_file_path=stats_file_path,
            model_dir=model_dir,
            base_name=base_name
        )

        logging.info("Treinamento concluído.")

        # --- 4. Finalização e Promoção do Modelo ---
        finalize_training(
            config=config,
            strategy_name=strategy_name,
            ticker=ticker
        )

    except KeyboardInterrupt:
        logging.warning("Treinamento interrompido pelo usuário (main).")
        # Mesmo se interrompido, tenta finalizar com o que temos
        finalize_training(
            config=config,
            strategy_name=strategy_name,
            ticker=ticker
        )
    except Exception as e:
        logging.error(f"Erro fatal no script de treinamento: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logging.info("Script finalizado.")
        # Limpar handlers do logging se necessário
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)

if __name__ == "__main__":
    main()