"""
Esquemas Pydantic para endpoints de captura, cálculo y resultados (Fase 3).
"""
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class RangoOverrideItem(BaseModel):
    limite_inferior: Optional[Any] = None
    limite_superior: Optional[Any] = None
    texto: Optional[str] = None
    reestablecer: bool = False


class CalcularRequest(BaseModel):
    valores: dict[str, Any] = Field(default_factory=dict, description="Conjunto completo de entradas actuales.")
    rangos_override: Optional[dict[str, RangoOverrideItem]] = Field(default=None, description="Overrides de rangos por código de parámetro.")
    unidades_override: dict[str, str | None] | None = None


class ResultadosUpdateRequest(BaseModel):
    valores: dict[str, Any] = Field(default_factory=dict, description="Cambios parciales a persistir.")
    rangos_override: Optional[dict[str, RangoOverrideItem]] = Field(default=None, description="Overrides de rangos por código de parámetro.")
    observaciones_estudios: Optional[dict[str, Optional[str]]] = Field(default=None, description="Observaciones por código de estudio.")
    observaciones_orden: Optional[str] = Field(default=None, description="Observaciones finales de la orden.")
    etiquetas_estudios: Optional[dict[str, str | None]] = Field(default=None, description="Etiquetas de presentación editables por estudio.")
    unidades_override: dict[str, str | None] | None = None


class VistaPreviaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valores: dict[str, Any] = Field(default_factory=dict)
    rangos_override: Optional[dict[str, RangoOverrideItem]] = None
    observaciones_estudios: Optional[dict[str, Optional[str]]] = None
    observaciones_orden: Optional[str] = Field(default=None, max_length=10000)
    etiqueta_cayados: Optional[str] = Field(default=None, max_length=80)
    unidades_override: dict[str, str | None] | None = None


class PaginaVistaPrevia(BaseModel):
    numero: int
    ancho: int
    alto: int
    imagen: str


class VistaPreviaResponse(BaseModel):
    formato: str = "Carta"
    paginas: list[PaginaVistaPrevia]


class ConfirmarDefectosRequest(BaseModel):
    parametros: Optional[list[str]] = Field(default=None, description="Códigos de parámetros por defecto a confirmar.")


class ConfiguracionLaboratorioResponse(BaseModel):
    nombre_laboratorio: str
    separador_decimal: str
