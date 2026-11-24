"""Preparación visual de la curva de tolerancia desde los resultados medidos."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from app.reports.presentation import formatear_numero_informe

_ZONA_LABORATORIO = ZoneInfo("America/La_Paz")
_GLUCOSA_MINIMA = Decimal("0")
_GLUCOSA_MAXIMA = Decimal("200")
_INTERVALO_GLUCOMETRICO = Decimal("20")


def _minuto_local(instante: str) -> int:
    fecha_hora = datetime.fromisoformat(instante)
    if fecha_hora.tzinfo is None:
        fecha_hora = fecha_hora.replace(tzinfo=timezone.utc)
    fecha_hora = fecha_hora.astimezone(_ZONA_LABORATORIO)
    return fecha_hora.date().toordinal() * 1440 + fecha_hora.hour * 60 + fecha_hora.minute


def _texto_decimal(valor: Decimal) -> str:
    texto = format(valor, "f")
    return texto.rstrip("0").rstrip(".") if "." in texto else texto


def preparar_curva(curva: dict[str, Any] | None, separador_decimal: str) -> dict[str, Any] | None:
    if not curva:
        return None

    filas = []
    segmentos: list[list[dict[str, Any]]] = []
    for indice, fila in enumerate(curva.get("filas") or []):
        glucosa = fila.get("glucosa_valor")
        punto = None
        if fila.get("instante") and glucosa is not None:
            try:
                glucosa_num = Decimal(str(glucosa))
                minuto = _minuto_local(fila["instante"])
            except (InvalidOperation, ValueError):
                pass
            else:
                punto = {
                    "fila": indice,
                    "minuto": minuto,
                    "glucosa": glucosa_num,
                    "fuera_de_escala": glucosa_num < _GLUCOSA_MINIMA or glucosa_num > _GLUCOSA_MAXIMA,
                    "x": None,
                    "y": None,
                    "etiqueta": (
                        f"{fila['etiqueta']} toma · {fila['hora_valor']} · "
                        f"{formatear_numero_informe(str(glucosa), separador_decimal)} mg/dL"
                    ),
                }
                if fila.get("minutos_desde_basal") is not None:
                    punto["etiqueta"] += f" · {_texto_decimal(Decimal(fila['minutos_desde_basal']))} min desde basal"
        filas.append({
            "etiqueta": fila.get("etiqueta") or "",
            "hora": fila.get("hora_valor") or "",
            "glucosa": formatear_numero_informe(str(glucosa), separador_decimal) if glucosa is not None else "",
            "unidad": (curva.get("configuracion") or {}).get("unidad") or "mg/dL",
            "punto": punto,
        })
        if punto is None:
            if segmentos and segmentos[-1]:
                segmentos.append([])
        else:
            if not segmentos or not segmentos[-1]:
                segmentos.append([])
            segmentos[-1].append(punto)

    puntos = [fila["punto"] for fila in filas if fila["punto"] is not None]
    ancho, alto = 720, 300
    izquierda, derecha, arriba, abajo = 54, 16, 20, 54
    plot_ancho, plot_alto = ancho - izquierda - derecha, alto - arriba - abajo
    if puntos:
        x_min = min(punto["minuto"] for punto in puntos)
        x_max = max(punto["minuto"] for punto in puntos)
        if x_min == x_max:
            x_inicio, x_fin = Decimal(x_min - 30), Decimal(x_max + 30)
        else:
            margen_x = max(Decimal("5"), Decimal(x_max - x_min) * Decimal("0.05"))
            x_inicio, x_fin = Decimal(x_min) - margen_x, Decimal(x_max) + margen_x

        def coordenada_x(minuto: int) -> str:
            valor = Decimal(izquierda) + (Decimal(minuto) - x_inicio) / (x_fin - x_inicio) * Decimal(plot_ancho)
            return format(valor.quantize(Decimal("0.01")), "f")

        def coordenada_y(glucosa: Decimal) -> str:
            valor = Decimal(arriba) + (_GLUCOSA_MAXIMA - glucosa) / (_GLUCOSA_MAXIMA - _GLUCOSA_MINIMA) * Decimal(plot_alto)
            return format(valor.quantize(Decimal("0.01")), "f")

        for punto in puntos:
            punto["x"] = coordenada_x(punto["minuto"])
            punto["y"] = coordenada_y(punto["glucosa"])
        ticks_y = []
        numero_ticks_y = int((_GLUCOSA_MAXIMA - _GLUCOSA_MINIMA) / _INTERVALO_GLUCOMETRICO) + 1
        for indice in range(numero_ticks_y):
            valor = _GLUCOSA_MINIMA + _INTERVALO_GLUCOMETRICO * indice
            y_coord = coordenada_y(valor)
            ticks_y.append({
                "y": y_coord,
                "label_y": format((Decimal(y_coord) + Decimal("4")).quantize(Decimal("0.01")), "f"),
                "valor": _texto_decimal(valor),
            })
        ticks_x = []
        for minuto in sorted({punto["minuto"] for punto in puntos}):
            ticks_x.append({
                "x": coordenada_x(minuto),
                "hora": f"{(minuto % 1440) // 60:02d}:{minuto % 60:02d}",
            })
    else:
        ticks_y, ticks_x = [], []

    trazos = []
    for segmento in segmentos:
        if len(segmento) > 1:
            trazos.append({
                "path": " ".join(
                    f"{'M' if indice == 0 else 'L'} {punto['x']} {punto['y']}"
                    for indice, punto in enumerate(segmento)
                )
            })
    return {
        "filas": filas,
        "puntos": puntos,
        "segmentos": trazos,
        "ticks_y": ticks_y,
        "ticks_x": ticks_x,
        "ancho": ancho,
        "alto": alto,
        "izquierda": izquierda,
        "derecha": derecha,
        "arriba": arriba,
        "abajo": abajo,
        "plot_ancho": plot_ancho,
        "plot_alto": plot_alto,
        "titulo_x": format((Decimal(izquierda) + Decimal(plot_ancho) / Decimal("2")).quantize(Decimal("0.01")), "f"),
        "titulo_y": format((Decimal(arriba) + Decimal(plot_alto) / Decimal("2")).quantize(Decimal("0.01")), "f"),
    }
