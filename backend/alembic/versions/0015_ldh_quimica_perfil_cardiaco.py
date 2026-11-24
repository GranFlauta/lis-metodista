"""Añade LDH a Química y Perfil Cardíaco y separa la captura cualitativa de Troponina."""
from alembic import op
import sqlalchemy as sa

revision = "0015_ldh_quimica_perfil_cardiaco"
down_revision = "0014_titulos_perfil_pancreatico"
branch_labels = None
depends_on = None


ESTUDIOS_LDH = {
    "QUIMICA_SANGUINEA": "LDH_QUIMICA",
    "PERFIL_CARDIACO": "LDH_CARDIACO",
}


def _sincronizar_ldh(connection, id_version: int, codigo: str, orden: int) -> None:
    id_parametro = connection.execute(sa.text("""
        SELECT id_parametro FROM laboratorio.parametros
        WHERE id_estudio_version = :version AND codigo = :codigo
    """), {"version": id_version, "codigo": codigo}).scalar_one_or_none()

    if id_parametro is None:
        id_parametro = connection.execute(sa.text("""
            INSERT INTO laboratorio.parametros (
                id_estudio_version, codigo, nombre, grupo, tipo_campo, unidad_medida,
                decimales, formula_expresion, opciones, valor_defecto,
                requiere_confirmacion, metodo, muestra, obligatorio, orden_visualizacion
            )
            VALUES (
                :version, :codigo, 'LDH', NULL, 'NUMERICO', 'UI/L',
                2, NULL, NULL, NULL, FALSE, NULL, NULL, TRUE, :orden
            )
            RETURNING id_parametro
        """), {"version": id_version, "codigo": codigo, "orden": orden}).scalar_one()
    else:
        connection.execute(sa.text("""
            UPDATE laboratorio.parametros
            SET nombre = 'LDH', grupo = NULL, tipo_campo = 'NUMERICO',
                unidad_medida = 'UI/L', decimales = 2,
                formula_expresion = NULL, opciones = NULL, valor_defecto = NULL,
                requiere_confirmacion = FALSE, metodo = NULL, muestra = NULL,
                obligatorio = TRUE
            WHERE id_parametro = :id
        """), {"id": id_parametro})

    connection.execute(sa.text("""
        DELETE FROM laboratorio.rangos_referencia WHERE id_parametro = :id
    """), {"id": id_parametro})
    connection.execute(sa.text("""
        INSERT INTO laboratorio.rangos_referencia (
            id_parametro, sexo, edad_min_meses, edad_max_meses,
            limite_inferior, inferior_inclusivo, limite_superior,
            superior_inclusivo, referencia_texto, requiere_validacion
        )
        VALUES (:id, NULL, NULL, NULL, 200, TRUE, 400, TRUE, '200-400 UI/L', FALSE)
    """), {"id": id_parametro})


def upgrade() -> None:
    connection = op.get_bind()
    versions = connection.execute(sa.text("""
        SELECT e.codigo AS estudio, ev.id_estudio_version,
               COALESCE(MAX(p.orden_visualizacion), 0) + 1 AS orden
        FROM laboratorio.estudios AS e
        JOIN laboratorio.estudio_versiones AS ev USING (id_estudio)
        LEFT JOIN laboratorio.parametros AS p USING (id_estudio_version)
        WHERE e.codigo IN ('QUIMICA_SANGUINEA', 'PERFIL_CARDIACO')
        GROUP BY e.codigo, ev.id_estudio_version
    """)).mappings().all()

    for version in versions:
        _sincronizar_ldh(
            connection,
            version["id_estudio_version"],
            ESTUDIOS_LDH[version["estudio"]],
            version["orden"],
        )

    connection.execute(sa.text("""
        UPDATE laboratorio.parametros AS p
        SET grupo = 'TROPONINA', tipo_campo = 'SELECCION',
            unidad_medida = NULL, formula_expresion = NULL,
            opciones = '["Negativo", "Positivo"]'::jsonb
        FROM laboratorio.estudio_versiones AS ev
        JOIN laboratorio.estudios AS e USING (id_estudio)
        WHERE p.id_estudio_version = ev.id_estudio_version
          AND e.codigo = 'PERFIL_CARDIACO'
          AND p.codigo = 'TROPONINA_CARDIACA'
    """))


def downgrade() -> None:
    raise NotImplementedError(
        "No se eliminan campos LDH que podrían tener resultados asociados."
    )
