"""
Endpoints administrativos para la gestión de usuarios (Fase 1).
Implementa estrictamente las directrices de docs/DECISIONES.md:
1. POST /api/users: Crear usuario (exclusivo ADMIN). Genera contraseña temporal
   aleatoria de 14 caracteres, debe_cambiar_password=TRUE, hash Argon2id,
   evento 'USUARIO_CREADO' en log_seguridad y retorna la contraseña en texto plano una sola vez.
2. POST /api/users/{id_usuario}/reset-password: Reset de contraseña por el admin. Mismo
   comportamiento, revoca sesiones previas y registra evento 'RESET_PASSWORD_ADMIN'.
3. DELETE /api/users/{id_usuario} (y POST /api/users/{id_usuario}/desactivar): Baja lógica
   obligatoria (activo=FALSE), prohibiendo de forma taxativa cualquier DELETE físico.
   Revoca sesiones activas y registra 'USUARIO_DESACTIVADO'.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    decode_access_token,
    generate_temporary_password,
    get_password_hash,
    TokenExpiredError,
    TokenInvalidError,
)
from app.models.session import LogSeguridad, Sesion
from app.models.user import Rol, Usuario
from app.schemas.auth import UsuarioAdminResponse, UsuarioResponse

# -----------------------------------------------------------------------------
# Enrutador y Esquemas de Petición
# -----------------------------------------------------------------------------

router = APIRouter(prefix="/api/users", tags=["Usuarios"])


class UsuarioCreateRequest(BaseModel):
    """Esquema de entrada para el registro de nuevos usuarios."""
    model_config = ConfigDict(str_strip_whitespace=True)

    usuario: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Nombre de usuario o login único.",
        examples=["mlopez"],
    )
    ci: str = Field(
        ...,
        min_length=4,
        max_length=30,
        description="Cédula de identidad única del usuario.",
        examples=["4567891-LP"],
    )
    nombres: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Nombres del profesional o usuario.",
    )
    apellido_paterno: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Primer apellido.",
    )
    apellido_materno: str | None = Field(
        default=None,
        max_length=100,
        description="Segundo apellido (opcional).",
    )
    correo: str | None = Field(
        default=None,
        max_length=255,
        description="Correo electrónico institucional (opcional).",
    )
    matricula_profesional: str | None = Field(
        default=None,
        max_length=50,
        description="Matrícula profesional para firma de informes clínicos.",
    )
    rol: str = Field(
        default="BIOQUIMICO",
        description="Rol del usuario en el sistema: ADMIN o BIOQUIMICO.",
        examples=["BIOQUIMICO"],
    )


# -----------------------------------------------------------------------------
# Funciones Auxiliares y Control de Acceso (RBAC)
# -----------------------------------------------------------------------------

def _obtener_ip_cliente(request: Request) -> str | None:
    """Extrae la IP real del cliente considerando proxies inversos."""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _registrar_evento_seguridad(
    db: Session,
    accion: str,
    id_usuario: int | None = None,
    id_objetivo: int | None = None,
    ip: str | None = None,
    detalle: dict[str, Any] | None = None,
) -> None:
    """Inserta un registro de auditoría en la tabla log_seguridad."""
    evento = LogSeguridad(
        id_usuario=id_usuario,
        id_objetivo=id_objetivo,
        accion=accion,
        ip=ip,
        detalle=detalle,
        creado_en=datetime.now(timezone.utc),
    )
    db.add(evento)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Dependencia que extrae y valida el usuario activo a partir del token JWT Bearer.
    """
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado. Token de acceso requerido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de acceso ha expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except TokenInvalidError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no contiene identificador de usuario.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador de usuario corrupto en el token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
    if not user or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o cuenta desactivada.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """
    Garantiza que el usuario autenticado posea el rol de Administrador.
    docs/DECISIONES.md §6: Solo ADMIN puede realizar CRUD de usuarios y reset de claves.
    """
    rol_nombre = current_user.rol.nombre if current_user.rol else ""
    if rol_nombre != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: Esta acción requiere privilegios de Administrador.",
        )
    return current_user


# -----------------------------------------------------------------------------
# Endpoints Administrativos
# -----------------------------------------------------------------------------

@router.post(
    "",
    response_model=UsuarioAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario nuevo (Exclusivo ADMIN)",
    description="Crea un usuario, genera contraseña temporal de 14 caracteres, establece debe_cambiar_password=TRUE y registra USUARIO_CREADO.",
)
def create_user(
    user_in: UsuarioCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> UsuarioAdminResponse:
    ip_cliente = _obtener_ip_cliente(request)

    # 1. Validar unicidad del login
    usuario_existente = (
        db.query(Usuario)
        .filter(func.lower(Usuario.usuario) == user_in.usuario.strip().lower())
        .first()
    )
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario ya se encuentra registrado.",
        )

    # 2. Validar unicidad de CI
    ci_existente = (
        db.query(Usuario)
        .filter(func.lower(Usuario.ci) == user_in.ci.strip().lower())
        .first()
    )
    if ci_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El número de documento de identidad (CI) ya está registrado.",
        )

    # 3. Validar correo si se proporciona
    if user_in.correo:
        correo_existente = (
            db.query(Usuario)
            .filter(func.lower(Usuario.correo) == user_in.correo.strip().lower())
            .first()
        )
        if correo_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo electrónico ya se encuentra registrado.",
            )

    # 4. Validar rol solicitado
    rol_db = (
        db.query(Rol)
        .filter(func.upper(Rol.nombre) == user_in.rol.strip().upper())
        .first()
    )
    if not rol_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El rol '{user_in.rol}' no es válido. Roles disponibles: ADMIN, BIOQUIMICO.",
        )

    # 5. Generar contraseña temporal segura de exactamente 14 caracteres aleatorios
    temp_password = generate_temporary_password(
        length=14,
        username=user_in.usuario,
        ci=user_in.ci,
    )
    hash_password = get_password_hash(temp_password)

    # 6. Crear instancia del usuario (debe_cambiar_password = TRUE)
    nuevo_usuario = Usuario(
        id_rol=rol_db.id_rol,
        usuario=user_in.usuario.strip(),
        ci=user_in.ci.strip(),
        nombres=user_in.nombres.strip(),
        apellido_paterno=user_in.apellido_paterno.strip(),
        apellido_materno=user_in.apellido_materno.strip() if user_in.apellido_materno else None,
        correo=user_in.correo.strip() if user_in.correo else None,
        matricula_profesional=(
            user_in.matricula_profesional.strip() if user_in.matricula_profesional else None
        ),
        hash_password=hash_password,
        debe_cambiar_password=True,
        intentos_fallidos=0,
        bloqueado_hasta=None,
        activo=True,
    )
    db.add(nuevo_usuario)
    db.flush()

    # 7. Registrar evento de auditoría en log_seguridad
    _registrar_evento_seguridad(
        db=db,
        accion="USUARIO_CREADO",
        id_usuario=admin.id_usuario,
        id_objetivo=nuevo_usuario.id_usuario,
        ip=ip_cliente,
        detalle={
            "usuario": nuevo_usuario.usuario,
            "ci": nuevo_usuario.ci,
            "rol": rol_db.nombre,
        },
    )
    db.commit()
    db.refresh(nuevo_usuario)

    return UsuarioAdminResponse(
        id_usuario=nuevo_usuario.id_usuario,
        id_rol=nuevo_usuario.id_rol,
        rol=rol_db.nombre,
        usuario=nuevo_usuario.usuario,
        ci=nuevo_usuario.ci,
        nombres=nuevo_usuario.nombres,
        apellido_paterno=nuevo_usuario.apellido_paterno,
        apellido_materno=nuevo_usuario.apellido_materno,
        correo=nuevo_usuario.correo,
        matricula_profesional=nuevo_usuario.matricula_profesional,
        debe_cambiar_password=True,
        activo=True,
        password_temporal=temp_password,
        mensaje="Usuario creado exitosamente. Entregue la contraseña temporal al usuario; se le exigirá cambiarla en su primer inicio de sesión.",
    )


@router.post(
    "/{id_usuario}/reset-password",
    response_model=UsuarioAdminResponse,
    summary="Restablecer contraseña de usuario (Exclusivo ADMIN)",
    description="Genera una nueva contraseña temporal de 14 caracteres, establece debe_cambiar_password=TRUE, revoca sesiones y registra RESET_PASSWORD_ADMIN.",
)
def reset_password_admin(
    id_usuario: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> UsuarioAdminResponse:
    ip_cliente = _obtener_ip_cliente(request)
    now = datetime.now(timezone.utc)

    # 1. Buscar usuario objetivo
    usuario_db = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not usuario_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    # 2. Generar nueva contraseña temporal de 14 caracteres y su hash Argon2id
    temp_password = generate_temporary_password(
        length=14,
        username=usuario_db.usuario,
        ci=usuario_db.ci,
    )
    nuevo_hash = get_password_hash(temp_password)

    # 3. Actualizar flags de seguridad y desbloquear cuenta
    usuario_db.hash_password = nuevo_hash
    usuario_db.debe_cambiar_password = True
    usuario_db.intentos_fallidos = 0
    usuario_db.bloqueado_hasta = None

    # 4. Revocar todas las sesiones activas del usuario por seguridad
    db.query(Sesion).filter(
        Sesion.id_usuario == id_usuario,
        Sesion.revocada_en.is_(None),
    ).update({"revocada_en": now})

    # 5. Registrar evento en log_seguridad
    _registrar_evento_seguridad(
        db=db,
        accion="RESET_PASSWORD_ADMIN",
        id_usuario=admin.id_usuario,
        id_objetivo=usuario_db.id_usuario,
        ip=ip_cliente,
        detalle={"usuario": usuario_db.usuario, "motivo": "Reseteo administrativo de credenciales"},
    )
    db.commit()
    db.refresh(usuario_db)

    rol_nombre = usuario_db.rol.nombre if usuario_db.rol else "BIOQUIMICO"

    return UsuarioAdminResponse(
        id_usuario=usuario_db.id_usuario,
        id_rol=usuario_db.id_rol,
        rol=rol_nombre,
        usuario=usuario_db.usuario,
        ci=usuario_db.ci,
        nombres=usuario_db.nombres,
        apellido_paterno=usuario_db.apellido_paterno,
        apellido_materno=usuario_db.apellido_materno,
        correo=usuario_db.correo,
        matricula_profesional=usuario_db.matricula_profesional,
        debe_cambiar_password=True,
        activo=usuario_db.activo,
        password_temporal=temp_password,
        mensaje="Contraseña restablecida exitosamente. Entregue la nueva clave temporal al usuario; se le exigirá cambiarla en su próximo inicio de sesión.",
    )


@router.delete(
    "/{id_usuario}",
    summary="Baja lógica de usuario (Exclusivo ADMIN)",
    description="Desactiva al usuario (activo = FALSE), revoca sus sesiones y registra USUARIO_DESACTIVADO. Prohíbe DELETE físico.",
)
@router.post(
    "/{id_usuario}/desactivar",
    summary="Baja lógica de usuario (Alternativa POST)",
    description="Desactiva al usuario (activo = FALSE), revoca sus sesiones y registra USUARIO_DESACTIVADO. Prohíbe DELETE físico.",
)
def deactivate_user(
    id_usuario: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> dict[str, Any]:
    ip_cliente = _obtener_ip_cliente(request)
    now = datetime.now(timezone.utc)

    # 1. Buscar usuario objetivo
    usuario_db = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not usuario_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    # 2. Impedir que el administrador se desactive a sí mismo
    if admin.id_usuario == usuario_db.id_usuario:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No es posible desactivar la propia cuenta de administrador en sesión.",
        )

    # 3. Si ya está inactivo, responder sin cambios
    if not usuario_db.activo:
        return {
            "status": "ok",
            "message": f"El usuario '{usuario_db.usuario}' ya se encuentra desactivado.",
            "id_usuario": usuario_db.id_usuario,
            "activo": False,
        }

    # 4. BAJA LÓGICA ESTRICTA: NUNCA DELETE físico (DECISIONES.md §6 y AGENTS.md Regla 6)
    usuario_db.activo = False

    # 5. Revocar inmediatamente todas las sesiones del usuario dado de baja
    db.query(Sesion).filter(
        Sesion.id_usuario == id_usuario,
        Sesion.revocada_en.is_(None),
    ).update({"revocada_en": now})

    # 6. Registrar evento en log_seguridad
    _registrar_evento_seguridad(
        db=db,
        accion="USUARIO_DESACTIVADO",
        id_usuario=admin.id_usuario,
        id_objetivo=usuario_db.id_usuario,
        ip=ip_cliente,
        detalle={"usuario": usuario_db.usuario, "motivo": "Baja lógica administrativa"},
    )
    db.commit()

    return {
        "status": "ok",
        "message": f"Usuario '{usuario_db.usuario}' desactivado exitosamente (baja lógica).",
        "id_usuario": usuario_db.id_usuario,
        "activo": False,
    }


@router.get(
    "",
    response_model=list[UsuarioResponse],
    summary="Listar usuarios del sistema (Exclusivo ADMIN)",
    description="Retorna la lista de usuarios registrados.",
)
def list_users(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> list[UsuarioResponse]:
    usuarios = db.query(Usuario).order_by(Usuario.id_usuario.asc()).all()
    return [UsuarioResponse.model_validate(u) for u in usuarios]


@router.get(
    "/{id_usuario}",
    response_model=UsuarioResponse,
    summary="Consultar detalles de un usuario (Exclusivo ADMIN)",
    description="Retorna la ficha de un usuario específico.",
)
def get_user_detail(
    id_usuario: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> UsuarioResponse:
    usuario_db = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not usuario_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )
    return UsuarioResponse.model_validate(usuario_db)
