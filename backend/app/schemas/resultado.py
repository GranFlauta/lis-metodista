"""
Esquemas Pydantic para endpoints de captura, cálculo y resultados (Fase 3).
"""
from typing import Any, Optional
from pydantic import BaseModel, Field


class CalcularRequest(BaseModel):
    valores: dict[str, Any] = Field(default_factory=dict, description="Conjunto completo de entradas actuales.")


class ResultadosUpdateRequest(BaseModel):
    valores: dict[str, Any] = Field(default_factory=dict, description="Cambios parciales a persistir.")


class ConfirmarDefectosRequest(BaseModel):
    parametros: Optional[list[str]] = Field(default=None, description="Códigos de parámetros por defecto a confirmar.")


class ConfiguracionLaboratorioResponse(BaseModel):
    nombre_laboratorio: str
    separador_decimal: str
