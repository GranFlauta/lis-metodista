"""Agregados operativos; no incluyen pacientes ni valores clínicos."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


FiltroRespuesta = Literal["todas", "hasta_60", "de_60_a_240", "mas_240", "sin_hora"]


class ProfesionalEstadistica(BaseModel):
    id: int
    nombre: str
    activo: bool


class SerieEstadistica(BaseModel):
    codigo: str
    nombre: str
    cantidad: int


class ActividadDiaria(BaseModel):
    fecha: date
    iniciadas: int
    publicadas: int


class ResumenEstadistica(BaseModel):
    ordenes: int
    publicadas: int
    pendientes: int
    estudios_informados: int
    respuesta_mediana_minutos: str | None
    respuestas_validas: int
    publicadas_sin_hora: int


class EstadisticaResponse(BaseModel):
    desde: date
    hasta: date
    generado_en: datetime
    alcance: Literal["laboratorio", "propio"]
    id_autor: int | None
    respuesta: FiltroRespuesta
    profesionales: list[ProfesionalEstadistica]
    resumen: ResumenEstadistica
    estados: list[SerieEstadistica]
    estudios: list[SerieEstadistica]
    responsables: list[SerieEstadistica]
    tiempos_respuesta: list[SerieEstadistica]
    actividad: list[ActividadDiaria]
