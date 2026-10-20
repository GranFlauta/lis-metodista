from __future__ import annotations

from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raíz del proyecto: backend/app/core/config.py → sube 3 niveles
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(_PROJECT_ROOT / ".env"),       # raíz del proyecto (producción/dev)
            str(_PROJECT_ROOT / "backend/.env"), # alternativa en backend/
            ".env",                             # fallback relativo al CWD
        ),
        extra="ignore",
    )

    database_url: str
    jwt_secret: str
    heartbeat_interval_seconds: int = 30
    session_dead_after_seconds: int = 86400000 # Pruebas: indefinido (~1000 días)
    idle_timeout_minutes: int = 525600         # Pruebas: indefinido (1 año)
    absolute_session_hours: int = 87600        # Pruebas: indefinido (10 años)

    access_token_minutes: int = 525600         # Pruebas: indefinido (1 año)
    max_login_attempts: int = 5
    lockout_minutes: int = 15
    cookie_secure: bool = False                # False para desarrollo local sin HTTPS

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> Settings:
        if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("CAMBIAR"):
            raise ValueError(
                "JWT_SECRET inválido: debe tener al menos 32 caracteres y no comenzar con 'CAMBIAR'."
            )
        return self

settings = Settings()  # type: ignore[call-arg]

