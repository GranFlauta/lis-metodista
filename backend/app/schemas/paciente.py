"""
Esquemas Pydantic para el módulo de Pacientes.
Alineados estrictamente con PROMPT_FASE_2.md §8.2.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class PacienteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ci: Optional[str] = None
    ci_complemento: Optional[str] = None
    sin_ci: bool = False
    nombres: str
    apellido_paterno: str
    apellido_materno: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    sexo: str
    telefono: Optional[str] = None


class PacienteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ci: Optional[str] = None
    ci_complemento: Optional[str] = None
    sin_ci: Optional[bool] = None
    nombres: Optional[str] = None
    apellido_paterno: Optional[str] = None
    apellido_materno: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    sexo: Optional[str] = None
    telefono: Optional[str] = None


class PacienteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int = Field(validation_alias=AliasChoices("id_paciente", "id"))
    ci: Optional[str] = None
    ci_complemento: Optional[str] = None
    sin_ci: bool
    nombres: str
    apellido_paterno: str
    apellido_materno: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    sexo: str
    telefono: Optional[str] = None
    creado_en: datetime
    pendientes: int = 0


class PacienteListaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PacienteResponse]
    total: int
    limit: int
    offset: int
