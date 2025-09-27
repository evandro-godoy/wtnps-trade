# src/backtest_engine/engine.py
import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
import logging

from src.strategies.base import BaseStrategy

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WalkForwardBacktester:
    """
    Motor de backtesting que implementa a validação Walk-Forward.
    """
    def __init__(self, strategy: BaseStrategy, n_splits: int = 10):
        if not isinstance(strategy, BaseStrategy):
            raise TypeError("A estratégia deve ser uma instância de BaseStrategy")
        self.strategy = strategy
        self.n_splits = n_splits

    def run(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """
        Executa o backtest e retorna um DataFrame com os resultados.
        """
        logging.info(f"Iniciando backtest com a estratégia: {type(self.strategy).__name__}")
        
        # 1. Gerar features e definir o target
        featured_data = self.strategy.define_features(market_data)
        featured_data['Target'] = (featured_data['Close'].shift(-1) > featured_data['Close']).astype(int)
        featured_data = featured_data.dropna()

        X = featured_data[self.strategy.get_feature_names()]
        y = featured_data['Target']

        if len(X) < self.n_splits:
            raise ValueError("Não há dados suficientes para o número de splits especificado.")

        # 2. Configurar o validador
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        
        all_predictions = []
        all_real_values = []
        prediction_indices = []

        # 3. Loop de Walk-Forward
        for fold, (train_index, test_index) in enumerate(tscv.split(X)):
            logging.info(f"  > Processando dobra {fold + 1}/{self.n_splits}...")
            
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]
            
            model = self.strategy.define_model()
            model.fit(X_train, y_train)
            
            predictions = model.predict(X_test)
            
            # all_predictions.extend(predictions)
            # all_real_values.extend(y_test)
            # prediction_indices.extend(y_test.index)
            
            if len(predictions) > 0:
                # O primeiro índice da predição corresponde ao último índice dos dados de teste
                # que foi possível formar uma sequência completa.
                start_index = len(y_test) - len(predictions)
                
                valid_y_test = y_test.iloc[start_index:]
                
                all_predictions.extend(predictions)
                all_real_values.extend(valid_y_test.values)
                prediction_indices.extend(valid_y_test.index)            

        # 4. Compilar resultados
        accuracy = accuracy_score(all_real_values, all_predictions)
        logging.info(f"Backtest concluído. Acurácia final: {accuracy:.4f}")

        results_df = pd.DataFrame({
            'Prediction': all_predictions,
            'Real_Target': all_real_values,
        }, index=prediction_indices)
        
        # Juntar com os retornos do mercado para análise futura
        results_df = results_df.join(featured_data[['Returns']], how='left')

        return results_df