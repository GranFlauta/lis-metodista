"""
Dependencias comunes de autenticación y autorización para la API.
Implementa estrictamente PROMPT_FASE_1.md §5 y §6.2:
- require_auth: Valida Bearer JWT, comprueba sesión viva (latido, inactividad, tope),
  actualiza ultima_actividad y bloquea con 403 DEBE_CAMBIAR_PASSWORD salvo en whitelist.
- require_admin: Restringe el acceso exclusivamente a usuarios con rol ADMIN (403 PROHIBIDO).
"""

from __future__ import annotations

from typing import Any
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.clock import ahora
from app.core.database import get_db
from app.core.errors import (
    DebeCambiarPasswordError,
    ProhibidoError,
    SesionExpiradaError,
)
from app.core.security import decode_access_token, TokenExpiredError, TokenInvalidError
from app.models.session import LogSeguridad, Sesion
from app.models.user import Usuario
from app.services.session_policy import validar_sesion_vigente

# Rutas exentas de bloqueo cuando debe_cambiar_password = TRUE (§6.1)
WHITELIST_CAMBIO_PASSWORD = (
    "/api/auth/me",
    "/api/auth/cambiar-password",
    "/api/auth/logout",
    "/api/auth/heartbeat",
)


def obtener_ip_cliente(request: Request) -> str | None:
    """
    Obtiene la IP del cliente usando request.client.host o cabecera x-forwarded-for.
    Uvicorn (con --proxy-headers) resuelve automáticamente la IP del cliente enviada por Caddy.
    """
    ip_raw = None
    if request.client and request.client.host:
        ip_raw = request.client.host.strip()
    elif request.headers.get("x-forwarded-for"):
        ip_raw = request.headers.get("x-forwarded-for", "").strip()

    if not ip_raw:
        return None

    if "," in ip_raw:
        ip_raw = ip_raw.split(",")[0].strip()

    if ip_raw in ("testclient", "localhost", "::1"):
        return "127.0.0.1"

    try:
        import ipaddress
        ipaddress.ip_address(ip_raw)
        return ip_raw
    except ValueError:
        return None



def registrar_evento_seguridad(
    db: Session,
    accion: str,
    id_usuario: int | None = None,
    id_objetivo: int | None = None,
    ip: str | None = None,
    detalle: dict[str, Any] | None = None,
) -> None:
    """Inserta un registro auditable en la tabla log_seguridad."""
    evento = LogSeguridad(
        id_usuario=id_usuario,
        id_objetivo=id_objetivo,
        accion=accion,
        ip=ip,
        detalle=detalle,
        creado_en=ahora(),
    )
    db.add(evento)


def require_auth(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Dependencia de autenticación principal según PROMPT_FASE_1.md §6.2:
    1. Decodificar el Bearer; error -> 401 SESION_EXPIRADA.
    2. Cargar sesión por sid; verificar regla de sesión viva; si no vive -> 401 SESION_EXPIRADA.
    3. Cargar usuario; si activo = FALSE -> 401 SESION_EXPIRADA.
    4. La actividad humana se registra únicamente mediante heartbeat autenticado.
    5. Si debe_cambiar_password y la ruta no está en whitelist -> 403 DEBE_CAMBIAR_PASSWORD.
    """
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise SesionExpiradaError("Cabecera Authorization Bearer ausente o inválida.")

    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except (TokenExpiredError, TokenInvalidError):
        raise SesionExpiradaError("Token de acceso expirado o malformado.")

    user_id_str = payload.get("sub")
    session_id_str = payload.get("sid")

    if not user_id_str or not session_id_str:
        raise SesionExpiradaError("Claims de token incompletos (sub o sid ausentes).")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise SesionExpiradaError("Identificador de usuario corrupto.")

    now = ahora()
    ip_cliente = obtener_ip_cliente(request)

    # Serialize protected requests with refresh and logout for this session.
    sesion = (
        db.query(Sesion)
        .filter(Sesion.id_sesion == session_id_str)
        .with_for_update()
        .first()
    )
    if not sesion:
        raise SesionExpiradaError("Sesión no encontrada.")

    validar_sesion_vigente(db, sesion, ip_cliente, now)

    # 3. Cargar el usuario
    usuario = db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
    if not usuario or not usuario.activo:
        if sesion.revocada_en is None:
            sesion.revocada_en = now
            db.commit()
        raise SesionExpiradaError("Usuario inactivo o no encontrado.")

    # Browser activity signals are recorded only by the heartbeat endpoint.
    path = request.url.path

    # 5. Si debe_cambiar_password y la ruta no está en la lista blanca -> 403 DEBE_CAMBIAR_PASSWORD
    if usuario.debe_cambiar_password:
        if not any(path.startswith(permitida) for permitida in WHITELIST_CAMBIO_PASSWORD):
            raise DebeCambiarPasswordError("Debe cambiar su contraseña antes de acceder a esta función.")

    # Inyectar sesión activa en request.state para uso en endpoints (ej. cambiar-password o logout)
    request.state.sesion_actual = sesion
    return usuario


def require_admin(
    current_user: Usuario = Depends(require_auth),
) -> Usuario:
    """Garantiza que el usuario autenticado posea rol ADMIN."""
    rol_nombre = current_user.rol.nombre if current_user.rol else ""
    if rol_nombre != "ADMIN":
        raise ProhibidoError("Acceso restringido: Se requieren privilegios de Administrador.")
    return current_user


def require_bioquimico(
    current_user: Usuario = Depends(require_auth),
) -> Usuario:
    """Garantiza que el usuario autenticado posea rol BIOQUIMICO."""
    rol_nombre = current_user.rol.nombre if current_user.rol else ""
    if rol_nombre != "BIOQUIMICO":
        raise ProhibidoError("Acceso restringido: Se requieren privilegios de Bioquímico.")
    return current_user
