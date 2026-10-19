from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "backend/.env", "../.env"), extra="ignore")

    database_url: str
    jwt_secret: str
    heartbeat_interval_seconds: int = 30
    session_dead_after_seconds: int = 150      # sin latidos => sesión muerta (pestaña cerrada / PC apagada)
    idle_timeout_minutes: int = 30             # sin actividad del usuario
    absolute_session_hours: int = 12           # tope duro

    access_token_minutes: int = 10
    max_login_attempts: int = 5
    lockout_minutes: int = 15
    cookie_secure: bool = True                  # Cambiar a false si estás en desarrollo local sin HTTPS
    enable_docs: bool = False                   # D35-01: /docs y /openapi.json solo si es true
    modo_demo: bool = False                     # Habilita /docs, CORS y SPA para presentaciones por ngrok
    sesion_indefinida: bool = False             # Si es true, la sesión no expira por inactividad ni falta de latidos

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> Settings:
        if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("CAMBIAR"):
            raise ValueError(
                "JWT_SECRET inválido: debe tener al menos 32 caracteres y no comenzar con 'CAMBIAR'."
            )
        return self

settings = Settings()  # type: ignore[call-arg]


def es_modo_demo() -> bool:
    """Indica si el modo demo o de sesión indefinida está activo fuera de pruebas unitarias."""
    import sys
    en_pruebas = "unittest" in sys.modules or "pytest" in sys.modules
    return bool((settings.modo_demo or settings.sesion_indefinida) and not en_pruebas)

