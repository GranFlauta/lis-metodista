"""Proyección de informe: sólo resultados usados, sin modificar el snapshot."""
from copy import deepcopy
import re


VACIOS = {"", "-", "--", "—", "–"}
SEMICUANTITATIVOS = {"PCR_DILUCION", "FR_DILUCION", "ASTO_DILUCION"}


def es_vacio(valor) -> bool:
    return valor is None or isinstance(valor, str) and valor.strip() in VACIOS


def es_negativo(parametro: dict) -> bool:
    if parametro.get("codigo") not in SEMICUANTITATIVOS:
        return False
    serologia = parametro.get("serologia") or {}
    return (serologia.get("entrada") or {}).get("reactividad") == "Negativo" or bool(
        re.match(r"^(negativo|no reactivo)(?:\b|:)", str(parametro.get("valor") or "").strip(), re.IGNORECASE)
    )


def resultado_para_informe(parametro: dict) -> str | None:
    if parametro.get("es_defecto") and not parametro.get("confirmado"):
        return None
    if es_negativo(parametro):
        return "Negativo"
    if parametro.get("muestras_seriadas") is not None:
        return parametro["muestras_seriadas"].get("resultado")
    if parametro.get("serologia") is not None:
        resultado = parametro["serologia"].get("resultado")
        return None if es_vacio(resultado) else str(resultado)
    if parametro.get("es_calculado") and parametro.get("calculable") is False:
        codigo = parametro.get("codigo_motivo_no_calculable")
        motivo = str(parametro.get("motivo_no_calculable") or "").casefold()
        if codigo == "FALTA_ENTRADA" or codigo is None and motivo.startswith(("falta", "requiere")):
            return None
        return "No calculable"
    raw = parametro.get("valor")
    if es_vacio(raw):
        return None
    valor = str(raw).strip()
    if parametro.get("codigo") in {"FR_DILUCION", "ASTO_DILUCION"}:
        primero = valor.split(";", 1)[0].strip()
        sin_dilucion = re.match(r"^Reactivo sin dilución:\s*(.+)$", primero, re.IGNORECASE)
        if sin_dilucion:
            return f"Reactivo · {sin_dilucion[1]}"
        dilucion = re.match(r"^Reactivo\s+(\S+):\s*(.+)$", primero, re.IGNORECASE)
        return f"Reactivo · {dilucion[1]} · {dilucion[2]}" if dilucion else primero
    return valor


def formatear_numero_informe(valor: str, separador_decimal: str) -> str:
    """Agrupa dígitos sin redondear ni convertir el resultado clínico a float."""
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", valor):
        return valor
    entero, punto, fraccion = valor.partition(".")
    miles = "." if separador_decimal == "," else ","
    entero = re.sub(r"\B(?=(\d{3})+(?!\d))", miles, entero)
    return entero + (separador_decimal + fraccion if punto else "")


def estudios_para_informe(estudios: list[dict]) -> list[dict]:
    salida = []
    for original in estudios:
        estudio = deepcopy(original)
        secciones = []
        for seccion in estudio.get("secciones") or []:
            parametros = []
            for parametro in seccion.get("parametros") or []:
                valor = resultado_para_informe(parametro)
                if valor is None:
                    continue
                columnas_originales = seccion.get("columnas") or {}
                if (
                    estudio.get("codigo") == "INMUNOSEROLOGIA"
                    and seccion.get("grupo") == "PARASITOLOGIA"
                    and columnas_originales.get("muestra")
                    and parametro.get("codigo") == "SANGRE_OCULTA_HECES_INMUNO"
                ):
                    parametro["nombre"] = "SANGRE OCULTA EN HECES"
                parametro["valor_informe"] = valor
                if es_negativo(parametro):
                    parametro.update(unidad=None, referencia=None, bandera=None)
                    if parametro.get("serologia"):
                        parametro["serologia"].update(resultado="Negativo", unidad="", referencia="")
                parametros.append(parametro)
            if parametros:
                seccion["parametros"] = parametros
                if estudio.get("codigo") == "INMUNOSEROLOGIA":
                    serologia_con_muestra = seccion.get("grupo") == "PARASITOLOGIA"
                    seccion["columnas"] = {
                        "unidad": any((p.get("serologia") or {}).get("unidad") or p.get("unidad") not in (None, "", "dilución") for p in parametros),
                        "referencia": any((p.get("serologia") or {}).get("referencia") for p in parametros),
                        "bandera": False,
                        "muestra": serologia_con_muestra and columnas_originales.get("muestra", False) and any(p.get("muestra") for p in parametros),
                        "metodo": serologia_con_muestra and columnas_originales.get("metodo", False) and any(p.get("metodo") for p in parametros),
                    }
                elif estudio.get("codigo") == "COAGULOGRAMA" and seccion.get("grupo") == "GRUPO_SANGUINEO" and columnas_originales:
                    seccion["columnas"] = {
                        "unidad": any(not es_vacio(p.get("unidad")) for p in parametros),
                        "referencia": False,
                        "bandera": False,
                    }
                secciones.append(seccion)
        if secciones:
            estudio["secciones"] = secciones
            salida.append(estudio)
    return salida
