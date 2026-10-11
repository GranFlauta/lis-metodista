"""
Motor de cálculo seguro para parámetros CALCULADOS.

Reglas (ver docs/DECISIONES.md, sección 5):
  * NUNCA se usa eval/exec. Se parsea la expresión con `ast` y solo se aceptan
    nodos de una lista blanca.
  * Toda la aritmética es Decimal (nunca float).
  * Un valor vacío es `None`, jamás 0. Si falta una entrada o hay división por
    cero, el resultado es NO_CALCULABLE (no se inventa un número).
  * El backend es la ÚNICA fuente de verdad. La vista previa del frontend llama
    a /calcular (con debounce); no se reimplementan fórmulas en TypeScript.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Mapping, Optional


class NoCalculable(Exception):
    """Falta una entrada, división por cero o regla de validez incumplida."""


@dataclass(frozen=True)
class ResultadoCalculo:
    valor: Optional[Decimal]
    calculable: bool
    motivo: Optional[str] = None


_BIN = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}
_CMP = {
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
}


def _no_calculable() -> None:
    raise NoCalculable("regla de validez incumplida")


_FUNCS = {"no_calculable": _no_calculable, "abs": abs, "min": min, "max": max}


def a_decimal(valor) -> Optional[Decimal]:
    """Convierte a Decimal aceptando coma decimal ('5,4'). Vacío -> None."""
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        return valor
    texto = str(valor).strip().replace(",", ".")
    if texto == "":
        return None
    try:
        return Decimal(texto)
    except InvalidOperation as exc:
        raise ValueError(f"valor numérico inválido: {valor!r}") from exc


def _eval(nodo: ast.AST, ctx: Mapping[str, Optional[Decimal]]):
    if isinstance(nodo, ast.Expression):
        return _eval(nodo.body, ctx)
    if isinstance(nodo, ast.Constant):
        if isinstance(nodo.value, (int, float)) and not isinstance(nodo.value, bool):
            return Decimal(str(nodo.value))
        raise ValueError("constante no permitida")
    if isinstance(nodo, ast.Name):
        if nodo.id not in ctx:
            raise ValueError(f"parámetro desconocido: {nodo.id}")
        valor = ctx[nodo.id]
        if valor is None:
            raise NoCalculable(f"falta {nodo.id}")
        return valor
    if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, (ast.USub, ast.UAdd)):
        v = _eval(nodo.operand, ctx)
        return -v if isinstance(nodo.op, ast.USub) else v
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in _BIN:
        izq, der = _eval(nodo.left, ctx), _eval(nodo.right, ctx)
        if isinstance(nodo.op, ast.Div) and der == 0:
            raise NoCalculable("división por cero")
        return _BIN[type(nodo.op)](izq, der)
    if isinstance(nodo, ast.Compare):
        izq = _eval(nodo.left, ctx)
        for op, comp in zip(nodo.ops, nodo.comparators):
            der = _eval(comp, ctx)
            if type(op) not in _CMP or not _CMP[type(op)](izq, der):
                return False
            izq = der
        return True
    if isinstance(nodo, ast.IfExp):
        # Solo se evalúa la rama elegida: así `x if cond else no_calculable()`
        # no explota cuando la condición falla.
        return _eval(nodo.body if _eval(nodo.test, ctx) else nodo.orelse, ctx)
    if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
        if nodo.func.id not in _FUNCS or nodo.keywords:
            raise ValueError(f"función no permitida: {nodo.func.id}")
        return _FUNCS[nodo.func.id](*[_eval(a, ctx) for a in nodo.args])
    raise ValueError(f"expresión no permitida: {type(nodo).__name__}")


def redondear(valor: Decimal, decimales: int) -> Decimal:
    return valor.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)


def calcular(
    formula: str,
    entradas: Mapping[str, Optional[Decimal]],
    decimales: int = 2,
) -> ResultadoCalculo:
    """Evalúa `formula` con `entradas` (codigo_en_minusculas -> Decimal|None)."""
    arbol = ast.parse(formula, mode="eval")
    try:
        valor = _eval(arbol, entradas)
    except NoCalculable as exc:
        return ResultadoCalculo(None, False, str(exc))
    if isinstance(valor, bool):
        raise ValueError("la fórmula debe devolver un número")
    return ResultadoCalculo(redondear(valor, decimales), True)


def variables_de(formula: str) -> set[str]:
    """Nombres de parámetros que usa una fórmula (para ordenar dependencias)."""
    nombres = {n.id for n in ast.walk(ast.parse(formula, mode="eval")) if isinstance(n, ast.Name)}
    return nombres - set(_FUNCS)
