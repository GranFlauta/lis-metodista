"""
Endpoints de lectura del catálogo clínico (Fase 2).
PROMPT_FASE_2.md §8.1:
- GET /api/catalogo/estudios
- GET /api/catalogo/perfiles
Accesible a cualquier usuario autenticado (ADMIN o BIOQUIMICO).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.core.database import get_db
from app.core.errors import NoEncontradoError, ValidacionError, ConflictoError
from app.models.catalog import Estudio, EstudioVersion, Parametro, Perfil, PerfilEstudio, PerfilRapido
from app.models.user import Usuario
from app.schemas.catalogo import EstudioCatalogo, GrupoEstudio, ParametroResumen, PerfilCatalogo, PerfilEstudioItem, PerfilRapidoRequest, PerfilRapidoResponse

router = APIRouter(prefix="/api/catalogo", tags=["Catálogo"])


@router.get("/estudios", response_model=list[EstudioCatalogo])
def listar_estudios(
    db: Session = Depends(get_db),
    _current_user: Usuario = Depends(require_auth),
) -> list[EstudioCatalogo]:
    """
    Retorna la lista de estudios activos con su configuración.
    Si seleccion_parcial es True, incluye los grupos con sus parámetros de la versión activa.
    Para los demás, grupos es null.
    """
    estudios = (
        db.query(Estudio)
        .filter(Estudio.activo == True)
        .order_by(Estudio.id_estudio)
        .all()
    )

    resultado: list[EstudioCatalogo] = []
    for estudio in estudios:
        grupos: list[GrupoEstudio] | None = None
        if estudio.seleccion_parcial:
            version_activa = (
                db.query(EstudioVersion)
                .filter(
                    EstudioVersion.id_estudio == estudio.id_estudio,
                    EstudioVersion.activa == True,
                )
                .first()
            )
            if version_activa:
                parametros = (
                    db.query(Parametro)
                    .filter(Parametro.id_estudio_version == version_activa.id_estudio_version)
                    .order_by(Parametro.orden_visualizacion)
                    .all()
                )
                grupos_dict: dict[str, list[ParametroResumen]] = {}
                for p in parametros:
                    if p.grupo:
                        if p.grupo not in grupos_dict:
                            grupos_dict[p.grupo] = []
                        grupos_dict[p.grupo].append(
                            ParametroResumen(codigo=p.codigo, nombre=p.nombre)
                        )
                grupos = [
                    GrupoEstudio(codigo=grupo_codigo, parametros=params_list)
                    for grupo_codigo, params_list in grupos_dict.items()
                ]

        resultado.append(
            EstudioCatalogo(
                codigo=estudio.codigo,
                nombre=estudio.nombre,
                categoria=estudio.categoria,
                seleccion_parcial=estudio.seleccion_parcial,
                grupos=grupos,
            )
        )

    return resultado


@router.get("/perfiles", response_model=list[PerfilCatalogo])
def listar_perfiles(
    db: Session = Depends(get_db),
    _current_user: Usuario = Depends(require_auth),
) -> list[PerfilCatalogo]:
    """
    Retorna los perfiles activos con sus estudios ordenados por orden_visualizacion.
    """
    perfiles = (
        db.query(Perfil)
        .filter(Perfil.activo == True)
        .order_by(Perfil.id_perfil)
        .all()
    )

    resultado: list[PerfilCatalogo] = []
    for perfil in perfiles:
        perfil_estudios = (
            db.query(PerfilEstudio)
            .filter(PerfilEstudio.id_perfil == perfil.id_perfil)
            .order_by(PerfilEstudio.orden_visualizacion)
            .all()
        )
        estudios_items = [
            PerfilEstudioItem(
                codigo=pe.estudio.codigo,
                grupos=list(pe.grupos) if pe.grupos is not None else None,
            )
            for pe in perfil_estudios
        ]
        resultado.append(
            PerfilCatalogo(
                codigo=perfil.codigo,
                nombre=perfil.nombre,
                estudios=estudios_items,
            )
        )

    return resultado


def _serializar_perfil_rapido(perfil: PerfilRapido) -> PerfilRapidoResponse:
    return PerfilRapidoResponse(
        id=perfil.id_perfil_rapido,
        nombre=perfil.nombre,
        estudios=[PerfilEstudioItem(**item) for item in perfil.estudios],
    )


def _validar_estudios_rapidos(db: Session, items: list[PerfilEstudioItem]) -> list[dict]:
    if not items:
        raise ValidacionError("Seleccione al menos un estudio para el perfil rápido.")
    codigos = [item.codigo for item in items]
    if len(codigos) != len(set(codigos)):
        raise ValidacionError("El perfil rápido contiene estudios repetidos.")
    resultado = []
    for item in items:
        estudio = db.query(Estudio).filter(Estudio.codigo == item.codigo, Estudio.activo == True).first()
        if not estudio:
            raise ValidacionError(f"El estudio '{item.codigo}' no está activo en el catálogo.")
        grupos = item.grupos
        if estudio.seleccion_parcial:
            version = db.query(EstudioVersion).filter(EstudioVersion.id_estudio == estudio.id_estudio, EstudioVersion.activa == True).first()
            existentes = {p.grupo for p in db.query(Parametro.grupo).filter(Parametro.id_estudio_version == version.id_estudio_version, Parametro.grupo.isnot(None)).distinct().all()} if version else set()
            if not grupos or not set(grupos).issubset(existentes):
                raise ValidacionError(f"Seleccione grupos válidos para '{estudio.nombre}'.")
        else:
            grupos = None
        resultado.append({"codigo": item.codigo, "grupos": grupos})
    return resultado


@router.get("/perfiles-rapidos", response_model=list[PerfilRapidoResponse])
def listar_perfiles_rapidos(db: Session = Depends(get_db), current_user: Usuario = Depends(require_auth)):
    perfiles = db.query(PerfilRapido).filter(PerfilRapido.id_usuario == current_user.id_usuario).order_by(PerfilRapido.nombre).all()
    return [_serializar_perfil_rapido(item) for item in perfiles]


@router.post("/perfiles-rapidos", response_model=PerfilRapidoResponse, status_code=201)
def crear_perfil_rapido(body: PerfilRapidoRequest, db: Session = Depends(get_db), current_user: Usuario = Depends(require_auth)):
    nombre = body.nombre.strip()
    if not nombre:
        raise ValidacionError("El nombre del perfil rápido es obligatorio.")
    perfil = PerfilRapido(id_usuario=current_user.id_usuario, nombre=nombre, estudios=_validar_estudios_rapidos(db, body.estudios))
    db.add(perfil)
    try:
        db.commit()
        db.refresh(perfil)
    except IntegrityError:
        db.rollback()
        raise ConflictoError("Ya existe un perfil rápido con ese nombre.")
    return _serializar_perfil_rapido(perfil)


@router.put("/perfiles-rapidos/{perfil_id}", response_model=PerfilRapidoResponse)
def actualizar_perfil_rapido(perfil_id: int, body: PerfilRapidoRequest, db: Session = Depends(get_db), current_user: Usuario = Depends(require_auth)):
    perfil = db.query(PerfilRapido).filter(PerfilRapido.id_perfil_rapido == perfil_id, PerfilRapido.id_usuario == current_user.id_usuario).first()
    if not perfil:
        raise NoEncontradoError("El perfil rápido no existe.")
    nombre = body.nombre.strip()
    if not nombre:
        raise ValidacionError("El nombre del perfil rápido es obligatorio.")
    perfil.nombre = nombre
    perfil.estudios = _validar_estudios_rapidos(db, body.estudios)
    try:
        db.commit()
        db.refresh(perfil)
    except IntegrityError:
        db.rollback()
        raise ConflictoError("Ya existe un perfil rápido con ese nombre.")
    return _serializar_perfil_rapido(perfil)


@router.delete("/perfiles-rapidos/{perfil_id}", status_code=204)
def eliminar_perfil_rapido(perfil_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_auth)):
    perfil = db.query(PerfilRapido).filter(PerfilRapido.id_perfil_rapido == perfil_id, PerfilRapido.id_usuario == current_user.id_usuario).first()
    if not perfil:
        raise NoEncontradoError("El perfil rápido no existe.")
    db.delete(perfil)
    db.commit()
