# DEO GLORIA

# Configuración de la aplicación desde variables de entorno.

from typing import Optional

from pydantic_settings import BaseSettings


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
    # Puerto real del NCT (ver nct/.env del Pilar 2): PORT=8080
    nct_base_url: str = "http://nct:8080"

    # ------------------------------------------------------------------
    # Autoridad académica (ACADEMIC_SYSTEM)
    #
    # El backend firma EARN en nombre de la universidad. Esta clave
    # privada NUNCA debe loguearse ni exponerse en ninguna respuesta.
    # `academic_authority_public_key` DEBE coincidir exactamente con
    # AUTHORITY_PUBKEY configurado en el NCT (nct/.env) — si no coinciden,
    # todo EARN será rechazado con 400 "EARN sender_pubkey does not match
    # AUTHORITY_PUBKEY".
    # ------------------------------------------------------------------
    academic_authority_private_key: str = ""
    academic_authority_public_key: str = ""

    # ------------------------------------------------------------------
    # Auth — challenge firmado (Ed25519, sin password)
    #
    # El challenge es un timestamp del servidor, generado dinámicamente
    # en GET /auth/challenge y NUNCA persistido. Se considera válido si,
    # al recibirlo de vuelta firmado, cae dentro de esta ventana hacia
    # atrás respecto al "ahora" del servidor.
    # ------------------------------------------------------------------
    auth_challenge_window_seconds: int = 60

    # Application
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


# Create settings instance
settings = Settings()