"""Añade CHAGAS y sensibilidad propia al catálogo de Inmunoserología."""
import json

from alembic import op
import sqlalchemy as sa

from app.catalog.definitions import INMUNOSEROLOGIA

revision = "0020_inmunoserologia_chagas_asto"
down_revision = "0019_serologia_muestra_metodo"
branch_labels = None
depends_on = None

PARAMETRO_CHAGAS = next(p for p in INMUNOSEROLOGIA.parametros if p.codigo == "CHAGAS")


def upgrade() -> None:
    connection = op.get_bind()
    estudio = connection.execute(sa.text("""
        SELECT e.id_estudio, ev.id_estudio_version
        FROM laboratorio.estudios AS e
        JOIN laboratorio.estudio_versiones AS ev USING (id_estudio)
        WHERE e.codigo = 'INMUNOSEROLOGIA' AND ev.activa
        FOR UPDATE OF ev
    """)).mappings().one_or_none()
    if estudio is None:
        raise RuntimeError("No existe una versión activa para Inmunoserología.")

    connection.execute(sa.text("""
        SELECT oe.id_orden_estudio
        FROM laboratorio.orden_estudios AS oe
        JOIN laboratorio.ordenes AS o USING (id_orden)
        WHERE oe.id_estudio = :estudio AND o.estado_trabajo <> 'PUBLICADA'
        ORDER BY oe.id_orden_estudio
        FOR UPDATE OF oe, o
    """), {"estudio": estudio["id_estudio"]}).all()

    numero = connection.execute(sa.text("""
        SELECT COALESCE(MAX(numero_version), 0) + 1
        FROM laboratorio.estudio_versiones
        WHERE id_estudio = :estudio
    """), {"estudio": estudio["id_estudio"]}).scalar_one()
    connection.execute(sa.text("""
        UPDATE laboratorio.estudio_versiones
        SET activa = FALSE
        WHERE id_estudio = :estudio AND activa
    """), {"estudio": estudio["id_estudio"]})
    version_nueva = connection.execute(sa.text("""
        INSERT INTO laboratorio.estudio_versiones
            (id_estudio, numero_version, configuracion_json, activa)
        SELECT id_estudio, :numero,
               jsonb_set(configuracion_json, '{captura}', CAST(:captura AS jsonb), TRUE)
                   || CAST(:revision AS jsonb),
               TRUE
        FROM laboratorio.estudio_versiones
        WHERE id_estudio_version = :version_anterior
        RETURNING id_estudio_version
    """), {
        "estudio": estudio["id_estudio"],
        "numero": numero,
        "captura": json.dumps(INMUNOSEROLOGIA.captura, ensure_ascii=False),
        "revision": json.dumps({"revision_catalogo": revision}),
        "version_anterior": estudio["id_estudio_version"],
    }).scalar_one()

    connection.execute(sa.text("""
        INSERT INTO laboratorio.parametros (
            id_estudio_version, codigo, nombre, grupo, tipo_campo, unidad_medida,
            decimales, formula_expresion, opciones, valor_defecto,
            requiere_confirmacion, metodo, muestra, obligatorio, orden_visualizacion
        )
        SELECT :version_nueva, codigo, nombre, grupo, tipo_campo, unidad_medida,
               decimales, formula_expresion, opciones, valor_defecto,
               requiere_confirmacion, metodo, muestra, obligatorio, orden_visualizacion
        FROM laboratorio.parametros
        WHERE id_estudio_version = :version_anterior
        ORDER BY orden_visualizacion
    """), {
        "version_nueva": version_nueva,
        "version_anterior": estudio["id_estudio_version"],
    })
    connection.execute(sa.text("""
        INSERT INTO laboratorio.rangos_referencia (
            id_parametro, sexo, edad_min_meses, edad_max_meses,
            limite_inferior, inferior_inclusivo, limite_superior,
            superior_inclusivo, referencia_texto, requiere_validacion
        )
        SELECT nueva.id_parametro, r.sexo, r.edad_min_meses, r.edad_max_meses,
               r.limite_inferior, r.inferior_inclusivo, r.limite_superior,
               r.superior_inclusivo, r.referencia_texto, r.requiere_validacion
        FROM laboratorio.rangos_referencia AS r
        JOIN laboratorio.parametros AS anterior ON anterior.id_parametro = r.id_parametro
        JOIN laboratorio.parametros AS nueva
          ON nueva.id_estudio_version = :version_nueva AND nueva.codigo = anterior.codigo
        WHERE anterior.id_estudio_version = :version_anterior
    """), {
        "version_nueva": version_nueva,
        "version_anterior": estudio["id_estudio_version"],
    })

    codigos = set(connection.execute(sa.text("""
        SELECT codigo
        FROM laboratorio.parametros
        WHERE id_estudio_version = :version
    """), {"version": version_nueva}).scalars().all())
    if "CHAGAS" not in codigos:
        connection.execute(sa.text("""
            INSERT INTO laboratorio.parametros (
                id_estudio_version, codigo, nombre, grupo, tipo_campo, unidad_medida,
                decimales, formula_expresion, opciones, valor_defecto,
                requiere_confirmacion, metodo, muestra, obligatorio, orden_visualizacion
            )
            SELECT :version, :codigo, :nombre, :grupo, :tipo, :unidad,
                   :decimales, NULL, CAST(:opciones AS jsonb), :defecto,
                   :confirmar, :metodo, :muestra, :obligatorio,
                   COALESCE(MAX(orden_visualizacion), 0) + 1
            FROM laboratorio.parametros
            WHERE id_estudio_version = :version
        """), {
            "version": version_nueva,
            "codigo": PARAMETRO_CHAGAS.codigo,
            "nombre": PARAMETRO_CHAGAS.nombre,
            "grupo": PARAMETRO_CHAGAS.grupo,
            "tipo": PARAMETRO_CHAGAS.tipo,
            "unidad": PARAMETRO_CHAGAS.unidad,
            "decimales": PARAMETRO_CHAGAS.decimales,
            "opciones": json.dumps(PARAMETRO_CHAGAS.opciones, ensure_ascii=False),
            "defecto": PARAMETRO_CHAGAS.defecto,
            "confirmar": PARAMETRO_CHAGAS.confirmar,
            "metodo": PARAMETRO_CHAGAS.metodo,
            "muestra": PARAMETRO_CHAGAS.muestra,
            "obligatorio": PARAMETRO_CHAGAS.obligatorio,
        })

    connection.execute(sa.text("""
        UPDATE laboratorio.parametros
        SET nombre = :nombre
        WHERE id_estudio_version = :version AND codigo = 'SANGRE_OCULTA_HECES_INMUNO'
    """), {"version": version_nueva, "nombre": "SANGRE OCULTA EN HECES"})

    sin_correspondencia = connection.execute(sa.text("""
        SELECT 1
        FROM laboratorio.resultados_borrador AS r
        JOIN laboratorio.orden_estudios AS oe USING (id_orden_estudio)
        JOIN laboratorio.ordenes AS o USING (id_orden)
        JOIN laboratorio.parametros AS anterior ON anterior.id_parametro = r.id_parametro
        WHERE oe.id_estudio = :estudio AND o.estado_trabajo <> 'PUBLICADA'
          AND r.id_edicion IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM laboratorio.parametros AS nueva
              WHERE nueva.id_estudio_version = :version_nueva
                AND nueva.codigo = anterior.codigo
          )
        LIMIT 1
    """), {
        "estudio": estudio["id_estudio"],
        "version_nueva": version_nueva,
    }).first()
    if sin_correspondencia:
        raise RuntimeError("Hay resultados de borrador sin parámetro equivalente en la nueva versión.")

    connection.execute(sa.text("""
        UPDATE laboratorio.resultados_borrador AS r
        SET id_parametro = nueva.id_parametro
        FROM laboratorio.orden_estudios AS oe
        JOIN laboratorio.ordenes AS o USING (id_orden),
             laboratorio.parametros AS anterior,
             laboratorio.parametros AS nueva
        WHERE r.id_orden_estudio = oe.id_orden_estudio
          AND r.id_parametro = anterior.id_parametro
          AND anterior.id_estudio_version = oe.id_estudio_version
          AND nueva.id_estudio_version = :version_nueva
          AND nueva.codigo = anterior.codigo
          AND oe.id_estudio = :estudio
          AND o.estado_trabajo <> 'PUBLICADA'
          AND r.id_edicion IS NULL
    """), {
        "estudio": estudio["id_estudio"],
        "version_nueva": version_nueva,
    })
    connection.execute(sa.text("""
        UPDATE laboratorio.orden_estudios AS oe
        SET id_estudio_version = :version_nueva
        FROM laboratorio.ordenes AS o
        WHERE o.id_orden = oe.id_orden
          AND oe.id_estudio = :estudio
          AND o.estado_trabajo <> 'PUBLICADA'
    """), {
        "estudio": estudio["id_estudio"],
        "version_nueva": version_nueva,
    })


def downgrade() -> None:
    raise NotImplementedError(
        "No se revierten versiones de catálogo asociadas a resultados clínicos."
    )
