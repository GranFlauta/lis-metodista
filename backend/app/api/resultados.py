"""
Endpoints para la captura de resultados, cálculo en vivo, confirmación de defectos
y configuración del laboratorio (Fase 3).
Implementa estrictamente PROMPT_FASE_3.md §8.2 y §8.3.
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Request, Response, status
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
from app.reports.pdf import generar_informe_pdf
from app.schemas.resultado import (
    CalcularRequest,
    ConfiguracionLaboratorioResponse,
    ConfirmarDefectosRequest,
    PreviewPDFRequest,
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


def _validar_control_factor_reumatoideo(valores: dict[str, Any]) -> None:
    for codigo in ("ASTO_DILUCION", "FR_DILUCION"):
        resultado_semi = valores.get(codigo)
        if isinstance(resultado_semi, str) and ("Dilución inválida" in resultado_semi or "dilución pendiente" in resultado_semi):
            raise ValidacionError("Indique un factor de dilución válido antes de guardar el resultado.")
    resultado = valores.get("FR_DILUCION")
    if isinstance(resultado, str) and "no conforme" in resultado.casefold():
        raise ValidacionError("No se puede guardar Factor Reumatoideo: los controles positivo y negativo deben estar conformes.")


@router.post("/api/ordenes/{id}/vista-previa.pdf", response_class=Response, summary="Generar PDF preliminar multipágina")
def generar_pdf_preliminar(
    id: int,
    payload: PreviewPDFRequest,
    current_user: Usuario = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Response:
    if current_user.rol and current_user.rol.nombre in ("ADMIN", "VISITANTE"):
        raise ProhibidoError("Este usuario no puede generar informes preliminares.")
    orden = db.query(Orden).filter(Orden.id_orden == id).first()
    if not orden or orden.id_usuario_autor != current_user.id_usuario:
        raise NoEncontradoError(f"Orden con id {id} no encontrada.")
    if orden.bloqueada or orden.estado_trabajo not in ("INCOMPLETO", "COMPLETO"):
        raise ConflictoError("La vista previa preliminar solo está disponible para órdenes en borrador.")
    if len(payload.valores) > 200:
        raise ValidacionError("Máximo 200 claves por petición.")
    _validar_control_factor_reumatoideo(payload.valores)

    alcance = obtener_parametros_alcance_orden(orden)
    params = {param.codigo: param for items in alcance.values() for param in items}
    for codigo, valor in payload.valores.items():
        param = params.get(codigo)
        if not param:
            raise ValidacionError(f"El parámetro '{codigo}' no pertenece al alcance de la orden.")
        if param.tipo_campo == "CALCULADO":
            raise ValidacionError(f"No se permite modificar el parámetro calculado '{codigo}'.")
        normalizar_y_validar_valor_entrada(param, valor)

    captura = evaluar_captura_orden(
        orden,
        valores_simulados=payload.valores,
        overrides_simulados=payload.rangos_override,
    )
    for estudio in captura["estudios"]:
        if payload.observaciones_estudios and estudio["codigo"] in payload.observaciones_estudios:
            estudio["observaciones"] = payload.observaciones_estudios[estudio["codigo"]]
        if estudio["codigo"] == "HEMOGRAMA" and payload.etiqueta_cayados:
            etiqueta = payload.etiqueta_cayados.strip()[:80]
            for seccion in estudio["secciones"]:
                for parametro in seccion["parametros"]:
                    if parametro["codigo"] in ("CAYADOS_PCT", "CAYADOS_ABS") and etiqueta:
                        parametro["nombre"] = etiqueta + (" (abs.)" if parametro["codigo"] == "CAYADOS_ABS" else "")

    paciente = orden.paciente
    edad = f"{orden.edad_anios} años" if orden.edad_anios is not None else (f"{orden.edad_meses} meses" if orden.edad_meses else "")
    nombre_completo = " ".join(filter(None, [paciente.nombres, paciente.apellido_paterno, paciente.apellido_materno]))
    firmante = current_user
    documento = {
        "aprobado": False,
        "folio": None,
        "numero_orden": orden.numero_orden_paciente,
        "numero_version": None,
        "publicado_en": None,
        "snapshot_sha256": None,
        "paciente": {
            "nombre_completo": nombre_completo,
            "ci": paciente.ci,
            "sexo_texto": "Masculino" if paciente.sexo == "M" else "Femenino" if paciente.sexo == "F" else "—",
            "edad": edad,
        },
        "orden": {
            "id_orden": orden.id_orden,
            "fecha_hora_toma_muestra": orden.fecha_hora_toma_muestra.isoformat() if orden.fecha_hora_toma_muestra else None,
            "fecha_solicitud": orden.fecha_solicitud.isoformat() if orden.fecha_solicitud else None,
            "medico_solicitante": orden.medico_solicitante,
            "pieza": orden.pieza,
            "observaciones": payload.observaciones_orden if payload.observaciones_orden is not None else orden.observaciones,
        },
        "firmante": {
            "nombre_completo": " ".join(filter(None, [firmante.nombres, firmante.apellido_paterno, firmante.apellido_materno])),
            "matricula": firmante.matricula_profesional,
        },
        "estudios": captura["estudios"],
    }
    pdf = generar_informe_pdf(documento)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="orden-{id}-preliminar.pdf"', "Cache-Control": "private, no-store, max-age=0"},
    )


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

    _validar_control_factor_reumatoideo(payload.valores)

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

    return evaluar_captura_orden(
        orden,
        valores_simulados=payload.valores,
        overrides_simulados=payload.rangos_override,
    )


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

    _validar_control_factor_reumatoideo(payload.valores)

    return guardar_resultados_orden(
        db,
        orden,
        payload.valores,
        current_user,
        rangos_override=payload.rangos_override,
        observaciones_estudios=payload.observaciones_estudios,
        observaciones_orden=payload.observaciones_orden,
        etiquetas_estudios=payload.etiquetas_estudios,
    )


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
        nombre_laboratorio=cfg.get("nombre_laboratorio", "LABORATORIO CLINICO METODISTA"),
        separador_decimal=cfg.get("separador_decimal", ","),
    )
