"""
Endpoints de autenticación y gestión de sesiones para FastAPI (Fase 1).
Implementa estrictamente PROMPT_FASE_1.md §5 y §6.2:
- POST /api/auth/login: Normalización, dummy hash para igualar tiempos, 423 CUENTA_BLOQUEADA,
  401 CREDENCIALES_INVALIDAS, emisión de JWT y cookie refresh (Path=/api/auth).
- POST /api/auth/refresh: Validación de cabecera X-LIS-Client: web, comprobación de sesión viva.
- POST /api/auth/heartbeat: 204 No Content, actualiza exclusivamente ultimo_latido.
- POST /api/auth/logout: 204 No Content, cabecera X-LIS-Client, revocación y borrado de cookie.
- GET /api/auth/me: 200 con datos del usuario autenticado.
- POST /api/auth/cambiar-password: 204 No Content, valida clave actual, valida política clínica (422),
  revoca las demás sesiones del usuario y actualiza estado.
"""

from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import (
    obtener_ip_cliente,
    registrar_evento_seguridad,
    require_auth,
)
from app.core.clock import ahora
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import (
    CredencialesInvalidasError,
    CuentaBloqueadaError,
    PasswordDebilError,
    SesionExpiradaError,
    ValidacionError,
)
from app.core.security import (
    check_password_policy,
    create_access_token,
    generate_refresh_token,
    get_password_hash,
    hash_token,
    verify_dummy_password,
    verify_password,
)
from app.models.session import Sesion
from app.models.user import Usuario
from app.schemas.auth import (
    CambiarPasswordRequest,
    LoginRequest,
    MeResponse,
    TokenResponse,
    UsuarioResumenResponse,
)

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión (Login)",
    description="Valida credenciales, aplica bloqueo temporal y emite tokens.",
)
def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    ip_cliente = obtener_ip_cliente(request)
    now = ahora()

    # 1. Normalizar usuario a minúsculas y sin espacios (§6.2)
    usuario_normalizado = login_data.usuario.strip().lower()

    # 2. Buscar usuario. Si no existe: ejecutar verificación dummy y responder 401
    usuario_db = (
        db.query(Usuario)
        .filter(func.lower(Usuario.usuario) == usuario_normalizado)
        .first()
    )

    if not usuario_db:
        verify_dummy_password(login_data.password)
        registrar_evento_seguridad(
            db=db,
            accion="LOGIN_FALLIDO",
            id_usuario=None,
            id_objetivo=None,
            ip=ip_cliente,
            detalle={"usuario_intentado": login_data.usuario},
        )
        db.commit()
        raise CredencialesInvalidasError()

    # 3. Si existe y bloqueado_hasta > ahora -> 423 CUENTA_BLOQUEADA (sin verificar clave)
    bloqueado_hasta = usuario_db.bloqueado_hasta
    if bloqueado_hasta:
        bloqueado_tz = bloqueado_hasta.replace(tzinfo=now.tzinfo) if bloqueado_hasta.tzinfo is None else bloqueado_hasta
        if bloqueado_tz > now:
            minutos_restantes = math.ceil((bloqueado_tz - now).total_seconds() / 60)
            registrar_evento_seguridad(
                db=db,
                accion="LOGIN_FALLIDO",
                id_usuario=usuario_db.id_usuario,
                id_objetivo=usuario_db.id_usuario,
                ip=ip_cliente,
                detalle={"motivo": f"Cuenta bloqueada hasta {bloqueado_tz.isoformat()}"},
            )
            db.commit()
            raise CuentaBloqueadaError(minutos_restantes=max(1, minutos_restantes))

    # 4. Si activo = FALSE -> 401 CREDENCIALES_INVALIDAS (mismo mensaje §6.1)
    if not usuario_db.activo:
        verify_dummy_password(login_data.password)
        registrar_evento_seguridad(
            db=db,
            accion="LOGIN_FALLIDO",
            id_usuario=usuario_db.id_usuario,
            id_objetivo=usuario_db.id_usuario,
            ip=ip_cliente,
            detalle={"motivo": "Usuario inactivo"},
        )
        db.commit()
        raise CredencialesInvalidasError()

    # 5. Verificar clave con Argon2id
    es_valida = verify_password(login_data.password, usuario_db.hash_password)

    if not es_valida:
        intentos = (usuario_db.intentos_fallidos or 0) + 1
        if intentos >= settings.max_login_attempts:
            usuario_db.bloqueado_hasta = now + timedelta(minutes=settings.lockout_minutes)
            usuario_db.intentos_fallidos = 0
            detalle = {
                "motivo": f"Máximo de intentos alcanzado ({settings.max_login_attempts}). Bloqueo de {settings.lockout_minutes} min.",
                "bloqueado_hasta": usuario_db.bloqueado_hasta.isoformat(),
            }
        else:
            usuario_db.intentos_fallidos = intentos
            detalle = {"intentos_fallidos": intentos}

        registrar_evento_seguridad(
            db=db,
            accion="LOGIN_FALLIDO",
            id_usuario=usuario_db.id_usuario,
            id_objetivo=usuario_db.id_usuario,
            ip=ip_cliente,
            detalle=detalle,
        )
        db.commit()
        raise CredencialesInvalidasError()

    # 6. Clave correcta
    usuario_db.intentos_fallidos = 0
    usuario_db.bloqueado_hasta = None
    usuario_db.ultimo_login = now

    registrar_evento_seguridad(
        db=db,
        accion="LOGIN_OK",
        id_usuario=usuario_db.id_usuario,
        id_objetivo=usuario_db.id_usuario,
        ip=ip_cliente,
        detalle={"user_agent": request.headers.get("user-agent")},
    )

    # Crear fila en sesiones (expira_en = ahora + ABSOLUTE_SESSION_HOURS)
    raw_refresh_token, refresh_hash = generate_refresh_token()
    expira_en = now + timedelta(hours=settings.absolute_session_hours)

    sesion = Sesion(
        id_usuario=usuario_db.id_usuario,
        refresh_hash=refresh_hash,
        ip=ip_cliente,
        user_agent=request.headers.get("user-agent"),
        creada_en=now,
        ultimo_latido=now,
        ultima_actividad=now,
        expira_en=expira_en,
        revocada_en=None,
    )
    db.add(sesion)
    db.commit()
    db.refresh(sesion)
    db.refresh(usuario_db)

    # Emitir access token con claims requeridos: sub, sid, rol, iat, exp, typ="access"
    rol_nombre = usuario_db.rol.nombre if usuario_db.rol else "BIOQUIMICO"
    access_token = create_access_token(
        subject=str(usuario_db.id_usuario),
        session_id=str(sesion.id_sesion),
        role=rol_nombre,
    )

    # Cookie refresh (§5): httpOnly, Secure, SameSite=Strict, Path=/api/auth, sin Max-Age
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )

    usuario_resumen = UsuarioResumenResponse(
        id_usuario=usuario_db.id_usuario,
        usuario=usuario_db.usuario,
        nombres=usuario_db.nombres,
        apellido_paterno=usuario_db.apellido_paterno,
        apellido_materno=usuario_db.apellido_materno,
        rol=rol_nombre,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_minutes * 60,
        debe_cambiar_password=usuario_db.debe_cambiar_password,
        usuario=usuario_resumen,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar Access Token",
    description="Exige cabecera X-LIS-Client: web y cookie refresh token válida.",
)
def refresh_token(
    request: Request,
    response: Response,
    x_lis_client: str | None = Header(default=None, alias="X-LIS-Client"),
    db: Session = Depends(get_db),
) -> TokenResponse:
    # CSRF check (§5 y §6.1)
    if x_lis_client != "web":
        raise ValidacionError("Cabecera X-LIS-Client: web requerida.")

    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise SesionExpiradaError("Cookie de refresh token ausente.")

    now = ahora()
    ip_cliente = obtener_ip_cliente(request)
    ref_hash = hash_token(raw_refresh)

    sesion = db.query(Sesion).filter(Sesion.refresh_hash == ref_hash).first()

    # Validar sesión viva (§5)
    esta_viva = True
    if not sesion or sesion.revocada_en is not None:
        esta_viva = False
    elif sesion.expira_en and (sesion.expira_en.replace(tzinfo=now.tzinfo) if sesion.expira_en.tzinfo is None else sesion.expira_en) <= now:
        esta_viva = False
    else:
        if settings.session_dead_after_seconds > 0:
            ultimo_latido_tz = sesion.ultimo_latido.replace(tzinfo=now.tzinfo) if sesion.ultimo_latido.tzinfo is None else sesion.ultimo_latido
            if (now - ultimo_latido_tz).total_seconds() > settings.session_dead_after_seconds:
                esta_viva = False
        if esta_viva and settings.idle_timeout_minutes > 0:
            ultima_act_tz = sesion.ultima_actividad.replace(tzinfo=now.tzinfo) if sesion.ultima_actividad.tzinfo is None else sesion.ultima_actividad
            if (now - ultima_act_tz).total_seconds() > (settings.idle_timeout_minutes * 60):
                esta_viva = False

    if not esta_viva:
        if sesion and sesion.revocada_en is None:
            sesion.revocada_en = now
            registrar_evento_seguridad(
                db=db,
                accion="SESION_EXPIRADA",
                id_usuario=sesion.id_usuario,
                id_objetivo=sesion.id_usuario,
                ip=ip_cliente,
                detalle={"motivo": "Refresh sobre sesión no viva."},
            )
            db.commit()

        # Limpiar cookie ante sesión expirada (§6.2)
        response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        delete_header = 'refresh_token=""; Path=/api/auth; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT'
        raise SesionExpiradaError("La sesión ha expirado.", headers={"Set-Cookie": delete_header})

    usuario = db.query(Usuario).filter(Usuario.id_usuario == sesion.id_usuario).first()
    if not usuario or not usuario.activo:
        sesion.revocada_en = now
        db.commit()
        response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        delete_header = 'refresh_token=""; Path=/api/auth; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT'
        raise SesionExpiradaError("Usuario inactivo.", headers={"Set-Cookie": delete_header})

    # La reactivación renueva la actividad
    sesion.ultima_actividad = now
    db.commit()

    rol_nombre = usuario.rol.nombre if usuario.rol else "BIOQUIMICO"
    nuevo_access_token = create_access_token(
        subject=str(usuario.id_usuario),
        session_id=str(sesion.id_sesion),
        role=rol_nombre,
    )

    usuario_resumen = UsuarioResumenResponse(
        id_usuario=usuario.id_usuario,
        usuario=usuario.usuario,
        nombres=usuario.nombres,
        apellido_paterno=usuario.apellido_paterno,
        apellido_materno=usuario.apellido_materno,
        rol=rol_nombre,
    )

    return TokenResponse(
        access_token=nuevo_access_token,
        token_type="bearer",
        expires_in=settings.access_token_minutes * 60,
        debe_cambiar_password=usuario.debe_cambiar_password,
        usuario=usuario_resumen,
    )


@router.post(
    "/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Registrar latido (Heartbeat)",
    description="Actualiza solo ultimo_latido de la sesión. Responde 204 No Content.",
)
def heartbeat(
    request: Request,
    current_user: Usuario = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    # require_auth ya validó token y sesión viva
    sesion: Sesion | None = getattr(request.state, "sesion_actual", None)
    if sesion:
        sesion.ultimo_latido = ahora()
        db.commit()


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión (Logout)",
    description="Revoca la sesión activa y borra la cookie refresh. Idempotente (204).",
)
def logout(
    request: Request,
    response: Response,
    x_lis_client: str | None = Header(default=None, alias="X-LIS-Client"),
    db: Session = Depends(get_db),
) -> None:
    if x_lis_client != "web":
        raise ValidacionError("Cabecera X-LIS-Client: web requerida.")

    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        ref_hash = hash_token(raw_refresh)
        sesion = (
            db.query(Sesion)
            .filter(Sesion.refresh_hash == ref_hash, Sesion.revocada_en.is_(None))
            .first()
        )
        if sesion:
            now = ahora()
            sesion.revocada_en = now
            registrar_evento_seguridad(
                db=db,
                accion="LOGOUT",
                id_usuario=sesion.id_usuario,
                id_objetivo=sesion.id_usuario,
                ip=obtener_ip_cliente(request),
            )
            db.commit()

    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Consultar usuario autenticado (/me)",
    description="Retorna el perfil del usuario activo en la sesión actual.",
)
def get_me(
    current_user: Usuario = Depends(require_auth),
) -> MeResponse:
    rol_nombre = current_user.rol.nombre if current_user.rol else "BIOQUIMICO"
    return MeResponse(
        id_usuario=current_user.id_usuario,
        usuario=current_user.usuario,
        nombres=current_user.nombres,
        apellido_paterno=current_user.apellido_paterno,
        apellido_materno=current_user.apellido_materno,
        rol=rol_nombre,
        debe_cambiar_password=current_user.debe_cambiar_password,
    )


@router.post(
    "/cambiar-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cambio de contraseña (obligatorio o voluntario)",
    description="Valida clave actual, política clínica (422), desactiva flag y revoca otras sesiones.",
)
def cambiar_password(
    body: CambiarPasswordRequest,
    request: Request,
    current_user: Usuario = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    ip_cliente = obtener_ip_cliente(request)
    now = ahora()

    # 1. Validar clave actual
    if not verify_password(body.password_actual, current_user.hash_password):
        raise ValidacionError("La contraseña actual es incorrecta.")

    # 2. Validar política clínica sobre la nueva contraseña (§5, §6.4)
    es_valida, error_msg = check_password_policy(
        new_password=body.password_nueva,
        username=current_user.usuario,
        ci=current_user.ci,
        current_password=body.password_actual,
        current_password_hash=current_user.hash_password,
    )
    if not es_valida:
        raise PasswordDebilError(error_msg or "La nueva contraseña no cumple con la política de seguridad.")

    # 3. Actualizar contraseña y quitar flag
    current_user.hash_password = get_password_hash(body.password_nueva)
    current_user.debe_cambiar_password = False

    # 4. Revocar las DEMÁS sesiones del usuario, manteniendo viva la actual (§6.2)
    sesion_actual: Sesion | None = getattr(request.state, "sesion_actual", None)
    id_sesion_actual = sesion_actual.id_sesion if sesion_actual else None

    sesiones_a_revocar = db.query(Sesion).filter(
        Sesion.id_usuario == current_user.id_usuario,
        Sesion.revocada_en.is_(None),
    )
    if id_sesion_actual:
        sesiones_a_revocar = sesiones_a_revocar.filter(Sesion.id_sesion != id_sesion_actual)

    sesiones_a_revocar.update({"revocada_en": now}, synchronize_session=False)

    # 5. Registrar evento CAMBIO_PASSWORD
    registrar_evento_seguridad(
        db=db,
        accion="CAMBIO_PASSWORD",
        id_usuario=current_user.id_usuario,
        id_objetivo=current_user.id_usuario,
        ip=ip_cliente,
        detalle={"motivo": "Cambio de contraseña exitoso"},
    )
    db.commit()
