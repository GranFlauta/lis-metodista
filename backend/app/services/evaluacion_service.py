"""
Servicio de evaluación clínica, cálculo en vivo, reglas cruzadas, banderas y completitud.
Implementa estrictamente PROMPT_FASE_3.md §7 y §8, y docs/DECISIONES.md §12 (D3-01 a D3-11).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy.orm import Session, joinedload

from app.calculation.engine import (
    ResultadoCalculo,
    a_decimal,
    calcular,
    redondear,
    variables_de,
)
from app.core.clock import ahora
from app.core.errors import (
    ConflictoError,
    NoEncontradoError,
    ProhibidoError,
    ValidacionError,
)
from app.models.catalog import Estudio, EstudioVersion, Parametro, RangoReferencia
from app.models.order import Orden, OrdenEstudio, OrdenEstudioGrupo
from app.models.patient import Paciente
from app.models.result import ResultadoBorrador
from app.models.user import Usuario


def formatear_decimal(val: Decimal | float | int | None) -> str | None:
    """Convierte un Decimal a string con punto sin ceros finales superfluos."""
    if val is None:
        return None
    d = Decimal(str(val))
    texto = f"{d:f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto if texto else "0"


def formatear_valor_parametro(tipo_campo: str, valor_numerico: Decimal | None, valor_texto: str | None, decimales: int = 2) -> str | None:
    """Formatea el valor para la API según su tipo de campo."""
    if tipo_campo in ("NUMERICO", "CALCULADO"):
        if valor_numerico is None:
            return None
        if tipo_campo == "CALCULADO":
            if decimales > 0:
                return f"{valor_numerico:.{decimales}f}"
            return f"{valor_numerico:.0f}"
        return formatear_decimal(valor_numerico)
    return valor_texto


def orden_topologico_parametros(parametros: list[Parametro]) -> tuple[list[Parametro], list[Parametro]]:
    """
    Separa parámetros no calculados y ordena topológicamente los calculados.
    Si se detecta un ciclo de dependencias entre calculados, lanza ValueError (error de configuración).
    """
    no_calculados = [p for p in parametros if p.tipo_campo != "CALCULADO"]
    calculados = [p for p in parametros if p.tipo_campo == "CALCULADO"]

    if not calculados:
        return no_calculados, []

    calc_map = {p.codigo.lower(): p for p in calculados}
    codigos_calc = set(calc_map.keys())

    # Grafo de dependencias entre calculados
    in_degree: dict[str, int] = defaultdict(int)
    dependientes: dict[str, list[str]] = defaultdict(list)

    for p in calculados:
        codigo = p.codigo.lower()
        if not p.formula_expresion:
            raise ValueError(f"Parámetro CALCULADO sin fórmula: {p.codigo}")
        vars_usadas = variables_de(p.formula_expresion)
        deps_calc = vars_usadas & codigos_calc
        in_degree[codigo] = len(deps_calc)
        for dep in deps_calc:
            dependientes[dep].append(codigo)

    cola = [c for c in codigos_calc if in_degree[c] == 0]
    ordenados_codigos: list[str] = []

    while cola:
        c = cola.pop(0)
        ordenados_codigos.append(c)
        for sig in dependientes[c]:
            in_degree[sig] -= 1
            if in_degree[sig] == 0:
                cola.append(sig)

    if len(ordenados_codigos) < len(calculados):
        ciclo_codigos = codigos_calc - set(ordenados_codigos)
        raise ValueError(f"Ciclo de dependencias detectado en parámetros calculados: {ciclo_codigos}")

    return no_calculados, [calc_map[c] for c in ordenados_codigos]


def evaluar_rango_y_bandera(
    parametro: Parametro,
    valor_numerico: Decimal | None,
    sexo_paciente: str | None,
    edad_meses_orden: int | None,
) -> tuple[dict[str, str | None] | None, str | None]:
    """
    Selecciona el rango de referencia aplicable por sexo y edad en meses (D3-07).
    Evalúa si el valor es BAJO, NORMAL o ALTO respetando límites inclusivos/exclusivos.
    Solo aplica a valores numéricos; para cualitativos o sin rango devuelve (None, None).
    """
    if parametro.tipo_campo not in ("NUMERICO", "CALCULADO") or not parametro.rangos_referencia:
        return None, None

    candidatos = []
    for r in parametro.rangos_referencia:
        # Filtro de sexo
        if r.sexo is not None and sexo_paciente is not None:
            if r.sexo.upper() != sexo_paciente.upper():
                continue

        # Filtro de edad
        if edad_meses_orden is not None:
            if r.edad_min_meses is not None and edad_meses_orden < r.edad_min_meses:
                continue
            if r.edad_max_meses is not None and edad_meses_orden > r.edad_max_meses:
                continue
        elif r.edad_min_meses is not None or r.edad_max_meses is not None:
            continue

        candidatos.append(r)

    if not candidatos:
        return None, None

    # Ordenar por especificidad: mayor preferencia a sexo coincidente y límites de edad definidos
    candidatos.sort(
        key=lambda r: (
            1 if (r.sexo is not None and sexo_paciente is not None and r.sexo.upper() == sexo_paciente.upper()) else 0,
            1 if (r.edad_min_meses is not None or r.edad_max_meses is not None) else 0,
        ),
        reverse=True,
    )
    r_elegido = candidatos[0]

    inf_str = formatear_decimal(r_elegido.limite_inferior) if r_elegido.limite_inferior is not None else None
    sup_str = formatear_decimal(r_elegido.limite_superior) if r_elegido.limite_superior is not None else None

    ref_dict = {
        "texto": r_elegido.referencia_texto or (f"{inf_str} - {sup_str}" if inf_str and sup_str else None),
        "inferior": inf_str,
        "superior": sup_str,
    }

    if valor_numerico is None:
        return ref_dict, None

    bandera = "NORMAL"
    # Límite inferior
    if r_elegido.limite_inferior is not None:
        if r_elegido.inferior_inclusivo:
            if valor_numerico < r_elegido.limite_inferior:
                bandera = "BAJO"
        else:
            if valor_numerico <= r_elegido.limite_inferior:
                bandera = "BAJO"

    # Límite superior
    if r_elegido.limite_superior is not None:
        if r_elegido.superior_inclusivo:
            if valor_numerico > r_elegido.limite_superior:
                bandera = "ALTO"
        else:
            if valor_numerico >= r_elegido.limite_superior:
                bandera = "ALTO"

    return ref_dict, bandera


def evaluar_reglas_cruzadas(
    reglas: list[dict[str, Any]],
    valores_numericos: dict[str, Decimal | None],
    parametros_por_codigo: dict[str, Parametro],
) -> list[dict[str, Any]]:
    """
    Evalúa reglas cruzadas SUMA_IGUAL y MENOR_IGUAL definidas en la versión del estudio.
    Lanza ValueError si se encuentra un tipo de regla desconocido (test 26).
    """
    validaciones = []
    for regla in reglas:
        tipo = regla.get("tipo")
        severidad = regla.get("severidad", "ADVERTENCIA")
        mensaje = regla.get("mensaje", "")
        param_codigos = regla.get("parametros", [])

        if tipo == "SUMA_IGUAL":
            # SUMA_IGUAL: se evalúa cuando todos los parámetros obligatorios listados tienen valor;
            # los opcionales ausentes cuentan como 0 solo para esta suma. Falla si |suma − valor| > tolerancia.
            obligatorios = [c for c in param_codigos if parametros_por_codigo.get(c) and parametros_por_codigo[c].obligatorio]
            todos_obligatorios_presentes = all(valores_numericos.get(c) is not None for c in obligatorios)

            if not todos_obligatorios_presentes:
                continue

            suma = Decimal("0")
            for c in param_codigos:
                v = valores_numericos.get(c)
                if v is not None:
                    suma += v
                else:
                    p = parametros_por_codigo.get(c)
                    if p and not p.obligatorio:
                        suma += Decimal("0")

            valor_esperado = Decimal(str(regla.get("valor", 100)))
            tolerancia = Decimal(str(regla.get("tolerancia", 0)))
            if abs(suma - valor_esperado) > tolerancia:
                validaciones.append({
                    "severidad": severidad,
                    "mensaje": mensaje,
                    "parametros": param_codigos,
                })

        elif tipo == "MENOR_IGUAL":
            # MENOR_IGUAL: parametros = [a, b], falla si a > b; se evalúa solo si ambos tienen valor.
            if len(param_codigos) != 2:
                raise ValueError(f"Regla MENOR_IGUAL requiere exactamente 2 parámetros: {param_codigos}")
            a_cod, b_cod = param_codigos[0], param_codigos[1]
            val_a = valores_numericos.get(a_cod)
            val_b = valores_numericos.get(b_cod)
            if val_a is not None and val_b is not None:
                if val_a > val_b:
                    validaciones.append({
                        "severidad": severidad,
                        "mensaje": mensaje,
                        "parametros": param_codigos,
                    })

        else:
            raise ValueError(f"Tipo de regla desconocido: {tipo}")

    return validaciones


def motivo_no_calculable_en_espanol(
    param_codigo: str,
    codigo_motivo: str | None,
    motivo_raw: str | None,
) -> str:
    """Traduce el motivo a mensaje clínico legible en español según §8.1."""
    if codigo_motivo == "FALTA_ENTRADA":
        if motivo_raw and motivo_raw.startswith("falta "):
            var_nom = motivo_raw.replace("falta ", "").upper()
            return f"Falta el valor de {var_nom}"
        return "Faltan datos de entrada"
    elif codigo_motivo == "DIVISION_POR_CERO":
        return "División por cero"
    elif codigo_motivo == "REGLA_INVALIDA":
        if param_codigo == "LDL":
            return "No válido con triglicéridos > 400"
        elif param_codigo == "BILIRRUBINA_INDIRECTA":
            return "Bilirrubina directa mayor que la total"
        elif param_codigo == "RELACION_AG":
            return "Albúmina mayor o igual que proteínas totales"
        return "Regla de validez incumplida"
    return motivo_raw or "No calculable"


def obtener_parametros_alcance_orden(orden: Orden) -> dict[int, list[Parametro]]:
    """
    Retorna los parámetros aplicables para cada OrdenEstudio de la orden,
    filtrando por orden_estudio_grupos en estudios de seleccion_parcial (D3-03).
    """
    alcance: dict[int, list[Parametro]] = {}
    for oe in orden.estudios:
        ev = oe.estudio_version
        est = oe.estudio
        todos_params = list(ev.parametros)
        if est.seleccion_parcial:
            grupos_pedidos = {g.grupo for g in oe.grupos}
            alcance[oe.id_orden_estudio] = [p for p in todos_params if p.grupo in grupos_pedidos]
        else:
            alcance[oe.id_orden_estudio] = todos_params
    return alcance


def normalizar_y_validar_valor_entrada(
    parametro: Parametro,
    valor_crudo: Any,
) -> tuple[Decimal | None, str | None]:
    """
    Valida y normaliza el valor según el tipo de campo del parámetro (D3-04).
    Devuelve (valor_numerico, valor_texto).
    """
    if valor_crudo is None or (isinstance(valor_crudo, str) and valor_crudo.strip() == ""):
        return None, None

    tipo = parametro.tipo_campo
    val_str = str(valor_crudo).strip()

    if tipo == "NUMERICO":
        texto_punto = val_str.replace(",", ".")
        try:
            d = Decimal(texto_punto)
        except InvalidOperation:
            raise ValidacionError(f"Valor numérico inválido para {parametro.codigo}: {val_str}")
        if d < 0:
            raise ValidacionError(f"El valor de {parametro.codigo} no puede ser negativo.")
        if "." in texto_punto:
            decimales_ingresados = len(texto_punto.split(".")[1])
            if decimales_ingresados > 6:
                raise ValidacionError(f"El valor de {parametro.codigo} no puede tener más de 6 decimales.")
        return d, None

    elif tipo == "SELECCION":
        opciones = parametro.opciones or []
        if val_str not in opciones:
            raise ValidacionError(f"El valor '{val_str}' no es una opción permitida para {parametro.codigo}.")
        return None, val_str

    elif tipo == "TEXTO_LIBRE":
        if len(val_str) > 500:
            raise ValidacionError(f"El texto para {parametro.codigo} no puede exceder 500 caracteres.")
        return None, val_str

    elif tipo == "RECUENTO_MICROSCOPICO":
        if len(val_str) > 50:
            raise ValidacionError(f"El recuento microscópico para {parametro.codigo} no puede exceder 50 caracteres.")
        return None, val_str

    elif tipo == "FECHA":
        try:
            f_fecha = date.fromisoformat(val_str)
        except ValueError:
            raise ValidacionError(f"Fecha inválida para {parametro.codigo}. Use formato AAAA-MM-DD.")
        hoy = ahora().date()
        if f_fecha > hoy:
            raise ValidacionError(f"La fecha para {parametro.codigo} no puede ser futura.")
        return None, val_str

    elif tipo == "CALCULADO":
        raise ValidacionError(f"No se permite ingresar valores directamente para el parámetro calculado {parametro.codigo}.")

    else:
        raise ValidacionError(f"Tipo de campo desconocido: {tipo}")


def evaluar_captura_orden(
    orden: Orden,
    valores_simulados: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Construye la forma común de respuesta ("captura") según §8.1.
    Si se suministra `valores_simulados`, evalúa en memoria (para POST /calcular) sin persistir.
    De lo contrario, evalúa a partir de las filas persistidas en `resultados_borrador`.
    """
    paciente = orden.paciente
    edad_meses_total = ((orden.edad_anios or 0) * 12) + (orden.edad_meses or 0)

    # Alcance de parámetros por estudio
    alcance_por_oe = obtener_parametros_alcance_orden(orden)

    # Cargar valores existentes o mapear simulados
    # mapa_por_oe_param: id_orden_estudio -> codigo -> (valor_numerico, valor_texto, confirmado, es_defecto)
    mapa_valores: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)

    if valores_simulados is None:
        # Modo lectura persistida
        session = Session.object_session(orden)
        if session:
            filas_db = (
                session.query(ResultadoBorrador)
                .join(OrdenEstudio)
                .filter(OrdenEstudio.id_orden == orden.id_orden, ResultadoBorrador.id_edicion.is_(None))
                .all()
            )
        else:
            filas_db = [rb for oe in orden.estudios for rb in oe.resultados if rb.id_edicion is None]

        for rb in filas_db:
            if rb.parametro:
                cod = rb.parametro.codigo
                mapa_valores[rb.id_orden_estudio][cod] = {
                    "valor_numerico": rb.valor_numerico,
                    "valor_texto": rb.valor_texto,
                    "confirmado": rb.confirmado,
                    "es_defecto": False,
                    "es_calculado": rb.es_calculado,
                    "calculable": rb.calculable,
                }
    else:
        # Modo simulación
        # Normalizar entradas simuladas
        for oe in orden.estudios:
            params_alcance = alcance_por_oe[oe.id_orden_estudio]
            params_map = {p.codigo: p for p in params_alcance}
            for cod, val in valores_simulados.items():
                if cod in params_map and params_map[cod].tipo_campo != "CALCULADO":
                    p = params_map[cod]
                    if val is not None and str(val).strip() != "":
                        v_num, v_txt = normalizar_y_validar_valor_entrada(p, val)
                        mapa_valores[oe.id_orden_estudio][cod] = {
                            "valor_numerico": v_num,
                            "valor_texto": v_txt,
                            "confirmado": True,
                            "es_defecto": False,
                            "es_calculado": False,
                            "calculable": True,
                        }

    # Procesar estudios, cálculos, banderas y validaciones
    estudios_resp = []
    pendientes_totales: list[str] = []
    sin_confirmar_totales: list[str] = []
    errores_totales: list[str] = []

    for oe in orden.estudios:
        est = oe.estudio
        ev = oe.estudio_version
        params_alcance = alcance_por_oe[oe.id_orden_estudio]
        params_por_cod = {p.codigo: p for p in params_alcance}

        # Separar no calculados y ordenar calculados topológicamente
        no_calc_params, calc_params = orden_topologico_parametros(params_alcance)

        # Contexto de cálculo para este estudio
        ctx_calculo: dict[str, Decimal | None] = {}
        for p in no_calc_params:
            stored = mapa_valores[oe.id_orden_estudio].get(p.codigo)
            if stored and stored.get("valor_numerico") is not None:
                ctx_calculo[p.codigo.lower()] = stored["valor_numerico"]
            else:
                ctx_calculo[p.codigo.lower()] = None

        # Evaluar cada calculado en orden de dependencias
        resultados_calc: dict[str, ResultadoCalculo] = {}
        for p in calc_params:
            if p.formula_expresion:
                vars_req = variables_de(p.formula_expresion)
                faltan_entradas = any(ctx_calculo.get(v) is None for v in vars_req)

                r_calc = calcular(p.formula_expresion, ctx_calculo, p.decimales)
                if faltan_entradas:
                    r_calc = ResultadoCalculo(None, False, "faltan datos de entrada", "FALTA_ENTRADA")

                resultados_calc[p.codigo] = r_calc
                if r_calc.calculable and r_calc.valor is not None:
                    ctx_calculo[p.codigo.lower()] = r_calc.valor
                else:
                    ctx_calculo[p.codigo.lower()] = None

        # Evaluar reglas cruzadas
        reglas = ev.configuracion_json.get("reglas", []) if ev.configuracion_json else []
        valores_numericos_estudio: dict[str, Decimal | None] = {}
        for p in params_alcance:
            if p.tipo_campo == "CALCULADO":
                r_c = resultados_calc.get(p.codigo)
                valores_numericos_estudio[p.codigo] = r_c.valor if (r_c and r_c.calculable) else None
            else:
                st = mapa_valores[oe.id_orden_estudio].get(p.codigo)
                valores_numericos_estudio[p.codigo] = st.get("valor_numerico") if st else None

        validaciones_estudio = evaluar_reglas_cruzadas(reglas, valores_numericos_estudio, params_por_cod)
        for val_err in validaciones_estudio:
            if val_err["severidad"] == "ERROR":
                errores_totales.append(val_err["mensaje"])

        # Agrupar parámetros por secciones (grupos)
        # Mantener orden de primera aparición del grupo según orden_visualizacion
        secciones_map: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
        grupos_orden: list[str | None] = []

        for p in params_alcance:
            grp = p.grupo
            if grp not in grupos_orden:
                grupos_orden.append(grp)

            # Extraer valor actual, estado de defecto y banderas
            valor_final_str: str | None = None
            es_calculado = (p.tipo_campo == "CALCULADO")
            calculable = True
            motivo_no_calc: str | None = None
            confirmado = True
            es_defecto = False
            v_num: Decimal | None = None

            if es_calculado:
                r_c = resultados_calc.get(p.codigo)
                if r_c and r_c.calculable and r_c.valor is not None:
                    v_num = r_c.valor
                    valor_final_str = formatear_valor_parametro(p.tipo_campo, v_num, None, p.decimales)
                    calculable = True
                else:
                    v_num = None
                    valor_final_str = None
                    calculable = False
                    codigo_mot = r_c.codigo_motivo if r_c else "FALTA_ENTRADA"
                    mot_raw = r_c.motivo if r_c else None
                    motivo_no_calc = motivo_no_calculable_en_espanol(p.codigo, codigo_mot, mot_raw)
            else:
                st = mapa_valores[oe.id_orden_estudio].get(p.codigo)
                if st is not None:
                    v_num = st.get("valor_numerico")
                    valor_final_str = formatear_valor_parametro(p.tipo_campo, v_num, st.get("valor_texto"), p.decimales)
                    confirmado = st.get("confirmado", True)
                    es_defecto = st.get("es_defecto", False)
                elif p.valor_defecto is not None:
                    # Valor por defecto virtual (D3-05)
                    valor_final_str = p.valor_defecto
                    es_defecto = True
                    confirmado = False
                    if p.tipo_campo == "NUMERICO":
                        try:
                            v_num = a_decimal(p.valor_defecto)
                        except ValueError:
                            v_num = None
                else:
                    valor_final_str = None
                    confirmado = True
                    es_defecto = False

            # Evaluar referencia y bandera
            ref_dict, bandera = evaluar_rango_y_bandera(p, v_num, paciente.sexo if paciente else None, edad_meses_total)

            # Evaluación de completitud para este parámetro
            if p.obligatorio:
                if es_calculado:
                    r_c = resultados_calc.get(p.codigo)
                    if r_c and not r_c.calculable:
                        if r_c.codigo_motivo == "FALTA_ENTRADA":
                            pendientes_totales.append(p.codigo)
                        # Si es REGLA_INVALIDA o DIVISION_POR_CERO, NO bloquea COMPLETO (D3-06)
                else:
                    if valor_final_str is None or valor_final_str == "":
                        pendientes_totales.append(p.codigo)
                    elif not confirmado and es_defecto:
                        sin_confirmar_totales.append(p.codigo)
            else:
                if not confirmado and es_defecto:
                    sin_confirmar_totales.append(p.codigo)

            param_dict = {
                "codigo": p.codigo,
                "nombre": p.nombre,
                "tipo_campo": p.tipo_campo,
                "unidad": p.unidad_medida,
                "decimales": p.decimales,
                "opciones": p.opciones,
                "obligatorio": p.obligatorio,
                "requiere_confirmacion": p.requiere_confirmacion,
                "metodo": p.metodo,
                "muestra": p.muestra,
                "valor": valor_final_str,
                "es_calculado": es_calculado,
                "calculable": calculable,
                "motivo_no_calculable": motivo_no_calc,
                "confirmado": confirmado,
                "es_defecto": es_defecto,
                "valor_defecto": p.valor_defecto,
                "referencia": ref_dict,
                "bandera": bandera,
            }
            secciones_map[grp].append(param_dict)

        secciones = [{"grupo": grp, "parametros": secciones_map[grp]} for grp in grupos_orden]

        grupos_sel = [g.grupo for g in oe.grupos] if est.seleccion_parcial else None
        estudios_resp.append({
            "codigo": est.codigo,
            "nombre": est.nombre,
            "grupos_seleccionados": grupos_sel,
            "secciones": secciones,
            "validaciones": validaciones_estudio,
        })

    es_completo = (len(pendientes_totales) == 0 and len(sin_confirmar_totales) == 0 and len(errores_totales) == 0)

    return {
        "orden": {
            "id": orden.id_orden,
            "estado_trabajo": "COMPLETO" if es_completo else "INCOMPLETO",
            "bloqueada": orden.bloqueada,
            "paciente": {"id": paciente.id_paciente, "sexo": paciente.sexo} if paciente else None,
            "edad_anios": orden.edad_anios,
            "edad_meses": orden.edad_meses,
        },
        "estudios": estudios_resp,
        "completitud": {
            "completo": es_completo,
            "pendientes": pendientes_totales,
            "sin_confirmar": sin_confirmar_totales,
            "errores": errores_totales,
        },
    }


def guardar_resultados_orden(
    db: Session,
    orden: Orden,
    valores_cambios: dict[str, Any],
    usuario: Usuario,
) -> dict[str, Any]:
    """
    Persiste los cambios parciales en `resultados_borrador`, recalcula todos los CALCULADO
    en el alcance, actualiza el estado de la orden y retorna la forma común (§8.2 / D3-08).
    """
    # 1. Precondiciones de escritura
    if orden.bloqueada or orden.estado_trabajo == "PUBLICADA":
        raise ConflictoError("La orden se encuentra bloqueada o publicada y no permite modificaciones.")

    if len(valores_cambios) > 200:
        raise ValidacionError("Máximo 200 claves por petición.")

    alcance_por_oe = obtener_parametros_alcance_orden(orden)
    # Mapear códigos a (OrdenEstudio, Parametro)
    mapa_codigo_alcance: dict[str, tuple[OrdenEstudio, Parametro]] = {}
    for oe in orden.estudios:
        for p in alcance_por_oe[oe.id_orden_estudio]:
            mapa_codigo_alcance[p.codigo] = (oe, p)

    # Validar claves y valores antes de persistir
    cambios_validados: dict[str, tuple[OrdenEstudio, Parametro, Decimal | None, str | None]] = {}
    for cod, val in valores_cambios.items():
        if cod not in mapa_codigo_alcance:
            raise ValidacionError(f"El parámetro '{cod}' no pertenece al alcance de la orden.")
        oe, param = mapa_codigo_alcance[cod]
        if param.tipo_campo == "CALCULADO":
            raise ValidacionError(f"No se permite modificar el parámetro calculado '{cod}'.")
        v_num, v_txt = normalizar_y_validar_valor_entrada(param, val)
        cambios_validados[cod] = (oe, param, v_num, v_txt)

    now = ahora()

    # 2. Aplicar cambios a resultados_borrador (upsert o delete)
    for cod, (oe, param, v_num, v_txt) in cambios_validados.items():
        rb = (
            db.query(ResultadoBorrador)
            .filter(
                ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio,
                ResultadoBorrador.id_parametro == param.id_parametro,
                ResultadoBorrador.id_edicion.is_(None),
            )
            .first()
        )

        if v_num is None and v_txt is None:
            # null borra la fila (test 8)
            if rb:
                db.delete(rb)
        else:
            if rb:
                rb.valor_numerico = v_num
                rb.valor_texto = v_txt
                rb.confirmado = True
                rb.es_calculado = False
                rb.calculable = True
                rb.actualizado_por = usuario.id_usuario
                rb.actualizado_en = now
            else:
                rb = ResultadoBorrador(
                    id_orden_estudio=oe.id_orden_estudio,
                    id_parametro=param.id_parametro,
                    id_edicion=None,
                    valor_numerico=v_num,
                    valor_texto=v_txt,
                    es_calculado=False,
                    calculable=True,
                    confirmado=True,
                    actualizado_por=usuario.id_usuario,
                    actualizado_en=now,
                )
                db.add(rb)

    db.flush()

    # 3. Recalcular todos los CALCULADO del alcance de cada estudio (D3-08)
    for oe in orden.estudios:
        params_alcance = alcance_por_oe[oe.id_orden_estudio]
        no_calc_params, calc_params = orden_topologico_parametros(params_alcance)

        # Cargar valores actuales de este estudio
        filas_actuales = (
            db.query(ResultadoBorrador)
            .filter(
                ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio,
                ResultadoBorrador.id_edicion.is_(None),
            )
            .all()
        )
        mapa_filas = {f.id_parametro: f for f in filas_actuales}

        ctx_calc: dict[str, Decimal | None] = {}
        for p in no_calc_params:
            fila = mapa_filas.get(p.id_parametro)
            if fila and fila.valor_numerico is not None:
                ctx_calc[p.codigo.lower()] = fila.valor_numerico
            else:
                ctx_calc[p.codigo.lower()] = None

        for p in calc_params:
            vars_req = variables_de(p.formula_expresion)
            faltan_entradas = any(ctx_calc.get(v) is None for v in vars_req)

            r_c = calcular(p.formula_expresion, ctx_calc, p.decimales)
            if faltan_entradas:
                r_c = ResultadoCalculo(None, False, "faltan datos de entrada", "FALTA_ENTRADA")

            fila_calc = mapa_filas.get(p.id_parametro)

            if r_c.calculable and r_c.valor is not None:
                ctx_calc[p.codigo.lower()] = r_c.valor
                if fila_calc:
                    fila_calc.valor_numerico = r_c.valor
                    fila_calc.valor_texto = None
                    fila_calc.es_calculado = True
                    fila_calc.calculable = True
                    fila_calc.confirmado = True
                    fila_calc.actualizado_por = usuario.id_usuario
                    fila_calc.actualizado_en = now
                else:
                    fila_calc = ResultadoBorrador(
                        id_orden_estudio=oe.id_orden_estudio,
                        id_parametro=p.id_parametro,
                        id_edicion=None,
                        valor_numerico=r_c.valor,
                        valor_texto=None,
                        es_calculado=True,
                        calculable=True,
                        confirmado=True,
                        actualizado_por=usuario.id_usuario,
                        actualizado_en=now,
                    )
                    db.add(fila_calc)

            elif not r_c.calculable and r_c.codigo_motivo in ("REGLA_INVALIDA", "DIVISION_POR_CERO"):
                ctx_calc[p.codigo.lower()] = None
                if fila_calc:
                    fila_calc.valor_numerico = None
                    fila_calc.valor_texto = None
                    fila_calc.es_calculado = True
                    fila_calc.calculable = False
                    fila_calc.confirmado = True
                    fila_calc.actualizado_por = usuario.id_usuario
                    fila_calc.actualizado_en = now
                else:
                    fila_calc = ResultadoBorrador(
                        id_orden_estudio=oe.id_orden_estudio,
                        id_parametro=p.id_parametro,
                        id_edicion=None,
                        valor_numerico=None,
                        valor_texto=None,
                        es_calculado=True,
                        calculable=False,
                        confirmado=True,
                        actualizado_por=usuario.id_usuario,
                        actualizado_en=now,
                    )
                    db.add(fila_calc)

            else:
                # FALTA_ENTRADA -> sin fila (D3-08, test 12)
                ctx_calc[p.codigo.lower()] = None
                if fila_calc:
                    db.delete(fila_calc)

    db.flush()

    # 4. Evaluar completitud y actualizar estado_trabajo de la orden
    captura = evaluar_captura_orden(orden)
    nuevo_estado = "COMPLETO" if captura["completitud"]["completo"] else "INCOMPLETO"

    if orden.estado_trabajo != nuevo_estado:
        orden.estado_trabajo = nuevo_estado
        # D3-09: No modificar fila_version

    db.commit()
    db.refresh(orden)

    return evaluar_captura_orden(orden)


def confirmar_defectos_orden(
    db: Session,
    orden: Orden,
    parametros_a_confirmar: list[str] | None,
    usuario: Usuario,
) -> dict[str, Any]:
    """
    Persiste valores por defecto virtuales con confirmado = TRUE (D3-05, test 20).
    """
    if orden.bloqueada or orden.estado_trabajo == "PUBLICADA":
        raise ConflictoError("La orden se encuentra bloqueada o publicada y no permite modificaciones.")

    alcance_por_oe = obtener_parametros_alcance_orden(orden)
    filtro_codigos = set(parametros_a_confirmar) if parametros_a_confirmar is not None else None
    now = ahora()

    for oe in orden.estudios:
        params_alcance = alcance_por_oe[oe.id_orden_estudio]
        for p in params_alcance:
            if p.tipo_campo != "CALCULADO" and p.valor_defecto is not None:
                if filtro_codigos is not None and p.codigo not in filtro_codigos:
                    continue

                rb = (
                    db.query(ResultadoBorrador)
                    .filter(
                        ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio,
                        ResultadoBorrador.id_parametro == p.id_parametro,
                        ResultadoBorrador.id_edicion.is_(None),
                    )
                    .first()
                )

                if not rb:
                    v_num, v_txt = normalizar_y_validar_valor_entrada(p, p.valor_defecto)
                    rb = ResultadoBorrador(
                        id_orden_estudio=oe.id_orden_estudio,
                        id_parametro=p.id_parametro,
                        id_edicion=None,
                        valor_numerico=v_num,
                        valor_texto=v_txt,
                        es_calculado=False,
                        calculable=True,
                        confirmado=True,
                        actualizado_por=usuario.id_usuario,
                        actualizado_en=now,
                    )
                    db.add(rb)
                elif not rb.confirmado:
                    rb.confirmado = True
                    rb.actualizado_por = usuario.id_usuario
                    rb.actualizado_en = now

    db.flush()

    # Recalcular tras confirmar
    return guardar_resultados_orden(db, orden, {}, usuario)
