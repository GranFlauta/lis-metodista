"""
Módulo de seguridad para el LIS Laboratorio Clínico (Fase 1).
Implementa:
- Hashing y verificación de contraseñas con Argon2id mediante pwdlib.
- Generación de contraseñas temporales seguras de exactamente 14 caracteres aleatorios.
- Validación de política de contraseñas según docs/DECISIONES.md:
  * Longitud entre 10 y 128 caracteres.
  * No contener nombre de usuario ni CI.
  * Distinta de la actual (verificación directa o por hash).
- Emisión y decodificación de JWT de acceso según configuración (config.access_token_minutes).
- Generación y hash SHA-256 de refresh tokens opacos para la tabla sesiones.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import settings

# Algoritmo estándar para JWT simétrico
JWT_ALGORITHM = "HS256"

# Parámetros de la política de contraseñas
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

# Instancia de hasher configurada explícitamente con Argon2id
password_hash = PasswordHash((Argon2Hasher(),))


# -----------------------------------------------------------------------------
# Excepciones de Seguridad
# -----------------------------------------------------------------------------

class SecurityError(Exception):
    """Excepción base para errores del módulo de seguridad."""
    pass


class PasswordPolicyError(SecurityError, ValueError):
    """Excepción lanzada cuando una contraseña viola la política de seguridad."""
    pass


class TokenError(SecurityError, ValueError):
    """Excepción base para errores relacionados con tokens JWT."""
    pass


class TokenExpiredError(TokenError, jwt.ExpiredSignatureError):
    """Excepción lanzada cuando el token JWT ha expirado."""
    pass


class TokenInvalidError(TokenError, jwt.InvalidTokenError):
    """Excepción lanzada cuando el token JWT es inválido, manipulado o malformado."""
    pass


# -----------------------------------------------------------------------------
# 1. Hashing y Verificación de Contraseñas (Argon2id con pwdlib)
# -----------------------------------------------------------------------------

def get_password_hash(password: str) -> str:
    """
    Genera un hash Argon2id a partir de una contraseña en texto plano utilizando pwdlib.
    """
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica de forma segura si la contraseña en texto plano coincide con el hash Argon2id.
    Retorna False si los valores están vacíos o si el hash es inválido o no reconocido.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return password_hash.verify(plain_password, hashed_password)
    except Exception:
        # Previene caídas no controladas por hashes corruptos o cadenas arbitrarias
        return False


# -----------------------------------------------------------------------------
# 2. Generación de Contraseñas Temporales
# -----------------------------------------------------------------------------

def generate_temporary_password(
    length: int = 14,
    username: str | None = None,
    ci: str | None = None,
) -> str:
    """
    Genera una contraseña temporal segura de exactamente `length` caracteres aleatorios
    (por defecto 14), con entropía criptográfica garantizada usando el módulo `secrets`.

    Garantiza la presencia de al menos una letra mayúscula, una minúscula, un dígito
    y un símbolo especial seguro. Además asegura que no colisione con el usuario o CI si se proporcionan.
    """
    if length < 10:
        raise ValueError("La longitud de la contraseña no puede ser inferior a 10 caracteres.")
    if length > 128:
        raise ValueError("La longitud de la contraseña no puede exceder los 128 caracteres.")

    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%*-_+?"
    all_chars = lower + upper + digits + symbols

    rng = secrets.SystemRandom()

    for _ in range(10):
        chars = [
            secrets.choice(lower),
            secrets.choice(upper),
            secrets.choice(digits),
            secrets.choice(symbols),
        ]
        chars.extend(secrets.choice(all_chars) for _ in range(length - len(chars)))
        rng.shuffle(chars)
        candidate = "".join(chars)

        is_valid, _ = check_password_policy(
            new_password=candidate,
            username=username,
            ci=ci,
        )
        if is_valid:
            return candidate

    return candidate


# -----------------------------------------------------------------------------
# 3. Validador de Política de Contraseñas
# -----------------------------------------------------------------------------

def check_password_policy(
    new_password: str,
    username: str | None = None,
    ci: str | None = None,
    current_password: str | None = None,
    current_password_hash: str | None = None,
) -> tuple[bool, str | None]:
    """
    Evalúa si la nueva contraseña cumple con la política de seguridad establecida:
    - Longitud entre 10 y 128 caracteres.
    - No contener el nombre de usuario (case-insensitive).
    - No contener el documento de identidad CI (case-insensitive ni alfanumérico).
    - Distinta de la actual (comparada contra texto plano o hash Argon2id).

    Retorna:
        (True, None) si es válida.
        (False, mensaje_error) si incumple alguna regla.
    """
    if not isinstance(new_password, str):
        return False, "La contraseña debe ser una cadena de texto."

    # 1. Regla de longitud
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return False, f"La contraseña debe contener al menos {MIN_PASSWORD_LENGTH} caracteres."
    if len(new_password) > MAX_PASSWORD_LENGTH:
        return False, f"La contraseña no puede exceder los {MAX_PASSWORD_LENGTH} caracteres."

    password_lower = new_password.lower()

    # 2. Regla: no contener el nombre de usuario
    if username:
        user_clean = username.strip().lower()
        if len(user_clean) >= 3 and user_clean in password_lower:
            return False, "La contraseña no puede contener el nombre de usuario."
        # Verificar partes del nombre de usuario si tiene separadores (. _ -)
        user_parts = [p for p in re.split(r"[\._\-\s]+", user_clean) if len(p) >= 3]
        for part in user_parts:
            if part in password_lower:
                return False, "La contraseña no puede contener el nombre de usuario."

    # 3. Regla: no contener el CI
    if ci:
        ci_clean = ci.strip().lower()
        if len(ci_clean) >= 3 and ci_clean in password_lower:
            return False, "La contraseña no puede contener el documento de identidad (CI)."

        # Verificar la secuencia solo de dígitos del CI (para cubrir extensiones como -LP o puntos)
        ci_digits = "".join(ch for ch in ci_clean if ch.isdigit())
        if len(ci_digits) >= 4 and ci_digits in password_lower:
            return False, "La contraseña no puede contener el número de CI."

        # Verificar la secuencia alfanumérica completa sin separadores
        ci_alnum = "".join(ch for ch in ci_clean if ch.isalnum())
        if len(ci_alnum) >= 4 and ci_alnum in password_lower:
            return False, "La contraseña no puede contener el número de CI."

    # 4. Regla: distinta de la actual
    if current_password is not None:
        if new_password == current_password:
            return False, "La nueva contraseña debe ser distinta de la contraseña actual."
        # Si current_password es un hash Argon2id
        if current_password.startswith(("$argon2id$", "$argon2i$", "$argon2d$")):
            if verify_password(new_password, current_password):
                return False, "La nueva contraseña debe ser distinta de la contraseña actual."

    if current_password_hash is not None:
        if verify_password(new_password, current_password_hash):
            return False, "La nueva contraseña debe ser distinta de la contraseña actual."

    return True, None


def validate_password_policy(
    new_password: str,
    username: str | None = None,
    ci: str | None = None,
    current_password: str | None = None,
    current_password_hash: str | None = None,
) -> bool:
    """
    Valida la política de contraseñas.
    Si la contraseña es válida retorna True.
    Si la contraseña viola la política, lanza PasswordPolicyError con el motivo específico.
    """
    is_valid, error_msg = check_password_policy(
        new_password=new_password,
        username=username,
        ci=ci,
        current_password=current_password,
        current_password_hash=current_password_hash,
    )
    if not is_valid:
        raise PasswordPolicyError(error_msg or "La contraseña no cumple con la política de seguridad.")
    return True


# -----------------------------------------------------------------------------
# 4. Tokens JWT de Acceso (Access Token)
# -----------------------------------------------------------------------------

def create_access_token(
    data: dict[str, Any] | None = None,
    subject: str | int | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Crea un token de acceso JWT codificado con el algoritmo HS256.

    Parámetros:
        data: Diccionario con claims adicionales (opcional).
        subject: Identificador del sujeto ('sub' claim). Puede ser el ID de usuario o login.
        expires_delta: Duración personalizada. Si no se especifica, toma `settings.access_token_minutes`.

    Retorna:
        Token JWT firmado en formato string.
    """
    to_encode: dict[str, Any] = {}
    if data:
        to_encode.update(data)

    if subject is not None:
        to_encode["sub"] = str(subject)

    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_minutes)

    to_encode["iat"] = int(now.timestamp())
    to_encode["exp"] = int(expire.timestamp())

    return jwt.encode(to_encode, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodifica y valida un token de acceso JWT.

    Verifica la firma con `settings.jwt_secret` y comprueba la expiración ('exp').

    Retorna:
        Diccionario con los claims del payload decodificado.

    Lanza:
        TokenExpiredError si el token ha expirado.
        TokenInvalidError si el token no es válido, tiene firma incorrecta o está corrupto.
    """
    if not token:
        raise TokenInvalidError("El token no puede estar vacío.")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("El token de acceso ha expirado.") from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalidError("El token de acceso no es válido o está malformado.") from exc


# -----------------------------------------------------------------------------
# 5. Refresh Tokens Opacos y Hash SHA-256 (Tabla sesiones)
# -----------------------------------------------------------------------------

def generate_opaque_token(nbytes: int = 32) -> str:
    """
    Genera un token opaco aleatorio criptográficamente seguro, codificado en base64 URL-safe.
    Con 32 bytes genera una cadena de 43 caracteres con 256 bits de entropía.
    """
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """
    Genera el hash SHA-256 en formato hexadecimal de 64 caracteres de un token opaco.
    Diseñado para almacenarse en la columna `sesiones.refresh_hash CHAR(64)`.
    """
    if not token:
        raise ValueError("El token no puede estar vacío.")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token(nbytes: int = 32) -> tuple[str, str]:
    """
    Genera un par (token_opaco, hash_sha256).

    El token opaco se entrega al cliente (en cookie HttpOnly segura),
    mientras que el hash se almacena en la base de datos (tabla sesiones).
    """
    raw_token = generate_opaque_token(nbytes)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash


def verify_refresh_token(raw_token: str, stored_hash: str) -> bool:
    """
    Compara en tiempo constante un refresh token en texto plano con el hash almacenado,
    previniendo ataques de temporización (timing attacks).
    """
    if not raw_token or not stored_hash:
        return False
    computed_hash = hash_token(raw_token)
    return hmac.compare_digest(computed_hash, stored_hash)


# -----------------------------------------------------------------------------
# Aliases para compatibilidad idiomática y convención de nombres
# -----------------------------------------------------------------------------
hash_password = get_password_hash
generar_password_temporal = generate_temporary_password
generar_contrasena_temporal = generate_temporary_password
validar_politica_password = validate_password_policy
verificar_politica_password = check_password_policy
crear_token_acceso = create_access_token
decodificar_token_acceso = decode_access_token
generar_token_opaco = generate_opaque_token
generar_refresh_token = generate_refresh_token
hash_refresh_token = hash_token
verificar_refresh_token = verify_refresh_token