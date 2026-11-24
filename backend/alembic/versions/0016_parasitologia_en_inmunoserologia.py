"""Mueve H. pylori en suero y copia las pruebas cualitativas a Inmunoserología."""
import json

from alembic import op
import sqlalchemy as sa

from app.catalog.definitions import INMUNOSEROLOGIA, PARASITOLOGIA, Param

revision = "0016_inmuno_parasito"
down_revision = "0015_ldh_quimica_perfil_cardiaco"
branch_labels = None
depends_on = None

CODIGO_PARASITOLOGIA = "PARASITOLOGIA"
CODIGO_INMUNOSEROLOGIA = "INMUNOSEROLOGIA"
CODIGO_H_PYLORI_SUERO = "H_PYLORI_SUERO"
CODIGOS_COPIADOS = {
    "H_PYLORI_HECES_INMUNO",
    "SANGRE_OCULTA_HECES_INMUNO",
}
ALIAS_INMUNOSEROLOGIA = {
    "H_PYLORI_HECES": "H_PYLORI_HECES_INMUNO",
    "SANGRE_OCULTA_HECES": "SANGRE_OCULTA_HECES_INMUNO",
}
GRUPOS_INMUNOSEROLOGIA_ANTERIORES = {
    "H_PYLORI_SUERO", "H_PYLORI_HECES", "SANGRE_OCULTA",
}


def _crear_version(connection, codigo_estudio: str, excluir_codigo: str = "") -> tuple[int, int]:
    estudio = connection.execute(sa.text("""
        SELECT e.id_estudio, ev.id_estudio_version
        FROM laboratorio.estudios AS e
        JOIN laboratorio.estudio_versiones AS ev USING (id_estudio)
        WHERE e.codigo = :codigo AND ev.activa
        FOR UPDATE OF ev
    """), {"codigo": codigo_estudio}).mappings().one_or_none()
    if estudio is None:
        raise RuntimeError(f"No existe versión activa para {codigo_estudio}.")

    numero = connection.execute(sa.text("""
        SELECT COALESCE(MAX(numero_version), 0) + 1
        FROM laboratorio.estudio_versiones
        WHERE id_estudio = :id_estudio
    """), {"id_estudio": estudio["id_estudio"]}).scalar_one()
    connection.execute(sa.text("""
        UPDATE laboratorio.estudio_versiones
        SET activa = FALSE
        WHERE id_estudio = :id_estudio AND activa
    """), {"id_estudio": estudio["id_estudio"]})
    id_nueva_version = connection.execute(sa.text("""
        INSERT INTO laboratorio.estudio_versiones
            (id_estudio, numero_version, configuracion_json, activa)
        SELECT id_estudio, :numero,
               configuracion_json || CAST(:revision AS jsonb), TRUE
        FROM laboratorio.estudio_versiones
        WHERE id_estudio_version = :version_anterior
        RETURNING id_estudio_version
    """), {
        "numero": numero,
        "revision": json.dumps({"revision_catalogo": revision}),
        "version_anterior": estudio["id_estudio_version"],
    }).scalar_one()

    connection.execute(sa.text("""
        INSERT INTO laboratorio.parametros (
            id_estudio_version, codigo, nombre, grupo, tipo_campo, unidad_medida,
            decimales, formula_expresion, opciones, valor_defecto,
            requiere_confirmacion, metodo, muestra, obligatorio, orden_visualizacion
        )
        SELECT :version_nueva, codigo, nombre, grupo, tipo_campo, unidad_medida,
               decimales, formula_expresion, opciones, valor_defecto,
               requiere_confirmacion, metodo, muestra, obligatorio, orden_visualizacion
        FROM laboratorio.parametros
        WHERE id_estudio_version = :version_anterior AND codigo <> :excluir
        ORDER BY orden_visualizacion
    """), {
        "version_nueva": id_nueva_version,
        "version_anterior": estudio["id_estudio_version"],
        "excluir": excluir_codigo,
    })
    connection.execute(sa.text("""
        INSERT INTO laboratorio.rangos_referencia (
            id_parametro, sexo, edad_min_meses, edad_max_meses,
            limite_inferior, inferior_inclusivo, limite_superior,
            superior_inclusivo, referencia_texto, requiere_validacion
        )
        SELECT nueva.id_parametro, r.sexo, r.edad_min_meses, r.edad_max_meses,
               r.limite_inferior, r.inferior_inclusivo, r.limite_superior,
               r.superior_inclusivo, r.referencia_texto, r.requiere_validacion
        FROM laboratorio.rangos_referencia AS r
        JOIN laboratorio.parametros AS anterior ON anterior.id_parametro = r.id_parametro
        JOIN laboratorio.parametros AS nueva
          ON nueva.id_estudio_version = :version_nueva AND nueva.codigo = anterior.codigo
        WHERE anterior.id_estudio_version = :version_anterior
    """), {
        "version_nueva": id_nueva_version,
        "version_anterior": estudio["id_estudio_version"],
    })
    return estudio["id_estudio"], id_nueva_version


def _sincronizar_parametro(connection, version: int, parametro: Param, siguiente_orden: int) -> int:
    existente = connection.execute(sa.text("""
        SELECT id_parametro, orden_visualizacion
        FROM laboratorio.parametros
        WHERE id_estudio_version = :version AND codigo = :codigo
    """), {"version": version, "codigo": parametro.codigo}).mappings().one_or_none()
    if existente is None:
        id_parametro = connection.execute(sa.text("""
            INSERT INTO laboratorio.parametros (
                id_estudio_version, codigo, nombre, grupo, tipo_campo, unidad_medida,
                decimales, formula_expresion, opciones, valor_defecto,
                requiere_confirmacion, metodo, muestra, obligatorio, orden_visualizacion
            )
            VALUES (
                :version, :codigo, :nombre, :grupo, :tipo, :unidad,
                :decimales, :formula, CAST(:opciones AS jsonb), :defecto,
                :confirmar, :metodo, :muestra, :obligatorio, :orden
            )
            RETURNING id_parametro
        """), {
            "version": version,
            "codigo": parametro.codigo,
            "nombre": parametro.nombre,
            "grupo": parametro.grupo,
            "tipo": parametro.tipo,
            "unidad": parametro.unidad,
            "decimales": parametro.decimales,
            "formula": parametro.formula,
            "opciones": json.dumps(parametro.opciones),
            "defecto": parametro.defecto,
            "confirmar": parametro.confirmar,
            "metodo": parametro.metodo,
            "muestra": parametro.muestra,
            "obligatorio": parametro.obligatorio,
            "orden": siguiente_orden,
        }).scalar_one()
        siguiente_orden += 1
    else:
        id_parametro = existente["id_parametro"]
        connection.execute(sa.text("""
            UPDATE laboratorio.parametros
            SET nombre = :nombre, grupo = :grupo, tipo_campo = :tipo,
                unidad_medida = :unidad, decimales = :decimales,
                formula_expresion = :formula, opciones = CAST(:opciones AS jsonb),
                valor_defecto = :defecto, requiere_confirmacion = :confirmar,
                metodo = :metodo, muestra = :muestra, obligatorio = :obligatorio
            WHERE id_parametro = :id
        """), {
            "id": id_parametro,
            "nombre": parametro.nombre,
            "grupo": parametro.grupo,
            "tipo": parametro.tipo,
            "unidad": parametro.unidad,
            "decimales": parametro.decimales,
            "formula": parametro.formula,
            "opciones": json.dumps(parametro.opciones),
            "defecto": parametro.defecto,
            "confirmar": parametro.confirmar,
            "metodo": parametro.metodo,
            "muestra": parametro.muestra,
            "obligatorio": parametro.obligatorio,
        })
    connection.execute(sa.text("""
        DELETE FROM laboratorio.rangos_referencia WHERE id_parametro = :id
    """), {"id": id_parametro})
    return siguiente_orden


def _siguiente_orden(connection, version: int) -> int:
    return connection.execute(sa.text("""
        SELECT COALESCE(MAX(orden_visualizacion), 0) + 1
        FROM laboratorio.parametros WHERE id_estudio_version = :version
    """), {"version": version}).scalar_one()


def _sincronizar_subestudios_inmuno(connection, version: int) -> None:
    for codigo in ALIAS_INMUNOSEROLOGIA:
        connection.execute(sa.text("""
            DELETE FROM laboratorio.parametros
            WHERE id_estudio_version = :version AND codigo = :codigo
        """), {"version": version, "codigo": codigo})

    siguiente = _siguiente_orden(connection, version)
    subestudios = [
        parametro for parametro in INMUNOSEROLOGIA.parametros
        if parametro.codigo == CODIGO_H_PYLORI_SUERO or parametro.codigo in CODIGOS_COPIADOS
    ]
    for parametro in subestudios:
        siguiente = _sincronizar_parametro(connection, version, parametro, siguiente)


def _sincronizar_selecciones_parasito(connection, version: int) -> None:
    siguiente = _siguiente_orden(connection, version)
    for parametro in PARASITOLOGIA.parametros:
        if parametro.codigo in {"H_PYLORI_HECES", "SANGRE_OCULTA_HECES"}:
            siguiente = _sincronizar_parametro(connection, version, parametro, siguiente)


def _mapa_parametros(connection, version: int) -> dict[str, int]:
    return dict(connection.execute(sa.text("""
        SELECT codigo, id_parametro
        FROM laboratorio.parametros WHERE id_estudio_version = :version
    """), {"version": version}).all())


def _estudios_borrador(connection, id_estudio: int) -> list[tuple[int, int]]:
    return connection.execute(sa.text("""
        SELECT oe.id_orden_estudio, oe.id_orden
        FROM laboratorio.orden_estudios AS oe
        JOIN laboratorio.ordenes AS o USING (id_orden)
        WHERE oe.id_estudio = :estudio AND o.estado_trabajo <> 'PUBLICADA'
        ORDER BY oe.id_orden_estudio
        FOR UPDATE OF oe, o
    """), {"estudio": id_estudio}).all()


def _resultados_borrador(connection, id_orden_estudio: int) -> list[tuple[int, str]]:
    return connection.execute(sa.text("""
        SELECT r.id_resultado, p.codigo
        FROM laboratorio.resultados_borrador AS r
        JOIN laboratorio.parametros AS p USING (id_parametro)
        WHERE r.id_orden_estudio = :orden_estudio AND r.id_edicion IS NULL
        FOR UPDATE OF r
    """), {"orden_estudio": id_orden_estudio}).all()


def _agregar_grupo_parasito(connection, id_orden_estudio: int) -> None:
    connection.execute(sa.text("""
        INSERT INTO laboratorio.orden_estudio_grupos (id_orden_estudio, grupo)
        VALUES (:orden_estudio, :grupo)
        ON CONFLICT (id_orden_estudio, grupo) DO NOTHING
    """), {"orden_estudio": id_orden_estudio, "grupo": CODIGO_PARASITOLOGIA})


def _orden_inmunoserologia(connection, id_orden: int, id_estudio: int, version: int) -> int:
    existente = connection.execute(sa.text("""
        SELECT id_orden_estudio
        FROM laboratorio.orden_estudios
        WHERE id_orden = :orden AND id_estudio = :estudio
        FOR UPDATE
    """), {"orden": id_orden, "estudio": id_estudio}).scalar_one_or_none()
    if existente is not None:
        connection.execute(sa.text("""
            UPDATE laboratorio.orden_estudios SET id_estudio_version = :version
            WHERE id_orden_estudio = :orden_estudio
        """), {"version": version, "orden_estudio": existente})
        return existente

    return connection.execute(sa.text("""
        INSERT INTO laboratorio.orden_estudios (id_orden, id_estudio, id_estudio_version)
        VALUES (:orden, :estudio, :version)
        RETURNING id_orden_estudio
    """), {"orden": id_orden, "estudio": id_estudio, "version": version}).scalar_one()


def _mover_resultado(
    connection,
    id_resultado: int,
    id_orden_estudio: int,
    id_parametro: int,
) -> None:
    conflicto = connection.execute(sa.text("""
        SELECT 1
        FROM laboratorio.resultados_borrador
        WHERE id_orden_estudio = :orden_estudio AND id_parametro = :parametro
          AND id_edicion IS NULL AND id_resultado <> :resultado
    """), {
        "orden_estudio": id_orden_estudio,
        "parametro": id_parametro,
        "resultado": id_resultado,
    }).first()
    if conflicto:
        raise RuntimeError("Hay resultados duplicados para un subestudio; se cancela la migración sin fusionarlos.")

    connection.execute(sa.text("""
        UPDATE laboratorio.resultados_borrador
        SET id_orden_estudio = :orden_estudio, id_parametro = :parametro
        WHERE id_resultado = :resultado
    """), {
        "orden_estudio": id_orden_estudio,
        "parametro": id_parametro,
        "resultado": id_resultado,
    })


def _migrar_borradores_inmuno(connection, id_estudio: int, version: int, parametros: dict[str, int]) -> None:
    for id_orden_estudio, _ in _estudios_borrador(connection, id_estudio):
        grupos = connection.execute(sa.text("""
            SELECT grupo FROM laboratorio.orden_estudio_grupos
            WHERE id_orden_estudio = :orden_estudio
        """), {"orden_estudio": id_orden_estudio}).scalars().all()
        grupos_anteriores = set(grupos) & GRUPOS_INMUNOSEROLOGIA_ANTERIORES
        for grupo in grupos_anteriores:
            connection.execute(sa.text("""
                DELETE FROM laboratorio.orden_estudio_grupos
                WHERE id_orden_estudio = :orden_estudio AND grupo = :grupo
            """), {"orden_estudio": id_orden_estudio, "grupo": grupo})
        if grupos_anteriores:
            _agregar_grupo_parasito(connection, id_orden_estudio)

        for id_resultado, codigo in _resultados_borrador(connection, id_orden_estudio):
            codigo_destino = ALIAS_INMUNOSEROLOGIA.get(codigo, codigo)
            id_parametro = parametros.get(codigo_destino)
            if id_parametro is None:
                raise RuntimeError(f"No hay correspondencia en Inmunoserología para {codigo}.")
            _mover_resultado(connection, id_resultado, id_orden_estudio, id_parametro)
            if codigo_destino in {CODIGO_H_PYLORI_SUERO, *CODIGOS_COPIADOS}:
                _agregar_grupo_parasito(connection, id_orden_estudio)
        connection.execute(sa.text("""
            UPDATE laboratorio.orden_estudios
            SET id_estudio_version = :version
            WHERE id_orden_estudio = :orden_estudio
        """), {"version": version, "orden_estudio": id_orden_estudio})


def _migrar_borradores_parasito(
    connection,
    id_estudio: int,
    version: int,
    parametros: dict[str, int],
    id_estudio_inmuno: int,
    version_inmuno: int,
    parametros_inmuno: dict[str, int],
) -> None:
    for id_orden_estudio, id_orden in _estudios_borrador(connection, id_estudio):
        for id_resultado, codigo in _resultados_borrador(connection, id_orden_estudio):
            if codigo == CODIGO_H_PYLORI_SUERO:
                id_destino_orden = _orden_inmunoserologia(
                    connection, id_orden, id_estudio_inmuno, version_inmuno
                )
                _agregar_grupo_parasito(connection, id_destino_orden)
                id_parametro = parametros_inmuno.get(CODIGO_H_PYLORI_SUERO)
                if id_parametro is None:
                    raise RuntimeError("No hay correspondencia de H. pylori (suero) en Inmunoserología.")
            else:
                id_destino_orden = id_orden_estudio
                id_parametro = parametros.get(codigo)
                if id_parametro is None:
                    raise RuntimeError(f"No hay correspondencia en Parasitología para {codigo}.")
            _mover_resultado(connection, id_resultado, id_destino_orden, id_parametro)
        connection.execute(sa.text("""
            UPDATE laboratorio.orden_estudios
            SET id_estudio_version = :version
            WHERE id_orden_estudio = :orden_estudio
        """), {"version": version, "orden_estudio": id_orden_estudio})


def upgrade() -> None:
    connection = op.get_bind()
    id_estudio_inmuno, version_inmuno = _crear_version(connection, CODIGO_INMUNOSEROLOGIA)
    _sincronizar_subestudios_inmuno(connection, version_inmuno)
    id_estudio_parasito, version_parasito = _crear_version(
        connection, CODIGO_PARASITOLOGIA, excluir_codigo=CODIGO_H_PYLORI_SUERO
    )
    _sincronizar_selecciones_parasito(connection, version_parasito)

    parametros_inmuno = _mapa_parametros(connection, version_inmuno)
    parametros_parasito = _mapa_parametros(connection, version_parasito)
    _migrar_borradores_inmuno(
        connection, id_estudio_inmuno, version_inmuno, parametros_inmuno
    )
    _migrar_borradores_parasito(
        connection, id_estudio_parasito, version_parasito, parametros_parasito,
        id_estudio_inmuno, version_inmuno, parametros_inmuno,
    )


def downgrade() -> None:
    raise NotImplementedError(
        "No se revierten los movimientos de resultados ni se eliminan versiones de catálogo con datos asociados."
    )
