"""Separa la unidad personalizada del resultado numérico en borradores."""
from alembic import op
import sqlalchemy as sa

revision = "0021_unidades_coagulacion"
down_revision = "0020_inmunoserologia_chagas_asto"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resultados_borrador", sa.Column("unidad_override", sa.String(30), nullable=True), schema="laboratorio")


def downgrade() -> None:
    op.drop_column("resultados_borrador", "unidad_override", schema="laboratorio")
