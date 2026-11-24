"""Muestras seriadas: fechas reales y resultados explícitos, sin valores automáticos."""
from __future__ import annotations

from datetime import date, datetime, time
import json
import re
from zoneinfo import ZoneInfo

from app.core.clock import ahora
from app.core.errors import ValidacionError

ZONA = ZoneInfo("America/La_Paz")
HORA = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
TURNOS = {"MAÑANA", "TARDE", "NOCHE"}
CAMPOS_MUESTRA = {"numero", "fecha", "hora", "turno", "resultado"}


def configuracion_muestras(parametro) -> dict | None:
    version = parametro.estudio_version
    captura = (version.configuracion_json or {}).get("captura", {}) if version else {}
    return captura.get("muestras_seriadas", {}).get(parametro.codigo)


def _muestra(numero: int, fecha=None, hora=None, turno=None, resultado=None) -> dict:
    return {"numero": numero, "fecha": fecha, "hora": hora, "turno": turno, "resultado": resultado}


def _muestras_vacias(config):
    return [_muestra(numero) for numero in range(1, config["muestras_iniciales"] + 1)]


def normalizar_muestras(valor, config: dict, valor_anterior: str | None = None) -> str:
    if isinstance(valor, str):
        try:
            entrada = json.loads(valor)
        except (ValueError, TypeError):
            entrada = None
        # Sólo se admite el texto histórico si ya estaba guardado e idéntico.
        if not isinstance(entrada, dict) and valor == valor_anterior:
            return valor
    else:
        entrada = valor
    if not isinstance(entrada, dict) or set(entrada) != {"muestras"} or not isinstance(entrada["muestras"], list):
        raise ValidacionError("Ingrese las muestras con su fecha y resultado.")
    muestras = []
    ahora_local = ahora().astimezone(ZONA).replace(second=0, microsecond=0)
    hoy = ahora_local.date()
    for numero, item in enumerate(entrada["muestras"], 1):
        if not isinstance(item, dict) or set(item) - CAMPOS_MUESTRA:
            raise ValidacionError("Cada muestra sólo admite número, fecha, hora, turno y resultado.")
        if "numero" in item and (type(item["numero"]) is not int or item["numero"] != numero):
            raise ValidacionError("Las muestras deben numerarse consecutivamente desde 1.")
        fecha = item.get("fecha")
        fecha_real = None
        if fecha not in (None, ""):
            if not isinstance(fecha, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
                raise ValidacionError(f"Fecha inválida en la muestra {numero}. Use AAAA-MM-DD.")
            try:
                fecha_real = date.fromisoformat(fecha)
            except ValueError:
                raise ValidacionError(f"Fecha inválida en la muestra {numero}.")
            if fecha_real > hoy:
                raise ValidacionError(f"La fecha de la muestra {numero} no puede ser futura.")
        hora = item.get("hora")
        if hora not in (None, ""):
            if not isinstance(hora, str) or not HORA.fullmatch(hora.strip()):
                raise ValidacionError(f"Hora inválida en la muestra {numero}. Use HH:mm.")
            hora = hora.strip()
            if fecha_real is not None and datetime.combine(fecha_real, time.fromisoformat(hora), ZONA) > ahora_local:
                raise ValidacionError(f"La hora de la muestra {numero} no puede ser futura.")
        else:
            hora = None
        turno = item.get("turno")
        if turno not in (None, ""):
            if not isinstance(turno, str) or turno.strip().upper() not in TURNOS:
                raise ValidacionError(f"El turno de la muestra {numero} debe ser MAÑANA, TARDE o NOCHE.")
            turno = turno.strip().upper()
        else:
            turno = None
        resultado = item.get("resultado")
        if resultado is not None and not isinstance(resultado, str):
            raise ValidacionError(f"El resultado de la muestra {numero} debe ser texto.")
        resultado = resultado.strip() if resultado is not None else None
        if resultado in ("", "-", "--", "—", "–"):
            resultado = None
        muestras.append(_muestra(numero, fecha or None, hora, turno, resultado))
    while len(muestras) < config["muestras_iniciales"]:
        muestras.append(_muestra(len(muestras) + 1))
    return json.dumps({"muestras": muestras}, ensure_ascii=False, separators=(",", ":"))


def presentar_muestras(valor: str | None, config: dict) -> dict:
    if valor in (None, "", "-", "--", "—", "–"):
        muestras, anterior = _muestras_vacias(config), None
    else:
        try:
            entrada = json.loads(valor)
        except (ValueError, TypeError):
            entrada = None
        if not isinstance(entrada, dict) or not isinstance(entrada.get("muestras"), list):
            muestras, anterior = _muestras_vacias(config), valor
        else:
            muestras, anterior = entrada["muestras"], None
    def iniciada(muestra: dict) -> bool:
        return bool(muestra.get("fecha") or muestra.get("hora") or muestra.get("turno") or muestra.get("resultado"))

    utilizadas = [m for m in muestras if iniciada(m)]
    pendientes = [m["numero"] for m in utilizadas if not m.get("fecha") or not m.get("resultado")]
    completas = [m for m in utilizadas if m.get("fecha") and m.get("resultado")]

    def linea(muestra: dict) -> str:
        cuando = muestra["fecha"] + (f" {muestra['hora']}" if muestra.get("hora") else "")
        turno = f" · {muestra['turno']}" if muestra.get("turno") else ""
        return f"{muestra['numero']}.ª muestra · {cuando}{turno} · {muestra['resultado']}"

    resumen = "\n".join(linea(m) for m in completas)
    return {"muestras": muestras, "resultado_anterior": anterior, "utilizado": bool(utilizadas or anterior),
            "completo": bool(utilizadas or anterior) and not pendientes, "pendientes": pendientes,
            "resultado": anterior or resumen or None}
