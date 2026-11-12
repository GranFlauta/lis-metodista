"""Guarda la etiqueta local del diferencial de cayados por orden-estudio."""
from typing import Sequence, Union
from alembic import op

revision: str = "0006_etiqueta_cayados"
down_revision: Union[str, None] = "0005_troponinas_inmunoserologia"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE laboratorio.orden_estudios ADD COLUMN IF NOT EXISTS etiqueta_cayados VARCHAR(80)")


def downgrade() -> None:
    op.execute("ALTER TABLE laboratorio.orden_estudios DROP COLUMN IF EXISTS etiqueta_cayados")
