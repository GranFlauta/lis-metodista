"""
Esquemas Pydantic para el módulo de Autenticación y Seguridad (Fase 1).
Basado estrictamente en docs/DECISIONES.md y el esquema de base de datos.

Incluye:
1. Esquema de Login (credenciales de acceso).
2. Esquema para cambio de contraseña obligatorio (flujo primer inicio / reset).
3. Esquemas de respuesta para token JWT de acceso y datos del usuario autenticado.
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
# 2. Esquema para Cambio de Contraseña Obligatorio
# -----------------------------------------------------------------------------

class CambioPasswordRequest(BaseModel):
    """
    Datos para el cambio obligatorio de contraseña (nuevo usuario o reset por admin)
    o cambio voluntario. Valida la diferencia entre la clave actual y la nueva.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    password_actual: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Contraseña actual o temporal asignada.",
    )
    password_nuevo: str = Field(
        ...,
        min_length=10,
        max_length=128,
        description="Nueva contraseña (debe cumplir longitud 10-128 caracteres y política de seguridad).",
    )
    confirmar_password: str | None = Field(
        default=None,
        description="Confirmación opcional de la nueva contraseña para validación de formularios.",
    )

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

class UsuarioResponse(BaseModel):
    """
    Información pública del usuario autenticado (sin contraseñas ni datos sensibles).
    """
    model_config = ConfigDict(from_attributes=True)

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
        """
        Permite extraer el nombre del rol directamente desde el modelo SQLAlchemy Rol
        o recibirlo como cadena de texto.
        """
        if hasattr(value, "nombre"):
            return str(value.nombre)
        if isinstance(value, str):
            return value
        return str(value)

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
    Respuesta exitosa de autenticación con token JWT de acceso.
    El refresh token opaco viaja exclusivamente en cookie HttpOnly/Secure/SameSite=Strict.
    """
    access_token: str = Field(..., description="Token de acceso JWT firmado.")
    token_type: str = Field(default="bearer", description="Tipo de autorización HTTP (Bearer).")
    expires_in: int = Field(..., description="Tiempo de vigencia del token de acceso en segundos.")
    debe_cambiar_password: bool = Field(
        ...,
        description="Informa al cliente si debe forzar la redirección a la pantalla de cambio de clave.",
    )
    usuario: UsuarioResponse = Field(..., description="Detalles del usuario autenticado.")


# -----------------------------------------------------------------------------
# 4. Esquema de Respuesta Administrativa (Creación y Reseteo)
# -----------------------------------------------------------------------------

class UsuarioAdminResponse(BaseModel):
    """
    Respuesta para el Administrador tras registrar un usuario nuevo o ejecutar un reset de clave.
    Devuelve la contraseña temporal generada aleatoriamente de exactamente 14 caracteres en texto plano
    para ser comunicada al usuario por única vez (DECISIONES.md §6).
    """
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int = Field(..., description="Identificador único del usuario.")
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
        if isinstance(value, str):
            return value
        return str(value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def nombre_completo(self) -> str:
        partes = [self.nombres, self.apellido_paterno]
        if self.apellido_materno:
            partes.append(self.apellido_materno)
        return " ".join(partes)


# -----------------------------------------------------------------------------
# Aliases para compatibilidad idiomática
# -----------------------------------------------------------------------------
LoginSchema = LoginRequest
PasswordChangeRequest = CambioPasswordRequest
UsuarioInfoResponse = UsuarioResponse
UsuarioCreadoAdminResponse = UsuarioAdminResponse
UsuarioResetPasswordAdminResponse = UsuarioAdminResponse
