# src/agents/drl_agent.py
"""
Agente Double Deep Q-Network (DDQN) para treinamento de estratégias DRL.
Adaptado do notebook 04_q_learning_for_trading.ipynb para uso com TradingEnv customizado.
"""

import numpy as np
import logging
from collections import deque
from random import sample
from typing import Tuple

import tensorflow as tf
from tensorflow.keras import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.regularizers import l2

logger = logging.getLogger(__name__)


class ReplayBuffer:
    """
    Replay Buffer para armazenar experiências (s, a, r, s', done).
    """
    
    def __init__(self, capacity: int, state_dim: int):
        """
        Args:
            capacity: Capacidade máxima do buffer
            state_dim: Dimensão do vetor de estado
        """
        self.capacity = capacity
        self.idx = 0
        
        # Armazena experiências como arrays numpy
        self.state_memory = np.zeros(shape=(capacity, state_dim), dtype=np.float32)
        self.new_state_memory = np.zeros_like(self.state_memory)
        self.action_memory = np.zeros(capacity, dtype=np.int32)
        self.reward_memory = np.zeros(capacity, dtype=np.float32)
        self.done_memory = np.zeros(capacity, dtype=np.float32)  # 0 se done, 1 se continua
    
    def store(self, state, action, reward, next_state, done):
        """Armazena uma transição."""
        index = self.idx % self.capacity  # Circular buffer
        
        self.state_memory[index, :] = state
        self.new_state_memory[index, :] = next_state if next_state is not None else state
        self.reward_memory[index] = reward
        self.action_memory[index] = action
        self.done_memory[index] = 0.0 if done else 1.0  # Inverte: 0=terminou, 1=continua
        
        self.idx += 1
    
    def sample(self, batch_size: int) -> Tuple:
        """
        Amostra um mini-batch aleatório.
        
        Returns:
            Tupla (states, actions, rewards, next_states, not_done)
        """
        max_mem = min(self.idx, self.capacity)
        batch_indices = np.random.choice(max_mem, batch_size, replace=False)
        
        states = self.state_memory[batch_indices]
        next_states = self.new_state_memory[batch_indices]
        rewards = self.reward_memory[batch_indices]
        actions = self.action_memory[batch_indices]
        not_done = self.done_memory[batch_indices]
        
        return states, actions, rewards, next_states, not_done
    
    def __len__(self):
        """Retorna o número de experiências armazenadas."""
        return min(self.idx, self.capacity)


class DDQNAgent:
    """
    Agente Double Deep Q-Network (DDQN).
    
    Implementa:
    - Q-Network online (atualizada a cada step)
    - Q-Network target (atualizada periodicamente para estabilidade)
    - Experience replay
    - Epsilon-greedy policy com decay
    """
    
    def __init__(
        self,
        state_dim: int,
        num_actions: int,
        learning_rate: float = 0.0001,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_min: float = 0.01,
        epsilon_exponential_decay: float = 0.99,
        replay_capacity: int = int(1e6),
        architecture: Tuple[int, ...] = (256, 256),
        l2_reg: float = 1e-6,
        tau: int = 100,
        batch_size: int = 4096
    ):
        """
        Inicializa o agente DDQN.
        
        Args:
            state_dim: Dimensão do estado
            num_actions: Número de ações possíveis
            learning_rate: Taxa de aprendizado
            gamma: Fator de desconto
            epsilon_start: Epsilon inicial (exploração)
            epsilon_min: Epsilon mínimo (valor final)
            epsilon_exponential_decay: Fator de decay exponencial após decay linear
            replay_capacity: Capacidade do replay buffer
            architecture: Tupla com número de unidades por camada oculta
            l2_reg: Regularização L2
            tau: Frequência de atualização da target network
            batch_size: Tamanho do mini-batch
        """
        self.state_dim = state_dim
        self.num_actions = num_actions
        self.gamma = gamma
        self.batch_size = batch_size
        self.tau = tau
        self.architecture = architecture
        self.l2_reg = l2_reg
        self.learning_rate = learning_rate
        
        # Replay buffer
        self.experience = ReplayBuffer(replay_capacity, state_dim)
        
        # Networks
        self.online_network = self._build_model()
        self.target_network = self._build_model(trainable=False)
        self.update_target()
        
        # Epsilon-greedy
        self.epsilon = epsilon_start
        self.epsilon_min = epsilon_min
        self.epsilon_exponential_decay = epsilon_exponential_decay
        self.epsilon_decay_episodes = None  # Set via set_epsilon_decay()
        self.epsilon_decay_per_episode = None  # Set via set_epsilon_decay()
        self.epsilon_history = []
        
        # Tracking
        self.total_steps = 0
        self.train_steps = 0
        self.episodes = 0
        self.episode_length = 0
        self.episode_reward = 0.0
        self.rewards_history = []
        self.steps_per_episode = []
        self.losses = []
        
        # Batch indices (pré-alocado)
        self.idx = tf.range(batch_size)
        
        logger.info(
            f"DDQNAgent inicializado: StateDim={state_dim}, Actions={num_actions}, "
            f"Architecture={architecture}, LR={learning_rate}, Gamma={gamma}, "
            f"ReplayCapacity={replay_capacity}, BatchSize={batch_size}"
        )
    
    def _build_model(self, trainable: bool = True) -> Sequential:
        """
        Constrói a Q-Network (online ou target).
        
        Args:
            trainable: Se os pesos devem ser treináveis
        
        Returns:
            Modelo Keras Sequential
        """
        layers = []
        
        # Camadas ocultas
        for i, units in enumerate(self.architecture, 1):
            layers.append(Dense(
                units=units,
                input_dim=self.state_dim if i == 1 else None,
                activation='relu',
                kernel_regularizer=l2(self.l2_reg),
                name=f'Dense_{i}',
                trainable=trainable
            ))
        
        # Dropout para regularização
        layers.append(Dropout(0.1))
        
        # Camada de saída: Q-values para cada ação
        layers.append(Dense(
            units=self.num_actions,
            trainable=trainable,
            name='Output'
        ))
        
        model = Sequential(layers)
        model.compile(
            loss='mean_squared_error',
            optimizer=Adam(learning_rate=self.learning_rate)
        )
        
        return model
    
    def set_epsilon_decay(self, num_episodes: int):
        """
        Configura epsilon decay baseado no número total de episódios.
        
        Args:
            num_episodes: Número total de episódios de treinamento
        """
        # 80% dos episódios para decay linear
        self.epsilon_decay_episodes = int(num_episodes * 0.8)
        # Decay por episódio para atingir epsilon_min em 80% dos episódios
        self.epsilon_decay_per_episode = (1.0 - self.epsilon_min) / self.epsilon_decay_episodes
        
        logger.info(
            f"Epsilon decay configurado: {self.epsilon_decay_episodes} episódios lineares "
            f"(decay={self.epsilon_decay_per_episode:.6f} por episódio)"
        )
    
    def update_target(self):
        """Copia pesos da online network para a target network."""
        self.target_network.set_weights(self.online_network.get_weights())
    
    def epsilon_greedy_policy(self, state: np.ndarray) -> int:
        """
        Seleciona uma ação usando política epsilon-greedy.
        
        Args:
            state: Vetor de estado (shape: (state_dim,))
        
        Returns:
            Ação escolhida (0, 1, ou 2)
        """
        self.total_steps += 1
        
        # Exploração
        if np.random.rand() <= self.epsilon:
            return np.random.choice(self.num_actions)
        
        # Exploitação: escolhe melhor ação
        state_reshaped = state.reshape(1, -1)
        q_values = self.online_network.predict(state_reshaped, verbose=0)
        return int(np.argmax(q_values[0]))
    
    def memorize_transition(self, state, action, reward, next_state, done):
        """
        Armazena transição no replay buffer e atualiza métricas de episódio.
        
        Args:
            state: Estado atual
            action: Ação executada
            reward: Recompensa obtida
            next_state: Próximo estado (ou None se done=True)
            done: Se o episódio terminou
        """
        # Armazena experiência
        # Se done=True, next_state pode ser None; buffer lidará com isso
        state_to_store = state if state is not None else np.zeros(self.state_dim)
        next_state_to_store = next_state if next_state is not None else state_to_store
        
        self.experience.store(state_to_store, action, reward, next_state_to_store, done)
        
        # Atualiza episódio
        if not done:
            self.episode_reward += reward
            self.episode_length += 1
        else:
            # Fim do episódio: registra métricas e decai epsilon
            self.episode_reward += reward
            self.episode_length += 1
            
            self.episodes += 1
            self.rewards_history.append(self.episode_reward)
            self.steps_per_episode.append(self.episode_length)
            self.epsilon_history.append(self.epsilon)
            
            # Decay epsilon
            self._decay_epsilon()
            
            # Log a cada 10 episódios
            if self.episodes % 10 == 0:
                avg_reward_100 = np.mean(self.rewards_history[-100:])
                avg_reward_10 = np.mean(self.rewards_history[-10:])
                logger.info(
                    f"Episode {self.episodes} | Reward: {self.episode_reward:.4f} | "
                    f"Avg(100): {avg_reward_100:.4f} | Avg(10): {avg_reward_10:.4f} | "
                    f"Epsilon: {self.epsilon:.4f} | Steps: {self.episode_length}"
                )
            
            # Reseta para próximo episódio
            self.episode_reward = 0.0
            self.episode_length = 0
    
    def _decay_epsilon(self):
        """Decai epsilon (linear primeiro, depois exponencial)."""
        if self.epsilon_decay_episodes is None or self.epsilon_decay_per_episode is None:
            logger.warning("Epsilon decay não configurado. Chame set_epsilon_decay() primeiro.")
            return
        
        if self.episodes < self.epsilon_decay_episodes:
            # Decay linear até 80% dos episódios
            self.epsilon -= self.epsilon_decay_per_episode
            self.epsilon = max(self.epsilon, self.epsilon_min)
        else:
            # Decay exponencial após 80% dos episódios
            self.epsilon *= self.epsilon_exponential_decay
            self.epsilon = max(self.epsilon, self.epsilon_min)
    
    def  experience_replay(self):
        """
        Treina a online network usando experience replay (DDQN).
        """
        # Precisa ter experiências suficientes
        if len(self.experience) < self.batch_size:
            return
        
        # Amostra mini-batch
        states, actions, rewards, next_states, not_done = self.experience.sample(self.batch_size)
        
        # --- Double DQN Logic ---
        
        # 1. Online network escolhe a melhor ação para next_state
        next_q_values_online = self.online_network.predict(next_states, verbose=0)
        best_actions = tf.argmax(next_q_values_online, axis=1)
        
        # 2. Target network fornece Q-value para essa ação
        next_q_values_target = self.target_network.predict(next_states, verbose=0)
        target_q_values = tf.gather_nd(
            next_q_values_target,
            tf.stack((self.idx, tf.cast(best_actions, tf.int32)), axis=1)
        )
        
        # 3. Calcula TD target
        targets = rewards + not_done * self.gamma * target_q_values.numpy()
        
        # 4. Q-values atuais da online network
        q_values = self.online_network.predict(states, verbose=0)
        
        # 5. Atualiza apenas o Q-value da ação executada
        for i in range(self.batch_size):
            q_values[i, actions[i]] = targets[i]
        
        # 6. Treina a online network
        loss = self.online_network.train_on_batch(x=states, y=q_values)
        self.losses.append(loss)
        self.train_steps += 1
        
        # 7. Atualiza target network periodicamente
        if self.total_steps % self.tau == 0:
            self.update_target()
            logger.debug(f"Target network atualizada @ step {self.total_steps}")
