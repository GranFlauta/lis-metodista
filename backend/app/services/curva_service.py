"""Tomas reales de glucosa: validación temporal, sin estimaciones clínicas."""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
import re
from typing import Any
from zoneinfo import ZoneInfo

from app.core.errors import ValidacionError

ZONA = ZoneInfo("America/La_Paz")
HORA = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")


def rol_parametro_curva(parametro) -> str | None:
    version = parametro.estudio_version
    config = (version.configuracion_json or {}).get("captura", {}).get("curva_tolerancia") if version else None
    for fila in (config or {}).get("filas", []):
        for rol in ("hora", "glucosa", "fecha"):
            if fila[rol] == parametro.codigo:
                return rol
    return None


def validar_hora(valor: str) -> str:
    if not HORA.fullmatch(valor):
        raise ValidacionError("Hora de toma inválida. Use HH:mm en formato de 24 horas.")
    return valor


def construir_curva(config: dict, valores: dict[str, Any], fecha_estudio: date | None) -> dict:
    """Conserva cada posición, incluido un hueco que debe interrumpir el trazo."""
    filas = []
    anterior = None
    for definicion in config["filas"]:
        hora = valores.get(definicion["hora"]) or None
        glucosa = valores.get(definicion["glucosa"])
        glucosa = None if glucosa in (None, "") else str(glucosa)
        fecha_manual = valores.get(definicion["fecha"]) or None
        fecha = date.fromisoformat(str(fecha_manual)) if fecha_manual else fecha_estudio
        instante = None
        error = None
        utilizada = hora is not None or glucosa is not None or fecha_manual is not None
        if hora:
            validar_hora(str(hora))
        if utilizada and (not hora or glucosa is None):
            error = "Completa la hora y la glucosa de esta toma; puedes guardar el avance."
        if hora and not fecha:
            error = "Indica la fecha real de la toma."
        if hora and fecha:
            instante = datetime.combine(fecha, time.fromisoformat(str(hora)), tzinfo=ZONA)
            if anterior is not None and instante < anterior:
                error = "La hora es anterior a la toma previa. Aclara la fecha real o corrige la hora; no se asume el día siguiente."
                instante = None
            if instante is not None:
                anterior = instante
        filas.append({**definicion, "hora_valor": hora, "glucosa_valor": glucosa,
                      "fecha_valor": fecha.isoformat() if fecha else None, "fecha_explicita": bool(fecha_manual),
                      "instante": instante.isoformat() if instante is not None and glucosa is not None else None,
                      "minutos_desde_basal": None, "utilizada": utilizada, "error": error})
    basal = filas[0]
    basal_fecha = basal["fecha_valor"]
    basal_hora = basal["hora_valor"]
    base = datetime.combine(date.fromisoformat(basal_fecha), time.fromisoformat(basal_hora), tzinfo=ZONA) if basal_fecha and basal_hora else None
    for fila in filas:
        if base and fila["instante"]:
            diferencia = datetime.fromisoformat(fila["instante"]) - base
            segundos = diferencia.days * 86400 + diferencia.seconds
            fila["minutos_desde_basal"] = str(Decimal(segundos) / Decimal(60))
    return {"configuracion": config, "fecha_estudio": fecha_estudio.isoformat() if fecha_estudio else None, "filas": filas}
