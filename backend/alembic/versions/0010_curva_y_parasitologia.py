"""Curva de tolerancia y Parasitología independientes; conserva el catálogo histórico."""
import json

from alembic import op
import sqlalchemy as sa

from app.catalog.definitions import CURVA_TOLERANCIA, INMUNOSEROLOGIA, PARASITOLOGIA

revision = "0010_curva_parasitologia"
down_revision = "0009_perfil_pancreatico"
branch_labels = None
depends_on = None

LEGACY_GRUPOS = {"H_PYLORI_SUERO", "H_PYLORI_HECES", "SANGRE_OCULTA"}
ALIAS_INMUNOSEROLOGIA = {
    "H_PYLORI_HECES": "H_PYLORI_HECES_INMUNO",
    "SANGRE_OCULTA_HECES": "SANGRE_OCULTA_HECES_INMUNO",
}
CODIGOS_SUBESTUDIO_INMUNO = set(ALIAS_INMUNOSEROLOGIA) | set(ALIAS_INMUNOSEROLOGIA.values()) | {
    "H_PYLORI_SUERO",
}


def _version(connection, estudio, numero=1):
    id_estudio = connection.execute(sa.text("""
        INSERT INTO laboratorio.estudios (codigo, nombre, categoria, seleccion_parcial)
        VALUES (:codigo, :nombre, :categoria, :parcial)
        ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre
        RETURNING id_estudio
    """), dict(codigo=estudio.codigo, nombre=estudio.nombre, categoria=estudio.categoria,
               parcial=estudio.seleccion_parcial)).scalar_one()
    config = json.dumps(dict(reglas=list(estudio.reglas), captura=estudio.captura,
                             seleccion_campos=estudio.seleccion_campos, revision_catalogo=revision))
    version = connection.execute(sa.text("""
        INSERT INTO laboratorio.estudio_versiones (id_estudio, numero_version, configuracion_json)
        VALUES (:id, :numero, CAST(:config AS jsonb))
        ON CONFLICT (id_estudio, numero_version) DO UPDATE SET configuracion_json = EXCLUDED.configuracion_json
        RETURNING id_estudio_version
    """), dict(id=id_estudio, numero=numero, config=config)).scalar_one()
    for orden, p in enumerate(estudio.parametros, 1):
        connection.execute(sa.text("""
            INSERT INTO laboratorio.parametros
              (id_estudio_version, codigo, nombre, grupo, tipo_campo, unidad_medida, decimales,
               formula_expresion, opciones, valor_defecto, requiere_confirmacion, metodo, muestra,
               obligatorio, orden_visualizacion)
            VALUES (:version, :codigo, :nombre, :grupo, :tipo, :unidad, :decimales, :formula,
                    CAST(:opciones AS jsonb), :defecto, :confirmar, :metodo, :muestra, :obligatorio, :orden)
            ON CONFLICT (id_estudio_version, codigo) DO NOTHING
        """), dict(version=version, codigo=p.codigo, nombre=p.nombre, grupo=p.grupo, tipo=p.tipo,
                   unidad=p.unidad, decimales=p.decimales, formula=p.formula, opciones=json.dumps(p.opciones),
                   defecto=p.defecto, confirmar=p.confirmar, metodo=p.metodo, muestra=p.muestra,
                   obligatorio=p.obligatorio, orden=orden))
        # Las nuevas definiciones no agregan referencias ni fórmulas clínicas.
    return id_estudio, version


def upgrade():
    connection = op.get_bind()
    parasi_id, parasi_version = _version(connection, PARASITOLOGIA)
    _version(connection, CURVA_TOLERANCIA)
    existente = connection.execute(sa.text("""
        SELECT ev.numero_version FROM laboratorio.estudio_versiones ev
        JOIN laboratorio.estudios e USING (id_estudio)
        WHERE e.codigo = :codigo AND ev.configuracion_json->>'revision_catalogo' = :revision
        ORDER BY ev.numero_version DESC LIMIT 1
    """), dict(codigo=INMUNOSEROLOGIA.codigo, revision=revision)).scalar_one_or_none()
    numero = existente or connection.execute(sa.text("""
        SELECT COALESCE(MAX(ev.numero_version), 0) + 1 FROM laboratorio.estudio_versiones ev
        JOIN laboratorio.estudios e USING (id_estudio) WHERE e.codigo = :codigo
    """), dict(codigo=INMUNOSEROLOGIA.codigo)).scalar_one()
    id_inmuno_existente = connection.execute(sa.text("""
        SELECT id_estudio FROM laboratorio.estudios WHERE codigo = :codigo
    """), dict(codigo=INMUNOSEROLOGIA.codigo)).scalar_one_or_none()
    if id_inmuno_existente is not None:
        connection.execute(sa.text("""
            UPDATE laboratorio.estudio_versiones SET activa = FALSE
            WHERE id_estudio = :id AND activa
        """), dict(id=id_inmuno_existente))
    inmuno_id, inmuno_version = _version(connection, INMUNOSEROLOGIA, numero)
    connection.execute(sa.text("""
        UPDATE laboratorio.estudio_versiones SET activa = (id_estudio_version = :version)
        WHERE id_estudio = :id
    """), dict(version=inmuno_version, id=inmuno_id))
    codigos_parasi = {p.codigo for p in PARASITOLOGIA.parametros}
    destinos = dict(connection.execute(sa.text("""
        SELECT codigo, id_parametro FROM laboratorio.parametros WHERE id_estudio_version = :version
    """), dict(version=parasi_version)).all())
    nuevos_inmuno = dict(connection.execute(sa.text("""
        SELECT codigo, id_parametro FROM laboratorio.parametros WHERE id_estudio_version = :version
    """), dict(version=inmuno_version)).all())
    borradores = connection.execute(sa.text("""
        SELECT oe.id_orden_estudio, oe.id_orden, oe.observaciones FROM laboratorio.orden_estudios oe
        JOIN laboratorio.ordenes o USING (id_orden)
        WHERE oe.id_estudio = :id AND o.estado_trabajo <> 'PUBLICADA'
        FOR UPDATE OF oe, o
    """), dict(id=inmuno_id)).all()
    for oe_id, orden_id, observaciones in borradores:
        grupos = set(connection.execute(sa.text("SELECT grupo FROM laboratorio.orden_estudio_grupos WHERE id_orden_estudio = :id"), dict(id=oe_id)).scalars())
        resultados = connection.execute(sa.text("""
            SELECT r.id_resultado, p.codigo FROM laboratorio.resultados_borrador r
            JOIN laboratorio.parametros p USING (id_parametro)
            WHERE r.id_orden_estudio = :id AND r.id_edicion IS NULL
        """), dict(id=oe_id)).all()
        tiene_parasi = any(c in codigos_parasi and c not in CODIGOS_SUBESTUDIO_INMUNO for _, c in resultados)
        parasi_oe = None
        if tiene_parasi:
            parasi_oe = connection.execute(sa.text("""
                INSERT INTO laboratorio.orden_estudios (id_orden, id_estudio, id_estudio_version, observaciones)
                VALUES (:orden, :estudio, :version, :observaciones)
                ON CONFLICT (id_orden, id_estudio) DO UPDATE SET id_estudio = EXCLUDED.id_estudio
                RETURNING id_orden_estudio
            """), dict(orden=orden_id, estudio=parasi_id, version=parasi_version,
                       observaciones=observaciones if not grupos - LEGACY_GRUPOS else None)).scalar_one()
        for resultado_id, codigo in resultados:
            codigo_inmuno = ALIAS_INMUNOSEROLOGIA.get(codigo, codigo)
            es_subestudio_inmuno = codigo in CODIGOS_SUBESTUDIO_INMUNO
            mover_a_parasi = codigo in codigos_parasi and not es_subestudio_inmuno
            destino_oe = parasi_oe if mover_a_parasi else oe_id
            parametro_id = (destinos if mover_a_parasi else nuevos_inmuno).get(
                codigo if mover_a_parasi else codigo_inmuno
            )
            if parametro_id is None:
                raise RuntimeError("El catálogo histórico contiene un parámetro sin correspondencia; no se alteraron sus resultados.")
            conflicto = connection.execute(sa.text("""
                SELECT 1 FROM laboratorio.resultados_borrador
                WHERE id_orden_estudio = :oe AND id_parametro = :parametro
                  AND id_edicion IS NULL AND id_resultado <> :resultado
            """), dict(oe=destino_oe, parametro=parametro_id, resultado=resultado_id)).first()
            if conflicto:
                raise RuntimeError("Existen dos resultados para la misma prueba de Parasitología; revise el borrador antes de migrar.")
            connection.execute(sa.text("""
                UPDATE laboratorio.resultados_borrador SET id_orden_estudio = :oe, id_parametro = :parametro
                WHERE id_resultado = :resultado
            """), dict(oe=destino_oe, parametro=parametro_id, resultado=resultado_id))
        for grupo in grupos & LEGACY_GRUPOS:
            connection.execute(sa.text("DELETE FROM laboratorio.orden_estudio_grupos WHERE id_orden_estudio = :id AND grupo = :grupo"), dict(id=oe_id, grupo=grupo))
        tiene_subestudio_inmuno = bool(grupos & LEGACY_GRUPOS) or any(
            codigo in CODIGOS_SUBESTUDIO_INMUNO for _, codigo in resultados
        )
        if tiene_subestudio_inmuno:
            connection.execute(sa.text("""
                INSERT INTO laboratorio.orden_estudio_grupos (id_orden_estudio, grupo)
                VALUES (:id, 'PARASITOLOGIA')
                ON CONFLICT (id_orden_estudio, grupo) DO NOTHING
            """), dict(id=oe_id))
        grupos_inmuno = grupos - LEGACY_GRUPOS
        if tiene_parasi and not grupos_inmuno and not tiene_subestudio_inmuno:
            connection.execute(sa.text("DELETE FROM laboratorio.orden_estudios WHERE id_orden_estudio = :id"), dict(id=oe_id))
        else:
            connection.execute(sa.text("UPDATE laboratorio.orden_estudios SET id_estudio_version = :version WHERE id_orden_estudio = :id"), dict(version=inmuno_version, id=oe_id))

    # Los grupos antiguos pasan a la nueva selección cualitativa de Inmunoserología.
    for perfil_id, items in connection.execute(sa.text("SELECT id_perfil_rapido, estudios FROM laboratorio.perfiles_rapidos")).all():
        nuevos, cambio = [], False
        for item in items:
            grupos = set(item.get("grupos") or [])
            if item["codigo"] == INMUNOSEROLOGIA.codigo and grupos & LEGACY_GRUPOS:
                cambio = True
                nuevos.append({**item, "grupos": sorted((grupos - LEGACY_GRUPOS) | {"PARASITOLOGIA"})})
            else:
                nuevos.append(item)
        if cambio:
            connection.execute(sa.text("UPDATE laboratorio.perfiles_rapidos SET estudios = CAST(:items AS jsonb) WHERE id_perfil_rapido = :id"), dict(id=perfil_id, items=json.dumps(nuevos)))
    for perfil_id, grupos in connection.execute(sa.text("SELECT id_perfil, grupos FROM laboratorio.perfil_estudios WHERE id_estudio = :id"), dict(id=inmuno_id)).all():
        if set(grupos or []) & LEGACY_GRUPOS:
            nuevos_grupos = sorted((set(grupos or []) - LEGACY_GRUPOS) | {"PARASITOLOGIA"})
            connection.execute(sa.text("""
                UPDATE laboratorio.perfil_estudios
                SET grupos = :grupos
                WHERE id_perfil = :perfil AND id_estudio = :id
            """), dict(grupos=nuevos_grupos, perfil=perfil_id, id=inmuno_id))


def downgrade():
    raise NotImplementedError("No se fusionan ni se borran estudios que pueden contener resultados clínicos.")
