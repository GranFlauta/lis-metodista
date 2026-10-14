"""
Módulo de seguridad para el LIS Laboratorio Clínico (Fase 1).
Implementa estrictamente docs/DECISIONES.md y PROMPT_FASE_1.md §5:
- Hashing y verificación de contraseñas con Argon2id mediante pwdlib.
- Generación de contraseñas temporales seguras de 14 caracteres aleatorios sin caracteres ambiguos (0 O 1 l I).
- Validación de política de contraseñas:
  * Longitud entre 10 y 128 caracteres.
  * No contener nombre de usuario ni CI.
  * No pertenecer a la lista cerrada de contraseñas prohibidas (§6.4).
  * Distinta de la actual.
- Emisión y decodificación de JWT de acceso según configuración y claims estándar:
  sub, sid, rol, iat, exp, typ="access".
- Reloj centralizado mediante app.core.clock.ahora().
- Generación y hash SHA-256 de refresh tokens opacos para la tabla sesiones.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import string
from datetime import timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.exceptions import UnknownHashError, PwdlibError
from argon2.exceptions import InvalidHash, InvalidHashError, VerifyMismatchError

from app.core.clock import ahora
from app.core.config import settings

# Algoritmo estándar para JWT simétrico
JWT_ALGORITHM = "HS256"

# Parámetros de la política de contraseñas
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

# Lista cerrada de contraseñas prohibidas (PROMPT_FASE_1.md §6.4 - 21 entradas)
CLAVES_PROHIBIDAS = frozenset({
    "12345", "123456", "1234567", "12345678", "123456789", "1234567890",
    "0123456789", "password", "contraseña", "contrasena", "qwerty", "qwertyuiop",
    "abcdef", "abcd1234", "admin", "admin123", "administrador", "lis123",
    "laboratorio", "urgenlab", "bioquimico",
})

# Instancia de hasher configurada explícitamente con Argon2id
password_hash = PasswordHash((Argon2Hasher(),))

# Hash ficticio generado al importar el módulo para mitigar ataques de temporización (timing attack) en login (§6.2, G5)
DUMMY_ARGON2_HASH = password_hash.hash(secrets.token_urlsafe(16))


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
    Acota excepciones a UnknownHashError e InvalidHashError para no silenciar errores inesperados (G5).
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return password_hash.verify(plain_password, hashed_password)
    except (UnknownHashError, InvalidHash, InvalidHashError, ValueError):
        return False


def verify_dummy_password(plain_password: str = "dummy_clinical_attempt") -> None:
    """
    Ejecuta una verificación contra un hash Argon2id precalculado para igualar
    los tiempos de respuesta ante usuarios no existentes (§6.2).
    """
    verify_password(plain_password, DUMMY_ARGON2_HASH)


# -----------------------------------------------------------------------------
# 2. Generación de Contraseñas Temporales
# -----------------------------------------------------------------------------

def generate_temporary_password(
    length: int = 14,
    username: str | None = None,
    ci: str | None = None,
) -> str:
    """
    Genera una contraseña temporal segura de exactamente `length` caracteres aleatorios (por defecto 14).
    PROMPT_FASE_1.md §5: alfabeto sin caracteres ambiguos (0 O 1 l I).
    Si tras los intentos ninguna candidata cumple la política, lanza excepción (G5).
    """
    if length < 10:
        raise ValueError("La longitud de la contraseña no puede ser inferior a 10 caracteres.")
    if length > 128:
        raise ValueError("La longitud de la contraseña no puede exceder los 128 caracteres.")

    # Alfabeto sin caracteres ambiguos (0, O, 1, l, I)
    lower = "".join(c for c in string.ascii_lowercase if c not in "l")
    upper = "".join(c for c in string.ascii_uppercase if c not in "OI")
    digits = "".join(c for c in string.digits if c not in "01")
    symbols = "!@#$%*-_+?"
    all_chars = lower + upper + digits + symbols

    rng = secrets.SystemRandom()

    for _ in range(20):
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

    raise PasswordPolicyError("No fue posible generar una contraseña temporal válida tras múltiples intentos.")



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
    - No pertenecer a la lista de contraseñas prohibidas (§6.4) ni contener patrones prohibidos >= 8 caracteres.
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

    # 2. Regla: lista de contraseñas prohibidas (§6.4)
    if password_lower in CLAVES_PROHIBIDAS:
        return False, "La contraseña elegida es demasiado común y no está permitida."

    for patron in CLAVES_PROHIBIDAS:
        if len(patron) >= 8 and patron in password_lower:
            return False, "La contraseña elegida contiene un término común no permitido."

    # 3. Regla: no contener el nombre de usuario
    if username:
        user_clean = username.strip().lower()
        if len(user_clean) >= 3 and user_clean in password_lower:
            return False, "La contraseña no puede contener el nombre de usuario."
        # Verificar partes del nombre de usuario si tiene separadores (. _ -)
        user_parts = [p for p in re.split(r"[\._\-\s]+", user_clean) if len(p) >= 3]
        for part in user_parts:
            if part in password_lower:
                return False, "La contraseña no puede contener el nombre de usuario."

    # 4. Regla: no contener el CI
    if ci:
        ci_clean = ci.strip().lower()
        if len(ci_clean) >= 3 and ci_clean in password_lower:
            return False, "La contraseña no puede contener el documento de identidad (CI)."

        # Verificar secuencia de dígitos del CI (para cubrir extensiones como -LP o puntos)
        ci_digits = "".join(ch for ch in ci_clean if ch.isdigit())
        if len(ci_digits) >= 4 and ci_digits in password_lower:
            return False, "La contraseña no puede contener el número de CI."

        # Verificar secuencia alfanumérica completa sin separadores
        ci_alnum = "".join(ch for ch in ci_clean if ch.isalnum())
        if len(ci_alnum) >= 4 and ci_alnum in password_lower:
            return False, "La contraseña no puede contener el número de CI."

    # 5. Regla: distinta de la actual
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
    session_id: str | None = None,
    role: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Crea un token de acceso JWT codificado con el algoritmo HS256.
    Claims (§5): sub, sid, rol, iat, exp, typ="access".
    """
    to_encode: dict[str, Any] = {}
    if data:
        to_encode.update(data)

    if subject is not None:
        to_encode["sub"] = str(subject)

    if session_id is not None and "sid" not in to_encode:
        to_encode["sid"] = str(session_id)

    if role is not None and "rol" not in to_encode:
        to_encode["rol"] = str(role)

    to_encode["typ"] = "access"

    now = ahora()
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
    Verifica firma con settings.jwt_secret y comprueba expiración usando ahora().
    """
    if not token:
        raise TokenInvalidError("El token no puede estar vacío.")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False},
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalidError("El token de acceso no es válido o está malformado.") from exc

    exp = payload.get("exp")
    if exp is not None and ahora().timestamp() > exp:
        raise TokenExpiredError("El token de acceso ha expirado.")

    return payload


# -----------------------------------------------------------------------------
# 5. Refresh Tokens Opacos y Hash SHA-256 (Tabla sesiones)
# -----------------------------------------------------------------------------

def generate_opaque_token(nbytes: int = 32) -> str:
    """
    Genera un token opaco aleatorio criptográficamente seguro de 256 bits (32 bytes).
    """
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """
    Genera el hash SHA-256 en formato hexadecimal de 64 caracteres de un token opaco.
    """
    if not token:
        raise ValueError("El token no puede estar vacío.")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token(nbytes: int = 32) -> tuple[str, str]:
    """
    Genera un par (token_opaco, hash_sha256).
    """
    raw_token = generate_opaque_token(nbytes)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash


def verify_refresh_token(raw_token: str, stored_hash: str) -> bool:
    """
    Compara en tiempo constante un refresh token en texto plano con el hash almacenado.
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