"""
Endpoints administrativos para la gestión de usuarios (Fase 1).
Implementa estrictamente PROMPT_FASE_1.md §6.3:
- Prefijo /api/usuarios. Exclusivo para rol ADMIN.
- GET /api/usuarios?activo=&rol=&q=
- POST /api/usuarios: crea usuario, contraseña temporal de 14 caracteres (única vez), 201.
- GET /api/usuarios/{id}
- PATCH /api/usuarios/{id}: edición parcial. No permite cambiar login. Impide dejar sin ADMIN activo.
- POST /api/usuarios/{id}/desactivar: 204. Baja lógica. Impide auto-desactivación y quedar sin admin.
- POST /api/usuarios/{id}/reactivar: 204. Limpia bloqueo e intentos.
- POST /api/usuarios/{id}/reset-password: 200 con password_temporal, revoca sesiones.
- REGLA: No existe ruta DELETE /api/usuarios/{id}.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import (
    obtener_ip_cliente,
    registrar_evento_seguridad,
    require_admin,
)
from app.core.clock import ahora
from app.core.database import get_db
from app.core.errors import (
    ConflictoError,
    NoEncontradoError,
    ProhibidoError,
    ValidacionError,
)
from app.core.security import (
    generate_temporary_password,
    get_password_hash,
)
from app.models.session import Sesion
from app.models.user import Rol, Usuario
from app.schemas.usuario import (
    ResetPasswordResponse,
    UsuarioCreadoResponse,
    UsuarioCreate,
    UsuarioDetalleResponse,
    UsuarioUpdate,
)

router = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])


@router.get(
    "",
    response_model=list[UsuarioDetalleResponse],
    summary="Listar usuarios",
    description="Filtra por estado activo, rol y búsqueda libre 'q' (usuario, nombres, apellidos, CI).",
)
def listar_usuarios(
    activo: bool | None = Query(default=None, description="Filtrar por estado activo/inactivo"),
    rol: str | None = Query(default=None, description="Filtrar por nombre de rol"),
    q: str | None = Query(default=None, description="Buscar en usuario, nombres, apellidos y CI"),
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> list[UsuarioDetalleResponse]:
    query = db.query(Usuario).join(Rol)

    if activo is not None:
        query = query.filter(Usuario.activo == activo)

    if rol is not None and rol.strip():
        query = query.filter(func.upper(Rol.nombre) == rol.strip().upper())

    if q is not None and q.strip():
        termino = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Usuario.usuario).like(termino),
                func.lower(Usuario.nombres).like(termino),
                func.lower(Usuario.apellido_paterno).like(termino),
                func.lower(func.coalesce(Usuario.apellido_materno, "")).like(termino),
                func.lower(Usuario.ci).like(termino),
            )
        )

    usuarios = query.order_by(Usuario.id_usuario.asc()).all()
    return [UsuarioDetalleResponse.model_validate(u) for u in usuarios]


@router.post(
    "",
    response_model=UsuarioCreadoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario",
    description="Crea usuario con debe_cambiar_password=TRUE y devuelve la clave temporal en texto plano una sola vez.",
)
def crear_usuario(
    body: UsuarioCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> UsuarioCreadoResponse:
    ip_cliente = obtener_ip_cliente(request)

    # 1. Comprobar duplicados (§6.1: 409 CONFLICTO)
    if db.query(Usuario).filter(func.lower(Usuario.usuario) == body.usuario).first():
        raise ConflictoError(f"El nombre de usuario '{body.usuario}' ya está en uso.")

    if db.query(Usuario).filter(func.lower(Usuario.ci) == body.ci.strip().lower()).first():
        raise ConflictoError(f"El CI '{body.ci}' ya está registrado.")

    if body.correo:
        if db.query(Usuario).filter(func.lower(Usuario.correo) == body.correo.strip().lower()).first():
            raise ConflictoError(f"El correo '{body.correo}' ya está registrado.")

    # 2. Validar rol
    rol_db = db.query(Rol).filter(func.upper(Rol.nombre) == body.rol.strip().upper()).first()
    if not rol_db:
        raise ValidacionError(f"El rol '{body.rol}' no existe. Roles permitidos: ADMIN, BIOQUIMICO.")

    # 3. Generar contraseña temporal de 14 caracteres (sin 0, O, 1, l, I)
    temp_password = generate_temporary_password(
        length=14,
        username=body.usuario,
        ci=body.ci,
    )
    hash_pass = get_password_hash(temp_password)

    nuevo_usuario = Usuario(
        id_rol=rol_db.id_rol,
        usuario=body.usuario,
        ci=body.ci.strip(),
        nombres=body.nombres.strip(),
        apellido_paterno=body.apellido_paterno.strip(),
        apellido_materno=body.apellido_materno.strip() if body.apellido_materno else None,
        correo=body.correo.strip() if body.correo else None,
        matricula_profesional=body.matricula_profesional.strip() if body.matricula_profesional else None,
        hash_password=hash_pass,
        debe_cambiar_password=True,
        intentos_fallidos=0,
        bloqueado_hasta=None,
        activo=True,
    )
    db.add(nuevo_usuario)
    db.flush()

    registrar_evento_seguridad(
        db=db,
        accion="USUARIO_CREADO",
        id_usuario=admin.id_usuario,
        id_objetivo=nuevo_usuario.id_usuario,
        ip=ip_cliente,
        detalle={"usuario": nuevo_usuario.usuario, "rol": rol_db.nombre, "ci": nuevo_usuario.ci},
    )
    db.commit()
    db.refresh(nuevo_usuario)

    # Devolver usuario con password_temporal una sola vez
    detalle = UsuarioDetalleResponse.model_validate(nuevo_usuario).model_dump()
    return UsuarioCreadoResponse(**detalle, password_temporal=temp_password)


@router.get(
    "/{id_usuario}",
    response_model=UsuarioDetalleResponse,
    summary="Consultar usuario por ID",
)
def obtener_usuario(
    id_usuario: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> UsuarioDetalleResponse:
    usuario_db = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not usuario_db:
        raise NoEncontradoError(f"Usuario con ID {id_usuario} no encontrado.")
    return UsuarioDetalleResponse.model_validate(usuario_db)


@router.patch(
    "/{id_usuario}",
    response_model=UsuarioDetalleResponse,
    summary="Editar usuario",
    description="Modifica atributos permitidos. No permite cambiar login. Impide dejar el sistema sin ADMIN activo.",
)
def editar_usuario(
    id_usuario: int,
    body: UsuarioUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> UsuarioDetalleResponse:
    ip_cliente = obtener_ip_cliente(request)
    usuario_db = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not usuario_db:
        raise NoEncontradoError(f"Usuario con ID {id_usuario} no encontrado.")

    campos_cambiados: dict[str, Any] = {}

    # Validar que admin no se cambie su propio rol (§6.3)
    if body.rol is not None:
        rol_nuevo = db.query(Rol).filter(func.upper(Rol.nombre) == body.rol.strip().upper()).first()
        if not rol_nuevo:
            raise ValidacionError(f"El rol '{body.rol}' no existe.")

        if admin.id_usuario == usuario_db.id_usuario and rol_nuevo.id_rol != usuario_db.id_rol:
            raise ProhibidoError("Un administrador no puede modificarse su propio rol.")

        # Validar no dejar el sistema sin ADMIN activo (§6.3)
        if usuario_db.rol.nombre == "ADMIN" and rol_nuevo.nombre != "ADMIN":
            otros_admin = (
                db.query(Usuario)
                .join(Rol)
                .filter(Rol.nombre == "ADMIN", Usuario.activo == True, Usuario.id_usuario != id_usuario)
                .count()
            )
            if otros_admin < 1:
                raise ProhibidoError("El sistema no puede quedar sin al menos un administrador activo.")

        if usuario_db.id_rol != rol_nuevo.id_rol:
            usuario_db.id_rol = rol_nuevo.id_rol
            campos_cambiados["rol"] = rol_nuevo.nombre

    # Validar CI duplicado si cambia
    if body.ci is not None and body.ci.strip().lower() != usuario_db.ci.lower():
        if db.query(Usuario).filter(func.lower(Usuario.ci) == body.ci.strip().lower(), Usuario.id_usuario != id_usuario).first():
            raise ConflictoError(f"El CI '{body.ci}' ya está registrado por otro usuario.")
        usuario_db.ci = body.ci.strip()
        campos_cambiados["ci"] = usuario_db.ci

    # Validar correo duplicado si cambia
    if body.correo is not None:
        correo_clean = body.correo.strip().lower() if body.correo else None
        if correo_clean != (usuario_db.correo.lower() if usuario_db.correo else None):
            if correo_clean and db.query(Usuario).filter(func.lower(Usuario.correo) == correo_clean, Usuario.id_usuario != id_usuario).first():
                raise ConflictoError(f"El correo '{body.correo}' ya está registrado por otro usuario.")
            usuario_db.correo = body.correo.strip() if body.correo else None
            campos_cambiados["correo"] = usuario_db.correo

    if body.nombres is not None:
        usuario_db.nombres = body.nombres.strip()
        campos_cambiados["nombres"] = usuario_db.nombres

    if body.apellido_paterno is not None:
        usuario_db.apellido_paterno = body.apellido_paterno.strip()
        campos_cambiados["apellido_paterno"] = usuario_db.apellido_paterno

    if body.apellido_materno is not None:
        usuario_db.apellido_materno = body.apellido_materno.strip() if body.apellido_materno else None
        campos_cambiados["apellido_materno"] = usuario_db.apellido_materno

    if body.matricula_profesional is not None:
        usuario_db.matricula_profesional = body.matricula_profesional.strip() if body.matricula_profesional else None
        campos_cambiados["matricula_profesional"] = usuario_db.matricula_profesional

    if campos_cambiados:
        registrar_evento_seguridad(
            db=db,
            accion="USUARIO_EDITADO",
            id_usuario=admin.id_usuario,
            id_objetivo=usuario_db.id_usuario,
            ip=ip_cliente,
            detalle={"campos": list(campos_cambiados.keys())},
        )
        db.commit()
        db.refresh(usuario_db)

    return UsuarioDetalleResponse.model_validate(usuario_db)


@router.post(
    "/{id_usuario}/desactivar",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Baja lógica de usuario",
    description="Pone activo = FALSE y revoca todas sus sesiones. Prohíbe auto-desactivación y quedar sin ADMIN.",
)
def desactivar_usuario(
    id_usuario: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> None:
    ip_cliente = obtener_ip_cliente(request)
    usuario_db = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not usuario_db:
        raise NoEncontradoError(f"Usuario con ID {id_usuario} no encontrado.")

    # 1. No auto-desactivarse (§6.3)
    if admin.id_usuario == usuario_db.id_usuario:
        raise ProhibidoError("Un administrador no puede desactivarse a sí mismo.")

    # 2. No dejar el sistema sin ADMIN activo (§6.3)
    if usuario_db.rol.nombre == "ADMIN":
        otros_admin = (
            db.query(Usuario)
            .join(Rol)
            .filter(Rol.nombre == "ADMIN", Usuario.activo == True, Usuario.id_usuario != id_usuario)
            .count()
        )
        if otros_admin < 1:
            raise ProhibidoError("El sistema no puede quedar sin al menos un administrador activo.")

    now = ahora()
    usuario_db.activo = False

    # Revocar todas las sesiones del usuario (§6.3)
    db.query(Sesion).filter(
        Sesion.id_usuario == id_usuario,
        Sesion.revocada_en.is_(None),
    ).update({"revocada_en": now}, synchronize_session=False)

    registrar_evento_seguridad(
        db=db,
        accion="USUARIO_DESACTIVADO",
        id_usuario=admin.id_usuario,
        id_objetivo=usuario_db.id_usuario,
        ip=ip_cliente,
        detalle={"motivo": "Baja lógica administrativa"},
    )
    db.commit()


@router.post(
    "/{id_usuario}/reactivar",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reactivar usuario",
    description="Pone activo = TRUE, intentos_fallidos = 0, bloqueado_hasta = NULL.",
)
def reactivar_usuario(
    id_usuario: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> None:
    ip_cliente = obtener_ip_cliente(request)
    usuario_db = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not usuario_db:
        raise NoEncontradoError(f"Usuario con ID {id_usuario} no encontrado.")

    usuario_db.activo = True
    usuario_db.intentos_fallidos = 0
    usuario_db.bloqueado_hasta = None

    registrar_evento_seguridad(
        db=db,
        accion="USUARIO_EDITADO",
        id_usuario=admin.id_usuario,
        id_objetivo=usuario_db.id_usuario,
        ip=ip_cliente,
        detalle={"activo": True, "motivo": "Reactivación de cuenta"},
    )
    db.commit()


@router.post(
    "/{id_usuario}/reset-password",
    response_model=ResetPasswordResponse,
    summary="Reset de contraseña por administrador",
    description="Genera clave temporal de 14 caracteres, fija debe_cambiar_password=TRUE y revoca sesiones.",
)
def reset_password(
    id_usuario: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
) -> ResetPasswordResponse:
    ip_cliente = obtener_ip_cliente(request)
    now = ahora()
    usuario_db = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not usuario_db:
        raise NoEncontradoError(f"Usuario con ID {id_usuario} no encontrado.")

    # Generar nueva contraseña temporal de 14 caracteres sin ambiguos (§5)
    temp_password = generate_temporary_password(
        length=14,
        username=usuario_db.usuario,
        ci=usuario_db.ci,
    )
    hash_pass = get_password_hash(temp_password)

    usuario_db.hash_password = hash_pass
    usuario_db.debe_cambiar_password = True
    usuario_db.intentos_fallidos = 0
    usuario_db.bloqueado_hasta = None

    # Revocar todas sus sesiones (§6.3)
    db.query(Sesion).filter(
        Sesion.id_usuario == id_usuario,
        Sesion.revocada_en.is_(None),
    ).update({"revocada_en": now}, synchronize_session=False)

    registrar_evento_seguridad(
        db=db,
        accion="RESET_PASSWORD_ADMIN",
        id_usuario=admin.id_usuario,
        id_objetivo=usuario_db.id_usuario,
        ip=ip_cliente,
        detalle={"motivo": "Reseteo administrativo"},
    )
    db.commit()

    return ResetPasswordResponse(password_temporal=temp_password)
