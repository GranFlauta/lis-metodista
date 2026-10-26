"""
Esquemas Pydantic para Publicación, Versiones, Papelera e Informes Oficiales (Fase 4).
"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class PublicarOrdenRequest(BaseModel):
    justificativo_urgencia: Optional[str] = Field(
        default=None,
        description="Obligatorio si la publicación se realiza bajo modalidad de urgencia por un bioquímico ajeno.",
    )


class JustificativoRequest(BaseModel):
    justificativo: str = Field(
        ...,
        min_length=5,
        description="Motivo o justificación auditada de la acción (obligatorio, mín. 5 caracteres).",
    )


class NuevaVersionRequest(BaseModel):
    justificativo: str = Field(
        ...,
        min_length=5,
        description="Motivo clínico o administrativo para crear la nueva versión V2/V3.",
    )


class InformeEventoResponse(BaseModel):
    id_evento: int
    folio: str
    numero_version: Optional[int]
    accion: str
    justificativo: Optional[str]
    detalle: Optional[dict[str, Any]]
    id_usuario: int
    usuario_nombre: str
    creado_en: datetime


class InformeItemResponse(BaseModel):
    id_informe: int
    folio: str
    numero_version: int
    id_orden: int
    estado: str
    es_urgencia: bool
    justificativo: Optional[str]
    publicado_en: datetime
    paciente_nombre: str
    paciente_ci: Optional[str]
    firmante_nombre: str
    publicador_nombre: str
    snapshot_sha256: str


class InformeDetalleResponse(BaseModel):
    id_informe: int
    folio: str
    numero_version: int
    id_orden: int
    estado: str
    es_urgencia: bool
    justificativo: Optional[str]
    publicado_en: datetime
    snapshot_json: dict[str, Any]
    snapshot_sha256: str
    firmante: dict[str, Any]
    publicador: dict[str, Any]
    eventos: list[InformeEventoResponse] = []
    versiones_disponibles: list[dict[str, Any]] = []


class PapeleraItemResponse(BaseModel):
    id_informe: int
    folio: str
    numero_version: int
    id_orden: int
    estado: str
    paciente_nombre: str
    paciente_ci: Optional[str]
    firmante_nombre: str
    motivo_papelera: Optional[str]
    fecha_papelera: datetime
