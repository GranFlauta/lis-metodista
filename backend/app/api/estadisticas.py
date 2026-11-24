"""Estadísticas de órdenes iniciadas en un período, agregadas en PostgreSQL."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import obtener_ip_cliente, registrar_evento_seguridad, require_auth
from app.core.clock import ahora
from app.core.database import get_db
from app.core.errors import ProhibidoError, ValidacionError
from app.models.user import Rol, Usuario
from app.schemas.estadistica import EstadisticaResponse, FiltroRespuesta

router = APIRouter(prefix="/api/estadisticas", tags=["Estadísticas"])
ZONA = ZoneInfo("America/La_Paz")

# Una fila por orden. Las reediciones y las impresiones no suman entregas.
# La primera publicación y su snapshot permanecen inmutables.
CONJUNTO = """
WITH iniciales AS (
    SELECT o.id_orden, o.id_usuario_autor, o.creado_en, o.estado_trabajo,
           i.id_informe, i.snapshot_json -> 'estudios' AS estudios,
           CASE WHEN i.publicado_en >= COALESCE(o.fecha_hora_toma_muestra, o.creado_en)
                THEN EXTRACT(EPOCH FROM (i.publicado_en - COALESCE(o.fecha_hora_toma_muestra, o.creado_en))) / 60
           END AS respuesta_minutos
    FROM laboratorio.ordenes o
    LEFT JOIN LATERAL (
        SELECT id_informe, publicado_en, snapshot_json
        FROM laboratorio.informes
        WHERE id_orden = o.id_orden AND numero_version = 1
        ORDER BY publicado_en, id_informe LIMIT 1
    ) i ON TRUE
    WHERE o.creado_en >= :inicio AND o.creado_en < :fin
      AND (CAST(:id_autor AS bigint) IS NULL OR o.id_usuario_autor = CAST(:id_autor AS bigint))
), filtradas AS (
    SELECT * FROM iniciales
    WHERE :respuesta = 'todas'
       OR (:respuesta = 'hasta_60' AND respuesta_minutos <= 60)
       OR (:respuesta = 'de_60_a_240' AND respuesta_minutos > 60 AND respuesta_minutos <= 240)
       OR (:respuesta = 'mas_240' AND respuesta_minutos > 240)
       OR (:respuesta = 'sin_hora' AND id_informe IS NOT NULL AND respuesta_minutos IS NULL)
)
"""


@router.get("", response_model=EstadisticaResponse)
def obtener_estadisticas(
    request: Request,
    desde: date | None = None,
    hasta: date | None = None,
    id_autor: int | None = Query(None, ge=1),
    respuesta: FiltroRespuesta = "todas",
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth),
) -> dict:
    rol = current_user.rol.nombre
    if rol not in {"ADMIN", "BIOQUIMICO"}:
        raise ProhibidoError()
    es_admin = rol == "ADMIN"
    if not es_admin:
        if id_autor is not None and id_autor != current_user.id_usuario:
            raise ProhibidoError("Sólo puede consultar las estadísticas de sus propias órdenes.")
        id_autor = current_user.id_usuario

    hoy = ahora().astimezone(ZONA).date()
    hasta = hasta or hoy
    desde = desde or hasta - timedelta(days=29)
    if hasta < desde:
        raise ValidacionError("La fecha final debe ser igual o posterior a la inicial.")
    if (hasta - desde).days >= 366:
        raise ValidacionError("Seleccione un período de hasta 366 días.")

    parametros = {
        "inicio": datetime.combine(desde, time.min, tzinfo=ZONA),
        "fin": datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=ZONA),
        "id_autor": id_autor,
        "respuesta": respuesta,
    }

    resumen = dict(db.execute(text(CONJUNTO + """
        SELECT COUNT(*) AS ordenes,
               COUNT(id_informe) AS publicadas,
               COUNT(*) FILTER (WHERE id_informe IS NULL) AS pendientes,
               COUNT(respuesta_minutos) AS respuestas_validas,
               COUNT(*) FILTER (WHERE id_informe IS NOT NULL AND respuesta_minutos IS NULL) AS publicadas_sin_hora
        FROM filtradas
    """), parametros).mappings().one())

    # percentile_disc conserva un valor NUMERIC real, sin convertir a double.
    mediana = db.execute(text(CONJUNTO + """
        SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY respuesta_minutos)
        FROM filtradas WHERE respuesta_minutos IS NOT NULL
    """), parametros).scalar_one()
    resumen["respuesta_mediana_minutos"] = (
        str(Decimal(mediana).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        if mediana is not None else None
    )

    estados = list(db.execute(text(CONJUNTO + """
        SELECT CASE WHEN id_informe IS NOT NULL THEN 'PUBLICADA' ELSE estado_trabajo END AS codigo,
               COUNT(*) AS cantidad FROM filtradas GROUP BY 1
    """), parametros).mappings())
    nombres = {"PUBLICADA": "Publicadas", "COMPLETO": "Listas para publicar", "INCOMPLETO": "En captura"}
    estados = [{**fila, "nombre": nombres.get(fila["codigo"], fila["codigo"])} for fila in estados]

    estudios = list(db.execute(text(CONJUNTO + """
        SELECT e ->> 'codigo' AS codigo, MIN(e ->> 'nombre') AS nombre, COUNT(*) AS cantidad
        FROM filtradas f
        CROSS JOIN LATERAL (
            SELECT DISTINCT ON (item ->> 'codigo') item AS e
            FROM jsonb_array_elements(COALESCE(f.estudios, '[]'::jsonb)) item
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(COALESCE(item -> 'secciones', '[]'::jsonb)) seccion
                WHERE jsonb_array_length(COALESCE(seccion -> 'parametros', '[]'::jsonb)) > 0
            )
        ) usados
        GROUP BY 1 ORDER BY cantidad DESC, codigo
    """), parametros).mappings())
    resumen["estudios_informados"] = sum(fila["cantidad"] for fila in estudios)

    responsables = list(db.execute(text(CONJUNTO + """
        SELECT u.id_usuario::text AS codigo,
               concat_ws(' ', u.nombres, u.apellido_paterno, u.apellido_materno) AS nombre,
               COUNT(f.id_informe) AS cantidad
        FROM filtradas f JOIN laboratorio.usuarios u ON u.id_usuario = f.id_usuario_autor
        GROUP BY u.id_usuario HAVING COUNT(f.id_informe) > 0
        ORDER BY cantidad DESC, u.id_usuario
    """), parametros).mappings())

    tiempos = db.execute(text(CONJUNTO + """
        SELECT COUNT(*) FILTER (WHERE respuesta_minutos <= 60) AS hasta_60,
               COUNT(*) FILTER (WHERE respuesta_minutos > 60 AND respuesta_minutos <= 240) AS de_60_a_240,
               COUNT(*) FILTER (WHERE respuesta_minutos > 240) AS mas_240
        FROM filtradas
    """), parametros).mappings().one()
    tiempos_respuesta = [
        {"codigo": "hasta_60", "nombre": "Hasta 1 hora", "cantidad": tiempos["hasta_60"]},
        {"codigo": "de_60_a_240", "nombre": "De 1 a 4 horas", "cantidad": tiempos["de_60_a_240"]},
        {"codigo": "mas_240", "nombre": "Más de 4 horas", "cantidad": tiempos["mas_240"]},
        {"codigo": "sin_hora", "nombre": "Sin hora válida", "cantidad": resumen["publicadas_sin_hora"]},
    ]
    actividad_db = db.execute(text(CONJUNTO + """
        SELECT (creado_en AT TIME ZONE 'America/La_Paz')::date AS fecha,
               COUNT(*) AS iniciadas, COUNT(id_informe) AS publicadas
        FROM filtradas GROUP BY 1 ORDER BY 1
    """), parametros).mappings()
    por_dia = {fila["fecha"]: dict(fila) for fila in actividad_db}
    actividad = [por_dia.get(desde + timedelta(days=i), {
        "fecha": desde + timedelta(days=i), "iniciadas": 0, "publicadas": 0,
    }) for i in range((hasta - desde).days + 1)]

    profesionales_db = db.query(Usuario).join(Rol).filter(Rol.nombre == "BIOQUIMICO")
    if not es_admin:
        profesionales_db = profesionales_db.filter(Usuario.id_usuario == current_user.id_usuario)
    profesionales = [{
        "id": usuario.id_usuario,
        "nombre": " ".join(filter(None, [usuario.nombres, usuario.apellido_paterno, usuario.apellido_materno])),
        "activo": usuario.activo,
    } for usuario in profesionales_db.order_by(Usuario.apellido_paterno, Usuario.nombres).all()]

    if es_admin and resumen["ordenes"]:
        registrar_evento_seguridad(db, accion="ADMIN_VE_PRIVADO", id_usuario=current_user.id_usuario,
            ip=obtener_ip_cliente(request), detalle={"modulo": "estadisticas", "solo_agregados": True,
                "desde": desde.isoformat(), "hasta": hasta.isoformat(), "id_autor": id_autor})
        db.commit()

    return {"desde": desde, "hasta": hasta, "generado_en": ahora(),
        "alcance": "laboratorio" if es_admin else "propio", "id_autor": id_autor,
        "respuesta": respuesta, "profesionales": profesionales, "resumen": resumen,
        "estados": estados, "estudios": estudios, "responsables": responsables,
        "tiempos_respuesta": tiempos_respuesta, "actividad": actividad}
