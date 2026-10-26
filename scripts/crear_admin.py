#!/usr/bin/env python3
"""
Script de terminal para crear o restablecer un usuario con rol ADMIN.

Uso:
    python scripts/crear_admin.py
    python scripts/crear_admin.py --usuario admin --password 'ClaveSegura123!' --ci 1234567 --nombres 'Administrador' --apellido 'Sistema'
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

# Añadir carpeta backend al path de python
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import Rol, Usuario


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear o actualizar un usuario ADMIN en el LIS.")
    parser.add_argument("--usuario", "-u", help="Nombre de usuario (ej: admin)")
    parser.add_argument("--password", "-p", help="Contraseña del usuario")
    parser.add_argument("--ci", help="Cédula de identidad (ej: 1234567)")
    parser.add_argument("--nombres", help="Nombres del administrador", default="Administrador")
    parser.add_argument("--apellido", help="Primer apellido", default="Principal")
    parser.add_argument("--correo", help="Correo electrónico (opcional)")
    args = parser.parse_args()

    es_interactivo = sys.stdin.isatty() and not (args.usuario and args.password)

    usuario = args.usuario or (input("Nombre de usuario [admin]: ").strip() if es_interactivo else "admin") or "admin"
    ci = args.ci or (input(f"C.I. para {usuario} [1234567]: ").strip() if es_interactivo else "1234567") or "1234567"
    nombres = args.nombres or "Administrador"
    apellido = args.apellido or "Principal"
    correo = args.correo or (input("Correo (opcional): ").strip() if es_interactivo else None) or None

    password = args.password
    if not password:
        if es_interactivo:
            password = getpass.getpass("Contraseña para el administrador: ")
            confirmacion = getpass.getpass("Confirme la contraseña: ")
            if password != confirmacion:
                print("Error: Las contraseñas no coinciden.", file=sys.stderr)
                sys.exit(1)
        else:
            print("Error: Debe especificar --password cuando no se ejecuta interactivamente.", file=sys.stderr)
            sys.exit(1)

    if len(password) < 8:
        print("Error: La contraseña debe tener al menos 8 caracteres.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        rol_admin = db.query(Rol).filter(Rol.nombre == "ADMIN").first()
        if not rol_admin:
            print("Error: El rol ADMIN no existe en la base de datos.", file=sys.stderr)
            sys.exit(1)

        pass_hash = hash_password(password)

        # Verificar si el usuario ya existe para actualizarlo
        usuario_db = db.query(Usuario).filter(Usuario.usuario == usuario.lower().strip()).first()
        if usuario_db:
            print(f"El usuario '{usuario}' ya existe. Actualizando rol a ADMIN y restableciendo clave...")
            usuario_db.id_rol = rol_admin.id_rol
            usuario_db.hash_password = pass_hash
            usuario_db.activo = True
            usuario_db.debe_cambiar_password = False
            usuario_db.intentos_fallidos = 0
            usuario_db.bloqueado_hasta = None
            db.commit()
            print(f"✓ Usuario ADMIN '{usuario}' actualizado exitosamente.")
            return

        # Verificar CI duplicado
        ci_existente = db.query(Usuario).filter(Usuario.ci == ci.strip()).first()
        if ci_existente:
            print(f"Error: El CI '{ci}' ya pertenece al usuario '{ci_existente.usuario}'.", file=sys.stderr)
            sys.exit(1)

        nuevo_admin = Usuario(
            id_rol=rol_admin.id_rol,
            usuario=usuario.lower().strip(),
            ci=ci.strip(),
            nombres=nombres.strip(),
            apellido_paterno=apellido.strip(),
            correo=correo.strip() if correo else None,
            hash_password=pass_hash,
            debe_cambiar_password=False,
            intentos_fallidos=0,
            bloqueado_hasta=None,
            activo=True,
        )
        db.add(nuevo_admin)
        db.commit()
        print(f"✓ Usuario ADMIN '{usuario}' creado exitosamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
