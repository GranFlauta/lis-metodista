"""Captura semicuantitativa: entradas separadas del resultado clínico.

Se persiste la entrada como JSON en valor_texto; el backend deriva la presentación
y la congela en el snapshot. Las fórmulas y sensibilidades vienen del catálogo.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.calculation.engine import calcular
from app.catalog.definitions import INMUNOSEROLOGIA, SELECCION
from app.core.errors import ValidacionError

OPCIONES_CUALITATIVAS = {p.codigo: p.opciones for p in INMUNOSEROLOGIA.parametros if p.tipo == SELECCION}


class EntradaSerologia(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reactividad: Literal["", "Negativo", "Positivo"] = ""
    dilucion: str = Field(default="", max_length=40)
    reactivo: str = Field(default="", max_length=40)
    sensibilidad: str = Field(default="", max_length=30)
    unidad: str = Field(default="", max_length=12)


def configuracion_serologia(parametro) -> dict | None:
    version = parametro.estudio_version
    configuracion = (version.configuracion_json or {}).get("captura", {}) if version else {}
    return configuracion.get(parametro.codigo) or INMUNOSEROLOGIA.captura.get(parametro.codigo)


def leer_entrada(valor) -> EntradaSerologia | None:
    if isinstance(valor, str):
        if not valor.lstrip().startswith("{"):
            return None
        try:
            valor = json.loads(valor)
        except ValueError:
            raise ValidacionError("Captura de serología inválida.")
    if not isinstance(valor, dict):
        return None
    try:
        return EntradaSerologia.model_validate(valor)
    except ValidationError:
        raise ValidacionError("Campos de captura de serología inválidos.")


def normalizar_entrada(valor, config: dict) -> str | None:
    entrada = leer_entrada(valor)
    if entrada is None:
        return None  # Conserva la lectura de resultados anteriores.
    nombres = [r["nombre"] for r in config.get("reactivos", [])]
    if entrada.reactivo and entrada.reactivo not in nombres:
        if entrada.reactivo != "PERSONALIZADO" or not config.get("personalizable"):
            raise ValidacionError("Reactivo de serología no permitido.")
    if entrada.unidad and entrada.unidad not in config.get("unidades", []):
        raise ValidacionError("Unidad de serología no permitida.")
    if entrada.reactividad != "Positivo":
        entrada.dilucion = ""
    return entrada.model_dump_json()


def _numero(valor: str) -> Decimal | None:
    if not re.fullmatch(r"\d{1,12}(?:[.,]\d{1,6})?", valor):
        return None
    numero = Decimal(valor.replace(",", "."))
    return numero if numero > 0 else None


def _texto(numero: Decimal) -> str:
    texto = format(numero, "f")
    return texto.rstrip("0").rstrip(".") if "." in texto else texto


def presentar_serologia(valor, config: dict, referencia_anterior: str | None = None) -> dict | None:
    entrada = leer_entrada(valor)
    if entrada is None:
        if not valor:
            return None
        # Los borradores anteriores conservan su valor ya registrado. Solo se
        # recalculan cuando el usuario edita sus controles de captura.
        texto = str(valor).split(";", 1)[0].strip()
        negativo = texto.lower().startswith(("negativo", "no reactivo"))
        positivo = texto.lower().startswith(("positivo", "reactivo"))
        dilucion = re.search(r"1/\d+(?:[.,]\d+)?", texto)
        concentracion = re.search(r"([<>≥]?\s*\d+(?:[.,]\d+)?)\s*(UI/mL|mg/dL|mg/L)", texto)
        sensibilidad = re.search(r"(\d+(?:[.,]\d+)?)\s*(UI/mL|mg/dL|mg/L)", referencia_anterior or str(valor).partition("; sensibilidad ")[2])
        reactivo = next((r for r in config.get("reactivos", [])
                         if (sensibilidad and r["unidad"] == sensibilidad[2] and Decimal(r["sensibilidad"]) == Decimal(sensibilidad[1].replace(",", ".")))
                         or (not sensibilidad and concentracion and r["unidad"] == concentracion[2])), None)
        entrada = EntradaSerologia(reactividad="Negativo" if negativo else "Positivo" if positivo else "",
                                   dilucion=dilucion[0] if dilucion else "", reactivo=reactivo["nombre"] if reactivo else "")
        if sensibilidad and not reactivo and config.get("personalizable"):
            entrada.reactivo = "PERSONALIZADO"
            entrada.sensibilidad = sensibilidad[1].replace(",", ".")
            entrada.unidad = sensibilidad[2]
        resultado = "Negativo" if negativo else concentracion[1].replace(",", ".").replace(" ", "") if concentracion else texto
        return {"entrada": entrada.model_dump(), "resultado": resultado,
                "unidad": "" if negativo else concentracion[2] if concentracion else "", "referencia": "" if negativo else referencia_anterior or "", "completo": True, "motivo": None}
    salida = {"entrada": entrada.model_dump(), "resultado": None, "unidad": "", "referencia": "", "completo": False, "motivo": None}
    reactivos = config.get("reactivos", [])
    reactivo = next((r for r in reactivos if r["nombre"] == entrada.reactivo), None)
    if not entrada.reactivo and reactivos:
        reactivo = reactivos[0]
    sensibilidad = _numero(reactivo["sensibilidad"]) if reactivo else _numero(entrada.sensibilidad)
    unidad = reactivo["unidad"] if reactivo else entrada.unidad
    if config["modo"] == "CALCULO":
        salida["unidad"] = unidad
        if sensibilidad is not None and unidad:
            nombre = reactivo["nombre"] if reactivo else "Propio"
            salida["referencia"] = f"{nombre} <{_texto(sensibilidad)} {unidad}"
    if not entrada.reactividad:
        return salida
    if entrada.reactividad == "Negativo":
        salida.update(resultado="Negativo", unidad="", referencia="", completo=True)
        return salida
    match = re.fullmatch(r"1\s*/\s*(\d+(?:[.,]\d+)?)", entrada.dilucion.strip())
    factor = _numero(match[1]) if match else None
    if config["modo"] == "TITULO":
        if factor is not None:
            salida.update(resultado=f"Positivo · 1/{_texto(factor)}", completo=True)
        else:
            salida["motivo"] = "Indique una dilución válida (1/n)."
        return salida
    if sensibilidad is None or not unidad:
        salida["motivo"] = "Complete la sensibilidad y su unidad."
        return salida
    if not entrada.dilucion and config.get("sin_dilucion"):
        salida.update(resultado=f"≥{_texto(sensibilidad)}", completo=True)
        return salida
    if factor is None:
        salida["motivo"] = "Indique una dilución válida (1/n)."
        return salida
    try:
        calculo = calcular(config["formula"], {"sensibilidad": sensibilidad, "factor": factor}, config["decimales"])
    except InvalidOperation:
        salida["motivo"] = "El resultado excede la precisión permitida."
        return salida
    salida.update(resultado=_texto(calculo.valor) if calculo.calculable else "No calculable", completo=calculo.calculable)
    return salida


def columnas_serologia(parametros: list[dict]) -> dict:
    configuraciones = [
        (p, p.get("captura_serologia") or INMUNOSEROLOGIA.captura.get(p.get("codigo"), {}))
        for p in parametros
    ]
    calculo = any(config.get("modo") == "CALCULO" for _, config in configuraciones)
    unidad_explicita = any(
        config.get("modo") != "TITULO" and p.get("unidad") and p.get("unidad") != "dilución"
        for p, config in configuraciones
    )
    return {"unidad": calculo or unidad_explicita, "referencia": calculo, "bandera": False}
