"""
Endpoints para la gestión de Órdenes en borrador (Fase 2).
PROMPT_FASE_2.md §8.3:
- POST /api/ordenes (solo BIOQUIMICO, 201)
- GET /api/ordenes?estado=&id_paciente=&q=&id_autor=&limit=&offset= (BIOQUIMICO, ADMIN)
- GET /api/ordenes/{id} (BIOQUIMICO autor, ADMIN auditado)
- PATCH /api/ordenes/{id} (solo BIOQUIMICO autor)
- DELETE /api/ordenes/{id} (descarte de borrador, solo autor, 204)
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import (
    obtener_ip_cliente,
    registrar_evento_seguridad,
    require_auth,
    require_bioquimico,
)
from app.api.pacientes import (
    comprobar_unicidad_ci,
    normalizar_ci,
    normalizar_ci_complemento,
    normalizar_texto,
    validar_ci_y_sin_ci,
    validar_fecha_nacimiento,
    validar_sexo,
)
from app.core.clock import ahora
from app.core.database import get_db
from app.core.errors import (
    ConflictoError,
    ConflictoVersionError,
    NoEncontradoError,
    OrdenDuplicadaEnCursoError,
    ProhibidoError,
    ValidacionError,
)
from app.models.catalog import Estudio, EstudioVersion, Parametro, Perfil
from app.models.order import (
    BorradorDescartado,
    Orden,
    OrdenEstudio,
    OrdenEstudioGrupo,
)
from app.models.patient import Paciente
from app.models.user import Usuario
from app.schemas.orden import (
    AdvertenciaSolapamiento,
    AutorResumen,
    EstudioItemResponse,
    OrdenCreate,
    OrdenCreadaResponse,
    OrdenListItem,
    OrdenListaResponse,
    OrdenResponse,
    OrdenUpdate,
    PacienteListaItem,
    PacienteResumenOrden,
    PerfilResumen,
)

router = APIRouter(prefix="/api/ordenes", tags=["Órdenes"])


def calcular_edad(fn: date, hoy: date) -> tuple[int, int]:
    """Calcula edad en años y meses cumplidos."""
    anios = hoy.year - fn.year
    meses = hoy.month - fn.month
    dias = hoy.day - fn.day
    if dias < 0:
        meses -= 1
    if meses < 0:
        anios -= 1
        meses += 12
    return max(0, anios), max(0, meses)


def serializar_orden(orden: Orden) -> OrdenResponse:
    """Construye el esquema OrdenResponse a partir del modelo ORM."""
    p = orden.paciente
    paciente_resumen = PacienteResumenOrden(
        id=p.id_paciente,
        ci=p.ci,
        ci_complemento=p.ci_complemento,
        nombres=p.nombres,
        apellido_paterno=p.apellido_paterno,
        apellido_materno=p.apellido_materno,
        sexo=p.sexo,
        fecha_nacimiento=p.fecha_nacimiento,
    )

    autor_resumen = AutorResumen(
        id=orden.autor.id_usuario if orden.autor else None,
        nombres=orden.autor.nombres if orden.autor else "",
        apellido_paterno=orden.autor.apellido_paterno if orden.autor else "",
    )

    perfil_resumen = (
        PerfilResumen(codigo=orden.perfil.codigo, nombre=orden.perfil.nombre)
        if orden.perfil
        else None
    )

    estudios_resp: list[EstudioItemResponse] = []
    for oe in orden.estudios:
        grupos_list = (
            [g.grupo for g in oe.grupos]
            if oe.estudio.seleccion_parcial
            else None
        )
        estudios_resp.append(
            EstudioItemResponse(
                codigo=oe.estudio.codigo,
                nombre=oe.estudio.nombre,
                grupos=grupos_list,
            )
        )

    return OrdenResponse(
        id=orden.id_orden,
        paciente=paciente_resumen,
        numero_orden_paciente=orden.numero_orden_paciente,
        autor=autor_resumen,
        perfil=perfil_resumen,
        origen_solicitud=orden.origen_solicitud,
        medico_solicitante=orden.medico_solicitante,
        pieza=orden.pieza,
        edad_anios=orden.edad_anios,
        edad_meses=orden.edad_meses,
        fecha_solicitud=orden.fecha_solicitud,
        fecha_hora_toma_muestra=orden.fecha_hora_toma_muestra,
        estado_trabajo=orden.estado_trabajo,
        bloqueada=orden.bloqueada,
        fila_version=orden.fila_version,
        estudios=estudios_resp,
        creado_en=orden.creado_en,
        actualizado_en=orden.actualizado_en,
    )


@router.post("", response_model=OrdenCreadaResponse, status_code=status.HTTP_201_CREATED)
def crear_orden(
    body: OrdenCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_bioquimico),
) -> OrdenCreadaResponse:
    """
    Crea una nueva orden en borrador.
    Soporta paciente existente o alta de paciente + orden en una sola transacción.
    Aplica D2-04 (detección de trabajo duplicado).
    """
    # 1. Exactamente uno entre id_paciente y paciente
    if (body.id_paciente is not None and body.paciente is not None) or (
        body.id_paciente is None and body.paciente is None
    ):
        raise ValidacionError("Debe proporcionar exactamente uno de 'id_paciente' o 'paciente'.")

    now = ahora()
    hoy = now.date()

    # 2. Cargar o registrar paciente
    if body.id_paciente is not None:
        paciente = (
            db.query(Paciente)
            .filter(Paciente.id_paciente == body.id_paciente)
            .with_for_update()
            .first()
        )
        if not paciente:
            raise NoEncontradoError(f"Paciente con id {body.id_paciente} no encontrado.")
    else:
        # Alta de paciente en la misma transacción
        p_data = body.paciente
        assert p_data is not None

        nombres = normalizar_texto(p_data.nombres)
        apellido_paterno = normalizar_texto(p_data.apellido_paterno)
        apellido_materno = normalizar_texto(p_data.apellido_materno)
        ci = normalizar_ci(p_data.ci)
        ci_complemento = normalizar_ci_complemento(p_data.ci_complemento)
        telefono = normalizar_texto(p_data.telefono)
        sexo = validar_sexo(p_data.sexo)

        if not nombres:
            raise ValidacionError("El campo nombres es obligatorio para el paciente.")
        if len(nombres) > 100:
            raise ValidacionError("El campo nombres no puede superar 100 caracteres.")
        if not apellido_paterno:
            raise ValidacionError("El campo apellido_paterno es obligatorio para el paciente.")
        if len(apellido_paterno) > 100:
            raise ValidacionError("El campo apellido_paterno no puede superar 100 caracteres.")
        if apellido_materno and len(apellido_materno) > 100:
            raise ValidacionError("El campo apellido_materno no puede superar 100 caracteres.")
        if ci_complemento and len(ci_complemento) > 5:
            raise ValidacionError("El campo ci_complemento no puede superar 5 caracteres.")
        if telefono and len(telefono) > 30:
            raise ValidacionError("El campo telefono no puede superar 30 caracteres.")

        validar_ci_y_sin_ci(ci=ci, sin_ci=p_data.sin_ci)
        if p_data.sin_ci and ci_complemento is not None:
            raise ValidacionError("Un paciente sin CI no puede tener complemento de CI.")

        validar_fecha_nacimiento(p_data.fecha_nacimiento)
        comprobar_unicidad_ci(db=db, ci=ci, ci_complemento=ci_complemento)

        paciente = Paciente(
            ci=ci,
            ci_complemento=ci_complemento,
            sin_ci=p_data.sin_ci,
            nombres=nombres,
            apellido_paterno=apellido_paterno,
            apellido_materno=apellido_materno,
            fecha_nacimiento=p_data.fecha_nacimiento,
            sexo=sexo,
            telefono=telefono,
            creado_por=current_user.id_usuario,
            creado_en=now,
            actualizado_en=now,
        )
        db.add(paciente)
        db.flush()

    # 3. Validar estudios
    if not body.estudios or len(body.estudios) == 0:
        raise ValidacionError("La orden debe incluir al menos un estudio.")

    codigos_vistos = set()
    estudios_procesados: list[tuple[Estudio, EstudioVersion, Optional[list[str]]]] = []

    for item in body.estudios:
        if item.codigo in codigos_vistos:
            raise ValidacionError(f"Estudio repetido en la solicitud: '{item.codigo}'.")
        codigos_vistos.add(item.codigo)

        estudio_db = (
            db.query(Estudio)
            .filter(Estudio.codigo == item.codigo)
            .first()
        )
        if not estudio_db or not estudio_db.activo:
            raise ValidacionError(f"El estudio '{item.codigo}' no existe o no está activo.")

        version_activa = (
            db.query(EstudioVersion)
            .filter(
                EstudioVersion.id_estudio == estudio_db.id_estudio,
                EstudioVersion.activa == True,
            )
            .first()
        )
        if not version_activa:
            raise ValidacionError(f"El estudio '{item.codigo}' no posee una versión activa en el catálogo.")

        if estudio_db.seleccion_parcial:
            if not item.grupos or len(item.grupos) == 0:
                raise ValidacionError(f"El estudio '{item.codigo}' requiere especificar al menos un grupo.")

            grupos_set = set()
            for g in item.grupos:
                if g in grupos_set:
                    raise ValidacionError(f"Grupo duplicado en estudio '{item.codigo}': '{g}'.")
                grupos_set.add(g)

            params_version = (
                db.query(Parametro)
                .filter(Parametro.id_estudio_version == version_activa.id_estudio_version)
                .all()
            )
            grupos_validos = {p.grupo for p in params_version if p.grupo}
            for g in item.grupos:
                if g not in grupos_validos:
                    raise ValidacionError(f"El grupo '{g}' no existe en el estudio '{item.codigo}'.")

            estudios_procesados.append((estudio_db, version_activa, item.grupos))
        else:
            if item.grupos is not None and len(item.grupos) > 0:
                raise ValidacionError(f"El estudio '{item.codigo}' no admite selección por grupos.")
            estudios_procesados.append((estudio_db, version_activa, None))

    # 4. Validar perfil opcional
    id_perfil: Optional[int] = None
    if body.perfil:
        perfil_db = db.query(Perfil).filter(Perfil.codigo == body.perfil).first()
        if not perfil_db:
            raise ValidacionError(f"El perfil '{body.perfil}' no existe.")
        id_perfil = perfil_db.id_perfil

    # 5. Edad (D2-08)
    if paciente.fecha_nacimiento is not None:
        edad_anios, edad_meses = calcular_edad(paciente.fecha_nacimiento, hoy)
    else:
        if body.edad_anios is None:
            raise ValidacionError("edad_anios es obligatorio cuando el paciente no tiene fecha de nacimiento.")
        if body.edad_anios < 0 or body.edad_anios > 130:
            raise ValidacionError("edad_anios debe estar entre 0 y 130.")
        edad_anios = body.edad_anios
        edad_meses = body.edad_meses if body.edad_meses is not None else 0
        if edad_meses < 0 or edad_meses > 11:
            raise ValidacionError("edad_meses debe estar entre 0 y 11.")

    # 6. Validar toma de muestra
    if body.fecha_hora_toma_muestra is not None:
        limite_tolerancia = now + timedelta(minutes=5)
        toma_tz = (
            body.fecha_hora_toma_muestra.replace(tzinfo=limite_tolerancia.tzinfo)
            if body.fecha_hora_toma_muestra.tzinfo is None
            else body.fecha_hora_toma_muestra
        )
        if toma_tz > limite_tolerancia:
            raise ValidacionError("La fecha y hora de toma de muestra no puede ser futura (> 5 minutos).")

    if body.origen_solicitud and len(body.origen_solicitud) > 100:
        raise ValidacionError("El campo origen_solicitud no puede superar 100 caracteres.")
    if body.medico_solicitante and len(body.medico_solicitante) > 150:
        raise ValidacionError("El campo medico_solicitante no puede superar 150 caracteres.")
    if body.pieza and len(body.pieza) > 100:
        raise ValidacionError("El campo pieza no puede superar 100 caracteres.")

    # 7. Detección de trabajo duplicado (D2-04)
    conjunto_nuevo: set[str] = set()
    for est, _ver, grps in estudios_procesados:
        if est.seleccion_parcial and grps:
            for g in grps:
                conjunto_nuevo.add(f"{est.codigo}:{g}")
        else:
            conjunto_nuevo.add(est.codigo)

    borradores_ajenos = (
        db.query(Orden)
        .filter(
            Orden.id_paciente == paciente.id_paciente,
            Orden.estado_trabajo.in_(["INCOMPLETO", "COMPLETO"]),
            Orden.bloqueada == False,
            Orden.id_usuario_autor != current_user.id_usuario,
        )
        .all()
    )

    # Evaluar si la nueva orden es subconjunto de UN borrador ajeno
    for otro in borradores_ajenos:
        conjunto_otro: set[str] = set()
        for oe in otro.estudios:
            if oe.estudio.seleccion_parcial:
                for oeg in oe.grupos:
                    conjunto_otro.add(f"{oe.estudio.codigo}:{oeg.grupo}")
            else:
                conjunto_otro.add(oe.estudio.codigo)

        if conjunto_nuevo.issubset(conjunto_otro):
            detalle = {
                "autor": {
                    "nombres": otro.autor.nombres,
                    "apellido_paterno": otro.autor.apellido_paterno,
                },
                "estudios": [est.codigo for est, _ver, _grps in estudios_procesados],
            }
            raise OrdenDuplicadaEnCursoError(
                "Existe una orden en curso de otro bioquímico que cubre los estudios solicitados.",
                detalle=detalle,
            )

    # Evaluar advertencias de solapamiento parcial
    advertencias: list[AdvertenciaSolapamiento] = []
    for otro in borradores_ajenos:
        conjunto_otro = set()
        for oe in otro.estudios:
            if oe.estudio.seleccion_parcial:
                for oeg in oe.grupos:
                    conjunto_otro.add(f"{oe.estudio.codigo}:{oeg.grupo}")
            else:
                conjunto_otro.add(oe.estudio.codigo)

        interseccion = conjunto_nuevo.intersection(conjunto_otro)
        if len(interseccion) > 0:
            codigos_solapados = sorted({item.split(":")[0] for item in interseccion})
            autor_res = AutorResumen(
                nombres=otro.autor.nombres,
                apellido_paterno=otro.autor.apellido_paterno,
            )
            advertencias.append(
                AdvertenciaSolapamiento(
                    tipo="SOLAPAMIENTO",
                    autor=autor_res,
                    estudios=codigos_solapados,
                )
            )

    # 8. Número correlativo por paciente (D2-10)
    max_num = (
        db.query(func.coalesce(func.max(Orden.numero_orden_paciente), 0))
        .filter(Orden.id_paciente == paciente.id_paciente)
        .scalar()
    )
    numero_orden_paciente = max_num + 1

    # 9. Inserción de orden y registros hijos
    orden = Orden(
        id_paciente=paciente.id_paciente,
        numero_orden_paciente=numero_orden_paciente,
        id_usuario_autor=current_user.id_usuario,
        id_perfil=id_perfil,
        origen_solicitud=normalizar_texto(body.origen_solicitud),
        medico_solicitante=normalizar_texto(body.medico_solicitante),
        pieza=normalizar_texto(body.pieza),
        edad_anios=edad_anios,
        edad_meses=edad_meses,
        fecha_solicitud=hoy,
        fecha_hora_toma_muestra=body.fecha_hora_toma_muestra,
        estado_trabajo="INCOMPLETO",
        bloqueada=False,
        fila_version=1,
        creado_en=now,
        actualizado_en=now,
    )
    db.add(orden)
    db.flush()

    for est, ver, grps in estudios_procesados:
        oe = OrdenEstudio(
            id_orden=orden.id_orden,
            id_estudio=est.id_estudio,
            id_estudio_version=ver.id_estudio_version,
        )
        db.add(oe)
        db.flush()

        if est.seleccion_parcial and grps:
            for g in grps:
                oeg = OrdenEstudioGrupo(
                    id_orden_estudio=oe.id_orden_estudio,
                    grupo=g,
                )
                db.add(oeg)

    db.commit()
    db.refresh(orden)

    return OrdenCreadaResponse(
        orden=serializar_orden(orden),
        advertencias=advertencias,
    )


@router.get("", response_model=OrdenListaResponse)
def listar_ordenes(
    request: Request,
    estado: Optional[str] = Query(None, description="Filtro por estado de trabajo"),
    id_paciente: Optional[int] = Query(None, description="Filtro por ID de paciente"),
    q: Optional[str] = Query(None, description="Búsqueda en datos del paciente"),
    id_autor: Optional[int] = Query(None, description="Filtro por ID de autor (solo ADMIN)"),
    limit: int = Query(25, description="Cantidad máxima de registros (1-100)"),
    offset: int = Query(0, description="Desplazamiento (>= 0)"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> OrdenListaResponse:
    """
    Lista órdenes con paginación y filtros.
    BIOQUIMICO: solo sus órdenes.
    ADMIN: todas las órdenes, audita ADMIN_VE_PRIVADO si hay resultados.
    """
    if limit < 1 or limit > 100:
        raise ValidacionError("El parámetro limit debe estar entre 1 y 100.")
    if offset < 0:
        raise ValidacionError("El parámetro offset debe ser mayor o igual a 0.")

    if estado and estado not in ("INCOMPLETO", "COMPLETO", "PUBLICADA"):
        raise ValidacionError(f"Estado '{estado}' inválido.")

    query = db.query(Orden)

    es_admin = current_user.rol and current_user.rol.nombre == "ADMIN"

    if es_admin:
        if id_autor is not None:
            query = query.filter(Orden.id_usuario_autor == id_autor)
        if estado:
            query = query.filter(Orden.estado_trabajo == estado)
    else:
        query = query.filter(Orden.id_usuario_autor == current_user.id_usuario)
        if estado:
            query = query.filter(Orden.estado_trabajo == estado)
        else:
            query = query.filter(Orden.estado_trabajo.in_(["INCOMPLETO", "COMPLETO"]))

    if id_paciente is not None:
        query = query.filter(Orden.id_paciente == id_paciente)

    if q and q.strip():
        termino = f"%{q.strip().lower()}%"
        query = query.join(Paciente, Orden.id_paciente == Paciente.id_paciente)
        query = query.filter(
            or_(
                func.lower(func.coalesce(Paciente.ci, "")).like(termino),
                func.lower(Paciente.nombres).like(termino),
                func.lower(Paciente.apellido_paterno).like(termino),
                func.lower(func.coalesce(Paciente.apellido_materno, "")).like(termino),
            )
        )

    query = query.order_by(Orden.creado_en.desc(), Orden.id_orden.desc())

    total = query.count()
    ordenes = query.offset(offset).limit(limit).all()

    # Auditoría para ADMIN si la respuesta incluye >= 1 orden (§8.3 / D2-06)
    if es_admin and len(ordenes) > 0:
        filtros = {
            "estado": estado,
            "id_paciente": id_paciente,
            "q": q,
            "id_autor": id_autor,
        }
        registrar_evento_seguridad(
            db=db,
            accion="ADMIN_VE_PRIVADO",
            id_usuario=current_user.id_usuario,
            id_objetivo=None,
            ip=obtener_ip_cliente(request),
            detalle={"recurso": "ordenes", "filtros": filtros, "cantidad": len(ordenes)},
        )
        db.commit()

    items: list[OrdenListItem] = []
    for o in ordenes:
        paciente_item = PacienteListaItem(
            id=o.paciente.id_paciente,
            ci=o.paciente.ci,
            nombres=o.paciente.nombres,
            apellido_paterno=o.paciente.apellido_paterno,
            apellido_materno=o.paciente.apellido_materno,
        )
        codigos_estudios = [oe.estudio.codigo for oe in o.estudios]
        items.append(
            OrdenListItem(
                id=o.id_orden,
                paciente=paciente_item,
                numero_orden_paciente=o.numero_orden_paciente,
                estado_trabajo=o.estado_trabajo,
                bloqueada=o.bloqueada,
                estudios=codigos_estudios,
                fecha_solicitud=o.fecha_solicitud,
                creado_en=o.creado_en,
            )
        )

    return OrdenListaResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{id}", response_model=OrdenResponse)
def obtener_orden(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> OrdenResponse:
    """
    Obtiene el detalle completo de una orden.
    Autor o ADMIN. Cualquier otro BIOQUIMICO recibe 404 (D2-07).
    ADMIN sobre orden ajena registra evento ADMIN_VE_PRIVADO.
    """
    orden = db.query(Orden).filter(Orden.id_orden == id).first()
    if not orden:
        raise NoEncontradoError(f"Orden con id {id} no encontrada.")

    es_admin = current_user.rol and current_user.rol.nombre == "ADMIN"
    es_autor = orden.id_usuario_autor == current_user.id_usuario

    if not es_admin and not es_autor:
        # D2-07: Una orden ajena para un BIOQUIMICO responde 404 para no revelar su existencia
        raise NoEncontradoError(f"Orden con id {id} no encontrada.")

    if es_admin and not es_autor:
        registrar_evento_seguridad(
            db=db,
            accion="ADMIN_VE_PRIVADO",
            id_usuario=current_user.id_usuario,
            id_objetivo=orden.id_usuario_autor,
            ip=obtener_ip_cliente(request),
            detalle={"recurso": "orden", "id_orden": orden.id_orden},
        )
        db.commit()

    return serializar_orden(orden)


@router.patch("/{id}", response_model=OrdenResponse)
def actualizar_orden(
    id: int,
    body: OrdenUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> OrdenResponse:
    """
    Edita la cabecera de una orden en borrador.
    Solo el autor (ADMIN recibe 403, otro BIOQUIMICO 404).
    Requiere fila_version (bloqueo optimista, 409 CONFLICTO_VERSION).
    """
    es_admin = current_user.rol and current_user.rol.nombre == "ADMIN"
    if es_admin:
        raise ProhibidoError("El administrador no puede modificar órdenes.")

    orden = db.query(Orden).filter(Orden.id_orden == id).first()
    if not orden or orden.id_usuario_autor != current_user.id_usuario:
        raise NoEncontradoError(f"Orden con id {id} no encontrada.")

    if orden.estado_trabajo == "PUBLICADA" or orden.bloqueada:
        raise ConflictoError("No se puede editar una orden publicada o bloqueada.")

    # Control de concurrencia optimista inicial
    if body.fila_version != orden.fila_version:
        raise ConflictoVersionError("Conflicto de versión optimista: la orden fue modificada.")

    campos_enviados = body.model_dump(exclude_unset=True)
    update_values: dict[str, Any] = {}

    # Validaciones de edad
    if orden.paciente.fecha_nacimiento is not None:
        if "edad_anios" in campos_enviados or "edad_meses" in campos_enviados:
            raise ValidacionError(
                "No se puede editar la edad de un paciente con fecha de nacimiento registrada."
            )
    else:
        if "edad_anios" in campos_enviados:
            if body.edad_anios is None or body.edad_anios < 0 or body.edad_anios > 130:
                raise ValidacionError("edad_anios debe estar entre 0 y 130.")
            update_values["edad_anios"] = body.edad_anios
        if "edad_meses" in campos_enviados:
            if body.edad_meses is None or body.edad_meses < 0 or body.edad_meses > 11:
                raise ValidacionError("edad_meses debe estar entre 0 y 11.")
            update_values["edad_meses"] = body.edad_meses

    if "fecha_hora_toma_muestra" in campos_enviados:
        if body.fecha_hora_toma_muestra is not None:
            now = ahora()
            limite = now + timedelta(minutes=5)
            toma_tz = (
                body.fecha_hora_toma_muestra.replace(tzinfo=limite.tzinfo)
                if body.fecha_hora_toma_muestra.tzinfo is None
                else body.fecha_hora_toma_muestra
            )
            if toma_tz > limite:
                raise ValidacionError("La fecha y hora de toma de muestra no puede ser futura (> 5 minutos).")
        update_values["fecha_hora_toma_muestra"] = body.fecha_hora_toma_muestra

    if "origen_solicitud" in campos_enviados:
        val = normalizar_texto(body.origen_solicitud)
        if val and len(val) > 100:
            raise ValidacionError("origen_solicitud no puede superar 100 caracteres.")
        update_values["origen_solicitud"] = val

    if "medico_solicitante" in campos_enviados:
        val = normalizar_texto(body.medico_solicitante)
        if val and len(val) > 150:
            raise ValidacionError("medico_solicitante no puede superar 150 caracteres.")
        update_values["medico_solicitante"] = val

    if "pieza" in campos_enviados:
        val = normalizar_texto(body.pieza)
        if val and len(val) > 100:
            raise ValidacionError("pieza no puede superar 100 caracteres.")
        update_values["pieza"] = val

    # Incrementar fila_version y actualizar marca temporal atómicamente en la sentencia UPDATE
    update_values["fila_version"] = Orden.fila_version + 1
    update_values["actualizado_en"] = ahora()

    filas_afectadas = (
        db.query(Orden)
        .filter(
            Orden.id_orden == id,
            Orden.fila_version == body.fila_version,
        )
        .update(update_values, synchronize_session=False)
    )

    if filas_afectadas == 0:
        db.rollback()
        raise ConflictoVersionError("Conflicto de versión optimista: la orden fue modificada.")

    db.commit()
    db.expire_all()
    orden_actualizada = db.query(Orden).filter(Orden.id_orden == id).first()

    return serializar_orden(orden_actualizada)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def descartar_orden(
    id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> Response:
    """
    Descarta un borrador de orden (eliminación física con registro en borradores_descartados).
    Solo el autor. ADMIN recibe 403, otro BIOQUIMICO 404. Orden PUBLICADA recibe 409 CONFLICTO.
    """
    es_admin = current_user.rol and current_user.rol.nombre == "ADMIN"
    if es_admin:
        raise ProhibidoError("El administrador no puede descartar órdenes.")

    orden = db.query(Orden).filter(Orden.id_orden == id).first()
    if not orden or orden.id_usuario_autor != current_user.id_usuario:
        raise NoEncontradoError(f"Orden con id {id} no encontrada.")

    if orden.estado_trabajo == "PUBLICADA":
        raise ConflictoError("No se puede descartar una orden publicada.")

    now = ahora()
    descarte = BorradorDescartado(
        id_orden=orden.id_orden,
        id_paciente=orden.id_paciente,
        id_usuario=current_user.id_usuario,
        estado_trabajo=orden.estado_trabajo,
        estaba_bloqueada=orden.bloqueada,
        folio_causa=None,
        descartado_en=now,
    )
    db.add(descarte)
    db.delete(orden)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
