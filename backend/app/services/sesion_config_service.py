"""
Servicio para configuración dinámica de tiempos de sesión (D35-02 / T5).
Lee las 4 claves de laboratorio_config con caché en memoria de 15 segundos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.clock import ahora
from app.core.config import settings
from app.models.result import LaboratorioConfig

CLAVE_INTERVALO = "sesion_intervalo_latido_seg"
CLAVE_MUERTA = "sesion_muerta_tras_seg"
CLAVE_INACTIVIDAD = "sesion_inactividad_min"
CLAVE_TOPE = "sesion_tope_absoluto_horas"

CACHE_DURACION_SEGUNDOS = 15


@dataclass
class ConfigSesion:
    intervalo_latido_seg: int
    muerta_tras_seg: int
    inactividad_min: int
    tope_absoluto_horas: int

    def to_dict(self) -> dict[str, int]:
        return {
            "sesion_intervalo_latido_seg": self.intervalo_latido_seg,
            "sesion_muerta_tras_seg": self.muerta_tras_seg,
            "sesion_inactividad_min": self.inactividad_min,
            "sesion_tope_absoluto_horas": self.tope_absoluto_horas,
            "intervalo_latido_seg": self.intervalo_latido_seg,
            "muerta_tras_seg": self.muerta_tras_seg,
            "inactividad_min": self.inactividad_min,
            "tope_absoluto_horas": self.tope_absoluto_horas,
        }


_cache_config: ConfigSesion | None = None
_cache_timestamp: datetime | None = None


def invalidar_cache_config_sesion() -> None:
    """Invalida la caché en memoria de la configuración de sesión."""
    global _cache_config, _cache_timestamp
    _cache_config = None
    _cache_timestamp = None


def obtener_config_sesion(db: Session) -> ConfigSesion:
    """
    Obtiene la configuración de sesión vigente.
    Usa caché en memoria de 15 s basada en el reloj de la aplicación (ahora()).
    Si una clave no existe en la BD o su valor no es entero válido, usa el valor de settings.
    """
    global _cache_config, _cache_timestamp

    now = ahora()
    if _cache_config is not None and _cache_timestamp is not None:
        delta = (now - _cache_timestamp).total_seconds()
        if 0 <= delta < CACHE_DURACION_SEGUNDOS:
            return _cache_config

    filas = (
        db.query(LaboratorioConfig)
        .filter(LaboratorioConfig.clave.in_([
            CLAVE_INTERVALO,
            CLAVE_MUERTA,
            CLAVE_INACTIVIDAD,
            CLAVE_TOPE,
        ]))
        .all()
    )
    valores_bd = {f.clave: f.valor for f in filas}

    def _parse_int(clave: str, default: int) -> int:
        raw = valores_bd.get(clave)
        if raw is None:
            return default
        try:
            return int(str(raw).strip())
        except (ValueError, TypeError):
            return default

    intervalo = _parse_int(CLAVE_INTERVALO, settings.heartbeat_interval_seconds)
    muerta = _parse_int(CLAVE_MUERTA, settings.session_dead_after_seconds)
    inactividad = _parse_int(CLAVE_INACTIVIDAD, settings.idle_timeout_minutes)
    tope = _parse_int(CLAVE_TOPE, settings.absolute_session_hours)

    cfg = ConfigSesion(
        intervalo_latido_seg=intervalo,
        muerta_tras_seg=muerta,
        inactividad_min=inactividad,
        tope_absoluto_horas=tope,
    )
    _cache_config = cfg
    _cache_timestamp = now
    return cfg
