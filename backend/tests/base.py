"""
Utilidades base para pruebas unitarias y de integración del sistema LIS.
PROMPT_FASE_1.md §10:
- Soporte para PostgreSQL real vía TEST_DATABASE_URL.
- Manejo de reloj simulado a través de app.core.clock.
- Fixtures de limpieza de datos e inicialización de roles.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime
from typing import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import reset_clock, set_simulated_time
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.session import LogSeguridad, Sesion
from app.models.user import Rol, Usuario

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/lis_test"),
)

test_engine = None
TestingSessionLocal = None
POSTGRES_DISPONIBLE = False

try:
    _connect_args = {}
    if "postgresql" in TEST_DATABASE_URL:
        _connect_args["options"] = "-csearch_path=laboratorio,public"

    _engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
        connect_args=_connect_args,
    )
    with _engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    test_engine = _engine
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    POSTGRES_DISPONIBLE = True
except Exception:
    POSTGRES_DISPONIBLE = False


class IntegrationTestCase(unittest.TestCase):
    """
    Clase base para pruebas de integración con PostgreSQL real.
    Si la base de datos no está disponible, omite los tests con un mensaje claro.
    """

    db: Session
    client: TestClient

    @classmethod
    def setUpClass(cls) -> None:
        if not POSTGRES_DISPONIBLE:
            raise unittest.SkipTest(
                "PostgreSQL de prueba no disponible. "
                "Para ejecutar tests de integración levante la base de datos (ej. docker compose up -d db) "
                "o defina TEST_DATABASE_URL."
            )

        # Asegurar esquema y tablas en la BD de prueba
        with test_engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS laboratorio"))
            conn.commit()
        Base.metadata.create_all(bind=test_engine)

        # Sembrar roles básicos si no existen
        with TestingSessionLocal() as session:
            admin_rol = session.query(Rol).filter(Rol.nombre == "ADMIN").first()
            if not admin_rol:
                session.add(Rol(nombre="ADMIN", descripcion="Administrador"))
            bio_rol = session.query(Rol).filter(Rol.nombre == "BIOQUIMICO").first()
            if not bio_rol:
                session.add(Rol(nombre="BIOQUIMICO", descripcion="Bioquímico"))
            session.commit()

    def setUp(self) -> None:
        reset_clock()
        self.db = TestingSessionLocal()

        # Limpiar datos transaccionales entre pruebas
        self.db.query(LogSeguridad).delete()
        self.db.query(Sesion).delete()
        self.db.query(Usuario).delete()
        self.db.commit()

        def override_get_db() -> Generator[Session, None, None]:
            db_session = TestingSessionLocal()
            try:
                yield db_session
            finally:
                db_session.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.db.close()
        app.dependency_overrides.clear()
        reset_clock()

    def crear_usuario_test(
        self,
        usuario: str = "admin",
        password: str = "ClaveSegura123!",
        rol: str = "ADMIN",
        ci: str | None = None,
        activo: bool = True,
        debe_cambiar_password: bool = False,
    ) -> Usuario:
        """Crea un usuario para escenarios de test."""
        import secrets
        ci_val = ci if ci is not None else f"CI{secrets.token_hex(4)}"
        rol_db = self.db.query(Rol).filter(Rol.nombre == rol).first()
        if not rol_db:
            rol_db = Rol(nombre=rol, descripcion=rol)
            self.db.add(rol_db)
            self.db.commit()

        u = Usuario(
            usuario=usuario,
            ci=ci_val,
            nombres="Test",
            apellido_paterno="Usuario",
            id_rol=rol_db.id_rol,
            hash_password=get_password_hash(password),
            activo=activo,
            debe_cambiar_password=debe_cambiar_password,
            intentos_fallidos=0,
            bloqueado_hasta=None,
        )
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        return u
