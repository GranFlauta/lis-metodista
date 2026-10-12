"""
Endpoints de lectura del catálogo clínico (Fase 2).
PROMPT_FASE_2.md §8.1:
- GET /api/catalogo/estudios
- GET /api/catalogo/perfiles
Accesible a cualquier usuario autenticado (ADMIN o BIOQUIMICO).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.core.database import get_db
from app.models.catalog import Estudio, EstudioVersion, Parametro, Perfil, PerfilEstudio
from app.models.user import Usuario
from app.schemas.catalogo import EstudioCatalogo, GrupoEstudio, ParametroResumen, PerfilCatalogo, PerfilEstudioItem

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
