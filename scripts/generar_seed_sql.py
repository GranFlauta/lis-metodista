#!/usr/bin/env python3
"""
Genera db/init/002_seed_catalogo.sql a partir de backend/app/catalog/definitions.py.

    python scripts/generar_seed_sql.py

NO editar el .sql a mano: cambia definitions.py y vuelve a generar.
(Cuando entre Alembic, este generador pasará a ser una migración de datos.)
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

from app.catalog.definitions import ESTUDIOS, PERFILES  # noqa: E402


def q(valor):
    """Literal SQL."""
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        return "TRUE" if valor else "FALSE"
    if isinstance(valor, (int, float)):
        return repr(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def qjson(valor):
    if valor is None:
        return "NULL"
    return q(json.dumps(valor, ensure_ascii=False)) + "::jsonb"


def ver_id(codigo):
    return ("SELECT ev.id_estudio_version FROM estudio_versiones ev "
            f"JOIN estudios e USING (id_estudio) WHERE e.codigo = {q(codigo)} AND ev.numero_version = 1")


def generar() -> str:
    L = [
        "-- GENERADO por scripts/generar_seed_sql.py desde backend/app/catalog/definitions.py",
        "-- NO EDITAR A MANO.",
        "SET search_path TO laboratorio, public;",
        "BEGIN;",
        "",
    ]
    for est in ESTUDIOS:
        L.append(f"-- ===== {est.codigo} =====")
        L.append("INSERT INTO estudios (codigo, nombre, categoria, seleccion_parcial) "
                 f"VALUES ({q(est.codigo)}, {q(est.nombre)}, {q(est.categoria)}, {q(est.seleccion_parcial)});")
        L.append("INSERT INTO estudio_versiones (id_estudio, numero_version, configuracion_json) "
                 f"SELECT id_estudio, 1, {qjson({'reglas': list(est.reglas)})} FROM estudios WHERE codigo = {q(est.codigo)};")
        for orden, p in enumerate(est.parametros, start=1):
            formula = p.formula
            L.append(
                "INSERT INTO parametros (id_estudio_version, codigo, nombre, grupo, tipo_campo, unidad_medida, decimales, "
                "formula_expresion, opciones, valor_defecto, requiere_confirmacion, metodo, muestra, obligatorio, orden_visualizacion) "
                f"SELECT ({ver_id(est.codigo)}), {q(p.codigo)}, {q(p.nombre)}, {q(p.grupo)}, {q(p.tipo)}, {q(p.unidad)}, "
                f"{p.decimales}, {q(formula)}, {qjson(p.opciones)}, {q(p.defecto)}, {q(p.confirmar)}, "
                f"{q(p.metodo)}, {q(p.muestra)}, {q(p.obligatorio)}, {orden};"
            )
            for r in p.rangos:
                L.append(
                    "INSERT INTO rangos_referencia (id_parametro, sexo, limite_inferior, inferior_inclusivo, "
                    "limite_superior, superior_inclusivo, referencia_texto, requiere_validacion) "
                    f"SELECT pa.id_parametro, {q(r.sexo)}, {q(r.inferior)}, {q(r.inferior_incl)}, {q(r.superior)}, "
                    f"{q(r.superior_incl)}, {q(r.texto)}, {q(r.validar)} FROM parametros pa "
                    f"WHERE pa.id_estudio_version = ({ver_id(est.codigo)}) AND pa.codigo = {q(p.codigo)};"
                )
        L.append("")

    L.append("-- ===== PERFILES =====")
    for perfil in PERFILES:
        L.append(f"INSERT INTO perfiles (codigo, nombre) VALUES ({q(perfil.codigo)}, {q(perfil.nombre)});")
        for orden, (cod_est, grupos) in enumerate(perfil.estudios, start=1):
            arr = "NULL" if not grupos else "ARRAY[" + ", ".join(q(g) for g in grupos) + "]::TEXT[]"
            L.append(
                "INSERT INTO perfil_estudios (id_perfil, id_estudio, grupos, orden_visualizacion) "
                f"SELECT pf.id_perfil, e.id_estudio, {arr}, {orden} FROM perfiles pf, estudios e "
                f"WHERE pf.codigo = {q(perfil.codigo)} AND e.codigo = {q(cod_est)};"
            )
    L += ["", "COMMIT;", ""]
    return "\n".join(L)


if __name__ == "__main__":
    destino = RAIZ / "db" / "init" / "002_seed_catalogo.sql"
    destino.write_text(generar(), encoding="utf-8")
    print(f"OK -> {destino.relative_to(RAIZ)}")
