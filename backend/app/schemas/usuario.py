"""
Esquemas Pydantic para la gestión de usuarios (Fase 1).
Alineado con PROMPT_FASE_1.md §6.3.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class UsuarioCreate(BaseModel):
    """Esquema para crear un nuevo usuario (§6.3)."""
    model_config = ConfigDict(str_strip_whitespace=True)

    usuario: str = Field(
        ...,
        description="Login del usuario: letras minúsculas, números, punto, guion o guion bajo (3 a 40 caracteres).",
    )
    ci: str = Field(
        ...,
        min_length=5,
        max_length=30,
        description="Documento de identidad único.",
    )
    nombres: str = Field(..., min_length=2, max_length=100)
    apellido_paterno: str = Field(..., min_length=2, max_length=100)
    apellido_materno: str | None = Field(default=None, max_length=100)
    correo: str | None = Field(default=None, max_length=255)
    matricula_profesional: str | None = Field(default=None, max_length=50)
    rol: str = Field(
        default="BIOQUIMICO",
        description="Rol: ADMIN o BIOQUIMICO.",
    )

    @field_validator("usuario")
    @classmethod
    def validar_usuario_login(cls, v: str) -> str:
        login = v.strip().lower()
        if not re.match(r"^[a-z0-9._-]{3,40}$", login):
            raise ValueError(
                "El usuario debe tener entre 3 y 40 caracteres y solo contener letras minúsculas, números, '.', '-' o '_'."
            )
        return login

    @field_validator("correo")
    @classmethod
    def validar_formato_correo(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        correo = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", correo):
            raise ValueError("Formato de correo electrónico inválido (debe ser usuario@dominio.tld).")
        return correo


class UsuarioUpdate(BaseModel):
    """Esquema para PATCH /api/usuarios/{id} (§6.3)."""
    model_config = ConfigDict(str_strip_whitespace=True)

    nombres: str | None = Field(default=None, min_length=2, max_length=100)
    apellido_paterno: str | None = Field(default=None, min_length=2, max_length=100)
    apellido_materno: str | None = Field(default=None, max_length=100)
    correo: str | None = Field(default=None, max_length=255)
    matricula_profesional: str | None = Field(default=None, max_length=50)
    rol: str | None = Field(default=None)
    ci: str | None = Field(default=None, min_length=5, max_length=30)

    @field_validator("correo")
    @classmethod
    def validar_correo_update(cls, v: str | None) -> str | None:
        if v is None:
            return None
        correo = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", correo):
            raise ValueError("Formato de correo electrónico inválido.")
        return correo


class UsuarioDetalleResponse(BaseModel):
    """Representación de usuario en la lista o detalle (sin hash_password ni firma_imagen)."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int = Field(..., alias="id_usuario")
    usuario: str
    ci: str
    nombres: str
    apellido_paterno: str
    apellido_materno: str | None = None
    correo: str | None = None
    matricula_profesional: str | None = None
    rol: str
    debe_cambiar_password: bool
    activo: bool
    ultimo_login: datetime | None = None
    creado_en: datetime

    @field_validator("rol", mode="before")
    @classmethod
    def extraer_rol(cls, v: Any) -> str:
        if hasattr(v, "nombre"):
            return str(v.nombre)
        return str(v)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def nombre_completo(self) -> str:
        partes = [self.nombres, self.apellido_paterno]
        if self.apellido_materno:
            partes.append(self.apellido_materno)
        return " ".join(partes)


class UsuarioCreadoResponse(UsuarioDetalleResponse):
    """Respuesta tras POST /api/usuarios incluyendo la contraseña temporal (§6.3)."""
    password_temporal: str


class ResetPasswordResponse(BaseModel):
    """Respuesta tras POST /api/usuarios/{id}/reset-password (§6.3)."""
    password_temporal: str
