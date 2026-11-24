"""Orden microscópico de EGO y controles de captura de serología."""
import json
from alembic import op
import sqlalchemy as sa

from app.catalog.definitions import EGO, INMUNOSEROLOGIA

revision = "0007_captura_serologia_ego"
down_revision = "0006_etiqueta_cayados"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE laboratorio.estudio_versiones ev
        SET configuracion_json = jsonb_set(ev.configuracion_json, '{captura}', CAST(:captura AS jsonb))
        FROM laboratorio.estudios e WHERE e.id_estudio = ev.id_estudio AND e.codigo = 'INMUNOSEROLOGIA'
    """), {"captura": json.dumps(INMUNOSEROLOGIA.captura)})
    for estudio in (EGO, INMUNOSEROLOGIA):
        for orden, parametro in enumerate(estudio.parametros, 1):
            connection.execute(sa.text("""
                UPDATE laboratorio.parametros p SET orden_visualizacion = :orden,
                    unidad_medida = :unidad, tipo_campo = :tipo, opciones = CAST(:opciones AS jsonb)
                FROM laboratorio.estudio_versiones ev, laboratorio.estudios e
                WHERE p.id_estudio_version = ev.id_estudio_version AND ev.id_estudio = e.id_estudio
                  AND e.codigo = :estudio AND p.codigo = :codigo
            """), {"orden": orden, "unidad": parametro.unidad, "tipo": parametro.tipo,
                    "opciones": json.dumps(parametro.opciones) if parametro.opciones is not None else None,
                    "estudio": estudio.codigo, "codigo": parametro.codigo})


def downgrade() -> None:
    op.execute("""UPDATE laboratorio.estudio_versiones ev SET configuracion_json = configuracion_json - 'captura'
        FROM laboratorio.estudios e WHERE e.id_estudio = ev.id_estudio AND e.codigo = 'INMUNOSEROLOGIA'""")
    op.execute("""UPDATE laboratorio.parametros p SET unidad_medida = 'dilución'
        FROM laboratorio.estudio_versiones ev, laboratorio.estudios e
        WHERE p.id_estudio_version = ev.id_estudio_version AND ev.id_estudio = e.id_estudio
        AND e.codigo = 'INMUNOSEROLOGIA' AND (p.codigo LIKE 'WIDAL_%' OR p.codigo LIKE '%_DILUCION')""")
    op.execute("UPDATE laboratorio.parametros SET tipo_campo = 'TEXTO_LIBRE', opciones = NULL WHERE codigo = 'VDRL_DILUCION'")
    op.execute("""UPDATE laboratorio.parametros SET orden_visualizacion = CASE codigo
        WHEN 'BACTERIAS' THEN orden_visualizacion - 1 WHEN 'CILINDROS' THEN orden_visualizacion + 1 END
        WHERE codigo IN ('BACTERIAS', 'CILINDROS')""")
