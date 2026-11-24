"""Selección de grupo sanguíneo y lectura compatible de borradores anteriores."""
from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import ValidacionError
from app.reports.presentation import es_vacio


class EntradaGrupoSanguineo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    valor: str = ""
    unidad: str = Field(default="", max_length=30)


def es_parametro_grupo_sanguineo(parametro) -> bool:
    return (
        parametro.grupo == "GRUPO_SANGUINEO"
        and parametro.codigo in {"GRUPO_SANGUINEO", "FACTOR_RH"}
        and parametro.tipo_campo == "SELECCION"
    )


def leer_entrada_grupo_sanguineo(valor) -> EntradaGrupoSanguineo:
    if es_vacio(valor):
        return EntradaGrupoSanguineo()
    if isinstance(valor, str):
        if not valor.lstrip().startswith("{"):
            return EntradaGrupoSanguineo(valor=valor)
        try:
            valor = json.loads(valor)
        except ValueError:
            raise ValidacionError("Captura de grupo sanguíneo inválida.")
    try:
        return EntradaGrupoSanguineo.model_validate(valor)
    except ValidationError:
        raise ValidacionError("Campos de captura de grupo sanguíneo inválidos.")


def normalizar_entrada_grupo_sanguineo(parametro, valor) -> str | None:
    entrada = leer_entrada_grupo_sanguineo(valor)
    if es_vacio(entrada.valor):
        entrada.valor = ""
    elif entrada.valor not in (parametro.opciones or []):
        raise ValidacionError(f"Opción no permitida para {parametro.codigo}.")
    # La unidad de la captura anterior se descarta; sólo se guarda la selección.
    return entrada.valor or None
