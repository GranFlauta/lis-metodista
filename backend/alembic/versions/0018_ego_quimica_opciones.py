"""Opciones semicuantitativas enriquecidas para química de EGO."""
import json
from alembic import op
import sqlalchemy as sa

from app.catalog.definitions import EGO

revision = "0018_ego_quimica_opciones"
down_revision = "0017_orden_lipidico"
branch_labels = None
depends_on = None

PARAMETROS_QUIMICA = {p.codigo: p for p in EGO.parametros if p.grupo == "QUIMICO"}


def upgrade() -> None:
    connection = op.get_bind()
    for codigo, parametro in PARAMETROS_QUIMICA.items():
        connection.execute(sa.text("""
            UPDATE laboratorio.parametros p
            SET opciones = CAST(:opciones AS jsonb), valor_defecto = :defecto
            FROM laboratorio.estudio_versiones ev, laboratorio.estudios e
            WHERE p.id_estudio_version = ev.id_estudio_version AND ev.id_estudio = e.id_estudio
              AND e.codigo = 'EGO' AND p.codigo = :codigo
        """), {
            "opciones": json.dumps(parametro.opciones),
            "defecto": parametro.defecto,
            "codigo": codigo,
        })


def downgrade() -> None:
    pass
