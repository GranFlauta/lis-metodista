"""Ordena el perfil pancreático y sincroniza sus referencias con el catálogo."""
from alembic import op
import sqlalchemy as sa

from app.catalog.definitions import PANCREATICO

revision = "0009_perfil_pancreatico"
down_revision = "0008_catalogo_campos_usados"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    for orden, parametro in enumerate(PANCREATICO.parametros, 1):
        ids = connection.execute(sa.text("""
            UPDATE laboratorio.parametros AS p SET orden_visualizacion = :orden
            FROM laboratorio.estudio_versiones AS ev, laboratorio.estudios AS e
            WHERE p.id_estudio_version = ev.id_estudio_version
              AND ev.id_estudio = e.id_estudio AND e.codigo = :estudio
              AND p.codigo = :parametro
            RETURNING p.id_parametro
        """), {"orden": orden, "estudio": PANCREATICO.codigo, "parametro": parametro.codigo}).scalars().all()
        for id_parametro in ids:
            # Sólo referencias del catálogo: conserva overrides y snapshots oficiales.
            connection.execute(sa.text("DELETE FROM laboratorio.rangos_referencia WHERE id_parametro = :id"), {"id": id_parametro})
            for rango in parametro.rangos:
                connection.execute(sa.text("""
                    INSERT INTO laboratorio.rangos_referencia
                        (id_parametro, sexo, limite_inferior, inferior_inclusivo,
                         limite_superior, superior_inclusivo, referencia_texto, requiere_validacion)
                    VALUES (:id, :sexo, :inferior, :inf_incl, :superior, :sup_incl, :texto, :validar)
                """), {"id": id_parametro, "sexo": rango.sexo, "inferior": rango.inferior,
                        "inf_incl": rango.inferior_incl, "superior": rango.superior,
                        "sup_incl": rango.superior_incl, "texto": rango.texto, "validar": rango.validar})


def downgrade() -> None:
    raise NotImplementedError("Las referencias clínicas se corrigen desde el catálogo, sin revertir valores por defecto.")
