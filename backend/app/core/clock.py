"""
Módulo de reloj centralizado del sistema clínico LIS.
docs/DECISIONES.md y PROMPT_FASE_1.md exigen que todo el código use `ahora()`
en lugar de llamar directamente a datetime.now() fuera de este módulo.
Permite simulación temporal determinista en pruebas unitarias e integración.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Variable para tiempo simulado en entornos de test
_simulated_time: datetime | None = None


def ahora() -> datetime:
    """
    Retorna la fecha y hora actual en UTC consciente de zona horaria.
    Si se ha fijado un tiempo simulado (vía set_simulated_time), retorna dicho valor.
    """
    global _simulated_time
    if _simulated_time is not None:
        return _simulated_time
    return datetime.now(timezone.utc)


def set_simulated_time(dt: datetime | None) -> None:
    """
    Establece el tiempo simulado para testing.
    """
    global _simulated_time
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    _simulated_time = dt


def reset_clock() -> None:
    """Restablece el reloj al tiempo real del sistema."""
    global _simulated_time
    _simulated_time = None
