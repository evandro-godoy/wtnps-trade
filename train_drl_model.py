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

import yaml
import logging
from pathlib import Path
from time import time

# Imports do projeto
from src.environments.trading_env import TradingEnv
from src.agents.drl_agent import DDQNAgent
from src.data_handler.provider import get_provider_instance
from src.strategies.drl_strategy import DRLStrategy

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path: str = 'configs/main.yaml') -> dict:
    """Carrega o arquivo de configuração YAML."""
    logger.info(f"Carregando configuração: {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_asset_config(config: dict, ticker: str) -> dict:
    """Busca a configuração de um ativo específico."""
    assets_list = config.get('assets', [])
    for asset_cfg in assets_list:
        if asset_cfg.get('ticker') == ticker:
            return asset_cfg
    raise ValueError(f"Ticker '{ticker}' não encontrado em configs/main.yaml")


def get_strategy_config(asset_config: dict, strategy_name: str) -> dict:
    """Busca a configuração de uma estratégia específica dentro de um ativo."""
    strategies_list = asset_config.get('strategies', [])
    for strat_cfg in strategies_list:
        if strat_cfg.get('name') == strategy_name:
            return strat_cfg
    
    available = [s.get('name') for s in strategies_list]
    raise ValueError(
        f"Estratégia '{strategy_name}' não encontrada para '{asset_config.get('ticker')}'. "
        f"Disponíveis: {available}"
    )


def format_time(seconds: float) -> str:
    """Formata tempo em HH:MM:SS."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f'{h:02d}:{m:02d}:{s:02d}'


def main():
    """Função principal de treinamento."""
    
    print("=" * 80)
    print("TREINAMENTO DE AGENTE DEEP REINFORCEMENT LEARNING (DDQN)")
    print("=" * 80)
    print()
    
    # 1. Carrega configuração
    config = load_config()
    
    # 2. Lista ativos disponíveis
    assets_list = config.get('assets', [])
    print("Ativos disponíveis no config:")
    for i, asset in enumerate(assets_list, 1):
        ticker = asset.get('ticker', 'N/A')
        enabled = asset.get('enabled', False)
        strategies = asset.get('strategies', [])
        status = "✓ Habilitado" if enabled else "✗ Desabilitado"
        strategy_names = ', '.join([s.get('name', 'N/A') for s in strategies])
        print(f"  {i}. {ticker:<15} | Estratégias: {strategy_names:<30} | {status}")
    print()
    
    # 3. Solicita ticker ao usuário
    # ticker_input = input("Digite o ticker do ativo para treinar (ex: WDO$): ").strip()
    ticker_input = 'WDO$'
    
    
    if not ticker_input:
        logger.error("Ticker não fornecido. Abortando.")
        return
    
    # 4. Obtém configuração do ativo
    try:
        asset_config = get_asset_config(config, ticker_input)
    except ValueError as e:
        logger.error(str(e))
        return
    
    # 5. Lista estratégias disponíveis para este ativo
    strategies_list = asset_config.get('strategies', [])
    if not strategies_list:
        logger.error(f"Nenhuma estratégia configurada para '{ticker_input}'")
        return
    
    print(f"\nEstratégias disponíveis para {ticker_input}:")
    for i, strat in enumerate(strategies_list, 1):
        strat_name = strat.get('name', 'N/A')
        strat_provider = strat.get('provider', 'N/A')
        print(f"  {i}. {strat_name} (Provider: {strat_provider})")
    print()
    
    # 6. Busca estratégia DRL (ou solicita escolha)
    drl_strategy_config = None
    for strat in strategies_list:
        if strat.get('name') == 'DRLStrategy':
            drl_strategy_config = strat
            break
    
    if not drl_strategy_config:
        logger.error(f"Estratégia 'DRLStrategy' não encontrada para '{ticker_input}'")
        logger.info(f"Adicione uma estratégia DRL no config ou use outro ticker")
        return
    
    logger.info(f"Usando estratégia: DRLStrategy")
    logger.info(f"  Provider: {drl_strategy_config.get('provider')}")
    logger.info(f"  Dados: {drl_strategy_config['data']['start_date']} a {drl_strategy_config['data']['end_date']}")
    logger.info(f"  Timeframe: {drl_strategy_config['data']['timeframe_model']}")
    
    # 7. Instancia provider
    provider_name = drl_strategy_config.get('provider')
    logger.info(f"Conectando ao provider: {provider_name}...")
    provider = get_provider_instance(provider_name)
    
    # 8. Instancia ambiente de trading
    logger.info("Criando ambiente de trading...")
    # IMPORTANTE: TradingEnv agora recebe strategy_config + ticker
    env = TradingEnv(
        ticker=ticker_input,
        strategy_config=drl_strategy_config,
        provider=provider
    )
    logger.info(f"Ambiente criado: {len(env.market_features_df)} steps, state_dim={env.state_dim}")
    
    # 7. Define hiperparâmetros do agente
    # (Você pode ajustar estes valores ou torná-los configuráveis)
    hyperparams = {
        'state_dim': env.state_dim,
        'num_actions': env.num_actions,
        'learning_rate': 0.0001,
        'gamma': 0.99,
        'epsilon_start': 1.0,
        'epsilon_end': 0.01,
        'epsilon_decay_steps': 250,  # Episodes para decay linear
        'epsilon_exponential_decay': 0.99,
        'replay_capacity': int(1e6),
        'architecture': (256, 256),
        'l2_reg': 1e-6,
        'tau': 100,  # Steps para atualizar target network
        'batch_size': 4096
    }
    
    logger.info("Hiperparâmetros do agente:")
    for key, value in hyperparams.items():
        logger.info(f"  {key}: {value}")
    
    # 8. Instancia agente DDQN
    logger.info("Criando agente DDQN...")
    agent = DDQNAgent(**hyperparams)
    
    # 9. Solicita número de episódios e timeout
    """
    try:
        num_episodes_input = input("\nNúmero de episódios de treinamento (padrão: 1000): ").strip()
        num_episodes = int(num_episodes_input) if num_episodes_input else 1000
    except ValueError:
        logger.warning("Valor inválido. Usando padrão: 1000")
        num_episodes = 1000
    """

    num_episodes = 1000
    episode_timeout = 300
    
    # Máximo de steps por episódio (proteção contra loops infinitos)
    max_steps_per_episode = len(env.market_features_df)
    
    logger.info(f"Treinamento iniciará com {num_episodes} episódios.")
    logger.info(f"Timeout por episódio: {episode_timeout} segundos")
    logger.info(f"Max steps por episódio: {max_steps_per_episode}")
    
    # 10. Loop de Treinamento
    print("\n" + "=" * 80)
    print("INICIANDO TREINAMENTO")
    print("=" * 80 + "\n")
    
    start_time = time()
    logger.info(f"Início do treinamento: {format_time(start_time)}")
    
    # Estatísticas para estimativa de tempo
    episode_times = []
    interrupted_episodes = 0
    
    # Configuração de checkpoint automático
    checkpoint_interval = max(10, num_episodes // 10)  # A cada 10% ou mínimo 10 episódios
    logger.info(f"Checkpoint automático a cada {checkpoint_interval} episódios")

    for episode in range(1, num_episodes + 1):
        # Reset do ambiente
        state = env.reset()
        done = False
        episode_start_time = time()
        steps_in_episode = 0

        logger.info(f"Início do episódio {episode}")

        # Loop dentro do episódio com proteções
        while not done:
            # Proteção 1: Limite de steps por episódio
            if steps_in_episode >= max_steps_per_episode:
                logger.warning(
                    f"Episódio {episode} atingiu o limite de {max_steps_per_episode} steps. "
                    f"Forçando encerramento."
                )
                done = True
                interrupted_episodes += 1
                break
            
            # Proteção 2: Timeout por episódio
            episode_elapsed = time() - episode_start_time
            if episode_elapsed > episode_timeout:
                logger.warning(
                    f"Episódio {episode} excedeu timeout de {episode_timeout}s "
                    f"(executou por {episode_elapsed:.1f}s após {steps_in_episode} steps). "
                    f"Forçando encerramento."
                )
                
                # Calcula estimativa de conclusão
                episodes_remaining = num_episodes - episode
                if episode_times:
                    avg_episode_time = sum(episode_times) / len(episode_times)
                    estimated_time_remaining = avg_episode_time * episodes_remaining
                    
                    print("\n" + "=" * 80)
                    print("TIMEOUT DETECTADO")
                    print("=" * 80)
                    print(f"Episódio atual: {episode}/{num_episodes}")
                    print(f"Episódios restantes: {episodes_remaining}")
                    print(f"Tempo médio por episódio: {format_time(avg_episode_time)}")
                    print(f"Tempo estimado para conclusão: {format_time(estimated_time_remaining)}")
                    print(f"Tempo total estimado: {format_time((time() - start_time) + estimated_time_remaining)}")
                    print("=" * 80)
                    
                    user_choice = input("\nDeseja continuar o treinamento? (s/N): ").strip().lower()
                    if user_choice not in ['s', 'sim', 'y', 'yes']:
                        logger.info("Treinamento interrompido pelo usuário.")
                        print("\n" + "=" * 80)
                        print("TREINAMENTO INTERROMPIDO PELO USUÁRIO")
                        print("=" * 80)
                        break
                    else:
                        logger.info("Usuário optou por continuar o treinamento.")
                        # Dobra o timeout para o próximo episódio
                        episode_timeout *= 2
                        logger.info(f"Timeout aumentado para {episode_timeout}s")
                
                done = True
                interrupted_episodes += 1
                break
            
            # Agente escolhe ação (epsilon-greedy)
            action = agent.epsilon_greedy_policy(state)
            
            # Executa ação no ambiente
            next_state, reward, done = env.step(action)
            
            # Memoriza transição
            agent.memorize_transition(state, action, reward, next_state, done)
            
            # Experience replay (treina a rede)
            agent.experience_replay()
            
            # Incrementa contador de steps
            steps_in_episode += 1
            
            # Atualiza estado
            if not done:
                state = next_state
        
        # Verifica se usuário interrompeu
        if done and episode < num_episodes and interrupted_episodes > 0:
            # Checa se foi interrupção por usuário (timeout confirmado)
            if episode_times and (time() - episode_start_time) > episode_timeout / 2:
                # Possível que usuário tenha cancelado
                if episode == num_episodes - 1 or interrupted_episodes >= 3:
                    logger.warning(f"Múltiplas interrupções detectadas ({interrupted_episodes}). Abortando treinamento.")
                    break
        
        # Registra tempo do episódio
        episode_duration = time() - episode_start_time
        episode_times.append(episode_duration)
        
        # Log de cada episódio
        total_time = time() - start_time
        avg_reward_100 = sum(agent.rewards_history[-100:]) / min(len(agent.rewards_history), 100)
        avg_reward_10 = sum(agent.rewards_history[-10:]) / min(len(agent.rewards_history), 10)
        
        print(
            f"Episode {episode:4d}/{num_episodes} | "
            f"Steps: {steps_in_episode:5d} | "
            f"Duration: {format_time(episode_duration)} | "
            f"Reward(100): {avg_reward_100:8.4f} | "
            f"Reward(10): {avg_reward_10:8.4f} | "
            f"Epsilon: {agent.epsilon:.4f} | "
            f"Total Time: {format_time(total_time)} | "
            f"Loss: {agent.losses[-1] if agent.losses else 0:.6f}"
        )
        
        # Checkpoint automático
        if episode % checkpoint_interval == 0 and episode < num_episodes:
            logger.info(f"Salvando checkpoint em episódio {episode}...")
            models_dir = Path(config.get('global_settings', {}).get('model_directory', 'models'))
            models_dir.mkdir(parents=True, exist_ok=True)
            checkpoint_prefix = str(models_dir / f"{ticker_input}_DRLStrategy_checkpoint_ep{episode}")
            
            strategy_saver = DRLStrategy()
            strategy_saver.save(agent.online_network, checkpoint_prefix)
            logger.info(f"Checkpoint salvo: {checkpoint_prefix}_drl.keras")
    
    total_training_time = time() - start_time
    print("\n" + "=" * 80)
    print("TREINAMENTO CONCLUÍDO")
    print("=" * 80)
    print(f"Tempo total: {format_time(total_training_time)}")
    print(f"Episódios completados: {len(agent.rewards_history)}/{num_episodes}")
    print(f"Episódios interrompidos por timeout/limite: {interrupted_episodes}")
    if episode_times:
        print(f"Tempo médio por episódio: {format_time(sum(episode_times)/len(episode_times))}")
    print(f"Recompensa média (últimos 100): {sum(agent.rewards_history[-100:]) / min(len(agent.rewards_history), 100):.4f}")
    print()
    
    # 11. Salva o modelo treinado
    models_dir = Path(config.get('global_settings', {}).get('model_directory', 'models'))
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # NOVO FORMATO: ticker_StrategyName_prod
    model_prefix = str(models_dir / f"{ticker_input}_DRLStrategy_prod")
    
    logger.info(f"Salvando modelo treinado em: {model_prefix}_drl.keras")
    
    # Usa DRLStrategy para salvar (mantém interface consistente)
    strategy_saver = DRLStrategy()
    model_to_save = agent.online_network
    strategy_saver.save(model_to_save, model_prefix)
    
    logger.info("Modelo salvo com sucesso!")
    print()
    print("=" * 80)
    print("PRÓXIMOS PASSOS:")
    print("=" * 80)
    print(f"1. Teste o modelo usando SimulationEngine:")
    print(f"   - Abra notebooks/simulation/engine_simulation_single_cycle.ipynb")
    print(f"   - Configure asset_symbol='{ticker_input}', strategy_name='DRLStrategy'")
    print()
    print(f"2. Use em live trading (se configurado):")
    print(f"   - Verifique live_trading.enabled no config do ativo")
    print(f"   - Execute: poetry run python src/live_trader.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
