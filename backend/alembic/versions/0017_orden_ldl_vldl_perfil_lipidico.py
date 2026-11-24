"""Muestra LDL-COL antes de VLDL-COL en Perfil Lipídico."""
import json

from alembic import op
import sqlalchemy as sa

revision = "0017_orden_lipidico"
down_revision = "0016_inmuno_parasito"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    estudio = connection.execute(sa.text("""
        SELECT e.id_estudio, ev.id_estudio_version
        FROM laboratorio.estudios AS e
        JOIN laboratorio.estudio_versiones AS ev USING (id_estudio)
        WHERE e.codigo = 'PERFIL_LIPIDICO' AND ev.activa
        FOR UPDATE OF ev
    """)).mappings().one_or_none()
    if estudio is None:
        raise RuntimeError("No existe una versión activa para Perfil Lipídico.")

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
               configuracion_json || CAST(:revision AS jsonb), TRUE
        FROM laboratorio.estudio_versiones
        WHERE id_estudio_version = :version_anterior
        RETURNING id_estudio_version
    """), {
        "numero": numero,
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

    if connection.execute(sa.text("""
        SELECT COUNT(*)
        FROM laboratorio.parametros
        WHERE id_estudio_version = :version AND codigo IN ('LDL', 'VLDL')
    """), {"version": version_nueva}).scalar_one() != 2:
        raise RuntimeError("La versión activa de Perfil Lipídico no contiene LDL y VLDL.")

    connection.execute(sa.text("""
        UPDATE laboratorio.parametros
        SET orden_visualizacion = CASE codigo WHEN 'LDL' THEN 4 WHEN 'VLDL' THEN 5 END
        WHERE id_estudio_version = :version AND codigo IN ('LDL', 'VLDL')
    """), {"version": version_nueva})

    sin_correspondencia = connection.execute(sa.text("""
        SELECT 1
        FROM laboratorio.resultados_borrador AS r
        JOIN laboratorio.orden_estudios AS oe USING (id_orden_estudio)
        JOIN laboratorio.ordenes AS o USING (id_orden)
        JOIN laboratorio.parametros AS anterior ON anterior.id_parametro = r.id_parametro
        WHERE oe.id_estudio = :estudio AND o.estado_trabajo <> 'PUBLICADA'
          AND r.id_edicion IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM laboratorio.parametros AS nueva
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
