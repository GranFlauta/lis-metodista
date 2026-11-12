"""Añade selección cualitativa de Troponinas al grupo de Inmunoserología."""
from typing import Sequence, Union
from alembic import op

revision: str = "0005_troponinas_inmunoserologia"
down_revision: Union[str, None] = "0004_perfiles_rapidos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO laboratorio.parametros
            (id_estudio_version, codigo, nombre, grupo, tipo_campo, opciones, obligatorio, orden_visualizacion)
        SELECT ev.id_estudio_version, 'TROPONINAS', 'Troponinas', 'TROPONINAS', 'SELECCION',
               '["Positivo", "Negativo"]'::jsonb, TRUE,
               COALESCE((SELECT MAX(p.orden_visualizacion) + 1 FROM laboratorio.parametros p
                         WHERE p.id_estudio_version = ev.id_estudio_version), 1)
        FROM laboratorio.estudio_versiones ev
        JOIN laboratorio.estudios e ON e.id_estudio = ev.id_estudio
        WHERE e.codigo = 'INMUNOSEROLOGIA' AND ev.activa = TRUE
        ON CONFLICT (id_estudio_version, codigo) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM laboratorio.parametros p
        USING laboratorio.estudio_versiones ev, laboratorio.estudios e
        WHERE p.id_estudio_version = ev.id_estudio_version
          AND ev.id_estudio = e.id_estudio
          AND e.codigo = 'INMUNOSEROLOGIA'
          AND p.codigo = 'TROPONINAS'
    """)
