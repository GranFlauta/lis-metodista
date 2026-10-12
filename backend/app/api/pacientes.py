"""
Endpoints de Pacientes (Fase 2).
PROMPT_FASE_2.md §8.2:
- GET /api/pacientes?q=&limit=&offset= (BIOQUIMICO, ADMIN)
- GET /api/pacientes/{id} (BIOQUIMICO, ADMIN)
- POST /api/pacientes (solo BIOQUIMICO, 201)
- PATCH /api/pacientes/{id} (solo BIOQUIMICO, 200)
- REGLA: No existe DELETE de pacientes.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import require_auth, require_bioquimico
from app.core.clock import ahora
from app.core.database import get_db
from app.core.errors import ConflictoError, NoEncontradoError, ValidacionError
from app.models.patient import Paciente
from app.models.user import Usuario
from app.schemas.paciente import (
    PacienteCreate,
    PacienteListaResponse,
    PacienteResponse,
    PacienteUpdate,
)

router = APIRouter(prefix="/api/pacientes", tags=["Pacientes"])


def normalizar_texto(texto: Optional[str]) -> Optional[str]:
    """Colapsa espacios múltiples y aplica strip. Retorna None si queda vacío."""
    if texto is None:
        return None
    limpio = re.sub(r"\s+", " ", texto).strip()
    return limpio if limpio else None


def normalizar_ci(ci: Optional[str]) -> Optional[str]:
    """Remueve todos los espacios y convierte a mayúsculas."""
    if ci is None:
        return None
    limpio = re.sub(r"\s+", "", ci).upper()
    return limpio if limpio else None


def normalizar_ci_complemento(comp: Optional[str]) -> Optional[str]:
    """Remueve todos los espacios y convierte a mayúsculas. Cadena vacía -> None."""
    if comp is None:
        return None
    limpio = re.sub(r"\s+", "", comp).upper()
    return limpio if limpio else None


def validar_fecha_nacimiento(fn: Optional[date]) -> None:
    """Valida que la fecha de nacimiento no sea futura y no sea anterior a 130 años."""
    if fn is None:
        return
    hoy = ahora().date()
    if fn > hoy:
        raise ValidacionError("La fecha de nacimiento no puede ser futura.")
    try:
        limite_130 = hoy.replace(year=hoy.year - 130)
    except ValueError:
        limite_130 = hoy.replace(year=hoy.year - 130, day=28)
    if fn < limite_130:
        raise ValidacionError("La fecha de nacimiento no puede ser anterior a 130 años.")


def validar_ci_y_sin_ci(ci: Optional[str], sin_ci: bool) -> None:
    """Aplica la regla excluyente de CI vs sin_ci."""
    if sin_ci:
        if ci is not None:
            raise ValidacionError("Si sin_ci es verdadero, el CI debe ser nulo.")
    else:
        if ci is None:
            raise ValidacionError("El CI es obligatorio cuando sin_ci es falso.")
        if len(ci) < 5 or len(ci) > 30:
            raise ValidacionError("El CI debe tener entre 5 y 30 caracteres.")


def validar_sexo(sexo: Optional[str]) -> str:
    """Valida que el sexo sea 'M' o 'F'."""
    if not sexo:
        raise ValidacionError("El campo sexo es obligatorio.")
    s = sexo.strip().upper()
    if s not in ("M", "F"):
        raise ValidacionError("El campo sexo debe ser 'M' o 'F'.")
    return s


def comprobar_unicidad_ci(
    db: Session,
    ci: Optional[str],
    ci_complemento: Optional[str],
    paciente_id_excluir: Optional[int] = None,
) -> None:
    """Verifica unicidad de la tupla (ci, coalesce(ci_complemento, ''))."""
    if ci is None:
        return
    query = db.query(Paciente).filter(
        Paciente.ci == ci,
        func.coalesce(Paciente.ci_complemento, "") == (ci_complemento or ""),
    )
    if paciente_id_excluir is not None:
        query = query.filter(Paciente.id_paciente != paciente_id_excluir)
    existente = query.first()
    if existente:
        raise ConflictoError(
            f"Ya existe un paciente registrado con el CI '{ci}' y complemento '{ci_complemento or ''}'.",
            extra={"paciente_existente_id": existente.id_paciente},
        )


@router.get("", response_model=PacienteListaResponse)
def listar_pacientes(
    q: Optional[str] = Query(None, description="Búsqueda por CI, nombres o apellidos"),
    limit: int = Query(25, description="Cantidad máxima de registros (1-100)"),
    offset: int = Query(0, description="Desplazamiento (>= 0)"),
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_auth),
) -> PacienteListaResponse:
    """
    Lista pacientes con paginación y filtro de búsqueda.
    Accesible para ADMIN y BIOQUIMICO.
    """
    if limit < 1 or limit > 100:
        raise ValidacionError("El parámetro limit debe estar entre 1 y 100.")
    if offset < 0:
        raise ValidacionError("El parámetro offset debe ser mayor o igual a 0.")

    query = db.query(Paciente)

    if q and q.strip():
        termino = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(func.coalesce(Paciente.ci, "")).like(termino),
                func.lower(Paciente.nombres).like(termino),
                func.lower(Paciente.apellido_paterno).like(termino),
                func.lower(func.coalesce(Paciente.apellido_materno, "")).like(termino),
            )
        )

    # Orden especificado: apellidos, nombres
    query = query.order_by(
        Paciente.apellido_paterno.asc(),
        func.coalesce(Paciente.apellido_materno, "").asc(),
        Paciente.nombres.asc(),
    )

    total = query.count()
    items = query.offset(offset).limit(limit).all()

    return PacienteListaResponse(
        items=[PacienteResponse.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{id}", response_model=PacienteResponse)
def obtener_paciente(
    id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_auth),
) -> PacienteResponse:
    """
    Obtiene la ficha de un paciente por su id.
    Accesible para ADMIN y BIOQUIMICO. 404 si no existe.
    """
    paciente = db.query(Paciente).filter(Paciente.id_paciente == id).first()
    if not paciente:
        raise NoEncontradoError(f"Paciente con id {id} no encontrado.")
    return PacienteResponse.model_validate(paciente)


@router.post("", response_model=PacienteResponse, status_code=status.HTTP_201_CREATED)
def crear_paciente(
    body: PacienteCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_bioquimico),
) -> PacienteResponse:
    """
    Registra un nuevo paciente en el sistema.
    Exclusivo para BIOQUIMICO.
    """
    # 1. Normalización
    nombres = normalizar_texto(body.nombres)
    apellido_paterno = normalizar_texto(body.apellido_paterno)
    apellido_materno = normalizar_texto(body.apellido_materno)
    ci = normalizar_ci(body.ci)
    ci_complemento = normalizar_ci_complemento(body.ci_complemento)
    telefono = normalizar_texto(body.telefono)
    sexo = validar_sexo(body.sexo)

    if not nombres:
        raise ValidacionError("El campo nombres es obligatorio.")
    if len(nombres) > 100:
        raise ValidacionError("El campo nombres no puede superar 100 caracteres.")

    if not apellido_paterno:
        raise ValidacionError("El campo apellido_paterno es obligatorio.")
    if len(apellido_paterno) > 100:
        raise ValidacionError("El campo apellido_paterno no puede superar 100 caracteres.")

    if apellido_materno and len(apellido_materno) > 100:
        raise ValidacionError("El campo apellido_materno no puede superar 100 caracteres.")

    if ci_complemento and len(ci_complemento) > 5:
        raise ValidacionError("El campo ci_complemento no puede superar 5 caracteres.")

    if telefono and len(telefono) > 30:
        raise ValidacionError("El campo telefono no puede superar 30 caracteres.")

    # 2. Regla CI vs sin_ci
    validar_ci_y_sin_ci(ci=ci, sin_ci=body.sin_ci)
    if body.sin_ci and ci_complemento is not None:
        raise ValidacionError("Un paciente sin CI no puede tener complemento de CI.")

    # 3. Validación de fecha de nacimiento
    validar_fecha_nacimiento(body.fecha_nacimiento)

    # 4. Unicidad de CI
    comprobar_unicidad_ci(db=db, ci=ci, ci_complemento=ci_complemento)

    # 5. Persistencia
    now = ahora()
    paciente = Paciente(
        ci=ci,
        ci_complemento=ci_complemento,
        sin_ci=body.sin_ci,
        nombres=nombres,
        apellido_paterno=apellido_paterno,
        apellido_materno=apellido_materno,
        fecha_nacimiento=body.fecha_nacimiento,
        sexo=sexo,
        telefono=telefono,
        creado_por=current_user.id_usuario,
        creado_en=now,
        actualizado_en=now,
    )
    db.add(paciente)
    db.commit()
    db.refresh(paciente)

    return PacienteResponse.model_validate(paciente)


@router.patch("/{id}", response_model=PacienteResponse)
def actualizar_paciente(
    id: int,
    body: PacienteUpdate,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_bioquimico),
) -> PacienteResponse:
    """
    Edita parcialmente los datos de un paciente.
    Exclusivo para BIOQUIMICO.
    """
    paciente = db.query(Paciente).filter(Paciente.id_paciente == id).first()
    if not paciente:
        raise NoEncontradoError(f"Paciente con id {id} no encontrado.")

    campos_enviados = body.model_dump(exclude_unset=True)

    # Valores proyectados
    nuevo_sin_ci = campos_enviados.get("sin_ci", paciente.sin_ci)

    if "ci" in campos_enviados:
        nuevo_ci = normalizar_ci(campos_enviados["ci"])
    else:
        nuevo_ci = paciente.ci

    if "ci_complemento" in campos_enviados:
        nuevo_ci_complemento = normalizar_ci_complemento(campos_enviados["ci_complemento"])
    else:
        nuevo_ci_complemento = paciente.ci_complemento

    if "nombres" in campos_enviados:
        nuevo_nombres = normalizar_texto(campos_enviados["nombres"])
        if not nuevo_nombres:
            raise ValidacionError("El campo nombres no puede estar vacío.")
        if len(nuevo_nombres) > 100:
            raise ValidacionError("El campo nombres no puede superar 100 caracteres.")
    else:
        nuevo_nombres = paciente.nombres

    if "apellido_paterno" in campos_enviados:
        nuevo_apellido_paterno = normalizar_texto(campos_enviados["apellido_paterno"])
        if not nuevo_apellido_paterno:
            raise ValidacionError("El campo apellido_paterno no puede estar vacío.")
        if len(nuevo_apellido_paterno) > 100:
            raise ValidacionError("El campo apellido_paterno no puede superar 100 caracteres.")
    else:
        nuevo_apellido_paterno = paciente.apellido_paterno

    if "apellido_materno" in campos_enviados:
        nuevo_apellido_materno = normalizar_texto(campos_enviados["apellido_materno"])
        if nuevo_apellido_materno and len(nuevo_apellido_materno) > 100:
            raise ValidacionError("El campo apellido_materno no puede superar 100 caracteres.")
    else:
        nuevo_apellido_materno = paciente.apellido_materno

    if "telefono" in campos_enviados:
        nuevo_telefono = normalizar_texto(campos_enviados["telefono"])
        if nuevo_telefono and len(nuevo_telefono) > 30:
            raise ValidacionError("El campo telefono no puede superar 30 caracteres.")
    else:
        nuevo_telefono = paciente.telefono

    if "sexo" in campos_enviados:
        nuevo_sexo = validar_sexo(campos_enviados["sexo"])
    else:
        nuevo_sexo = paciente.sexo

    if "fecha_nacimiento" in campos_enviados:
        nueva_fecha_nacimiento = campos_enviados["fecha_nacimiento"]
        validar_fecha_nacimiento(nueva_fecha_nacimiento)
    else:
        nueva_fecha_nacimiento = paciente.fecha_nacimiento

    if nuevo_ci_complemento and len(nuevo_ci_complemento) > 5:
        raise ValidacionError("El campo ci_complemento no puede superar 5 caracteres.")

    # Validar coherencia CI vs sin_ci
    validar_ci_y_sin_ci(ci=nuevo_ci, sin_ci=nuevo_sin_ci)
    if nuevo_sin_ci and nuevo_ci_complemento is not None:
        raise ValidacionError("Un paciente sin CI no puede tener complemento de CI.")

    # Validar unicidad de CI
    comprobar_unicidad_ci(
        db=db,
        ci=nuevo_ci,
        ci_complemento=nuevo_ci_complemento,
        paciente_id_excluir=paciente.id_paciente,
    )

    # Aplicar cambios
    paciente.sin_ci = nuevo_sin_ci
    paciente.ci = nuevo_ci
    paciente.ci_complemento = nuevo_ci_complemento
    paciente.nombres = nuevo_nombres
    paciente.apellido_paterno = nuevo_apellido_paterno
    paciente.apellido_materno = nuevo_apellido_materno
    paciente.telefono = nuevo_telefono
    paciente.sexo = nuevo_sexo
    paciente.fecha_nacimiento = nueva_fecha_nacimiento
    paciente.actualizado_en = ahora()

    db.commit()
    db.refresh(paciente)

    return PacienteResponse.model_validate(paciente)
