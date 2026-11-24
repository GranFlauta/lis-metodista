from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "backend/.env", "../.env"), extra="ignore")

    database_url: str
    jwt_secret: str
    heartbeat_interval_seconds: int = 30
    access_token_minutes: int = 10
    modo_produccion: bool = False
    session_idle_timeout_minutes: int = 60
    session_absolute_timeout_hours: int = 24
    max_login_attempts: int = 5
    lockout_minutes: int = 15
    cookie_secure: bool = False
    enable_docs: bool = False

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> Settings:
        if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("CAMBIAR"):
            raise ValueError(
                "JWT_SECRET inválido: debe tener al menos 32 caracteres y no comenzar con 'CAMBIAR'."
            )
        if not 1 <= self.session_idle_timeout_minutes <= 480:
            raise ValueError("SESSION_IDLE_TIMEOUT_MINUTES debe estar entre 1 y 480.")
        if not 1 <= self.session_absolute_timeout_hours <= 24:
            raise ValueError("SESSION_ABSOLUTE_TIMEOUT_HOURS debe estar entre 1 y 24.")
        if self.modo_produccion and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE debe ser true cuando MODO_PRODUCCION=true.")
        return self

settings = Settings()  # type: ignore[call-arg]

