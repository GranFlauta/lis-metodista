"""
Endpoints para la captura de resultados, cálculo en vivo, confirmación de defectos
y configuración del laboratorio (Fase 3).
Implementa estrictamente PROMPT_FASE_3.md §8.2 y §8.3.
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import (
    obtener_ip_cliente,
    registrar_evento_seguridad,
    require_auth,
)
from app.core.database import get_db
from app.core.errors import (
    ConflictoError,
    NoEncontradoError,
    ProhibidoError,
    ValidacionError,
)
from app.models.order import Orden
from app.models.result import LaboratorioConfig
from app.models.user import Usuario
from app.schemas.resultado import (
    CalcularRequest,
    ConfiguracionLaboratorioResponse,
    ConfirmarDefectosRequest,
    ResultadosUpdateRequest,
)
from app.services.evaluacion_service import (
    confirmar_defectos_orden,
    evaluar_captura_orden,
    guardar_resultados_orden,
    normalizar_y_validar_valor_entrada,
    obtener_parametros_alcance_orden,
)

router = APIRouter(tags=["Resultados"])


@router.get(
    "/api/ordenes/{id}/captura",
    summary="Obtener captura de resultados de la orden",
    description="Retorna la forma común con los valores persistidos. Solo autor o ADMIN (auditado).",
)
def obtener_captura(
    id: int,
    request: Request,
    current_user: Usuario = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    orden = db.query(Orden).filter(Orden.id_orden == id).first()
    if not orden:
        raise NoEncontradoError(f"Orden con id {id} no encontrada.")

    es_admin = (current_user.rol.nombre == "ADMIN") if current_user.rol else False
    es_autor = (orden.id_usuario_autor == current_user.id_usuario)

    if not es_admin and not es_autor:
        # D2-07: Responde 404 a bioquímicos ajenos para no revelar existencia
        raise NoEncontradoError(f"Orden con id {id} no encontrada.")

    if es_admin and not es_autor:
        registrar_evento_seguridad(
            db=db,
            accion="ADMIN_VE_PRIVADO",
            id_usuario=current_user.id_usuario,
            id_objetivo=orden.id_usuario_autor,
            ip=obtener_ip_cliente(request),
            detalle={"recurso": "captura", "id_orden": orden.id_orden},
        )
        db.commit()

    return evaluar_captura_orden(orden)


@router.post(
    "/api/ordenes/{id}/calcular",
    summary="Vista previa de cálculo en vivo (sin escribir)",
    description="Evalúa fórmulas, banderas y completitud con las entradas provistas sin persistir nada.",
)
def calcular_vista_previa(
    id: int,
    payload: CalcularRequest,
    current_user: Usuario = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    es_admin = (current_user.rol.nombre == "ADMIN") if current_user.rol else False
    if es_admin:
        raise ProhibidoError("El administrador solo tiene acceso de lectura.")

    orden = db.query(Orden).filter(Orden.id_orden == id).first()
    if not orden or orden.id_usuario_autor != current_user.id_usuario:
        raise NoEncontradoError(f"Orden con id {id} no encontrada.")

    if orden.bloqueada or orden.estado_trabajo not in ("INCOMPLETO", "COMPLETO"):
        raise ConflictoError("La orden se encuentra bloqueada o publicada y no permite modificaciones.")

    if len(payload.valores) > 200:
        raise ValidacionError("Máximo 200 claves por petición.")

    alcance_por_oe = obtener_parametros_alcance_orden(orden)
    params_map = {}
    for oe in orden.estudios:
        for p in alcance_por_oe[oe.id_orden_estudio]:
            params_map[p.codigo] = p

    for cod, val in payload.valores.items():
        if cod not in params_map:
            raise ValidacionError(f"El parámetro '{cod}' no pertenece al alcance de la orden.")
        p = params_map[cod]
        if p.tipo_campo == "CALCULADO":
            raise ValidacionError(f"No se permite modificar el parámetro calculado '{cod}'.")
        normalizar_y_validar_valor_entrada(p, val)

    return evaluar_captura_orden(orden, valores_simulados=payload.valores)


@router.put(
    "/api/ordenes/{id}/resultados",
    summary="Guardar resultados parciales y recalcular",
    description="Persiste los cambios, recalcula los parámetros calculados y actualiza el estado de la orden.",
)
def actualizar_resultados(
    id: int,
    payload: ResultadosUpdateRequest,
    current_user: Usuario = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    es_admin = (current_user.rol.nombre == "ADMIN") if current_user.rol else False
    if es_admin:
        raise ProhibidoError("El administrador solo tiene acceso de lectura.")

    orden = (
        db.query(Orden)
        .filter(Orden.id_orden == id)
        .with_for_update()
        .first()
    )
    if not orden or orden.id_usuario_autor != current_user.id_usuario:
        raise NoEncontradoError(f"Orden con id {id} no encontrada.")

    if orden.bloqueada or orden.estado_trabajo not in ("INCOMPLETO", "COMPLETO"):
        raise ConflictoError("La orden se encuentra bloqueada o publicada y no permite modificaciones.")

    return guardar_resultados_orden(db, orden, payload.valores, current_user)


@router.post(
    "/api/ordenes/{id}/resultados/confirmar-defectos",
    summary="Confirmar valores por defecto virtuales",
    description="Persiste los valores por defecto virtuales con confirmado = TRUE.",
)
def confirmar_defectos(
    id: int,
    payload: ConfirmarDefectosRequest | None = None,
    current_user: Usuario = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    es_admin = (current_user.rol.nombre == "ADMIN") if current_user.rol else False
    if es_admin:
        raise ProhibidoError("El administrador solo tiene acceso de lectura.")

    orden = (
        db.query(Orden)
        .filter(Orden.id_orden == id)
        .with_for_update()
        .first()
    )
    if not orden or orden.id_usuario_autor != current_user.id_usuario:
        raise NoEncontradoError(f"Orden con id {id} no encontrada.")

    if orden.bloqueada or orden.estado_trabajo not in ("INCOMPLETO", "COMPLETO"):
        raise ConflictoError("La orden se encuentra bloqueada o publicada y no permite modificaciones.")

    codigos = payload.parametros if payload and payload.parametros else None
    return confirmar_defectos_orden(db, orden, codigos, current_user)


@router.get(
    "/api/configuracion/laboratorio",
    response_model=ConfiguracionLaboratorioResponse,
    summary="Configuración pública del laboratorio",
    description="Devuelve únicamente el nombre del laboratorio y el separador decimal.",
)
def obtener_configuracion_laboratorio(
    current_user: Usuario = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ConfiguracionLaboratorioResponse:
    filas = (
        db.query(LaboratorioConfig)
        .filter(LaboratorioConfig.clave.in_(["nombre_laboratorio", "separador_decimal"]))
        .all()
    )
    cfg = {f.clave: f.valor for f in filas}
    return ConfiguracionLaboratorioResponse(
        nombre_laboratorio=cfg.get("nombre_laboratorio", "LABORATORIO CLINICO URGENLAB"),
        separador_decimal=cfg.get("separador_decimal", ","),
    )
