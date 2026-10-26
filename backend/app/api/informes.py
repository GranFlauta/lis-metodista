"""
Endpoints para Informes Oficiales, Historial de Auditoría, Versiones y Papelera Lógica (Fase 4).
docs/DECISIONES.md §3, §4, §8:
- GET /api/informes (búsqueda y consulta de informes oficiales)
- GET /api/informes/papelera (consulta de papelera y reciclaje)
- GET /api/informes/{folio} (visualización de informe oficial inmutable)
- GET /api/informes/{folio}/historial (traza de auditoría append-only)
- GET /api/informes/{folio}/versiones (historial de versiones V1..V3)
- POST /api/informes/{folio}/papelera (mover a papelera con justificativo auditado)
- POST /api/informes/{folio}/restaurar (restaurar a RECICLAJE con justificativo)
- POST /api/informes/{folio}/versiones (emitir nueva versión V2/V3)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.core.database import get_db
from app.models.report import Informe, InformeEvento
from app.models.user import Usuario
from app.schemas.informe import (
    InformeDetalleResponse,
    InformeEventoResponse,
    InformeItemResponse,
    JustificativoRequest,
    NuevaVersionRequest,
    PapeleraItemResponse,
)
from app.services.informes_service import (
    crear_nueva_version_informe,
    listar_informes,
    listar_papelera,
    mover_informe_a_papelera,
    obtener_eventos_folio,
    obtener_informe_por_folio,
    restaurar_informe_de_papelera,
)

router = APIRouter(prefix="/api/informes", tags=["Informes"])


def serializar_item_informe(inf: Informe) -> dict[str, Any]:
    pac = inf.orden.paciente if inf.orden else None
    pac_nombre = f"{pac.nombres} {pac.apellido_paterno}".strip() if pac else "Desconocido"
    firm = inf.firmante
    firm_nombre = f"{firm.nombres} {firm.apellido_paterno}".strip() if firm else "Desconocido"
    pub = inf.publicador
    pub_nombre = f"{pub.nombres} {pub.apellido_paterno}".strip() if pub else "Desconocido"

    return {
        "id_informe": inf.id_informe,
        "folio": inf.folio,
        "numero_version": inf.numero_version,
        "id_orden": inf.id_orden,
        "estado": inf.estado,
        "es_urgencia": inf.es_urgencia,
        "justificativo": inf.justificativo,
        "publicado_en": inf.publicado_en,
        "paciente_nombre": pac_nombre,
        "paciente_ci": pac.ci if pac else None,
        "firmante_nombre": firm_nombre,
        "publicador_nombre": pub_nombre,
        "snapshot_sha256": inf.snapshot_sha256,
    }


@router.get("", response_model=list[InformeItemResponse])
def listar_informes_endpoint(
    q: Optional[str] = Query(None, description="Buscar por folio, CI o nombre de paciente"),
    estado: str = Query("VIGENTE", description="VIGENTE, RECICLAJE, DESPLAZADO, PAPELERA"),
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> list[dict[str, Any]]:
    """Lista informes oficiales con filtros de búsqueda."""
    informes = listar_informes(
        db,
        q=q,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limit=limit,
        offset=offset,
    )
    return [serializar_item_informe(inf) for inf in informes]


@router.get("/papelera", response_model=list[PapeleraItemResponse])
def listar_papelera_endpoint(
    q: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> list[dict[str, Any]]:
    """Lista todos los informes en papelera o reciclaje con su justificación."""
    return listar_papelera(db, q=q, limit=limit, offset=offset)


@router.get("/{folio}", response_model=InformeDetalleResponse)
def obtener_informe_endpoint(
    folio: str,
    version: Optional[int] = Query(None, ge=1, le=3),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> dict[str, Any]:
    """Obtiene el detalle completo del informe oficial inmutable con snapshot JSON."""
    informe = obtener_informe_por_folio(db, folio, numero_version=version)
    eventos = obtener_eventos_folio(db, folio)

    # Buscar todas las versiones existentes del folio
    versiones_db = (
        db.query(Informe)
        .filter(Informe.folio == folio)
        .order_by(Informe.numero_version.asc())
        .all()
    )
    versiones_list = [
        {
            "id_informe": v.id_informe,
            "numero_version": v.numero_version,
            "estado": v.estado,
            "publicado_en": v.publicado_en.isoformat(),
            "snapshot_sha256": v.snapshot_sha256,
        }
        for v in versiones_db
    ]

    eventos_list = [
        {
            "id_evento": ev.id_evento,
            "folio": ev.folio,
            "numero_version": ev.numero_version,
            "accion": ev.accion,
            "justificativo": ev.justificativo,
            "detalle": ev.detalle,
            "id_usuario": ev.id_usuario,
            "usuario_nombre": f"{ev.usuario.nombres} {ev.usuario.apellido_paterno}".strip() if ev.usuario else "Sistema",
            "creado_en": ev.creado_en,
        }
        for ev in eventos
    ]

    firm = informe.firmante
    pub = informe.publicador

    return {
        "id_informe": informe.id_informe,
        "folio": informe.folio,
        "numero_version": informe.numero_version,
        "id_orden": informe.id_orden,
        "estado": informe.estado,
        "es_urgencia": informe.es_urgencia,
        "justificativo": informe.justificativo,
        "publicado_en": informe.publicado_en,
        "snapshot_json": informe.snapshot_json,
        "snapshot_sha256": informe.snapshot_sha256,
        "firmante": {
            "id_usuario": firm.id_usuario,
            "usuario": firm.usuario,
            "nombres": firm.nombres,
            "apellido_paterno": firm.apellido_paterno,
            "matricula_profesional": firm.matricula_profesional,
        } if firm else {},
        "publicador": {
            "id_usuario": pub.id_usuario,
            "usuario": pub.usuario,
            "nombres": pub.nombres,
            "apellido_paterno": pub.apellido_paterno,
        } if pub else {},
        "eventos": eventos_list,
        "versiones_disponibles": versiones_list,
    }


@router.get("/{folio}/historial", response_model=list[InformeEventoResponse])
def obtener_historial_endpoint(
    folio: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> list[dict[str, Any]]:
    """Obtiene la traza de auditoría append-only para el folio especificado."""
    # Verificar que el folio existe
    obtener_informe_por_folio(db, folio)
    eventos = obtener_eventos_folio(db, folio)
    return [
        {
            "id_evento": ev.id_evento,
            "folio": ev.folio,
            "numero_version": ev.numero_version,
            "accion": ev.accion,
            "justificativo": ev.justificativo,
            "detalle": ev.detalle,
            "id_usuario": ev.id_usuario,
            "usuario_nombre": f"{ev.usuario.nombres} {ev.usuario.apellido_paterno}".strip() if ev.usuario else "Sistema",
            "creado_en": ev.creado_en,
        }
        for ev in eventos
    ]


@router.post("/{folio}/papelera", response_model=InformeItemResponse)
def mover_a_papelera_endpoint(
    folio: str,
    body: JustificativoRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> dict[str, Any]:
    """
    Envía un informe oficial a la papelera lógica (D-73).
    Solo el firmante original puede hacerlo, con justificativo obligatorio.
    """
    informe = mover_informe_a_papelera(
        db,
        folio=folio,
        current_user=current_user,
        justificativo=body.justificativo,
    )
    return serializar_item_informe(informe)


@router.post("/{folio}/restaurar", response_model=InformeItemResponse)
def restaurar_de_papelera_endpoint(
    folio: str,
    body: JustificativoRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> dict[str, Any]:
    """
    Restaura un informe de la papelera a estado RECICLAJE (D-74).
    Solo el firmante original puede hacerlo, con justificativo obligatorio.
    """
    informe = restaurar_informe_de_papelera(
        db,
        folio=folio,
        current_user=current_user,
        justificativo=body.justificativo,
    )
    return serializar_item_informe(informe)


@router.post("/{folio}/versiones", response_model=InformeItemResponse, status_code=status.HTTP_201_CREATED)
def crear_nueva_version_endpoint(
    folio: str,
    body: NuevaVersionRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> dict[str, Any]:
    """
    Crea una nueva versión oficial V2 o V3 (D-70).
    Solo el firmante original puede hacerlo, con justificativo obligatorio.
    """
    nuevo_informe = crear_nueva_version_informe(
        db,
        folio=folio,
        current_user=current_user,
        justificativo=body.justificativo,
    )
    return serializar_item_informe(nuevo_informe)
