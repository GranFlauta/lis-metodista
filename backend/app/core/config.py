from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

settings = Settings()  # type: ignore[call-arg]
