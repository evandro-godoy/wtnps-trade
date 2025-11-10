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
import pandas as pd
import numpy as np
import re
from tensorflow import keras
from collections import deque

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


def find_latest_checkpoint(models_dir: Path, ticker: str) -> tuple:
    """
    Busca o último checkpoint disponível para um ticker.
    
    Args:
        models_dir: Diretório de modelos
        ticker: Ticker do ativo (ex: 'WDO$')
    
    Returns:
        Tupla (checkpoint_path, episode_number) ou (None, 0) se não encontrar
    """
    pattern = f"{ticker}_DRLStrategy_checkpoint_ep*.keras"
    checkpoints = list(models_dir.glob(pattern))
    
    if not checkpoints:
        return None, 0
    
    # Extrai número do episódio de cada checkpoint
    checkpoint_episodes = []
    for cp in checkpoints:
        match = re.search(r'checkpoint_ep(\d+)_drl\.keras$', cp.name)
        if match:
            episode_num = int(match.group(1))
            checkpoint_episodes.append((cp, episode_num))
    
    if not checkpoint_episodes:
        return None, 0
    
    # Retorna o checkpoint com maior número de episódio
    latest = max(checkpoint_episodes, key=lambda x: x[1])
    return latest[0], latest[1]


def load_checkpoint(agent: DDQNAgent, checkpoint_path: Path) -> bool:
    """
    Carrega pesos de um checkpoint para o agente.
    
    Args:
        agent: Instância do agente DDQN
        checkpoint_path: Caminho para o arquivo .keras
    
    Returns:
        True se carregou com sucesso, False caso contrário
    """
    try:
        logger.info(f"Carregando checkpoint: {checkpoint_path}")
        model = keras.models.load_model(checkpoint_path)
        
        # Carrega pesos na online network
        agent.online_network.set_weights(model.get_weights())
        
        # Atualiza target network
        agent.update_target()
        
        logger.info("Checkpoint carregado com sucesso!")
        return True
    except Exception as e:
        logger.error(f"Erro ao carregar checkpoint: {e}")
        return False



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
    
    # 7. Define hiperparâmetros do agente DDQN
    hyperparams = {
        'state_dim': env.state_dim,
        'num_actions': env.num_actions,
        'learning_rate': 0.0001,           # Taxa de aprendizado
        'gamma': 0.99,                     # Fator de desconto
        'epsilon_start': 1.0,              # Epsilon inicial para exploração
        'epsilon_min': 0.01,               # Epsilon mínimo
        'epsilon_exponential_decay': 0.99, # Decay exponencial após linear
        'replay_capacity': int(1e6),       # Capacidade do replay buffer
        'architecture': (256, 256),        # Camadas ocultas da rede neural
        'l2_reg': 1e-6,                    # Regularização L2
        'tau': 100,                        # Frequência de atualização da target network
        'batch_size': 2048                 # Tamanho do batch para treinamento
    }
    
    logger.info("Hiperparâmetros do agente:")
    for key, value in hyperparams.items():
        logger.info(f"  {key}: {value}")
    
    # 8. Instancia agente DDQN
    logger.info("Criando agente DDQN...")
    agent = DDQNAgent(**hyperparams)
    
    # Configura epsilon decay baseado no número total de episódios
    num_episodes = 500
    episode_timeout = 300

    agent.set_epsilon_decay(num_episodes)
    
    # 9. Verifica se existe checkpoint para continuar treinamento
    models_dir = Path(config.get('global_settings', {}).get('model_directory', 'models'))
    models_dir.mkdir(parents=True, exist_ok=True)
    
    checkpoint_path, last_episode = find_latest_checkpoint(models_dir, ticker_input)
    start_episode = 1
    
    if checkpoint_path:
        print("\n" + "=" * 80)
        print("CHECKPOINT ENCONTRADO")
        print("=" * 80)
        print(f"Último checkpoint: {checkpoint_path.name}")
        print(f"Episódio do checkpoint: {last_episode}")
        print()
        
        # resume = input("Deseja continuar o treinamento a partir deste checkpoint? (S/n): ").strip().lower()
        resume = 'S'
        if resume not in ['n', 'no', 'não', 'nao']:
            if load_checkpoint(agent, checkpoint_path):
                start_episode = last_episode + 1
                
                # Reconfigura epsilon decay após restaurar checkpoint
                agent.set_epsilon_decay(num_episodes)
                
                # Ajusta epsilon baseado no progresso
                epsilon_decay_episodes = int(num_episodes * 0.8)
                if last_episode < epsilon_decay_episodes:
                    # Decay linear até 80% dos episódios
                    agent.epsilon = 1.0 - (last_episode * agent.epsilon_decay_per_episode)
                else:
                    # Decay exponencial após 80% dos episódios
                    steps_after_linear = last_episode - epsilon_decay_episodes
                    agent.epsilon = hyperparams['epsilon_min'] * (hyperparams['epsilon_exponential_decay'] ** steps_after_linear)
                
                agent.epsilon = max(agent.epsilon, hyperparams['epsilon_min'])
                
                # Restaura contador de episódios
                agent.episodes = last_episode
                
                logger.info(f"Treinamento continuará a partir do episódio {start_episode}")
                logger.info(f"Epsilon ajustado para: {agent.epsilon:.4f}")
            else:
                logger.warning("Falha ao carregar checkpoint. Iniciando treinamento do zero.")
        else:
            logger.info("Usuário optou por não usar checkpoint. Iniciando do zero.")
    
    
    # Máximo de steps por episódio (proteção contra loops infinitos)
    max_steps_per_episode = len(env.market_features_df)
    
    checkpoint_interval = max(10, num_episodes // 10)  # A cada 10% ou mínimo 10 episódios

    logger.info(f"Treinamento iniciará com {num_episodes} episódios.")
    logger.info(f"Timeout por episódio: {episode_timeout} segundos")
    logger.info(f"Max steps por episódio: {max_steps_per_episode}")
    
    # Validação e sumário de configuração
    print()
    print("=" * 80)
    print("SUMÁRIO DA CONFIGURAÇÃO")
    print("=" * 80)
    print(f"Ambiente:")
    print(f"  Ticker: {ticker_input}")
    print(f"  Provider: {drl_strategy_config.get('provider')}")
    print(f"  Período: {drl_strategy_config['data']['start_date']} a {drl_strategy_config['data']['end_date']}")
    print(f"  Timeframe: {drl_strategy_config['data']['timeframe_model']}")
    print(f"  Steps totais disponíveis: {len(env.market_features_df)}")
    print(f"  State dimension: {env.state_dim}")
    print()
    print(f"Agente DDQN:")
    print(f"  Arquitetura: {hyperparams['architecture']}")
    print(f"  Learning rate: {hyperparams['learning_rate']}")
    print(f"  Gamma (discount): {hyperparams['gamma']}")
    print(f"  Epsilon: {hyperparams['epsilon_start']} → {hyperparams['epsilon_min']} (linear em {int(num_episodes * 0.8)} eps, {num_episodes - int(num_episodes * 0.8)} exponencial)")
    print(f"  Replay buffer: {hyperparams['replay_capacity']:,} experiências")
    print(f"  Batch size: {hyperparams['batch_size']}")
    print(f"  Target network update: a cada {hyperparams['tau']} steps")
    print()
    print(f"Treinamento:")
    print(f"  Episódio inicial: {start_episode}")
    print(f"  Episódio final: {start_episode + num_episodes - 1}")
    print(f"  Total de episódios nesta sessão: {num_episodes}")
    print(f"  Epsilon inicial: {agent.epsilon:.4f}")
    print(f"  Timeout por episódio: {episode_timeout}s")
    print(f"  Checkpoint a cada: {checkpoint_interval} episódios")
    print(f"  Tempo estimado (pessimista): {format_time(num_episodes * episode_timeout)}")
    print("=" * 80)
    
 
    # 10. Loop de Treinamento
    print("\n" + "=" * 80)
    print("INICIANDO TREINAMENTO")
    print("=" * 80 + "\n")
    
    start_time = time()
    logger.info(f"Início do treinamento: {format_time(start_time)}")
    
    # Estatísticas para estimativa de tempo
    episode_times = []
    interrupted_episodes = 0
    
    # Tracking de métricas de performance
    episode_navs = []              # NAV final de cada episódio
    episode_portfolio_values = []  # Portfolio value final
    
    # Configuração de checkpoint automático
    logger.info(f"Checkpoint automático a cada {checkpoint_interval} episódios")
    
    # Rastreia os últimos 10 episódios para métricas móveis
    historical_loss_tracker = deque(maxlen=10) 

    for episode in range(start_episode, num_episodes+1):
        # Reset do ambiente
        state = env.reset()
        episode_start_time = time()

        # Loop do episódio: executa até max_steps_per_episode ou até done=True
        for episode_step in range(max_steps_per_episode):

            # Agente escolhe ação usando política epsilon-greedy
            action = agent.epsilon_greedy_policy(state)
            
            # Executa ação no ambiente
            next_state, reward, done = env.step(action)
            
            # Memoriza transição no replay buffer
            agent.memorize_transition(state, action, reward, next_state, done)
            
            # Se episódio terminou naturalmente, sai do loop
            if done:
                break
            
            # Atualiza estado para próximo step
            state = next_state
        
            # Informa a cada 250 steps executados
            steps_executed = episode_step + 1
            steps_remaining = max_steps_per_episode - steps_executed
            if steps_executed % 250 == 0:
                logger.info(f"Episódio {episode}: {steps_executed} steps executados de {max_steps_per_episode} (restam {steps_remaining})")


        # --- Treina a rede em lote após o episódio (otimização adaptativa) ---
        # Sistema de estudo adaptativo baseado no loss do agente
        
        # Verifica se há experiências suficientes no buffer
        if len(agent.experience) >= agent.batch_size:
            logger.info(f"Episódio {episode} concluído em {episode_step + 1} steps. Iniciando treinamento adaptativo...")
            
            
            # Etapa 1: Executa algumas iterações de amostragem para medir o loss atual
            SAMPLE_ITERATIONS = 8  # Número de iterações para calcular loss médio

            episode_losses = []

            for _ in range(SAMPLE_ITERATIONS):
                loss = agent.experience_replay()
                if loss is not None:
                    episode_losses.append(loss)

            # Calcula loss médio do episódio
            avg_episode_loss = np.mean(episode_losses) if episode_losses else 0.01
            
            
            # Etapa 2: Compara com o histórico de loss
            if not historical_loss_tracker:
                # Primeiro episódio: usa o loss atual como baseline
                historical_avg_loss = avg_episode_loss if avg_episode_loss > 0 else 0.01
            else:
                # Calcula média dos últimos episódios
                historical_avg_loss = np.mean(historical_loss_tracker)
            
            # Etapa 3: Calcula o "ratio de confusão" do agente
            # Se loss atual > média histórica → agente confuso → precisa estudar mais
            # Se loss atual < média histórica → agente confiante → estuda menos
            loss_ratio = (avg_episode_loss / historical_avg_loss) if historical_avg_loss > 0 else 1.0
            
            # Etapa 4: Define número de sessões de estudo adaptativas
            BASE_STUDY_SESSIONS = 8  # Sessões base quando ratio = 1.0
            MIN_STUDY_SESSIONS = 4   # Estudar no mínimo
            MAX_STUDY_SESSIONS = 64  # Estudar no máximo (se estiver muito confuso)

            study_sessions = int(BASE_STUDY_SESSIONS * loss_ratio)
                        
            # Limites de segurança: mínimo 4, máximo 64 sessões
            study_sessions = max(MIN_STUDY_SESSIONS, min(MAX_STUDY_SESSIONS, study_sessions))
            
            # Etapa 5: Executa as sessões de estudo (já fizemos SAMPLE_ITERATIONS, fazemos o resto)
            # remaining_sessions = max(0, study_sessions - SAMPLE_ITERATIONS)
            
            logger.info(
                f"Episódio {episode}: Loss={avg_episode_loss:.4f}, "
                f"Histórico={historical_avg_loss:.4f}, Ratio={loss_ratio:.2f}. "
                f"Executando {study_sessions} sessões de treinamento.)"
            )
            
            for _ in range(study_sessions):
                agent.experience_replay()
            
            # Etapa 6: Atualiza histórico de loss para próximo episódio
            historical_loss_tracker.append(avg_episode_loss)
        else:
            logger.info(
                f"Episódio {episode}: Buffer insuficiente "
                f"({len(agent.experience)}/{agent.batch_size}). Pulando treinamento."
            )

        # Registra tempo do episódio
        episode_duration = time() - episode_start_time
        episode_times.append(episode_duration)
        
        # Registra métricas do ambiente
        final_nav = env.portfolio_value
        episode_navs.append(final_nav)
        episode_portfolio_values.append(final_nav)       
        # Log detalhado a cada 10 episódios (formato do notebook)
        if episode % 10 == 0:
            total_time = time() - start_time
            
            # Calcula médias móveis de NAV (100 e 10 episódios)
            nav_ma_100 = np.mean(episode_navs[-100:]) if episode_navs else 1.0
            nav_ma_10 = np.mean(episode_navs[-10:]) if episode_navs else 1.0
            
            # Como não temos market_nav, usamos 1.0 (sem retorno) como referência
            # Ou poderia ser calculado como buy-and-hold se disponível
            market_nav_100 = 1.0
            market_nav_10 = 1.0
            
            # Calcula win ratio (NAV > 1.0 indica lucro)
            wins = sum([1 for nav in episode_navs[-100:] if nav > 1.0])
            win_ratio = wins / min(len(episode_navs), 100)
            
            # Formato idêntico ao notebook:
            # {episode:>4d} | {time} | Agent: {nav_ma_100-1:>6.1%} ({nav_ma_10-1:>6.1%}) | 
            # Market: {market_nav_100-1:>6.1%} ({market_nav_10-1:>6.1%}) | Wins: {win_ratio:>5.1%} | eps: {epsilon:>6.3f}
            template = '{:>4d} | {} | Agent: {:>6.1%} ({:>6.1%}) | '
            template += 'Market: {:>6.1%} ({:>6.1%}) | '
            template += 'Wins: {:>5.1%} | eps: {:>6.3f}'
            
            print(template.format(
                episode,
                format_time(total_time),
                nav_ma_100 - 1,  # Converte NAV para retorno percentual
                nav_ma_10 - 1,
                market_nav_100 - 1,
                market_nav_10 - 1,
                win_ratio,
                agent.epsilon
            ))
        
        # Checkpoint automático
        if episode % checkpoint_interval == 0:
            logger.info(f"Salvando checkpoint em episódio {episode}...")
            checkpoint_prefix = str(models_dir / f"{ticker_input}_DRLStrategy_checkpoint_ep{episode}")
            
            strategy_saver = DRLStrategy()
            strategy_saver.save(agent.online_network, checkpoint_prefix)
            logger.info(f"Checkpoint salvo: {checkpoint_prefix}_drl.keras")
    
    total_training_time = time() - start_time
    print("\n" + "=" * 80)
    print("TREINAMENTO CONCLUÍDO")
    print("=" * 80)
    print(f"Tempo total: {format_time(total_training_time)}")
    print(f"Episódios executados nesta sessão: {num_episodes}")
    print(f"Episódio final: {start_episode + num_episodes - 1}")
    print(f"Total de episódios acumulados: {agent.episodes}")
    print(f"Episódios interrompidos por timeout/limite: {interrupted_episodes}")
    if episode_times:
        print(f"Tempo médio por episódio: {format_time(sum(episode_times)/len(episode_times))}")
    print()
    print("Estatísticas de Performance:")
    print(f"  Recompensa média (últimos 100 eps): {sum(agent.rewards_history[-100:]) / min(len(agent.rewards_history), 100):.4f}")
    print(f"  Recompensa média (últimos 10 eps): {sum(agent.rewards_history[-10:]) / min(len(agent.rewards_history), 10):.4f}")
    if episode_navs:
        avg_nav_all = sum(episode_navs) / len(episode_navs)
        avg_nav_100 = sum(episode_navs[-100:]) / min(len(episode_navs), 100)
        avg_nav_10 = sum(episode_navs[-10:]) / min(len(episode_navs), 10)
        print(f"  NAV médio (todos): {avg_nav_all:.4f}")
        print(f"  NAV médio (últimos 100 eps): {avg_nav_100:.4f}")
        print(f"  NAV médio (últimos 10 eps): {avg_nav_10:.4f}")
        print(f"  ROI médio (últimos 100 eps): {(avg_nav_100 - 1.0) * 100:.2f}%")
        print(f"  ROI médio (últimos 10 eps): {(avg_nav_10 - 1.0) * 100:.2f}%")
    print()
    
    # 11. Salva estatísticas de treinamento
    logger.info("Salvando estatísticas de treinamento...")
    
    # Cria DataFrame com histórico de episódios
    training_stats = pd.DataFrame({
        'episode': list(range(start_episode, start_episode + len(agent.rewards_history))),
        'reward': agent.rewards_history,
        'steps': agent.steps_per_episode if hasattr(agent, 'steps_per_episode') else [0] * len(agent.rewards_history),
        'epsilon': agent.epsilon_history if hasattr(agent, 'epsilon_history') else [0] * len(agent.rewards_history),
        'nav': episode_navs[:len(agent.rewards_history)],  # Garante mesmo tamanho
    })
    
    # Adiciona médias móveis
    training_stats['reward_ma_10'] = training_stats['reward'].rolling(window=10, min_periods=1).mean()
    training_stats['reward_ma_100'] = training_stats['reward'].rolling(window=100, min_periods=1).mean()
    training_stats['nav_ma_10'] = training_stats['nav'].rolling(window=10, min_periods=1).mean()
    training_stats['nav_ma_100'] = training_stats['nav'].rolling(window=100, min_periods=1).mean()
    
    # Salva CSV
    stats_filename = f"{ticker_input}_DRLStrategy_training_stats.csv"
    stats_path = models_dir / stats_filename
    
    # Se continuou de checkpoint, mescla com estatísticas anteriores se existirem
    if start_episode > 1 and stats_path.exists():
        logger.info("Mesclando com estatísticas anteriores...")
        old_stats = pd.read_csv(stats_path)
        # Remove episódios duplicados (se existirem)
        old_stats = old_stats[old_stats['episode'] < start_episode]
        # Concatena com novas estatísticas
        training_stats = pd.concat([old_stats, training_stats], ignore_index=True)
    
    training_stats.to_csv(stats_path, index=False)
    logger.info(f"Estatísticas salvas em: {stats_path}")
    
    # 12. Atualiza o modelo de produção
    logger.info("Atualizando modelo de produção...")
    
    # NOVO FORMATO: ticker_StrategyName_prod
    model_prefix = str(models_dir / f"{ticker_input}_DRLStrategy_prod")
    
    logger.info(f"Atualizando modelo de produção: {model_prefix}_drl.keras")
    
    # Usa DRLStrategy para salvar (mantém interface consistente)
    strategy_saver = DRLStrategy()
    model_to_save = agent.online_network
    strategy_saver.save(model_to_save, model_prefix)
    
    logger.info("Modelo de produção atualizado com sucesso!")
    print()
    print("=" * 80)
    print("ARQUIVOS SALVOS/ATUALIZADOS")
    print("=" * 80)
    print(f"1. Modelo de PRODUÇÃO (atualizado):")
    print(f"   {model_prefix}_drl.keras")
    print(f"   {model_prefix}_params.joblib")
    print(f"2. Estatísticas de treinamento:")
    print(f"   {stats_path}")
    print(f"   Total de {len(training_stats)} episódios registrados")
    if checkpoint_interval > 0 and len(agent.rewards_history) >= checkpoint_interval:
        print(f"3. Checkpoints:")
        print(f"   {models_dir}/{ticker_input}_DRLStrategy_checkpoint_ep*.keras")
        print(f"   Último checkpoint: episódio {start_episode + num_episodes - 1}")
    print()
    print("=" * 80)
    print("INFORMAÇÕES IMPORTANTES:")
    print("=" * 80)
    print(f"✓ O modelo de produção foi ATUALIZADO com os pesos do episódio {start_episode + num_episodes - 1}")
    print(f"✓ Para continuar o treinamento, execute novamente este script")
    print(f"✓ O treinamento continuará automaticamente a partir do último checkpoint")
    print()
    print("=" * 80)
    print("PRÓXIMOS PASSOS:")
    print("=" * 80)
    print(f"1. Analise as estatísticas de treinamento:")
    print(f"   import pandas as pd")
    print(f"   stats = pd.read_csv('{stats_path}')")
    print(f"   stats[['episode', 'reward', 'nav', 'epsilon']].plot(subplots=True)")
    print()
    print(f"2. Teste o modelo usando SimulationEngine:")
    print(f"   - Abra notebooks/simulation/drl_inference_example.ipynb")
    print(f"   - Configure asset_symbol='{ticker_input}', strategy_name='DRLStrategy'")
    print()
    print(f"3. Use em live trading (se configurado):")
    print(f"   - Verifique live_trading.enabled no config do ativo")
    print(f"   - Execute: poetry run python src/live_trader.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
