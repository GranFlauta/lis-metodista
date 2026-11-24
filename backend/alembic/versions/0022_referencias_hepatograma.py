"""Sincroniza las referencias predeterminadas de GOT/AST y GPT/ALT."""
from alembic import op
import sqlalchemy as sa

from app.catalog.definitions import HEPATOGRAMA

revision = "0022_referencias_hepatograma"
down_revision = "0021_unidades_coagulacion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    for parametro in HEPATOGRAMA.parametros:
        if parametro.codigo not in {"GOT_AST", "GPT_ALT"}:
            continue
        rango = parametro.rangos[0]
        ids = connection.execute(sa.text("""
            SELECT p.id_parametro
            FROM laboratorio.parametros AS p
            JOIN laboratorio.estudio_versiones AS ev USING (id_estudio_version)
            JOIN laboratorio.estudios AS e USING (id_estudio)
            WHERE e.codigo = :estudio AND p.codigo = :parametro
        """), {"estudio": HEPATOGRAMA.codigo, "parametro": parametro.codigo}).scalars().all()
        for id_parametro in ids:
            valores = {"id": id_parametro, "superior": rango.superior,
                       "incl": rango.superior_incl, "texto": rango.texto, "validar": rango.validar}
            actualizados = connection.execute(sa.text("""
                UPDATE laboratorio.rangos_referencia
                SET limite_superior = :superior, superior_inclusivo = :incl,
                    referencia_texto = :texto, requiere_validacion = :validar
                WHERE id_parametro = :id AND sexo IS NULL
                  AND edad_min_meses IS NULL AND edad_max_meses IS NULL
                RETURNING id_rango_referencia
            """), valores).scalars().all()
            if not actualizados:
                connection.execute(sa.text("""
                    INSERT INTO laboratorio.rangos_referencia
                        (id_parametro, limite_inferior, inferior_inclusivo, limite_superior,
                         superior_inclusivo, referencia_texto, requiere_validacion)
                    VALUES (:id, :inferior, :inf_incl, :superior, :incl, :texto, :validar)
                """), {**valores, "inferior": rango.inferior, "inf_incl": rango.inferior_incl})
    # No se modifican resultados, referencias personalizadas ni snapshots publicados.


def downgrade() -> None:
    raise NotImplementedError("Las referencias clínicas confirmadas se corrigen desde el catálogo.")
