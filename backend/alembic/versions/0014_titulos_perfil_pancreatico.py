"""Alinea los títulos del perfil pancreático con las unidades de sus filas."""
from alembic import op
import sqlalchemy as sa

revision = "0014_titulos_perfil_pancreatico"
down_revision = "0013_coproparasitologicos"
branch_labels = None
depends_on = None


def _actualizar_nombres(amilasa: str, lipasa: str) -> None:
    op.get_bind().execute(sa.text("""
        UPDATE laboratorio.parametros AS p
        SET nombre = CASE p.codigo
            WHEN 'AMILASA_SERICA' THEN :amilasa
            WHEN 'LIPASA_SERICA' THEN :lipasa
        END
        FROM laboratorio.estudio_versiones AS ev
        JOIN laboratorio.estudios AS e USING (id_estudio)
        WHERE p.id_estudio_version = ev.id_estudio_version
          AND e.codigo = 'PERFIL_PANCREATICO'
          AND p.codigo IN ('AMILASA_SERICA', 'LIPASA_SERICA')
    """), {"amilasa": amilasa, "lipasa": lipasa})


def upgrade() -> None:
    _actualizar_nombres("Lipasa sérica", "Amilasa sérica")


def downgrade() -> None:
    _actualizar_nombres("Amilasa sérica", "Lipasa sérica")
