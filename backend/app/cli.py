"""
Herramienta de línea de comandos (CLI) para inicialización y administración del LIS.
Implementa el comando 'crear-admin' según PROMPT_FASE_1.md §13:
python -m app.cli crear-admin [--forzar]
"""

from __future__ import annotations

import argparse
import re
import sys

from sqlalchemy import func

from app.core.clock import ahora
from app.core.database import SessionLocal
from app.core.security import generate_temporary_password, get_password_hash
from app.models.session import LogSeguridad
from app.models.user import Rol, Usuario


def crear_admin(forzar: bool = False) -> None:
    """
    Crea el primer usuario con rol ADMIN solicitando los datos por consola interactiva.
    Genera e imprime una contraseña temporal de 14 caracteres una sola vez.
    """
    db = SessionLocal()
    try:
        # 1. Comprobar si ya existe un ADMIN activo (§13)
        admin_activo = (
            db.query(Usuario)
            .join(Rol)
            .filter(Rol.nombre == "ADMIN", Usuario.activo == True)
            .first()
        )
        if admin_activo and not forzar:
            print(
                f"\n[ERROR] Ya existe un usuario ADMIN activo en el sistema ('{admin_activo.usuario}').\n"
                "Para forzar la creación de un administrador adicional, ejecute:\n"
                "  python -m app.cli crear-admin --forzar\n"
            )
            sys.exit(1)

        print("\n=== Creación de Usuario Administrador (LIS) ===")

        # 2. Solicitar datos de entrada por consola
        while True:
            usuario = input("Usuario (login) [ej: admin]: ").strip().lower()
            if re.match(r"^[a-z0-9._-]{3,40}$", usuario):
                existente = db.query(Usuario).filter(func.lower(Usuario.usuario) == usuario).first()
                if existente:
                    print(f"El usuario '{usuario}' ya existe. Elija otro.")
                    continue
                break
            print("El usuario debe tener entre 3 y 40 caracteres (letras minúsculas, números, '.', '-' o '_').")

        while True:
            ci = input("Cédula de Identidad (CI): ").strip()
            if 5 <= len(ci) <= 30:
                existente_ci = db.query(Usuario).filter(func.lower(Usuario.ci) == ci.lower()).first()
                if existente_ci:
                    print(f"El CI '{ci}' ya se encuentra registrado.")
                    continue
                break
            print("El CI debe tener entre 5 y 30 caracteres.")

        while True:
            nombres = input("Nombres: ").strip()
            if len(nombres) >= 2:
                break
            print("Los nombres deben tener al menos 2 caracteres.")

        while True:
            apellido_paterno = input("Primer apellido: ").strip()
            if len(apellido_paterno) >= 2:
                break
            print("El primer apellido debe tener al menos 2 caracteres.")

        apellido_materno = input("Segundo apellido (opcional, Enter para omitir): ").strip() or None
        correo = input("Correo electrónico (opcional, Enter para omitir): ").strip() or None
        matricula = input("Matrícula profesional (opcional, Enter para omitir): ").strip() or None

        # 3. Obtener rol ADMIN
        rol_admin = db.query(Rol).filter(func.upper(Rol.nombre) == "ADMIN").first()
        if not rol_admin:
            # Crear rol ADMIN si por alguna razón no existiese en la BD
            rol_admin = Rol(nombre="ADMIN", descripcion="Administrador del sistema LIS")
            db.add(rol_admin)
            db.flush()

        # 4. Generar contraseña temporal segura de 14 caracteres sin ambiguos (§5)
        temp_password = generate_temporary_password(
            length=14,
            username=usuario,
            ci=ci,
        )
        hash_pass = get_password_hash(temp_password)

        # 5. Crear usuario con debe_cambiar_password = TRUE
        nuevo_admin = Usuario(
            id_rol=rol_admin.id_rol,
            usuario=usuario,
            ci=ci,
            nombres=nombres,
            apellido_paterno=apellido_paterno,
            apellido_materno=apellido_materno,
            correo=correo,
            matricula_profesional=matricula,
            hash_password=hash_pass,
            debe_cambiar_password=True,
            intentos_fallidos=0,
            bloqueado_hasta=None,
            activo=True,
        )
        db.add(nuevo_admin)
        db.flush()

        # 6. Registrar evento en log_seguridad
        log_event = LogSeguridad(
            id_usuario=nuevo_admin.id_usuario,
            id_objetivo=nuevo_admin.id_usuario,
            accion="USUARIO_CREADO",
            ip=None,
            detalle={"origen": "cli", "comando": "crear-admin"},
            creado_en=ahora(),
        )
        db.add(log_event)
        db.commit()

        # 7. Imprimir salida con la contraseña temporal por única vez
        print("\n" + "=" * 60)
        print(" [OK] Usuario Administrador creado exitosamente")
        print("=" * 60)
        print(f" ID de usuario:       {nuevo_admin.id_usuario}")
        print(f" Usuario (login):     {nuevo_admin.usuario}")
        print(f" Rol:                 ADMIN")
        print(f" Contraseña temporal: {temp_password}")
        print("-" * 60)
        print(" IMPORTANTE: Guarde o copie esta contraseña temporal ahora.")
        print(" Se muestra UNA SOLA VEZ y se exigirá cambiarla al iniciar sesión.")
        print("=" * 60 + "\n")

    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Utilidades de consola del sistema LIS Laboratorio Clínico.",
    )
    subparsers = parser.add_subparsers(dest="subcomando", required=True)

    # Subcomando crear-admin
    parser_admin = subparsers.add_parser(
        "crear-admin",
        help="Crea un usuario administrador inicial con contraseña temporal.",
    )
    parser_admin.add_argument(
        "--forzar",
        action="store_true",
        help="Permite crear un administrador aunque ya exista uno activo.",
    )

    args = parser.parse_args()

    if args.subcomando == "crear-admin":
        crear_admin(forzar=args.forzar)


if __name__ == "__main__":
    main()
