"""
Endpoints de autenticación y gestión de sesiones para FastAPI (Fase 1).
Implementa estrictamente las directrices de docs/DECISIONES.md:
1. POST /api/auth/login: Validación con Argon2id, límite de intentos fallidos (5),
   bloqueo temporal (15 min), registro en log_seguridad y cookie refresh token segura.
2. POST /api/auth/heartbeat: Actualiza exclusivamente ultimo_latido de la sesión activa.
3. POST /api/auth/refresh: Renueva el Access Token validando límites (latido, inactividad, tope absoluto).
4. POST /api/auth/logout: Revoca la sesión activa y elimina la cookie de refresh token.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_token,
    verify_password,
    TokenExpiredError,
    TokenInvalidError,
)
from app.models.session import LogSeguridad, Sesion
from app.models.user import Rol, Usuario
from app.schemas.auth import LoginRequest, TokenResponse, UsuarioResponse

# -----------------------------------------------------------------------------
# Constantes y Enrutador
# -----------------------------------------------------------------------------

REFRESH_COOKIE_NAME = "refresh_token"
router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


# -----------------------------------------------------------------------------
# Funciones Auxiliares
# -----------------------------------------------------------------------------

def _obtener_ip_cliente(request: Request) -> str | None:
    """Extrae la dirección IP del cliente, considerando el proxy Caddy o balanceador."""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _to_utc(dt: datetime | None) -> datetime | None:
    """Normaliza fechas a UTC consciente de zona horaria."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _registrar_evento_seguridad(
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
        creado_en=datetime.now(timezone.utc),
    )
    db.add(evento)


# -----------------------------------------------------------------------------
# Endpoints de Autenticación
# -----------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión y crear sesión con latido",
    description="Valida credenciales, aplica control de intentos y emite access token y cookie de refresh token.",
)
def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    ip_cliente = _obtener_ip_cliente(request)
    user_agent = request.headers.get("user-agent")
    now = datetime.now(timezone.utc)

    # 1. Búsqueda insensible a mayúsculas/minúsculas
    usuario_db = (
        db.query(Usuario)
        .filter(func.lower(Usuario.usuario) == login_data.usuario.strip().lower())
        .first()
    )

    if not usuario_db:
        _registrar_evento_seguridad(
            db=db,
            accion="LOGIN_FALLIDO",
            id_usuario=None,
            id_objetivo=None,
            ip=ip_cliente,
            detalle={"usuario_intentado": login_data.usuario, "motivo": "Usuario no encontrado"},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Verificar cuenta activa (baja lógica según DECISIONES.md)
    if not usuario_db.activo:
        _registrar_evento_seguridad(
            db=db,
            accion="LOGIN_FALLIDO",
            id_usuario=usuario_db.id_usuario,
            id_objetivo=usuario_db.id_usuario,
            ip=ip_cliente,
            detalle={"motivo": "Cuenta inactiva o deshabilitada"},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cuenta de usuario deshabilitada.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Verificar bloqueo temporal por exceso de intentos fallidos
    bloqueado_hasta_utc = _to_utc(usuario_db.bloqueado_hasta)
    if bloqueado_hasta_utc and bloqueado_hasta_utc > now:
        minutos_restantes = max(1, int((bloqueado_hasta_utc - now).total_seconds() // 60) + 1)
        _registrar_evento_seguridad(
            db=db,
            accion="LOGIN_FALLIDO",
            id_usuario=usuario_db.id_usuario,
            id_objetivo=usuario_db.id_usuario,
            ip=ip_cliente,
            detalle={"motivo": f"Cuenta bloqueada hasta {bloqueado_hasta_utc.isoformat()}"},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Cuenta bloqueada temporalmente por demasiados intentos fallidos. Intente nuevamente en {minutos_restantes} minuto(s).",
        )

    # 4. Validar contraseña con Argon2id
    es_valida = verify_password(login_data.password, usuario_db.hash_password)

    if not es_valida:
        # Incrementar contador de intentos fallidos
        intentos_actuales = (usuario_db.intentos_fallidos or 0) + 1
        usuario_db.intentos_fallidos = intentos_actuales

        detalle_fallo: dict[str, Any] = {
            "intentos_fallidos": intentos_actuales,
            "max_intentos": settings.max_login_attempts,
        }

        if intentos_actuales >= settings.max_login_attempts:
            nuevo_bloqueo = now + timedelta(minutes=settings.lockout_minutes)
            usuario_db.bloqueado_hasta = nuevo_bloqueo
            detalle_fallo["bloqueado_hasta"] = nuevo_bloqueo.isoformat()
            detalle_fallo["motivo"] = f"Superado el umbral de intentos ({settings.max_login_attempts}). Bloqueo de {settings.lockout_minutes} min activado."
            mensaje_error = f"Credenciales incorrectas. Se ha bloqueado la cuenta por {settings.lockout_minutes} minutos debido a múltiples intentos fallidos."
        else:
            intentos_restantes = settings.max_login_attempts - intentos_actuales
            detalle_fallo["motivo"] = "Contraseña incorrecta"
            mensaje_error = f"Credenciales incorrectas. Le restan {intentos_restantes} intento(s) antes del bloqueo temporal."

        _registrar_evento_seguridad(
            db=db,
            accion="LOGIN_FALLIDO",
            id_usuario=usuario_db.id_usuario,
            id_objetivo=usuario_db.id_usuario,
            ip=ip_cliente,
            detalle=detalle_fallo,
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=mensaje_error,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 5. Éxito: restablecer intentos, actualizar último login y registrar evento
    usuario_db.intentos_fallidos = 0
    usuario_db.bloqueado_hasta = None
    usuario_db.ultimo_login = now

    _registrar_evento_seguridad(
        db=db,
        accion="LOGIN_OK",
        id_usuario=usuario_db.id_usuario,
        id_objetivo=usuario_db.id_usuario,
        ip=ip_cliente,
        detalle={"user_agent": user_agent},
    )

    # 6. Crear sesión persistente con latido y tope absoluto (12 h)
    raw_refresh_token, refresh_hash = generate_refresh_token()
    expira_en_tope = now + timedelta(hours=settings.absolute_session_hours)

    nueva_sesion = Sesion(
        id_usuario=usuario_db.id_usuario,
        refresh_hash=refresh_hash,
        ip=ip_cliente,
        user_agent=user_agent,
        creada_en=now,
        ultimo_latido=now,
        ultima_actividad=now,
        expira_en=expira_en_tope,
        revocada_en=None,
    )
    db.add(nueva_sesion)
    db.commit()
    db.refresh(nueva_sesion)
    db.refresh(usuario_db)

    # 7. Crear access token JWT
    nombre_rol = (
        usuario_db.rol.nombre
        if hasattr(usuario_db, "rol") and hasattr(usuario_db.rol, "nombre")
        else "BIOQUIMICO"
    )
    token_claims = {
        "sub": str(usuario_db.id_usuario),
        "rol": nombre_rol,
        "sid": str(nueva_sesion.id_sesion),
    }
    access_token = create_access_token(data=token_claims)

    # 8. Configurar cookie segura del refresh token (DECISIONES.md §6)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
        max_age=settings.absolute_session_hours * 3600,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_minutes * 60,
        debe_cambiar_password=usuario_db.debe_cambiar_password,
        usuario=UsuarioResponse.model_validate(usuario_db),
    )


@router.post(
    "/heartbeat",
    summary="Registrar latido de la sesión activa",
    description="Actualiza de forma exclusiva el campo 'ultimo_latido' para evitar el vencimiento por abandono de pestaña.",
)
def heartbeat(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    sesion: Sesion | None = None

    # Identificar la sesión mediante la cookie de refresh token
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        h = hash_token(raw_refresh)
        sesion = (
            db.query(Sesion)
            .filter(Sesion.refresh_hash == h, Sesion.revocada_en.is_(None))
            .first()
        )

    # Alternativa: verificar si se proporcionó Bearer token con sid
    if not sesion:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                payload = decode_access_token(token)
                sid = payload.get("sid")
                if sid:
                    sesion = (
                        db.query(Sesion)
                        .filter(Sesion.id_sesion == sid, Sesion.revocada_en.is_(None))
                        .first()
                    )
            except (TokenExpiredError, TokenInvalidError):
                pass

    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no encontrada o ya revocada.",
        )

    # Verificar si superó el tope absoluto de la sesión
    expira_en_utc = _to_utc(sesion.expira_en)
    if expira_en_utc and expira_en_utc < now:
        sesion.revocada_en = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión ha expirado por superar el tope de tiempo absoluto.",
        )

    # Actualizar EXCLUSIVAMENTE el último latido (la pestaña sigue abierta)
    sesion.ultimo_latido = now
    db.commit()

    return {"status": "ok", "message": "Latido registrado exitosamente."}


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar token de acceso con refresh token",
    description="Valida ausencia de latido (150 s), inactividad (30 min) y tope absoluto (12 h) antes de emitir un nuevo access token.",
)
def refresh_session(
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    ip_cliente = _obtener_ip_cliente(request)
    now = datetime.now(timezone.utc)

    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se encontró la cookie de refresh token.",
        )

    refresh_hash = hash_token(raw_refresh)
    sesion = (
        db.query(Sesion)
        .filter(Sesion.refresh_hash == refresh_hash)
        .first()
    )

    if not sesion or sesion.revocada_en is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no válida o revocada.",
        )

    # 1. Validar tope absoluto de 12 horas
    expira_en_utc = _to_utc(sesion.expira_en)
    if expira_en_utc and expira_en_utc < now:
        sesion.revocada_en = now
        _registrar_evento_seguridad(
            db=db,
            accion="SESION_EXPIRADA",
            id_usuario=sesion.id_usuario,
            id_objetivo=sesion.id_usuario,
            ip=ip_cliente,
            detalle={"motivo": "Tope absoluto de sesión alcanzado."},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión ha expirado por límite de tiempo absoluto.",
        )

    # 2. Validar ausencia de latido (150 segundos según config.session_dead_after_seconds)
    latido_utc = _to_utc(sesion.ultimo_latido)
    if latido_utc:
        segundos_sin_latido = (now - latido_utc).total_seconds()
        if segundos_sin_latido > settings.session_dead_after_seconds:
            sesion.revocada_en = now
            _registrar_evento_seguridad(
                db=db,
                accion="SESION_EXPIRADA",
                id_usuario=sesion.id_usuario,
                id_objetivo=sesion.id_usuario,
                ip=ip_cliente,
                detalle={"motivo": f"Sin latido durante {int(segundos_sin_latido)}s (umbral {settings.session_dead_after_seconds}s)."},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión expirada por desconexión o cierre de navegador.",
            )

    # 3. Validar timeout por inactividad del usuario (30 minutos según config.idle_timeout_minutes)
    actividad_utc = _to_utc(sesion.ultima_actividad)
    if actividad_utc:
        segundos_inactivo = (now - actividad_utc).total_seconds()
        if segundos_inactivo > (settings.idle_timeout_minutes * 60):
            sesion.revocada_en = now
            _registrar_evento_seguridad(
                db=db,
                accion="SESION_EXPIRADA",
                id_usuario=sesion.id_usuario,
                id_objetivo=sesion.id_usuario,
                ip=ip_cliente,
                detalle={"motivo": f"Inactividad de {int(segundos_inactivo // 60)}m (umbral {settings.idle_timeout_minutes}m)."},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión expirada por inactividad prolongada.",
            )

    # 4. Validar estado del usuario
    usuario = db.query(Usuario).filter(Usuario.id_usuario == sesion.id_usuario).first()
    if not usuario or not usuario.activo:
        sesion.revocada_en = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o no encontrado.",
        )

    # 5. La reactivación mediante refresh actualiza la actividad y latido del usuario
    sesion.ultima_actividad = now
    sesion.ultimo_latido = now
    db.commit()

    # 6. Generar nuevo Access Token
    nombre_rol = (
        usuario.rol.nombre
        if hasattr(usuario, "rol") and hasattr(usuario.rol, "nombre")
        else "BIOQUIMICO"
    )
    token_claims = {
        "sub": str(usuario.id_usuario),
        "rol": nombre_rol,
        "sid": str(sesion.id_sesion),
    }
    nuevo_access_token = create_access_token(data=token_claims)

    return TokenResponse(
        access_token=nuevo_access_token,
        token_type="bearer",
        expires_in=settings.access_token_minutes * 60,
        debe_cambiar_password=usuario.debe_cambiar_password,
        usuario=UsuarioResponse.model_validate(usuario),
    )


@router.post(
    "/logout",
    summary="Cerrar y revocar sesión activa",
    description="Revoca la sesión en la base de datos, registra el evento LOGOUT y limpia la cookie del refresh token.",
)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    ip_cliente = _obtener_ip_cliente(request)
    now = datetime.now(timezone.utc)
    sesion: Sesion | None = None

    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        h = hash_token(raw_refresh)
        sesion = (
            db.query(Sesion)
            .filter(Sesion.refresh_hash == h, Sesion.revocada_en.is_(None))
            .first()
        )

    if not sesion:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                payload = decode_access_token(token)
                sid = payload.get("sid")
                if sid:
                    sesion = (
                        db.query(Sesion)
                        .filter(Sesion.id_sesion == sid, Sesion.revocada_en.is_(None))
                        .first()
                    )
            except (TokenExpiredError, TokenInvalidError):
                pass

    if sesion:
        sesion.revocada_en = now
        _registrar_evento_seguridad(
            db=db,
            accion="LOGOUT",
            id_usuario=sesion.id_usuario,
            id_objetivo=sesion.id_usuario,
            ip=ip_cliente,
            detalle={"motivo": "Cierre voluntario de sesión por el usuario"},
        )
        db.commit()

    # Eliminar cookie de refresh token en el cliente
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )

    return {"status": "ok", "message": "Sesión cerrada exitosamente."}
