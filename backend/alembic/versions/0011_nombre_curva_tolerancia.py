"""Aclara el nombre visible del estudio de curva de tolerancia."""
from alembic import op

revision = "0011_nombre_curva_tolerancia"
down_revision = "0010_curva_parasitologia"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE laboratorio.estudios "
        "SET nombre = 'Curva de tolerancia' "
        "WHERE codigo = 'CURVA_TOLERANCIA'"
    )


def downgrade():
    op.execute(
        "UPDATE laboratorio.estudios "
        "SET nombre = 'Curva tolerancia' "
        "WHERE codigo = 'CURVA_TOLERANCIA'"
    )
