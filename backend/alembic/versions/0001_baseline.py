"""baseline

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-10-11 00:00:00.000000

El esquema base lo crea db/init/*.sql. Desde el primer despliegue con datos reales,
db/init/001 queda CONGELADO y todo cambio va en migraciones.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # El esquema base lo crea db/init/*.sql. Desde el primer despliegue con datos reales,
    # db/init/001 queda CONGELADO y todo cambio va en migraciones.
    pass


def downgrade() -> None:
    pass
