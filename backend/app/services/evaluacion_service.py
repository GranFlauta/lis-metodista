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
from app.services.serologia_service import (
    OPCIONES_CUALITATIVAS, columnas_serologia, configuracion_serologia, normalizar_entrada, presentar_serologia,
)
from app.reports.presentation import es_vacio
from app.services.coproparasitologia_service import configuracion_muestras, normalizar_muestras, presentar_muestras
from app.services.curva_service import ZONA, construir_curva, rol_parametro_curva, validar_hora
from app.services.grupo_sanguineo_service import (
    es_parametro_grupo_sanguineo, leer_entrada_grupo_sanguineo, normalizar_entrada_grupo_sanguineo,
)
from app.services.coagulacion_service import normalizar_unidad_coagulacion, unidad_coagulacion_editable


def formatear_decimal(val: Decimal | float | int | None) -> str | None:
    """Convierte un Decimal a string con punto sin ceros finales superfluos."""
    if val is None:
        return None
    d = Decimal(str(val))
    texto = f"{d:f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto if texto else "0"


CODIGOS_EGO_QUIMICO = {
    "PROTEINAS", "GLUCOSA", "CETONAS", "ESTERASA_LEUCOCITARIA",
    "NITRITOS", "PIGMENTOS_BILIARES", "UROBILINOGENO", "SANGRE",
}


def _es_seleccion_simple(estudio_codigo: str, parametros: list[dict[str, Any]]) -> bool:
    return estudio_codigo in {"PARASITOLOGIA", "PERFIL_CARDIACO", "EGO"} and bool(parametros) and all(
        parametro["tipo_campo"] == "SELECCION"
        and not parametro.get("unidad")
        and not (parametro.get("referencia") or {}).get("texto")
        for parametro in parametros
    )


def _columnas_inmunoserologia(grupo: str, parametros: list[dict[str, Any]]) -> dict[str, bool]:
    columnas = columnas_serologia(parametros)
    if grupo == "PARASITOLOGIA":
        columnas["muestra"] = any(parametro.get("muestra") for parametro in parametros)
        columnas["metodo"] = any(parametro.get("metodo") for parametro in parametros)
    return columnas


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
    override: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Selecciona el rango de referencia aplicable por sexo y edad en meses (D3-07),
    o aplica el rango override personalizado para esta orden si existe.
    Evalúa si el valor es BAJO, NORMAL o ALTO respetando límites.
    """
    if override and override.get("modificada") and not override.get("reestablecer"):
        inf_val = override.get("limite_inferior")
        sup_val = override.get("limite_superior")
        txt_val = override.get("texto")

        inf_dec = a_decimal(inf_val) if (inf_val is not None and str(inf_val).strip() != "") else None
        sup_dec = a_decimal(sup_val) if (sup_val is not None and str(sup_val).strip() != "") else None

        inf_str = formatear_decimal(inf_dec) if inf_dec is not None else None
        sup_str = formatear_decimal(sup_dec) if sup_dec is not None else None

        ref_dict = {
            "texto": txt_val or (f"{inf_str} - {sup_str}" if inf_str and sup_str else None),
            "inferior": inf_str,
            "superior": sup_str,
            "modificada": True,
        }

        if valor_numerico is None:
            return ref_dict, None

        bandera = "NORMAL"
        if inf_dec is not None and valor_numerico < inf_dec:
            bandera = "BAJO"
        elif sup_dec is not None and valor_numerico > sup_dec:
            bandera = "ALTO"

        return ref_dict, bandera

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
        "modificada": False,
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


def normalizar_unidades_override(orden: Orden, unidades: dict[str, Any] | None) -> dict[str, str | None]:
    if not unidades:
        return {}
    alcance = obtener_parametros_alcance_orden(orden)
    permitidos = {
        p.codigo
        for oe in orden.estudios
        for p in alcance[oe.id_orden_estudio]
        if unidad_coagulacion_editable(oe.estudio.codigo, p)
    }
    salida = {}
    for codigo, unidad in (unidades or {}).items():
        if codigo not in permitidos:
            raise ValidacionError(f"No se permite editar la unidad de '{codigo}' en esta orden.")
        salida[codigo] = normalizar_unidad_coagulacion(unidad)
    return salida


def texto_sin_limite(parametro: Parametro) -> bool:
    version = parametro.estudio_version
    captura = (version.configuracion_json or {}).get("captura", {}) if version else {}
    return parametro.tipo_campo == "TEXTO_LIBRE" and parametro.codigo in captura.get("textos_sin_limite", [])


def normalizar_y_validar_valor_entrada(
    parametro: Parametro,
    valor_crudo: Any,
    valor_anterior: str | None = None,
) -> tuple[Decimal | None, str | None]:
    """
    Valida y normaliza el valor según el tipo de campo del parámetro (D3-04).
    Devuelve (valor_numerico, valor_texto).
    """
    if es_vacio(valor_crudo):
        return None, None

    if es_parametro_grupo_sanguineo(parametro):
        return None, normalizar_entrada_grupo_sanguineo(parametro, valor_crudo)

    config_muestras = configuracion_muestras(parametro)
    if config_muestras:
        return None, normalizar_muestras(valor_crudo, config_muestras, valor_anterior)

    tipo = "SELECCION" if parametro.codigo in OPCIONES_CUALITATIVAS else parametro.tipo_campo
    config_serologia = configuracion_serologia(parametro)
    if config_serologia:
        entrada_serologia = normalizar_entrada(valor_crudo, config_serologia)
        if entrada_serologia is not None:
            return None, entrada_serologia
    val_str = str(valor_crudo).strip()
    if rol_parametro_curva(parametro) == "hora":
        return None, validar_hora(val_str)

    if tipo == "NUMERICO":
        # La API recibe valores sin agrupación de miles. `decimales` define la
        # precisión de los calculados, no autoriza a borrar el decimal capturado.
        texto_punto = val_str.replace(",", ".")
        try:
            d = Decimal(texto_punto)
        except InvalidOperation:
            raise ValidacionError(f"Valor numérico inválido para {parametro.codigo}: {val_str}")
        if not d.is_finite():
            raise ValidacionError(f"Valor numérico inválido para {parametro.codigo}.")
        if d < 0:
            raise ValidacionError(f"El valor de {parametro.codigo} no puede ser negativo.")
        if d.as_tuple().exponent < -6:
            raise ValidacionError(f"El valor de {parametro.codigo} no puede tener más de 6 decimales.")
        return d, None

    elif tipo == "SELECCION":
        if parametro.codigo in CODIGOS_EGO_QUIMICO:
            if len(val_str) > 500:
                raise ValidacionError(f"El texto para {parametro.codigo} no puede exceder 500 caracteres.")
            return None, val_str
        opciones = OPCIONES_CUALITATIVAS.get(parametro.codigo, parametro.opciones) or []
        if "Negativo" in opciones and "Positivo" in opciones:
            val_str = {"No reactivo": "Negativo", "Reactivo": "Positivo"}.get(val_str, val_str)
        if val_str not in opciones:
            raise ValidacionError(f"El valor '{val_str}' no es una opción permitida para {parametro.codigo}.")
        return None, val_str

    elif tipo == "TEXTO_LIBRE":
        if not texto_sin_limite(parametro) and len(val_str) > 500:
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
    overrides_simulados: dict[str, Any] | None = None,
    unidades_simuladas: dict[str, str | None] | None = None,
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
    unidades = normalizar_unidades_override(orden, unidades_simuladas)

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

    unidades_por_param_id = {rb.id_parametro: rb.unidad_override for rb in filas_db if rb.unidad_override is not None}
    overrides_por_param_id: dict[int, dict[str, Any]] = {}
    for rb in filas_db:
        if getattr(rb, "ref_modificada", False):
            overrides_por_param_id[rb.id_parametro] = {
                "limite_inferior": getattr(rb, "ref_inferior_override", None),
                "limite_superior": getattr(rb, "ref_superior_override", None),
                "texto": getattr(rb, "ref_texto_override", None),
                "modificada": True,
            }

    # Cargar valores existentes o mapear simulados
    # mapa_por_oe_param: id_orden_estudio -> codigo -> (valor_numerico, valor_texto, confirmado, es_defecto)
    mapa_valores: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)

    # 1. Cargar filas persistidas de base de datos
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

    # 2. Si hay valores_simulados (POST /calcular), fusionar y actualizar sobre los existentes
    if valores_simulados is not None:
        for oe in orden.estudios:
            params_alcance = alcance_por_oe[oe.id_orden_estudio]
            params_map = {p.codigo: p for p in params_alcance}
            for cod, val in valores_simulados.items():
                if cod in params_map and params_map[cod].tipo_campo != "CALCULADO":
                    p = params_map[cod]
                    if val is not None and str(val).strip() != "":
                        previo = mapa_valores[oe.id_orden_estudio].get(cod, {}).get("valor_texto")
                        v_num, v_txt = normalizar_y_validar_valor_entrada(p, val, valor_anterior=previo)
                        mapa_valores[oe.id_orden_estudio][cod] = {
                            "valor_numerico": v_num,
                            "valor_texto": v_txt,
                            "confirmado": True,
                            "es_defecto": False,
                            "es_calculado": False,
                            "calculable": True,
                        }
                    else:
                        if cod in mapa_valores[oe.id_orden_estudio]:
                            del mapa_valores[oe.id_orden_estudio][cod]

    # Procesar estudios, cálculos, banderas y validaciones
    estudios_resp = []
    pendientes_totales: list[str] = []
    sin_confirmar_totales: list[str] = []
    errores_totales: list[str] = []
    hay_resultados_utilizados = False

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
        sumas = []
        for regla in reglas:
            if regla.get("tipo") != "SUMA_IGUAL":
                continue
            codigos_suma = regla.get("parametros", [])
            valores_suma = [valores_numericos_estudio[c] for c in codigos_suma if valores_numericos_estudio.get(c) is not None]
            total = sum(valores_suma, Decimal("0")) if valores_suma else None
            esperado = Decimal(str(regla.get("valor", 100)))
            tolerancia = Decimal(str(regla.get("tolerancia", 0)))
            entradas_completas = all(
                valores_numericos_estudio.get(c) is not None
                for c in codigos_suma if params_por_cod.get(c) and params_por_cod[c].obligatorio
            )
            sumas.append({
                "parametros": codigos_suma,
                "valor": formatear_decimal(total),
                "esperado": formatear_decimal(esperado),
                "tolerancia": formatear_decimal(tolerancia),
                "valida": total is not None and entradas_completas and abs(total - esperado) <= tolerancia,
            })
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
            codigo_motivo_no_calc: str | None = None
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
                    codigo_motivo_no_calc = codigo_mot
                    mot_raw = r_c.motivo if r_c else None
                    motivo_no_calc = motivo_no_calculable_en_espanol(p.codigo, codigo_mot, mot_raw)
            else:
                st = mapa_valores[oe.id_orden_estudio].get(p.codigo)
                if st is not None:
                    v_num = st.get("valor_numerico")
                    valor_final_str = formatear_valor_parametro(p.tipo_campo, v_num, st.get("valor_texto"), p.decimales)
                    confirmado = st.get("confirmado", True)
                    es_defecto = st.get("es_defecto", False)
                else:
                    valor_final_str = None
                    confirmado = True
                    es_defecto = False

            # Evaluar referencia y bandera (considerando overrides persistidos o simulados)
            override_param: dict[str, Any] | None = None
            if overrides_simulados and p.codigo in overrides_simulados:
                ov = overrides_simulados[p.codigo]
                if hasattr(ov, "dict"):
                    ov = ov.dict()
                elif hasattr(ov, "model_dump"):
                    ov = ov.model_dump()
                if ov.get("reestablecer"):
                    override_param = {"reestablecer": True, "modificada": False}
                else:
                    override_param = {
                        "limite_inferior": ov.get("limite_inferior"),
                        "limite_superior": ov.get("limite_superior"),
                        "texto": ov.get("texto"),
                        "modificada": True,
                    }
            elif p.id_parametro in overrides_por_param_id:
                override_param = overrides_por_param_id[p.id_parametro]

            unidad_final = p.unidad_medida
            unidad_editable = unidad_coagulacion_editable(est.codigo, p)
            unidad_modificada = False
            if unidad_editable:
                unidad_override = unidades[p.codigo] if p.codigo in unidades else unidades_por_param_id.get(p.id_parametro)
                unidad_modificada = unidad_override is not None
                if unidad_modificada:
                    unidad_final = unidad_override or None
            es_grupo_sanguineo = est.codigo == "COAGULOGRAMA" and es_parametro_grupo_sanguineo(p)
            if es_grupo_sanguineo:
                entrada_grupo = leer_entrada_grupo_sanguineo(valor_final_str)
                valor_final_str = entrada_grupo.valor or None
                unidad_final = None

            ref_dict, bandera = evaluar_rango_y_bandera(
                p, v_num, paciente.sexo if paciente else None, edad_meses_total, override=override_param
            )
            config_serologia = configuracion_serologia(p) if est.codigo == "INMUNOSEROLOGIA" else None
            serologia = presentar_serologia(valor_final_str, config_serologia, (ref_dict or {}).get("texto")) if config_serologia else None
            config_muestras = configuracion_muestras(p)
            muestras_seriadas = presentar_muestras(valor_final_str, config_muestras) if config_muestras else None
            if est.codigo == "INMUNOSEROLOGIA":
                bandera = None
            utilizado = bool(serologia["entrada"]["reactividad"]) if serologia else not es_vacio(valor_final_str)
            if muestras_seriadas:
                utilizado = muestras_seriadas["utilizado"]
                if muestras_seriadas["pendientes"]:
                    pendientes_totales.append(p.codigo)
                    for numero in muestras_seriadas["pendientes"]:
                        mensaje = f"Muestra {numero}: completa la fecha y confirma o escribe el resultado."
                        validaciones_estudio.append({"severidad": "ERROR", "mensaje": mensaje, "parametros": [p.codigo]})
                        errores_totales.append(mensaje)
            if not es_calculado and utilizado and confirmado:
                hay_resultados_utilizados = True
            if serologia and utilizado and not serologia["completo"]:
                pendientes_totales.append(p.codigo)

            # La selección por campos utilizados también aplica a borradores de catálogo anterior.
            # Un campo vacío no se vuelve obligatorio ni se convierte en un defecto virtual.
            if utilizado and not confirmado and (es_defecto or p.requiere_confirmacion):
                sin_confirmar_totales.append(p.codigo)

            param_dict = {
                "codigo": p.codigo,
                "nombre": (
                    oe.etiqueta_cayados if p.codigo == "CAYADOS_PCT" and oe.etiqueta_cayados
                    else f"{oe.etiqueta_cayados} (abs.)" if p.codigo == "CAYADOS_ABS" and oe.etiqueta_cayados
                    else p.nombre
                ),
                "tipo_campo": "SELECCION" if p.codigo in OPCIONES_CUALITATIVAS else p.tipo_campo,
                "texto_sin_limite": texto_sin_limite(p),
                "unidad": unidad_final,
                "decimales": p.decimales,
                "opciones": OPCIONES_CUALITATIVAS.get(p.codigo, p.opciones),
                "obligatorio": False,
                "requiere_confirmacion": p.requiere_confirmacion,
                "metodo": p.metodo,
                "muestra": p.muestra,
                "valor": {"No reactivo": "Negativo", "Reactivo": "Positivo"}.get(valor_final_str, valor_final_str)
                         if p.codigo in OPCIONES_CUALITATIVAS and "Negativo" in OPCIONES_CUALITATIVAS[p.codigo] else valor_final_str,
                "es_calculado": es_calculado,
                "calculable": calculable,
                "motivo_no_calculable": motivo_no_calc,
                "codigo_motivo_no_calculable": codigo_motivo_no_calc,
                "confirmado": confirmado,
                "es_defecto": es_defecto,
                "valor_defecto": p.valor_defecto,
                "referencia": ref_dict,
                "bandera": bandera,
                "captura_serologia": config_serologia,
                "serologia": serologia,
                "captura_muestras": config_muestras,
                "muestras_seriadas": muestras_seriadas,
            }
            if unidad_editable:
                param_dict.update(unidad_editable=True, unidad_modificada=unidad_modificada)
            secciones_map[grp].append(param_dict)

        listas_texto = (ev.configuracion_json or {}).get("captura", {}).get("listas_texto", [])
        secciones = [{"grupo": grp, "parametros": secciones_map[grp],
                      "formato": ("MUESTRAS_SERIADAS" if any(p["captura_muestras"] for p in secciones_map[grp])
                                  else "LISTA_TEXTO" if grp in listas_texto
                                  else "SELECCION_SIMPLE" if _es_seleccion_simple(est.codigo, secciones_map[grp])
                                  else None),
                      "columnas": _columnas_inmunoserologia(grp, secciones_map[grp]) if est.codigo == "INMUNOSEROLOGIA" else None}
                     for grp in grupos_orden]
        if est.codigo == "COAGULOGRAMA":
            for seccion in secciones:
                if seccion["grupo"] == "GRUPO_SANGUINEO":
                    seccion["columnas"] = {
                        "unidad": False,
                        "referencia": False,
                        "bandera": False,
                    }

        curva = None
        config_curva = (ev.configuracion_json or {}).get("captura", {}).get("curva_tolerancia")
        if config_curva:
            inicio = orden.fecha_hora_toma_muestra or orden.creado_en
            fecha_estudio = inicio.astimezone(ZONA).date() if inicio else None
            valores_curva = {p["codigo"]: p["valor"] for seccion in secciones for p in seccion["parametros"]}
            curva = construir_curva(config_curva, valores_curva, fecha_estudio)
            for fila in curva["filas"]:
                if fila["error"]:
                    mensaje = f"{fila['etiqueta']}: {fila['error']}"
                    pendientes_totales.append(fila["hora"] if not fila["hora_valor"] else fila["glucosa"])
                    validaciones_estudio.append({"severidad": "ERROR", "mensaje": mensaje,
                                                "parametros": [fila["hora"], fila["glucosa"], fila["fecha"]]})
                    errores_totales.append(mensaje)

        grupos_sel = [g.grupo for g in oe.grupos] if est.seleccion_parcial else None
        estudios_resp.append({
            "id_orden_estudio": oe.id_orden_estudio,
            "id_estudio": est.id_estudio,
            "codigo": est.codigo,
            "nombre": est.nombre,
            "observaciones": oe.observaciones,
            "etiqueta_cayados": oe.etiqueta_cayados,
            "grupos_seleccionados": grupos_sel,
            "secciones": secciones,
            "validaciones": validaciones_estudio,
            "sumas": sumas,
            "curva_tolerancia": curva,
        })

    es_completo = (len(pendientes_totales) == 0 and len(sin_confirmar_totales) == 0 and len(errores_totales) == 0
                   and hay_resultados_utilizados)

    return {
        "orden": {
            "id": orden.id_orden,
            "estado_trabajo": "COMPLETO" if es_completo else "INCOMPLETO",
            "bloqueada": orden.bloqueada,
            "paciente": {"id": paciente.id_paciente, "sexo": paciente.sexo} if paciente else None,
            "edad_anios": orden.edad_anios,
            "edad_meses": orden.edad_meses,
            "observaciones": orden.observaciones,
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
    rangos_override: dict[str, Any] | None = None,
    observaciones_estudios: dict[str, str | None] | None = None,
    observaciones_orden: str | None = None,
    etiquetas_estudios: dict[str, str | None] | None = None,
    unidades_override: dict[str, str | None] | None = None,
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
    unidades = normalizar_unidades_override(orden, unidades_override)

    # Guardar observaciones de la orden si se enviaron
    if observaciones_orden is not None:
        orden.observaciones = observaciones_orden.strip() if observaciones_orden.strip() else None

    # Guardar observaciones por estudio si se enviaron
    if observaciones_estudios is not None:
        for oe in orden.estudios:
            if oe.estudio.codigo in observaciones_estudios:
                obs_val = observaciones_estudios[oe.estudio.codigo]
                oe.observaciones = obs_val.strip() if obs_val and obs_val.strip() else None

    if etiquetas_estudios is not None:
        estudios_por_codigo = {oe.estudio.codigo: oe for oe in orden.estudios}
        for codigo, valor in etiquetas_estudios.items():
            oe = estudios_por_codigo.get(codigo)
            if not oe or oe.estudio.codigo != "HEMOGRAMA":
                raise ValidacionError(f"No se puede editar la etiqueta diferencial del estudio '{codigo}'.")
            etiqueta = valor.strip() if valor else ""
            if len(etiqueta) > 80:
                raise ValidacionError("La etiqueta de cayados debe tener como máximo 80 caracteres.")
            oe.etiqueta_cayados = etiqueta or None

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
        previo = None
        if configuracion_muestras(param):
            existente = db.query(ResultadoBorrador).filter(
                ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio,
                ResultadoBorrador.id_parametro == param.id_parametro,
                ResultadoBorrador.id_edicion.is_(None),
            ).first()
            previo = existente.valor_texto if existente else None
        v_num, v_txt = normalizar_y_validar_valor_entrada(param, val, valor_anterior=previo)
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
            # Una unidad o referencia personalizada puede existir sin resultado.
            if rb:
                if getattr(rb, "ref_modificada", False) or rb.unidad_override is not None:
                    rb.valor_numerico = None
                    rb.valor_texto = None
                    rb.confirmado = False
                    rb.actualizado_por = usuario.id_usuario
                    rb.actualizado_en = now
                else:
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

    # 2.1 Aplicar rangos_override si fueron suministrados
    if rangos_override:
        for cod, ro_item in rangos_override.items():
            if cod not in mapa_codigo_alcance:
                raise ValidacionError(f"El parámetro '{cod}' no pertenece al alcance de la orden.")
            oe, param = mapa_codigo_alcance[cod]
            ro_dict = ro_item.model_dump() if hasattr(ro_item, "model_dump") else (ro_item.dict() if hasattr(ro_item, "dict") else ro_item)
            es_reestablecer = ro_dict.get("reestablecer", False)

            rb = (
                db.query(ResultadoBorrador)
                .filter(
                    ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio,
                    ResultadoBorrador.id_parametro == param.id_parametro,
                    ResultadoBorrador.id_edicion.is_(None),
                )
                .first()
            )

            if es_reestablecer:
                if rb:
                    rb.ref_modificada = False
                    rb.ref_inferior_override = None
                    rb.ref_superior_override = None
                    rb.ref_texto_override = None
                    rb.actualizado_por = usuario.id_usuario
                    rb.actualizado_en = now
                    # Si no tiene valor y tampoco es calculado, se limpia la fila vacía
                    if rb.valor_numerico is None and rb.valor_texto is None and not rb.es_calculado and rb.unidad_override is None:
                        db.delete(rb)
            else:
                inf_val = ro_dict.get("limite_inferior")
                sup_val = ro_dict.get("limite_superior")
                txt_val = ro_dict.get("texto")

                inf_ov = a_decimal(inf_val) if (inf_val is not None and str(inf_val).strip() != "") else None
                sup_ov = a_decimal(sup_val) if (sup_val is not None and str(sup_val).strip() != "") else None
                txt_ov = str(txt_val).strip() if (txt_val is not None and str(txt_val).strip() != "") else None

                if not rb:
                    rb = ResultadoBorrador(
                        id_orden_estudio=oe.id_orden_estudio,
                        id_parametro=param.id_parametro,
                        id_edicion=None,
                        valor_numerico=None,
                        valor_texto=None,
                        es_calculado=(param.tipo_campo == "CALCULADO"),
                        calculable=False,
                        confirmado=False,
                        ref_modificada=True,
                        ref_inferior_override=inf_ov,
                        ref_superior_override=sup_ov,
                        ref_texto_override=txt_ov,
                        actualizado_por=usuario.id_usuario,
                        actualizado_en=now,
                    )
                    db.add(rb)
                else:
                    rb.ref_modificada = True
                    rb.ref_inferior_override = inf_ov
                    rb.ref_superior_override = sup_ov
                    rb.ref_texto_override = txt_ov
                    rb.actualizado_por = usuario.id_usuario
                    rb.actualizado_en = now

    db.flush()

    for codigo, unidad in unidades.items():
        oe, parametro = mapa_codigo_alcance[codigo]
        rb = db.query(ResultadoBorrador).filter(
            ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio,
            ResultadoBorrador.id_parametro == parametro.id_parametro,
            ResultadoBorrador.id_edicion.is_(None),
        ).first()
        if rb is None:
            if unidad is None:
                continue
            rb = ResultadoBorrador(
                id_orden_estudio=oe.id_orden_estudio, id_parametro=parametro.id_parametro,
                es_calculado=False, calculable=True, confirmado=False,
                actualizado_por=usuario.id_usuario, actualizado_en=now,
            )
            db.add(rb)
        rb.unidad_override = unidad
        rb.actualizado_por = usuario.id_usuario
        rb.actualizado_en = now
        if unidad is None and rb.valor_numerico is None and rb.valor_texto is None and not rb.ref_modificada:
            db.delete(rb)
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
