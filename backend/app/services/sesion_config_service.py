"""Adaptador de la política de sesión configurada por variables de entorno."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings


@dataclass(frozen=True)
class ConfigSesion:
    intervalo_latido_seg: int
    inactividad_min: int | None
    tope_absoluto_horas: int
    modo_produccion: bool


def obtener_config_sesion(_db: Session | None = None) -> ConfigSesion:
    """Devuelve la política efectiva, sin leer configuraciones antiguas de la base."""
    return ConfigSesion(
        intervalo_latido_seg=settings.heartbeat_interval_seconds,
        inactividad_min=(
            settings.session_idle_timeout_minutes
            if settings.modo_produccion
            else None
        ),
        tope_absoluto_horas=settings.session_absolute_timeout_hours,
        modo_produccion=settings.modo_produccion,
    )
