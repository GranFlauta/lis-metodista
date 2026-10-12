"""
Esquemas Pydantic para Órdenes en borrador.
Alineados estrictamente con PROMPT_FASE_2.md §8.3.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.paciente import PacienteCreate


class EstudioItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    grupos: Optional[list[str]] = None


class OrdenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_paciente: Optional[int] = None
    paciente: Optional[PacienteCreate] = None
    perfil: Optional[str] = None
    estudios: list[EstudioItemCreate]
    origen_solicitud: Optional[str] = None
    medico_solicitante: Optional[str] = None
    pieza: Optional[str] = None
    edad_anios: Optional[int] = None
    edad_meses: Optional[int] = None
    fecha_hora_toma_muestra: Optional[datetime] = None


class OrdenUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fila_version: int
    origen_solicitud: Optional[str] = None
    medico_solicitante: Optional[str] = None
    pieza: Optional[str] = None
    edad_anios: Optional[int] = None
    edad_meses: Optional[int] = None
    fecha_hora_toma_muestra: Optional[datetime] = None


class AutorResumen(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: Optional[int] = Field(None, validation_alias=AliasChoices("id_usuario", "id"))
    nombres: str
    apellido_paterno: str


class PerfilResumen(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    codigo: str
    nombre: str


class PacienteResumenOrden(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int = Field(validation_alias=AliasChoices("id_paciente", "id"))
    ci: Optional[str] = None
    ci_complemento: Optional[str] = None
    nombres: str
    apellido_paterno: str
    apellido_materno: Optional[str] = None
    sexo: Optional[str] = None
    fecha_nacimiento: Optional[date] = None


class PacienteListaItem(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int = Field(validation_alias=AliasChoices("id_paciente", "id"))
    ci: Optional[str] = None
    nombres: str
    apellido_paterno: str
    apellido_materno: Optional[str] = None


class EstudioItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    nombre: str
    grupos: Optional[list[str]] = None


class AdvertenciaSolapamiento(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: str = "SOLAPAMIENTO"
    autor: AutorResumen
    estudios: list[str]


class OrdenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int = Field(validation_alias=AliasChoices("id_orden", "id"))
    paciente: PacienteResumenOrden
    numero_orden_paciente: int
    autor: AutorResumen
    perfil: Optional[PerfilResumen] = None
    origen_solicitud: Optional[str] = None
    medico_solicitante: Optional[str] = None
    pieza: Optional[str] = None
    edad_anios: Optional[int] = None
    edad_meses: Optional[int] = None
    fecha_solicitud: date
    fecha_hora_toma_muestra: Optional[datetime] = None
    estado_trabajo: str
    bloqueada: bool
    fila_version: int
    estudios: list[EstudioItemResponse]
    creado_en: datetime
    actualizado_en: datetime


class OrdenCreadaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    orden: OrdenResponse
    advertencias: list[AdvertenciaSolapamiento] = []


class OrdenListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    paciente: PacienteListaItem
    numero_orden_paciente: int
    estado_trabajo: str
    bloqueada: bool
    estudios: list[str]
    fecha_solicitud: date
    creado_en: datetime


class OrdenListaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrdenListItem]
    total: int
    limit: int
    offset: int
