"""Amplía Moco fecal a diez campos de texto sin truncar resultados anteriores."""
import json

from alembic import op
import sqlalchemy as sa

from app.catalog.definitions import PARASITOLOGIA

revision = "0012_moco_fecal_texto_libre"
down_revision = "0011_nombre_curva_tolerancia"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    versiones = connection.execute(sa.text("""
        SELECT ev.id_estudio_version FROM laboratorio.estudio_versiones ev
        JOIN laboratorio.estudios e USING (id_estudio) WHERE e.codigo = :codigo
    """), {"codigo": PARASITOLOGIA.codigo}).scalars().all()
    for version in versiones:
        connection.execute(sa.text("""
            UPDATE laboratorio.estudio_versiones
            SET configuracion_json = jsonb_set(configuracion_json, '{captura}',
                COALESCE(configuracion_json->'captura', '{}'::jsonb) || CAST(:captura AS jsonb))
            WHERE id_estudio_version = :version
        """), {"version": version, "captura": json.dumps(PARASITOLOGIA.captura)})
        for orden, parametro in enumerate(PARASITOLOGIA.parametros, 1):
            # El código MOCO_FECAL conserva su id y cualquier texto Positivo/Negativo
            # ya capturado. No se actualizan resultados ni snapshots publicados.
            connection.execute(sa.text("""
                INSERT INTO laboratorio.parametros
                    (id_estudio_version, codigo, nombre, grupo, tipo_campo, unidad_medida,
                     decimales, opciones, muestra, obligatorio, orden_visualizacion)
                VALUES (:version, :codigo, :nombre, :grupo, :tipo, :unidad,
                        :decimales, CAST(:opciones AS jsonb), :muestra, :obligatorio, :orden)
                ON CONFLICT (id_estudio_version, codigo) DO UPDATE SET
                    nombre = EXCLUDED.nombre, grupo = EXCLUDED.grupo,
                    tipo_campo = EXCLUDED.tipo_campo, opciones = EXCLUDED.opciones,
                    obligatorio = EXCLUDED.obligatorio, orden_visualizacion = EXCLUDED.orden_visualizacion
            """), {"version": version, "codigo": parametro.codigo, "nombre": parametro.nombre,
                    "grupo": parametro.grupo, "tipo": parametro.tipo, "unidad": parametro.unidad,
                    "decimales": parametro.decimales, "opciones": json.dumps(parametro.opciones) if parametro.opciones is not None else None,
                    "muestra": parametro.muestra, "obligatorio": parametro.obligatorio, "orden": orden})


def downgrade():
    raise NotImplementedError("No se eliminan campos que pueden contener texto clínico ni se convierten en selecciones.")
