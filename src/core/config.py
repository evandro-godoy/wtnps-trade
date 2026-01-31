# src/core/config.py
import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Configurações globais validadas via Pydantic.
    Lê variáveis de ambiente ou usa defaults sensatos.
    """
    # Identificação
    PROJECT_NAME: str = "wtnps-finadv"
    VERSION: str = "0.1.0-mvp"
    
    # Caminhos (Baseados na estrutura do repo)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    MODELS_DIR: Path = BASE_DIR / "models"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Trading
    TRADING_ENABLED: bool = False  # Trava de segurança padrão
    TICKER_TARGET: str = "WDO$"    # Ativo padrão para o MVP
    
    # Event Bus
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True

# Singleton de configuração
settings = Settings()

# Garante que diretórios essenciais existam
os.makedirs(settings.LOGS_DIR, exist_ok=True)