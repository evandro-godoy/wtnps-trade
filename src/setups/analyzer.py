# src/setups/analyzer.py
import pandas as pd
import logging

# Configura o logger para este módulo
logger = logging.getLogger(__name__)

class SetupAnalyzer:
    """
    Classe para encapsular a lógica de análise e validação de setups técnicos.
    """

    def __init__(self):
        """
        Inicializador da classe. Pode ser usado para carregar
        configurações complexas de setup no futuro, se necessário.
        """
        logger.debug("SetupAnalyzer instanciado.")

    def evaluate_setups(self, current_candle_features: pd.DataFrame, setup_rules: list, ai_signal: str) -> dict:
        """
        Avalia uma lista de regras de setup (do config.yaml) contra
        os dados do candle atual (DataFrame de 1 linha).

        Args:
            current_candle_features (pd.DataFrame): DataFrame contendo 
                apenas a *última* linha (candle) com todas as features calculadas.
            setup_rules (list): A lista de dicionários de regras da seção 'setup'
                                do config.yaml.
            ai_signal (str): O sinal bruto da IA ("COMPRA" ou "VENDA").

        Returns:
            dict: Um dicionário contendo:
                "is_valid" (bool): True se todas as regras aplicáveis passarem.
                "details" (dict): Resultados individuais de cada regra.
                "final_decision" (str): "COMPRA", "VENDA", ou "HOLD".
        """
        
        # Se não há regras de setup, o setup é válido por padrão
        if not setup_rules:
            return {"is_valid": True, "details": {"info": "Nenhuma regra de setup definida."}, "final_decision": ai_signal}

        # Pega a última linha de dados (o candle atual) como uma Series
        if current_candle_features.empty:
             logger.warning("SetupAnalyzer: Recebeu DataFrame de features vazio.")
             return {"is_valid": False, "details": {"error": "No feature data"}, "final_decision": "HOLD"}
             
        try:
            # Pega a última (e única) linha como uma Series
            candle = current_candle_features.iloc[-1] 
        except IndexError:
            logger.warning("SetupAnalyzer: DataFrame de features não continha linhas.")
            return {"is_valid": False, "details": {"error": "IndexError on feature data"}, "final_decision": "HOLD"}

        is_setup_valid = True  # Assume que é válido até que uma regra falhe
        setup_details = {}     # Dicionário para armazenar o resultado de cada regra
        rules_for_signal = []  # Regras que se aplicam ao sinal da IA (COMPRA ou VENDA)

        # 1. Filtra as regras que se aplicam à condição (sinal) atual
        signal_condition = ai_signal.lower() # "compra" ou "venda"
        
        rules_for_signal = [rule for rule in setup_rules if rule.get('condition', '').lower() == signal_condition]

        # Se não houver regras *específicas* para este sinal, o setup é considerado válido
        if not rules_for_signal:
            logger.debug(f"Nenhuma regra de setup encontrada para a condição: {ai_signal}")
            return {"is_valid": True, "details": {"info": f"Nenhuma regra de setup aplicada para {ai_signal}"}, "final_decision": ai_signal}

        # 2. Avalia as regras filtradas
        for rule in rules_for_signal:
            rule_type = rule.get('type')
            rule_valid = False # Default para inválido até ser provado o contrário
            
            try:
                # --- Lógica das Regras ---
                
                if rule_type == 'price_above_ma':
                    ma_type = rule.get('ma_type', 'sma')
                    period = rule.get('period', 20)
                    ma_col = f"{ma_type}_{period}" # ex: "sma_20"
                    
                    if ma_col in candle:
                        rule_valid = candle['close'] > candle[ma_col]
                        setup_details[f"{ma_col}_above"] = f"Close ({candle['close']:.2f}) > MA ({candle[ma_col]:.2f}) -> {rule_valid}"
                    else:
                        setup_details[f"{ma_col}_above"] = f"Erro: Coluna {ma_col} não encontrada."
                        logger.warning(f"SetupAnalyzer: Coluna de MA '{ma_col}' não encontrada nos dados.")

                elif rule_type == 'price_below_ma':
                    ma_type = rule.get('ma_type', 'sma')
                    period = rule.get('period', 20)
                    ma_col = f"{ma_type}_{period}" # ex: "sma_20"
                    
                    if ma_col in candle:
                        rule_valid = candle['close'] < candle[ma_col]
                        setup_details[f"{ma_col}_below"] = f"Close ({candle['close']:.2f}) < MA ({candle[ma_col]:.2f}) -> {rule_valid}"
                    else:
                        setup_details[f"{ma_col}_below"] = f"Erro: Coluna {ma_col} não encontrada."
                        logger.warning(f"SetupAnalyzer: Coluna de MA '{ma_col}' não encontrada nos dados.")
                
                elif rule_type == 'rsi_below':
                    level = rule.get('level', 30)
                    if 'rsi' in candle:
                        rule_valid = candle['rsi'] < level
                        setup_details[f"rsi_below_{level}"] = f"RSI ({candle['rsi']:.2f}) < {level} -> {rule_valid}"
                    else:
                        setup_details[f"rsi_below_{level}"] = "Erro: Coluna 'rsi' não encontrada."
                        logger.warning("SetupAnalyzer: Coluna 'rsi' não encontrada para regra rsi_below.")

                elif rule_type == 'rsi_above':
                    level = rule.get('level', 70)
                    if 'rsi' in candle:
                        rule_valid = candle['rsi'] > level
                        setup_details[f"rsi_above_{level}"] = f"RSI ({candle['rsi']:.2f}) > {level} -> {rule_valid}"
                    else:
                        setup_details[f"rsi_above_{level}"] = "Erro: Coluna 'rsi' não encontrada."
                        logger.warning("SetupAnalyzer: Coluna 'rsi' não encontrada para regra rsi_above.")
                
                # (Adicione outras lógicas de regras aqui, como 'ema_crossed_up', etc.)

                else:
                    logger.warning(f"Tipo de regra de setup desconhecido: {rule_type}")
                    setup_details[f"unknown_rule_{rule_type}"] = "Erro: Tipo de regra desconhecido."
                    rule_valid = False # Regra desconhecida invalida a condição

                # Se *qualquer* regra (para esta condição) falhar, o setup todo é inválido
                if not rule_valid:
                    is_setup_valid = False
            
            except Exception as e:
                 logger.error(f"Erro ao avaliar regra de setup {rule}: {e}", exc_info=True)
                 setup_details[f"rule_error_{rule.get('type')}"] = str(e)
                 is_setup_valid = False # Erro na regra invalida o setup

        # 3. Determina a decisão final
        final_decision = "HOLD"
        if is_setup_valid:
            final_decision = ai_signal # Se o setup for válido, repassa o sinal da IA
        
        return {"is_valid": is_setup_valid, "details": setup_details, "final_decision": final_decision}