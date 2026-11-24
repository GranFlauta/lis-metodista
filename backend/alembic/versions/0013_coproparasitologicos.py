"""Coproparasitológico simple libre y seriado con muestras de fecha y resultado."""
import json

from alembic import op
import sqlalchemy as sa

from app.catalog.definitions import PARASITOLOGIA

revision = "0013_coproparasitologicos"
down_revision = "0012_moco_fecal_texto_libre"
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
        for parametro in PARASITOLOGIA.parametros:
            if parametro.codigo not in {"COPROPARASITOLOGICO_SIMPLE", "COPROPARASITOLOGICO_SERIADO"}:
                continue
            connection.execute(sa.text("""
                UPDATE laboratorio.parametros SET tipo_campo = :tipo, grupo = :grupo,
                    opciones = NULL, obligatorio = :obligatorio
                WHERE id_estudio_version = :version AND codigo = :codigo
            """), {"version": version, "codigo": parametro.codigo, "tipo": parametro.tipo,
                    "grupo": parametro.grupo, "obligatorio": parametro.obligatorio})
    # Los IDs, resultados previos y snapshots oficiales se conservan íntegros.


def downgrade():
    raise NotImplementedError("No se convierten textos ni series de muestras en selecciones positivo/negativo.")
