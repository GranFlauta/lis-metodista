"""Política central de expiración y actividad de sesiones."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from app.core.clock import ahora
from app.core.config import settings
from app.core.errors import SesionExpiradaError
from app.models.session import LogSeguridad, Sesion


MIN_INTERVALO_ACTIVIDAD_SEGUNDOS = 1


def _fecha_compatible(fecha: datetime, referencia: datetime) -> datetime:
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=referencia.tzinfo)
    return fecha


def motivo_expiracion(sesion: Sesion, now: datetime | None = None) -> str | None:
    """Evalúa revocación, tope absoluto e inactividad según una única política."""
    instante = now or ahora()
    if sesion.revocada_en is not None:
        return "Sesión revocada previamente."

    expira_en = _fecha_compatible(sesion.expira_en, instante)
    if expira_en <= instante:
        return "Tope absoluto de sesión alcanzado."

    if settings.modo_produccion:
        ultima_actividad = _fecha_compatible(sesion.ultima_actividad, instante)
        limite = timedelta(minutes=settings.session_idle_timeout_minutes)
        if instante - ultima_actividad >= limite:
            return f"Inactividad mayor o igual a {settings.session_idle_timeout_minutes} minutos."

    return None


def validar_sesion_vigente(
    db: DbSession,
    sesion: Sesion,
    ip: str | None,
    now: datetime | None = None,
) -> None:
    instante = now or ahora()
    motivo = motivo_expiracion(sesion, instante)
    if motivo is None:
        return

    if sesion.revocada_en is None:
        sesion.revocada_en = instante
        db.add(
            LogSeguridad(
                id_usuario=sesion.id_usuario,
                id_objetivo=sesion.id_usuario,
                accion="SESION_EXPIRADA",
                ip=ip,
                detalle={"motivo": motivo},
                creado_en=instante,
            )
        )
        db.commit()

    raise SesionExpiradaError("La sesión ha expirado o ha sido revocada.")


def registrar_actividad_humana(sesion: Sesion, now: datetime | None = None) -> bool:
    """Registra señales autenticadas de actividad con un intervalo mínimo entre escrituras."""
    instante = now or ahora()
    ultima_actividad = _fecha_compatible(sesion.ultima_actividad, instante)
    if instante - ultima_actividad < timedelta(seconds=MIN_INTERVALO_ACTIVIDAD_SEGUNDOS):
        return False
    sesion.ultima_actividad = instante
    return True
