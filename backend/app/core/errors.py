"""
Manejo estandarizado de errores del LIS Laboratorio Clínico.
docs/DECISIONES.md y PROMPT_FASE_1.md §6.1:
Todos los errores de la API devuelven el formato JSON:
{"codigo": "...", "mensaje": "..."}
"""

from __future__ import annotations

from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Excepción base para errores controlados de la API."""

    def __init__(
        self,
        status_code: int,
        codigo: str,
        mensaje: str,
        extra: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.codigo = codigo
        self.mensaje = mensaje
        self.extra = extra or {}
        self.headers = headers
        super().__init__(mensaje)

    def to_dict(self) -> dict[str, Any]:
        payload = {"codigo": self.codigo, "mensaje": self.mensaje}
        if self.extra:
            payload.update(self.extra)
        return payload


# --- Clases de Error Específicas por Código Clínico ---

class ValidacionError(AppError):
    def __init__(self, mensaje: str, extra: dict[str, Any] | None = None) -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, "VALIDACION", mensaje, extra)


class CredencialesInvalidasError(AppError):
    def __init__(self, mensaje: str = "Usuario o contraseña incorrectos") -> None:
        super().__init__(
            status.HTTP_401_UNAUTHORIZED,
            "CREDENCIALES_INVALIDAS",
            mensaje,
            headers={"WWW-Authenticate": "Bearer"},
        )


class SesionExpiradaError(AppError):
    def __init__(self, mensaje: str = "Sesión inválida o expirada.", headers: dict[str, str] | None = None) -> None:
        h = {"WWW-Authenticate": "Bearer"}
        if headers:
            h.update(headers)
        super().__init__(
            status.HTTP_401_UNAUTHORIZED,
            "SESION_EXPIRADA",
            mensaje,
            headers=h,
        )


class DebeCambiarPasswordError(AppError):
    def __init__(self, mensaje: str = "Debe cambiar su contraseña antes de continuar.") -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, "DEBE_CAMBIAR_PASSWORD", mensaje)


class ProhibidoError(AppError):
    def __init__(self, mensaje: str = "No posee permisos para realizar esta acción.") -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, "PROHIBIDO", mensaje)


class NoEncontradoError(AppError):
    def __init__(self, mensaje: str = "El recurso solicitado no fue encontrado.") -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "NO_ENCONTRADO", mensaje)


class ConflictoError(AppError):
    def __init__(self, mensaje: str = "Dato duplicado o en conflicto.") -> None:
        super().__init__(status.HTTP_409_CONFLICT, "CONFLICTO", mensaje)


class PasswordDebilError(AppError):
    def __init__(self, mensaje: str) -> None:
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, "PASSWORD_DEBIL", mensaje)


class CuentaBloqueadaError(AppError):
    def __init__(self, minutos_restantes: int, mensaje: str | None = None) -> None:
        msg = mensaje or f"Cuenta bloqueada por demasiados intentos. Espere {minutos_restantes} minuto(s)."
        super().__init__(
            status.HTTP_423_LOCKED,
            "CUENTA_BLOQUEADA",
            msg,
            extra={"minutos_restantes": minutos_restantes},
        )


def register_error_handlers(app: FastAPI) -> None:
    """Registra los manejadores de excepciones estándar en la instancia de FastAPI."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Convierte validaciones de Pydantic/FastAPI en 400 VALIDACION según §6.1
        errores = []
        for err in exc.errors():
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "")
            errores.append(f"{loc}: {msg}")
        mensaje = "; ".join(errores) if errores else "Datos mal formados."
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"codigo": "VALIDACION", "mensaje": mensaje},
        )
