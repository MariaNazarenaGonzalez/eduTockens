# TODO: Define application configuration and environment-based settings (JWT secret, database URL, NCT base URL, token expiry, etc.).

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables
    """
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/academic_points"
    
    # JWT
    jwt_secret: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    
    # NCT (Nodo Coordinador de Transacciones)
    nct_base_url: Optional[str] = "http://localhost:5000"
    
    # Application
    debug: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()
