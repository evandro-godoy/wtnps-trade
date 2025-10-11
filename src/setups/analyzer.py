# src/setups/analyzer.py
import pandas as pd
import numpy as np

# --- Funções de verificação para cada tipo de regra ---

def check_price_above_ema(data: pd.DataFrame, period: int) -> bool:
    """Verifica se o último preço de fecho está acima da EMA do período especificado."""
    if len(data) < period:
        return False
    ema = data['close'].ewm(span=period, adjust=False).mean()
    last_price = data['close'].iloc[-1]
    last_ema = ema.iloc[-1]
    return last_price > last_ema

def check_price_below_ema(data: pd.DataFrame, period: int) -> bool:
    """Verifica se o último preço de fecho está abaixo da EMA do período especificado."""
    if len(data) < period:
        return False
    ema = data['close'].ewm(span=period, adjust=False).mean()
    last_price = data['close'].iloc[-1]
    last_ema = ema.iloc[-1]
    return last_price < last_ema

def check_rsi_above(data: pd.DataFrame, period: int, level: int) -> bool:
    """Verifica se o último valor do RSI está acima de um determinado nível."""
    if len(data) < period:
        return False
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    if loss.iloc[-1] == 0: # Evita divisão por zero
        return True # Se não há perdas, a força é máxima
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    last_rsi = rsi.iloc[-1]
    return last_rsi > level

# --- Mapeamento de tipos de regra para funções ---

RULE_CHECKERS = {
    'price_above_ema': check_price_above_ema,
    'price_below_ema': check_price_below_ema,
    'rsi_above': check_rsi_above,
    # Adicione futuras funções de verificação aqui
}

# --- Função principal de avaliação ---

def evaluate_setups(ai_signal: int, setup_configs: list, data: pd.DataFrame) -> bool:
    """
    Avalia uma lista de regras de setup contra os dados de mercado.

    Args:
        ai_signal (int): O sinal do modelo de IA (1 para Compra, 0 para Venda).
        setup_configs (list): A lista de configurações de regras do main.yaml.
        data (pd.DataFrame): DataFrame com os dados de mercado recentes.

    Returns:
        bool: True se todos os critérios relevantes forem atendidos, False caso contrário.
    """
    signal_condition = 'buy' if ai_signal == 1 else 'sell'
    
    # Filtra as regras que se aplicam ao sinal atual da IA
    relevant_rules = [rule for rule in setup_configs if rule['condition'] == signal_condition]
    
    if not relevant_rules:
        # Se não há regras para este sinal, o setup é considerado válido por padrão
        return True
        
    for rule in relevant_rules:
        rule_type = rule.get('type')
        checker_function = RULE_CHECKERS.get(rule_type)
        
        if not checker_function:
            print(f"Aviso: Tipo de regra de setup desconhecido: {rule_type}")
            continue
            
        # Prepara os argumentos para a função de verificação
        params = rule.copy()
        params.pop('type')
        params.pop('condition')
        
        # Chama a função de verificação (ex: check_price_above_ema(data, period=21))
        if not checker_function(data, **params):
            # Se qualquer regra falhar, o setup inteiro é inválido
            return False
            
    # Se todas as regras relevantes passaram, o setup é válido
    return True