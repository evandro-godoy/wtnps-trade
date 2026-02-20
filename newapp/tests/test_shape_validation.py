"""Test script for LSTM input shape validation.

Valida que a exceção InputShapeValidationError é lançada corretamente
quando o tensor de entrada não possui o shape esperado.

Padrão: Fail-Fast - Detecta erros imediatamente antes de chamar model.predict()
"""

import numpy as np
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from newapp.src.strategies.lstm_volatility import (
    InputShapeValidationError,
    validate_lstm_input_shape
)


def test_validate_lstm_input_shape():
    """Tests for the validate_lstm_input_shape function."""
    
    print("=" * 70)
    print("TESTE: Validação de Shape para LSTM")
    print("=" * 70)
    
    # Parâmetros esperados
    expected_lookback = 108
    expected_n_features = 25
    
    # ========== TESTE 1: Shape correto (deve passar sem erro) ==========
    print("\n[TESTE 1] Shape correto (n_samples=5, lookback=108, n_features=25)")
    try:
        X_valid = np.random.randn(5, expected_lookback, expected_n_features)
        validate_lstm_input_shape(
            X_seq=X_valid,
            expected_lookback=expected_lookback,
            expected_n_features=expected_n_features
        )
        print("✅ PASSOU: Validação aceitou tensor com shape correto")
    except InputShapeValidationError as e:
        print(f"❌ FALHOU: {e}")
        return False
    
    # ========== TESTE 2: Lookback incorreto (deve falhar) ==========
    print("\n[TESTE 2] Lookback incorreto (lookback=96 em vez de 108)")
    try:
        X_wrong_lookback = np.random.randn(5, 96, expected_n_features)
        validate_lstm_input_shape(
            X_seq=X_wrong_lookback,
            expected_lookback=expected_lookback,
            expected_n_features=expected_n_features
        )
        print("❌ FALHOU: Deveria ter lançado InputShapeValidationError")
        return False
    except InputShapeValidationError as e:
        print(f"✅ PASSOU: Exceção lançada corretamente")
    
    # ========== TESTE 3: Número de features incorreto (deve falhar) ==========
    print("\n[TESTE 3] Features incorretas (n_features=20 em vez de 25)")
    try:
        X_wrong_features = np.random.randn(5, expected_lookback, 20)
        validate_lstm_input_shape(
            X_seq=X_wrong_features,
            expected_lookback=expected_lookback,
            expected_n_features=expected_n_features
        )
        print("❌ FALHOU: Deveria ter lançado InputShapeValidationError")
        return False
    except InputShapeValidationError as e:
        print(f"✅ PASSOU: Exceção lançada corretamente")
    
    # ========== TESTE 4: Tensor 2D em vez de 3D (deve falhar) ==========
    print("\n[TESTE 4] Dimensionalidade incorreta (2D em vez de 3D)")
    try:
        X_2d = np.random.randn(5, expected_n_features)
        validate_lstm_input_shape(
            X_seq=X_2d,
            expected_lookback=expected_lookback,
            expected_n_features=expected_n_features
        )
        print("❌ FALHOU: Deveria ter lançado InputShapeValidationError")
        return False
    except InputShapeValidationError as e:
        print(f"✅ PASSOU: Exceção lançada corretamente")
    
    # ========== TESTE 5: Tensor None (deve falhar) ==========
    print("\n[TESTE 5] Tensor None (entrada None)")
    try:
        validate_lstm_input_shape(
            X_seq=None,
            expected_lookback=expected_lookback,
            expected_n_features=expected_n_features
        )
        print("❌ FALHOU: Deveria ter lançado InputShapeValidationError")
        return False
    except InputShapeValidationError as e:
        print(f"✅ PASSOU: Exceção lançada corretamente")
    
    # ========== TESTE 6: Array com zero amostras (deve falhar) ==========
    print("\n[TESTE 6] Array com zero amostras (n_samples=0)")
    try:
        X_zero_samples = np.random.randn(0, expected_lookback, expected_n_features)
        validate_lstm_input_shape(
            X_seq=X_zero_samples,
            expected_lookback=expected_lookback,
            expected_n_features=expected_n_features
        )
        print("❌ FALHOU: Deveria ter lançado InputShapeValidationError")
        return False
    except InputShapeValidationError as e:
        print(f"✅ PASSOU: Exceção lançada corretamente")
    
    print("\n" + "=" * 70)
    print("✅ TODOS OS TESTES PASSARAM!")
    print("=" * 70)
    return True


def test_exception_attributes():
    """Tests that InputShapeValidationError stores all attributes correctly."""
    
    print("\n" + "=" * 70)
    print("TESTE: Atributos da Exceção InputShapeValidationError")
    print("=" * 70)
    
    expected_shape = (10, 108, 25)
    received_shape = (10, 96, 25)
    context = "Lookback mismatch"
    
    exc = InputShapeValidationError(
        expected_shape=expected_shape,
        received_shape=received_shape,
        context=context
    )
    
    assert exc.expected_shape == expected_shape, "expected_shape não armazenado"
    assert exc.received_shape == received_shape, "received_shape não armazenado"
    assert exc.context == context, "context não armazenado"
    assert str(exc), "Mensagem de exceção vazia"
    
    print(f"✅ expected_shape: {exc.expected_shape}")
    print(f"✅ received_shape: {exc.received_shape}")
    print(f"✅ context: {exc.context}")
    print(f"✅ message armazenada corretamente")
    print("\n✅ EXCEÇÃO IMPLEMENTADA CORRETAMENTE!")
    print("=" * 70)


if __name__ == "__main__":
    print("\nIniciando testes de validação de shape...\n")
    
    # Executar testes
    success = test_validate_lstm_input_shape()
    test_exception_attributes()
    
    if success:
        print("\n✨ Validação de shape está funcionando corretamente (Fail-Fast)")
        sys.exit(0)
    else:
        print("\n❌ Alguns testes falharam")
        sys.exit(1)
