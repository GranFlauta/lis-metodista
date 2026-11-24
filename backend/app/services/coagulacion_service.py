"""Unidades editables de coagulación; los valores y referencias no se convierten."""
from app.core.errors import ValidacionError
from app.reports.presentation import es_vacio


def unidad_coagulacion_editable(estudio_codigo, parametro) -> bool:
    return (
        estudio_codigo == "COAGULOGRAMA"
        and parametro.grupo == "COAGULACION"
        and parametro.tipo_campo == "NUMERICO"
    )


def normalizar_unidad_coagulacion(valor) -> str | None:
    if valor is None:
        return None  # Restablece la unidad del catálogo, incluido INR sin unidad.
    if not isinstance(valor, str):
        raise ValidacionError("La unidad de coagulación debe ser texto.")
    unidad = valor.strip()
    if len(unidad) > 30:
        raise ValidacionError("La unidad de coagulación no puede exceder 30 caracteres.")
    return "" if es_vacio(unidad) else unidad
