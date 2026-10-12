"""
Esquemas Pydantic para el módulo de Autenticación y Seguridad (Fase 1).
Basado estrictamente en docs/DECISIONES.md y PROMPT_FASE_1.md §6.

Incluye:
1. Esquema de Login (credenciales de acceso).
2. Esquema para cambio de contraseña obligatorio y voluntario.
3. Esquemas de respuesta para token JWT de acceso, /me y datos del usuario.
4. Esquema de respuesta administrativa con contraseña temporal en texto plano (14 caracteres).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


# -----------------------------------------------------------------------------
# 1. Esquema de Login
# -----------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """
    Datos de entrada para autenticación de usuarios.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    usuario: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Nombre de usuario o login único registrado en el sistema.",
        examples=["admin", "mlopez"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Contraseña del usuario en texto plano.",
    )


# -----------------------------------------------------------------------------
# 2. Esquema para Cambio de Contraseña (POST /api/auth/cambiar-password)
# -----------------------------------------------------------------------------

class CambiarPasswordRequest(BaseModel):
    """
    Cuerpo para POST /api/auth/cambiar-password según PROMPT_FASE_1.md §6.2.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    password_actual: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Contraseña actual del usuario.",
    )
    password_nueva: str = Field(
        ...,
        min_length=10,
        max_length=128,
        description="Nueva contraseña que debe cumplir con la política clínica.",
    )


class CambioPasswordRequest(BaseModel):
    """Alias compatible con formularios que usan password_nuevo y confirmación."""
    model_config = ConfigDict(str_strip_whitespace=True)

    password_actual: str = Field(..., min_length=1, max_length=128)
    password_nuevo: str = Field(..., min_length=10, max_length=128)
    confirmar_password: str | None = Field(default=None)

    @model_validator(mode="after")
    def validar_diferencia_y_coincidencia(self) -> CambioPasswordRequest:
        if self.password_nuevo == self.password_actual:
            raise ValueError("La nueva contraseña debe ser distinta de la contraseña actual.")
        if self.confirmar_password is not None and self.password_nuevo != self.confirmar_password:
            raise ValueError("La nueva contraseña y su confirmación no coinciden.")
        return self


# -----------------------------------------------------------------------------
# 3. Esquemas de Usuario y Token de Acceso
# -----------------------------------------------------------------------------

class UsuarioResumenResponse(BaseModel):
    """
    Representación resumida del usuario devuelta en login y refresh (§6.2).
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int = Field(..., alias="id_usuario", description="Identificador único del usuario.")
    usuario: str = Field(..., description="Login de usuario.")
    nombres: str = Field(..., description="Nombres.")
    apellido_paterno: str = Field(..., description="Primer apellido.")
    apellido_materno: str | None = Field(default=None, description="Segundo apellido.")
    rol: str = Field(..., description="Rol (ADMIN o BIOQUIMICO).")

    @field_validator("rol", mode="before")
    @classmethod
    def extraer_nombre_rol(cls, value: Any) -> str:
        if hasattr(value, "nombre"):
            return str(value.nombre)
        return str(value)


class MeResponse(BaseModel):
    """
    Respuesta para GET /api/auth/me según PROMPT_FASE_1.md §6.2.
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int = Field(..., alias="id_usuario", description="Identificador del usuario.")
    usuario: str = Field(..., description="Login del usuario.")
    nombres: str = Field(..., description="Nombres.")
    apellido_paterno: str = Field(..., description="Primer apellido.")
    apellido_materno: str | None = Field(default=None, description="Segundo apellido.")
    rol: str = Field(..., description="Rol.")
    debe_cambiar_password: bool = Field(..., description="Flag de cambio obligatorio de clave.")

    @field_validator("rol", mode="before")
    @classmethod
    def extraer_nombre_rol(cls, value: Any) -> str:
        if hasattr(value, "nombre"):
            return str(value.nombre)
        return str(value)


class UsuarioResponse(BaseModel):
    """
    Ficha completa pública del usuario.
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id_usuario: int = Field(..., description="Identificador único del usuario.")
    id_rol: int | None = Field(default=None, description="Identificador del rol.")
    rol: str = Field(..., description="Nombre del rol asignado (ADMIN o BIOQUIMICO).")
    usuario: str = Field(..., description="Login de usuario.")
    ci: str = Field(..., description="Documento de identidad del usuario.")
    nombres: str = Field(..., description="Nombres del usuario.")
    apellido_paterno: str = Field(..., description="Primer apellido.")
    apellido_materno: str | None = Field(default=None, description="Segundo apellido (opcional).")
    correo: str | None = Field(default=None, description="Correo electrónico institucional.")
    matricula_profesional: str | None = Field(
        default=None,
        description="Matrícula profesional para firma de informes (obligatoria en bioquímicos).",
    )
    debe_cambiar_password: bool = Field(
        ...,
        description="Indica si el usuario tiene pendiente un cambio de contraseña obligatorio.",
    )
    activo: bool = Field(..., description="Estado activo de la cuenta.")
    ultimo_login: datetime | None = Field(default=None, description="Fecha y hora del último inicio de sesión.")

    @field_validator("rol", mode="before")
    @classmethod
    def extraer_nombre_rol(cls, value: Any) -> str:
        if hasattr(value, "nombre"):
            return str(value.nombre)
        return str(value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> int:
        """Alias id para compatibilidad con el frontend."""
        return self.id_usuario

    @computed_field  # type: ignore[prop-decorator]
    @property
    def nombre_completo(self) -> str:
        """Nombre completo formateado para visualización e informes."""
        partes = [self.nombres, self.apellido_paterno]
        if self.apellido_materno:
            partes.append(self.apellido_materno)
        return " ".join(partes)


class TokenResponse(BaseModel):
    """
    Respuesta exitosa de autenticación con token JWT de acceso (§6.2).
    """
    access_token: str = Field(..., description="Token de acceso JWT firmado.")
    token_type: str = Field(default="bearer", description="Tipo de autorización HTTP (bearer).")
    expires_in: int = Field(..., description="Tiempo de vigencia del token de acceso en segundos.")
    debe_cambiar_password: bool = Field(..., description="Informa si debe forzarse el cambio de clave.")
    usuario: UsuarioResumenResponse = Field(..., description="Detalles del usuario autenticado.")


# -----------------------------------------------------------------------------
# 4. Esquema de Respuesta Administrativa (Creación y Reseteo)
# -----------------------------------------------------------------------------

class UsuarioAdminResponse(BaseModel):
    """
    Respuesta para el Administrador tras registrar un usuario nuevo o ejecutar reset.
    Devuelve la contraseña temporal aleatoria de 14 caracteres en texto plano por única vez (§6.3).
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int = Field(..., alias="id_usuario", description="Identificador único del usuario.")
    id_usuario: int | None = Field(default=None, description="Alias para id_usuario.")
    id_rol: int | None = Field(default=None, description="Identificador del rol.")
    rol: str = Field(..., description="Nombre del rol asignado.")
    usuario: str = Field(..., description="Login de usuario.")
    ci: str = Field(..., description="Documento de identidad.")
    nombres: str = Field(..., description="Nombres del usuario.")
    apellido_paterno: str = Field(..., description="Primer apellido.")
    apellido_materno: str | None = Field(default=None, description="Segundo apellido.")
    correo: str | None = Field(default=None, description="Correo electrónico.")
    matricula_profesional: str | None = Field(default=None, description="Matrícula profesional.")
    debe_cambiar_password: bool = Field(
        default=True,
        description="Siempre True tras creación o reseteo por el administrador.",
    )
    activo: bool = Field(default=True, description="Estado de la cuenta.")
    password_temporal: str = Field(
        ...,
        min_length=14,
        max_length=14,
        description="Contraseña temporal aleatoria de exactamente 14 caracteres en texto plano.",
        examples=["kP9#mX2$vL8@qT"],
    )
    mensaje: str = Field(
        default="Contraseña temporal generada. Debe entregarse al usuario; se le exigirá cambiarla en su primer inicio de sesión.",
        description="Instrucciones operativas para el administrador.",
    )

    @field_validator("rol", mode="before")
    @classmethod
    def extraer_nombre_rol(cls, value: Any) -> str:
        if hasattr(value, "nombre"):
            return str(value.nombre)
        return str(value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def nombre_completo(self) -> str:
        partes = [self.nombres, self.apellido_paterno]
        if self.apellido_materno:
            partes.append(self.apellido_materno)
        return " ".join(partes)


# Aliases
LoginSchema = LoginRequest
PasswordChangeRequest = CambiarPasswordRequest
UsuarioInfoResponse = UsuarioResponse
UsuarioCreadoAdminResponse = UsuarioAdminResponse
UsuarioResetPasswordAdminResponse = UsuarioAdminResponse
