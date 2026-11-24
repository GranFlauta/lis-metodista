"""Amplía el catálogo y permite informar únicamente campos utilizados."""
import json

from alembic import op
import sqlalchemy as sa

from app.catalog.definitions import ESTUDIOS

revision = "0008_catalogo_campos_usados"
down_revision = "0007_captura_serologia_ego"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    for estudio in ESTUDIOS:
        id_estudio = connection.execute(sa.text("""
            INSERT INTO laboratorio.estudios (codigo, nombre, categoria, seleccion_parcial)
            VALUES (:codigo, :nombre, :categoria, :parcial)
            ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre
            RETURNING id_estudio
        """), {"codigo": estudio.codigo, "nombre": estudio.nombre, "categoria": estudio.categoria,
                "parcial": estudio.seleccion_parcial}).scalar_one()
        config = json.dumps({"reglas": list(estudio.reglas), "captura": estudio.captura,
                             "seleccion_campos": estudio.seleccion_campos})
        connection.execute(sa.text("""
            INSERT INTO laboratorio.estudio_versiones (id_estudio, numero_version, configuracion_json)
            VALUES (:id, 1, CAST(:config AS jsonb)) ON CONFLICT (id_estudio, numero_version) DO NOTHING
        """), {"id": id_estudio, "config": config})
        versiones = connection.execute(sa.text("SELECT id_estudio_version FROM laboratorio.estudio_versiones WHERE id_estudio = :id"), {"id": id_estudio}).scalars().all()
        for version in versiones:
            connection.execute(sa.text("""
                UPDATE laboratorio.estudio_versiones SET configuracion_json = configuracion_json || CAST(:config AS jsonb)
                WHERE id_estudio_version = :version
            """), {"version": version, "config": config})
            for orden, parametro in enumerate(estudio.parametros, 1):
                existente = connection.execute(sa.text("SELECT id_parametro FROM laboratorio.parametros WHERE id_estudio_version = :version AND codigo = :codigo"),
                                                {"version": version, "codigo": parametro.codigo}).scalar_one_or_none()
                valores = {"version": version, "codigo": parametro.codigo, "nombre": parametro.nombre,
                           "grupo": parametro.grupo, "tipo": parametro.tipo, "unidad": parametro.unidad,
                           "decimales": parametro.decimales, "formula": parametro.formula,
                           "opciones": json.dumps(parametro.opciones) if parametro.opciones is not None else None,
                           "defecto": parametro.defecto, "confirmar": parametro.confirmar,
                           "metodo": parametro.metodo, "muestra": parametro.muestra,
                           "obligatorio": parametro.obligatorio, "orden": orden}
                if existente is not None:
                    # Actualiza la presentación del catálogo, nunca resultados ni snapshots.
                    connection.execute(sa.text("""
                        UPDATE laboratorio.parametros SET grupo = :grupo, orden_visualizacion = :orden,
                            tipo_campo = :tipo, opciones = CAST(:opciones AS jsonb), unidad_medida = :unidad
                        WHERE id_estudio_version = :version AND codigo = :codigo
                    """), valores)
                    continue
                id_parametro = connection.execute(sa.text("""
                    INSERT INTO laboratorio.parametros
                        (id_estudio_version, codigo, nombre, grupo, tipo_campo, unidad_medida, decimales,
                         formula_expresion, opciones, valor_defecto, requiere_confirmacion, metodo, muestra,
                         obligatorio, orden_visualizacion)
                    VALUES (:version, :codigo, :nombre, :grupo, :tipo, :unidad, :decimales, :formula,
                            CAST(:opciones AS jsonb), :defecto, :confirmar, :metodo, :muestra, :obligatorio, :orden)
                    RETURNING id_parametro
                """), valores).scalar_one()
                for rango in parametro.rangos:
                    connection.execute(sa.text("""
                        INSERT INTO laboratorio.rangos_referencia
                            (id_parametro, sexo, limite_inferior, inferior_inclusivo, limite_superior,
                             superior_inclusivo, referencia_texto, requiere_validacion)
                        VALUES (:id, :sexo, :inferior, :inf_incl, :superior, :sup_incl, :texto, :validar)
                    """), {"id": id_parametro, "sexo": rango.sexo, "inferior": rango.inferior,
                            "inf_incl": rango.inferior_incl, "superior": rango.superior,
                            "sup_incl": rango.superior_incl, "texto": rango.texto, "validar": rango.validar})
    connection.execute(sa.text("""
        INSERT INTO laboratorio.orden_estudio_grupos (id_orden_estudio, grupo)
        SELECT DISTINCT id_orden_estudio, 'PARASITOLOGIA' FROM laboratorio.orden_estudio_grupos
        WHERE grupo IN ('H_PYLORI_SUERO', 'H_PYLORI_HECES', 'SANGRE_OCULTA')
        ON CONFLICT DO NOTHING
    """))
    connection.execute(sa.text("DELETE FROM laboratorio.orden_estudio_grupos WHERE grupo IN ('H_PYLORI_SUERO', 'H_PYLORI_HECES', 'SANGRE_OCULTA')"))
    connection.execute(sa.text("""
        UPDATE laboratorio.perfil_estudios SET grupos = ARRAY(
            SELECT DISTINCT CASE WHEN g IN ('H_PYLORI_SUERO', 'H_PYLORI_HECES', 'SANGRE_OCULTA') THEN 'PARASITOLOGIA' ELSE g END
            FROM unnest(grupos) AS g
        ) WHERE grupos && ARRAY['H_PYLORI_SUERO', 'H_PYLORI_HECES', 'SANGRE_OCULTA']::text[]
    """))
    perfiles = connection.execute(sa.text("SELECT id_perfil_rapido, estudios FROM laboratorio.perfiles_rapidos")).all()
    for id_perfil, items in perfiles:
        cambio = False
        for item in items:
            if item.get("codigo") == "INMUNOSEROLOGIA" and item.get("grupos"):
                anteriores = item["grupos"]
                item["grupos"] = list(dict.fromkeys("PARASITOLOGIA" if g in {"H_PYLORI_SUERO", "H_PYLORI_HECES", "SANGRE_OCULTA"} else g for g in anteriores))
                cambio |= item["grupos"] != anteriores
        if cambio:
            connection.execute(sa.text("UPDATE laboratorio.perfiles_rapidos SET estudios = CAST(:items AS jsonb) WHERE id_perfil_rapido = :id"),
                               {"id": id_perfil, "items": json.dumps(items)})


def downgrade() -> None:
    raise NotImplementedError("Esta migración de catálogo conserva resultados clínicos y no se revierte borrando parámetros.")
