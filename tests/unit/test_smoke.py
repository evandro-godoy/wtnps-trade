"""
Smoke tests para validação básica do CI.
Verifica que os módulos principais podem ser importados sem erros.
"""

import pytest


def test_import_utils_logger():
    """Testa importação do logger."""
    try:
        from src.utils import logger
        assert logger is not None
    except ImportError as e:
        pytest.fail(f"Failed to import src.utils.logger: {e}")


def test_import_strategies_base():
    """Testa importação da classe base de estratégias."""
    try:
        from src.strategies.base import Strategy
        assert Strategy is not None
    except ImportError as e:
        pytest.fail(f"Failed to import Strategy base: {e}")


def test_import_simulation_engine():
    """Testa importação do simulation engine."""
    try:
        from src.simulation import engine
        assert engine is not None
    except ImportError as e:
        pytest.fail(f"Failed to import simulation engine: {e}")


def test_python_version():
    """Verifica versão do Python."""
    import sys
    assert sys.version_info >= (3, 12), f"Python 3.12+ required, got {sys.version}"


def test_critical_dependencies():
    """Verifica que dependências críticas estão instaladas."""
    try:
        import pandas as pd
        import numpy as np
        import yaml
        
        assert pd.__version__ >= "2.0", f"pandas 2.0+ required, got {pd.__version__}"
        assert np.__version__ >= "2.0", f"numpy 2.0+ required, got {np.__version__}"
    except ImportError as e:
        pytest.fail(f"Critical dependency missing: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
