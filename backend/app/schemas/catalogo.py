"""
Esquemas Pydantic para los endpoints de lectura del catálogo clínico.
Alineados con PROMPT_FASE_2.md §8.1.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ParametroResumen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    nombre: str


class GrupoEstudio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    parametros: list[ParametroResumen]


class EstudioCatalogo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    nombre: str
    categoria: str
    seleccion_parcial: bool
    grupos: Optional[list[GrupoEstudio]] = None


class PerfilEstudioItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    grupos: Optional[list[str]] = None


class PerfilCatalogo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    nombre: str
    estudios: list[PerfilEstudioItem]


class PerfilRapidoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=100)
    estudios: list[PerfilEstudioItem] = Field(min_length=1)


class PerfilRapidoResponse(BaseModel):
    id: int
    nombre: str
    estudios: list[PerfilEstudioItem]
