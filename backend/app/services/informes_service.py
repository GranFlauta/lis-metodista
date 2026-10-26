"""
Servicio central de Informes Oficiales, Publicación, Versiones V1-V3 y Papelera Lógica Auditada.
Alineado con docs/DECISIONES.md §3, §4, §8 y db/init/001_schema.sql.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from sqlalchemy import text, desc, or_
from sqlalchemy.orm import Session

from app.core.clock import ahora
from app.core.errors import (
    ConflictoError,
    NoEncontradoError,
    ProhibidoError,
    ValidacionError,
)
from app.models.catalog import Parametro
from app.models.order import Orden
from app.models.report import Folio, Informe, InformeEvento, Delegacion
from app.models.user import Usuario
from app.services.evaluacion_service import evaluar_captura_orden


def calcular_hash_snapshot(snapshot: dict[str, Any]) -> str:
    """Calcula el hash SHA-256 canónico del snapshot JSON (claves ordenadas, UTF-8)."""
    canon_bytes = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canon_bytes).hexdigest()


def publicar_orden(
    db: Session,
    id_orden: int,
    current_user: Usuario,
    justificativo_urgencia: str | None = None,
) -> Informe:
    """
    Publica una orden completada con folio oficial secuencial inmutable.
    - Valida permisos (autor, colaborador delegado o urgencia justificada).
    - Valida obligatoriedad de observaciones finales.
    - Valida que no queden valores por defecto sin confirmar ni pendientes.
    - Reserva folio atómicamente con `siguiente_folio()`.
    - Congela snapshot JSON inmutable y registra evento append-only PUBLICACION / URGENCIA.
    """
    es_admin = current_user.rol and current_user.rol.nombre == "ADMIN"
    if es_admin:
        raise ProhibidoError("El administrador no puede publicar órdenes clínicas.")

    orden = db.query(Orden).filter(Orden.id_orden == id_orden).with_for_update().first()
    if not orden:
        raise NoEncontradoError(f"Orden con id {id_orden} no encontrada.")

    if orden.bloqueada:
        raise ConflictoError("La orden se encuentra bloqueada por otra operación o concurrencia.")

    if orden.estado_trabajo == "PUBLICADA":
        raise ConflictoError("Esta orden ya ha sido publicada oficialmente.")

    # 1. Comprobar permisos
    es_autor = (orden.id_usuario_autor == current_user.id_usuario)
    es_urgencia = False

    if not es_autor:
        # Verificar si es colaborador con delegación aceptada
        delegacion = (
            db.query(Delegacion)
            .filter(
                Delegacion.id_orden == id_orden,
                Delegacion.id_usuario_colaborador == current_user.id_usuario,
                Delegacion.estado == "ACEPTADA",
            )
            .first()
        )
        if not delegacion:
            # Si no es autor ni colaborador delegado, solo puede publicar bajo modalidad de urgencia con justificativo
            if not justificativo_urgencia or len(justificativo_urgencia.strip()) < 5:
                raise ProhibidoError(
                    "Solo el autor original o un colaborador con delegación aceptada puede publicar la orden. "
                    "Para publicar por urgencia debe incluir un justificativo de al menos 5 caracteres."
                )
            es_urgencia = True

    # 2. Comprobar que tenga estudios
    if not orden.estudios or len(orden.estudios) == 0:
        raise ValidacionError("La orden no tiene estudios a realizar.")

    # 3. Observaciones finales de la orden son obligatorias para publicar (PLAN_DE_ACCION_Y_DIAGNOSTICO.md §1.2 B.5 y §3)
    if not orden.observaciones or not orden.observaciones.strip():
        raise ValidacionError("Las observaciones finales del informe son obligatorias para publicar el documento oficial.")

    # 4. Construir y validar captura de resultados
    captura = evaluar_captura_orden(orden)
    completitud = captura["completitud"]

    if completitud["sin_confirmar"]:
        nombres_sin_conf = ", ".join(completitud["sin_confirmar"])
        raise ValidacionError(f"Existen valores por defecto pendientes de confirmación: {nombres_sin_conf}. Debe confirmarlos antes de publicar.")

    if completitud["pendientes"]:
        nombres_pend = ", ".join(completitud["pendientes"])
        raise ValidacionError(f"Faltan parámetros obligatorios por capturar: {nombres_pend}.")

    if completitud["errores"]:
        nombres_err = ", ".join(completitud["errores"])
        raise ValidacionError(f"Existen errores de validación en los resultados: {nombres_err}.")

    # 5. Generar Snapshot inmutable
    now = ahora()
    paciente = orden.paciente
    firmante = orden.autor
    publicador = current_user

    snapshot: dict[str, Any] = {
        "version_schema": 1,
        "fecha_publicacion": now.isoformat(),
        "paciente": {
            "id_paciente": paciente.id_paciente,
            "ci": paciente.ci,
            "nombres": paciente.nombres,
            "apellido_paterno": paciente.apellido_paterno,
            "apellido_materno": paciente.apellido_materno,
            "sexo": paciente.sexo,
            "fecha_nacimiento": paciente.fecha_nacimiento.isoformat() if paciente.fecha_nacimiento else None,
            "edad_anios": orden.edad_anios,
            "edad_meses": orden.edad_meses,
        },
        "orden": {
            "id_orden": orden.id_orden,
            "numero_orden_paciente": orden.numero_orden_paciente,
            "fecha_solicitud": orden.fecha_solicitud.isoformat() if orden.fecha_solicitud else None,
            "fecha_hora_toma_muestra": orden.fecha_hora_toma_muestra.isoformat() if orden.fecha_hora_toma_muestra else None,
            "medico_solicitante": orden.medico_solicitante,
            "origen_solicitud": orden.origen_solicitud,
            "pieza": orden.pieza,
            "observaciones": orden.observaciones,
        },
        "firmante": {
            "id_usuario": firmante.id_usuario,
            "usuario": firmante.usuario,
            "nombres": firmante.nombres,
            "apellido_paterno": firmante.apellido_paterno,
            "apellido_materno": firmante.apellido_materno,
            "matricula_profesional": firmante.matricula_profesional,
        },
        "publicador": {
            "id_usuario": publicador.id_usuario,
            "usuario": publicador.usuario,
            "nombres": publicador.nombres,
            "apellido_paterno": publicador.apellido_paterno,
        },
        "estudios": captura["estudios"],
        "es_urgencia": es_urgencia,
        "justificativo": justificativo_urgencia.strip() if (es_urgencia and justificativo_urgencia) else None,
    }

    snapshot_sha256 = calcular_hash_snapshot(snapshot)

    # 6. Reservar folio atómico de PostgreSQL
    folio = db.execute(text("SELECT siguiente_folio()")).scalar_one()

    # 7. Crear fila de informe oficial
    informe = Informe(
        folio=folio,
        numero_version=1,
        id_orden=orden.id_orden,
        estado="VIGENTE",
        id_usuario_firmante=firmante.id_usuario,
        id_usuario_publicador=publicador.id_usuario,
        es_urgencia=es_urgencia,
        justificativo=justificativo_urgencia.strip() if (es_urgencia and justificativo_urgencia) else None,
        snapshot_json=snapshot,
        snapshot_sha256=snapshot_sha256,
        publicado_en=now,
    )
    db.add(informe)
    db.flush()

    # 8. Registrar evento de auditoría append-only
    accion_evento = "URGENCIA" if es_urgencia else "PUBLICACION"
    evento = InformeEvento(
        folio=folio,
        numero_version=1,
        id_usuario=publicador.id_usuario,
        accion=accion_evento,
        justificativo=justificativo_urgencia.strip() if (es_urgencia and justificativo_urgencia) else None,
        detalle={"id_orden": orden.id_orden, "numero_version": 1},
        creado_en=now,
    )
    db.add(evento)

    # 9. Actualizar estado de la orden
    orden.estado_trabajo = "PUBLICADA"
    orden.actualizado_en = now

    db.commit()
    db.refresh(informe)
    return informe


def mover_informe_a_papelera(
    db: Session,
    folio: str,
    current_user: Usuario,
    justificativo: str,
) -> Informe:
    """
    Envía un informe oficial a la papelera lógica con justificación obligatoria.
    - Cumple regla de negocio D-73: 'solo el firmante, justificativo obligatorio. El folio se va con el informe y no se reasigna.'
    - Cumple inmutabilidad: el trigger de BD permite cambiar estado a PAPELERA sin tocar el snapshot.
    """
    if not justificativo or len(justificativo.strip()) < 5:
        raise ValidacionError("El justificativo para enviar el informe a la papelera es obligatorio (mínimo 5 caracteres).")

    informe = (
        db.query(Informe)
        .filter(Informe.folio == folio, Informe.estado.in_(["VIGENTE", "RECICLAJE"]))
        .first()
    )
    if not informe:
        # Verificar si ya está en papelera
        inf_pap = db.query(Informe).filter(Informe.folio == folio, Informe.estado == "PAPELERA").first()
        if inf_pap:
            raise ConflictoError(f"El informe {folio} ya se encuentra en la papelera.")
        raise NoEncontradoError(f"Informe {folio} no encontrado o no está en un estado elegible para papelera.")

    if informe.id_usuario_firmante != current_user.id_usuario:
        raise ProhibidoError("Solo el bioquímico firmante original del informe puede enviarlo a la papelera.")

    now = ahora()
    informe.estado = "PAPELERA"

    # Registrar evento de auditoría obligatorio
    evento = InformeEvento(
        folio=folio,
        numero_version=informe.numero_version,
        id_usuario=current_user.id_usuario,
        accion="PAPELERA",
        justificativo=justificativo.strip(),
        detalle={"estado_anterior": informe.estado, "numero_version": informe.numero_version},
        creado_en=now,
    )
    db.add(evento)
    db.commit()
    db.refresh(informe)
    return informe


def restaurar_informe_de_papelera(
    db: Session,
    folio: str,
    current_user: Usuario,
    justificativo: str,
) -> Informe:
    """
    Restaura un informe de la papelera pasando a estado 'RECICLAJE'.
    - Cumple regla de negocio D-74: 'Restaurar -> RECICLAJE, conserva folio; se puede ver el PDF pero la impresión queda bloqueada.'
    - Solo el firmante puede restaurarlo, con justificativo obligatorio.
    """
    if not justificativo or len(justificativo.strip()) < 5:
        raise ValidacionError("El justificativo para restaurar el informe es obligatorio (mínimo 5 caracteres).")

    informe = (
        db.query(Informe)
        .filter(Informe.folio == folio, Informe.estado == "PAPELERA")
        .first()
    )
    if not informe:
        raise NoEncontradoError(f"Informe {folio} no encontrado en la papelera.")

    if informe.id_usuario_firmante != current_user.id_usuario:
        raise ProhibidoError("Solo el bioquímico firmante original del informe puede restaurarlo.")

    now = ahora()
    informe.estado = "RECICLAJE"

    evento = InformeEvento(
        folio=folio,
        numero_version=informe.numero_version,
        id_usuario=current_user.id_usuario,
        accion="RESTAURACION",
        justificativo=justificativo.strip(),
        detalle={"numero_version": informe.numero_version},
        creado_en=now,
    )
    db.add(evento)
    db.commit()
    db.refresh(informe)
    return informe


def crear_nueva_version_informe(
    db: Session,
    folio: str,
    current_user: Usuario,
    justificativo: str,
    actualizaciones_estudios: dict[str, Any] | None = None,
) -> Informe:
    """
    Crea una nueva versión oficial (V1 -> V2, V2 -> V3) para un informe existente.
    - Cumple D-70: solo el firmante, justificativo obligatorio.
    - Máximo 3 versiones (V4 no existe por CHECK de base de datos).
    - Desplaza la versión previa en la misma transacción antes de insertar la nueva.
    """
    if not justificativo or len(justificativo.strip()) < 5:
        raise ValidacionError("El justificativo para emitir una nueva versión es obligatorio (mínimo 5 caracteres).")

    informe_actual = (
        db.query(Informe)
        .filter(Informe.folio == folio, Informe.estado == "VIGENTE")
        .first()
    )
    if not informe_actual:
        raise NoEncontradoError(f"No se encontró una versión VIGENTE para el folio {folio}.")

    if informe_actual.id_usuario_firmante != current_user.id_usuario:
        raise ProhibidoError("Solo el bioquímico firmante original puede crear una nueva versión de este informe.")

    if informe_actual.numero_version >= 3:
        raise ConflictoError(
            "Se ha alcanzado el límite máximo de 3 versiones para este folio (D-71). "
            "Si requiere modificar este informe, debe enviarlo a la papelera con justificativo y crear un nuevo informe."
        )

    nueva_version_num = informe_actual.numero_version + 1
    now = ahora()

    # Desplazar versión previa
    informe_actual.estado = "DESPLAZADO"
    db.flush()

    # Clonar snapshot base y actualizar fecha y versión
    nuevo_snapshot = dict(informe_actual.snapshot_json)
    nuevo_snapshot["numero_version"] = nueva_version_num
    nuevo_snapshot["fecha_edicion"] = now.isoformat()
    nuevo_snapshot["justificativo_version"] = justificativo.strip()

    if actualizaciones_estudios and "estudios" in actualizaciones_estudios:
        nuevo_snapshot["estudios"] = actualizaciones_estudios["estudios"]

    nuevo_sha256 = calcular_hash_snapshot(nuevo_snapshot)

    nuevo_informe = Informe(
        folio=folio,
        numero_version=nueva_version_num,
        id_orden=informe_actual.id_orden,
        estado="VIGENTE",
        id_usuario_firmante=informe_actual.id_usuario_firmante,
        id_usuario_publicador=current_user.id_usuario,
        es_urgencia=False,
        justificativo=justificativo.strip(),
        snapshot_json=nuevo_snapshot,
        snapshot_sha256=nuevo_sha256,
        publicado_en=now,
    )
    db.add(nuevo_informe)
    db.flush()

    accion_evento = f"EDICION_V{nueva_version_num}"
    evento = InformeEvento(
        folio=folio,
        numero_version=nueva_version_num,
        id_usuario=current_user.id_usuario,
        accion=accion_evento,
        justificativo=justificativo.strip(),
        detalle={"version_previa": informe_actual.numero_version, "version_nueva": nueva_version_num},
        creado_en=now,
    )
    db.add(evento)

    db.commit()
    db.refresh(nuevo_informe)
    return nuevo_informe


def listar_informes(
    db: Session,
    q: str | None = None,
    estado: str = "VIGENTE",
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Informe]:
    """Lista informes aplicando filtros de búsqueda por folio, paciente o fechas."""
    query = db.query(Informe).join(Informe.orden).join(Orden.paciente)

    if estado:
        query = query.filter(Informe.estado == estado)

    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                Informe.folio.ilike(term),
                Orden.paciente.has(text("LOWER(nombres) LIKE :t OR LOWER(apellido_paterno) LIKE :t OR ci LIKE :t").bindparams(t=term)),
            )
        )

    if fecha_desde:
        query = query.filter(Informe.publicado_en >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Informe.publicado_en <= fecha_hasta)

    return query.order_by(desc(Informe.publicado_en)).offset(offset).limit(limit).all()


def listar_papelera(
    db: Session,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Devuelve los informes en PAPELERA o RECICLAJE con su último motivo y evento auditado."""
    informes = (
        db.query(Informe)
        .filter(Informe.estado.in_(["PAPELERA", "RECICLAJE"]))
        .order_by(desc(Informe.publicado_en))
        .offset(offset)
        .limit(limit)
        .all()
    )

    resultado = []
    for inf in informes:
        # Obtener el último evento de PAPELERA o RESTAURACION
        ultimo_ev = (
            db.query(InformeEvento)
            .filter(
                InformeEvento.folio == inf.folio,
                InformeEvento.accion.in_(["PAPELERA", "RESTAURACION"]),
            )
            .order_by(desc(InformeEvento.creado_en))
            .first()
        )

        pac = inf.orden.paciente if inf.orden else None
        pac_nombre = f"{pac.nombres} {pac.apellido_paterno}".strip() if pac else "Desconocido"
        firm = inf.firmante
        firm_nombre = f"{firm.nombres} {firm.apellido_paterno}".strip() if firm else "Desconocido"

        resultado.append({
            "id_informe": inf.id_informe,
            "folio": inf.folio,
            "numero_version": inf.numero_version,
            "id_orden": inf.id_orden,
            "estado": inf.estado,
            "paciente_nombre": pac_nombre,
            "paciente_ci": pac.ci if pac else None,
            "firmante_nombre": firm_nombre,
            "motivo_papelera": ultimo_ev.justificativo if ultimo_ev else inf.justificativo,
            "fecha_papelera": ultimo_ev.creado_en if ultimo_ev else inf.publicado_en,
        })

    return resultado


def obtener_informe_por_folio(
    db: Session,
    folio: str,
    numero_version: int | None = None,
) -> Informe:
    """Busca un informe por folio y versión (o la versión activa no desplazada si no se especifica)."""
    query = db.query(Informe).filter(Informe.folio == folio)
    if numero_version is not None:
        query = query.filter(Informe.numero_version == numero_version)
    else:
        # Preferir versión activa (VIGENTE, o la más reciente)
        query = query.order_by(desc(Informe.numero_version))

    informe = query.first()
    if not informe:
        raise NoEncontradoError(f"Informe con folio {folio} no encontrado.")
    return informe


def obtener_eventos_folio(
    db: Session,
    folio: str,
) -> list[InformeEvento]:
    """Obtiene la traza completa de auditoría para un folio en orden cronológico."""
    return (
        db.query(InformeEvento)
        .filter(InformeEvento.folio == folio)
        .order_by(InformeEvento.creado_en.asc())
        .all()
    )
