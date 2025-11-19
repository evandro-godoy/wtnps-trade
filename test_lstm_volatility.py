# test_lstm_volatility.py
"""
Script de teste simplificado para validar a estratégia LSTMVolatilityStrategy.
"""
import pandas as pd
import numpy as np
import logging
from pathlib import Path

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_strategy_instantiation():
    """Testa a instanciação da estratégia."""
    logger.info("=== Teste 1: Instanciação da Estratégia ===")
    try:
        from src.strategies.lstm_volatility import LSTMVolatilityStrategy
        
        strategy = LSTMVolatilityStrategy(
            lookback=20,
            lstm_units=64,
            dropout_rate=0.2,
            target_period=3,
            volatility_multiplier=2.5
        )
        
        logger.info(f"✓ Estratégia instanciada com sucesso")
        logger.info(f"  - Features: {len(strategy.feature_names)} features")
        logger.info(f"  - Lookback: {strategy.lookback}")
        logger.info(f"  - Target period: {strategy.target_period}")
        return True
    except Exception as e:
        logger.error(f"✗ Erro na instanciação: {e}", exc_info=True)
        return False


def test_feature_generation():
    """Testa a geração de features."""
    logger.info("\n=== Teste 2: Geração de Features ===")
    try:
        from src.strategies.lstm_volatility import LSTMVolatilityStrategy
        
        # Criar dados sintéticos
        dates = pd.date_range(start='2023-01-01', periods=300, freq='D')
        np.random.seed(42)
        
        close = 100 + np.cumsum(np.random.randn(300) * 2)
        high = close + np.abs(np.random.randn(300) * 0.5)
        low = close - np.abs(np.random.randn(300) * 0.5)
        open_price = close + np.random.randn(300) * 0.3
        volume = np.random.randint(1000, 10000, 300)
        
        data = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)
        
        strategy = LSTMVolatilityStrategy()
        df_features = strategy.define_features(data)
        
        logger.info(f"✓ Features geradas com sucesso")
        logger.info(f"  - Shape: {df_features.shape}")
        logger.info(f"  - Colunas: {list(df_features.columns)[:10]}...")
        
        # Verificar se todas as features esperadas existem
        missing = [f for f in strategy.feature_names if f not in df_features.columns]
        if missing:
            logger.warning(f"  ! Features ausentes: {missing}")
            return False
        
        logger.info(f"  ✓ Todas as {len(strategy.feature_names)} features presentes")
        return True
        
    except Exception as e:
        logger.error(f"✗ Erro na geração de features: {e}", exc_info=True)
        return False


def test_target_generation():
    """Testa a geração do target."""
    logger.info("\n=== Teste 3: Geração do Target ===")
    try:
        from src.strategies.lstm_volatility import LSTMVolatilityStrategy
        
        # Criar dados sintéticos
        dates = pd.date_range(start='2023-01-01', periods=300, freq='D')
        np.random.seed(42)
        
        close = 100 + np.cumsum(np.random.randn(300) * 2)
        high = close + np.abs(np.random.randn(300) * 0.5)
        low = close - np.abs(np.random.randn(300) * 0.5)
        open_price = close + np.random.randn(300) * 0.3
        volume = np.random.randint(1000, 10000, 300)
        
        data = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)
        
        strategy = LSTMVolatilityStrategy(target_period=3, volatility_multiplier=2.5)
        df_features = strategy.define_features(data)
        target = strategy.define_target(df_features)
        
        logger.info(f"✓ Target gerado com sucesso")
        logger.info(f"  - Shape: {target.shape}")
        logger.info(f"  - Tipo: {target.dtype}")
        
        # Verificar distribuição de classes
        counts = target.value_counts()
        logger.info(f"  - Distribuição:")
        for val, count in counts.items():
            logger.info(f"    Classe {val}: {count} ({count/len(target)*100:.1f}%)")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Erro na geração do target: {e}", exc_info=True)
        return False


def test_model_definition():
    """Testa a definição do modelo."""
    logger.info("\n=== Teste 4: Definição do Modelo ===")
    try:
        from src.strategies.lstm_volatility import LSTMVolatilityStrategy
        
        strategy = LSTMVolatilityStrategy(
            lookback=20,
            lstm_units=64,
            dropout_rate=0.2
        )
        
        model = strategy.define_model()
        
        logger.info(f"✓ Modelo definido com sucesso")
        logger.info(f"  - Tipo: {type(model).__name__}")
        logger.info(f"  - Lookback: {model.lookback}")
        logger.info(f"  - LSTM units: {model.lstm_units}")
        logger.info(f"  - Features: {model.n_features}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Erro na definição do modelo: {e}", exc_info=True)
        return False


def test_training_mini():
    """Testa um treinamento mínimo."""
    logger.info("\n=== Teste 5: Treinamento Mínimo ===")
    try:
        from src.strategies.lstm_volatility import LSTMVolatilityStrategy
        
        # Criar dados sintéticos maiores
        dates = pd.date_range(start='2023-01-01', periods=500, freq='D')
        np.random.seed(42)
        
        close = 100 + np.cumsum(np.random.randn(500) * 2)
        high = close + np.abs(np.random.randn(500) * 1.5)
        low = close - np.abs(np.random.randn(500) * 1.5)
        open_price = close + np.random.randn(500) * 0.5
        volume = np.random.randint(1000, 10000, 500)
        
        data = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)
        
        strategy = LSTMVolatilityStrategy(
            lookback=20,
            lstm_units=32,  # Menor para teste rápido
            dropout_rate=0.2,
            target_period=3,
            volatility_multiplier=2.0
        )
        
        logger.info("  Preparando dados...")
        df_features = strategy.define_features(data)
        target = strategy.define_target(df_features)
        
        # Alinhar features e target
        feature_names = strategy.get_feature_names()
        X = df_features[feature_names].iloc[:len(target)]
        y = target
        
        logger.info(f"  Dados preparados: X={X.shape}, y={y.shape}")
        
        logger.info("  Definindo modelo...")
        model = strategy.define_model()
        
        logger.info("  Iniciando treino (epochs=5 para teste)...")
        model.epochs = 5  # Reduzir épocas para teste rápido
        model.fit(X, y)
        
        logger.info(f"✓ Treinamento mínimo concluído com sucesso")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Erro no treinamento: {e}", exc_info=True)
        return False


def test_persistence():
    """Testa salvamento e carregamento do modelo."""
    logger.info("\n=== Teste 6: Persistência (Save/Load) ===")
    try:
        from src.strategies.lstm_volatility import LSTMVolatilityStrategy, LSTMVolatilityWrapper
        
        # Criar dados sintéticos
        dates = pd.date_range(start='2023-01-01', periods=300, freq='D')
        np.random.seed(42)
        
        close = 100 + np.cumsum(np.random.randn(300) * 2)
        high = close + np.abs(np.random.randn(300) * 1.5)
        low = close - np.abs(np.random.randn(300) * 1.5)
        open_price = close + np.random.randn(300) * 0.5
        volume = np.random.randint(1000, 10000, 300)
        
        data = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)
        
        strategy = LSTMVolatilityStrategy(lookback=20, lstm_units=32)
        
        df_features = strategy.define_features(data)
        target = strategy.define_target(df_features)
        
        feature_names = strategy.get_feature_names()
        X = df_features[feature_names].iloc[:len(target)]
        y = target
        
        model = strategy.define_model()
        model.epochs = 3  # Treino mínimo
        model.fit(X, y)
        
        # Testar salvamento
        test_path = Path("models/TEST_LSTMVolatilityStrategy_test")
        test_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"  Salvando modelo em {test_path}...")
        strategy.save(model, str(test_path))
        
        # Verificar arquivos criados
        expected_files = [
            f"{test_path}_lstm.keras",
            f"{test_path}_scaler.joblib",
            f"{test_path}_params.joblib"
        ]
        
        for filepath in expected_files:
            if not Path(filepath).exists():
                logger.error(f"  ✗ Arquivo não encontrado: {filepath}")
                return False
            logger.info(f"  ✓ Arquivo criado: {filepath}")
        
        # Testar carregamento
        logger.info(f"  Carregando modelo de {test_path}...")
        loaded_model = strategy.load(str(test_path))
        
        logger.info(f"✓ Modelo salvo e carregado com sucesso")
        logger.info(f"  - Lookback: {loaded_model.lookback}")
        logger.info(f"  - Features: {loaded_model.n_features}")
        
        # Limpar arquivos de teste
        for filepath in expected_files:
            Path(filepath).unlink(missing_ok=True)
        logger.info(f"  ✓ Arquivos de teste removidos")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Erro na persistência: {e}", exc_info=True)
        return False


def main():
    """Executa todos os testes."""
    logger.info("=" * 60)
    logger.info("TESTES DA ESTRATÉGIA LSTMVolatilityStrategy")
    logger.info("=" * 60)
    
    tests = [
        ("Instanciação", test_strategy_instantiation),
        ("Geração de Features", test_feature_generation),
        ("Geração de Target", test_target_generation),
        ("Definição de Modelo", test_model_definition),
        ("Treinamento Mínimo", test_training_mini),
        ("Persistência", test_persistence),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"Erro crítico no teste '{test_name}': {e}")
            results[test_name] = False
    
    # Resumo
    logger.info("\n" + "=" * 60)
    logger.info("RESUMO DOS TESTES")
    logger.info("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASSOU" if result else "✗ FALHOU"
        logger.info(f"{status}: {test_name}")
    
    logger.info("=" * 60)
    logger.info(f"Resultado: {passed}/{total} testes passaram ({passed/total*100:.0f}%)")
    logger.info("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
