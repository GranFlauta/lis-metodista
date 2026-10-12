"""
Utilidades base para pruebas unitarias y de integración del sistema LIS.
PROMT_FASE_1.5_CERRAR.md §3 G1:
- Conexión a PostgreSQL real vía TEST_DATABASE_URL (sin saltarse pruebas con SkipTest).
- Captura estricta de sqlalchemy.exc.OperationalError.
- Verificación de integridad del esquema real (tablas y trigger trg_proteger_informe).
- Prohibición de Base.metadata.create_all (la BD se crea con scripts/crear_bd_test.sh).
- Manejo de reloj simulado a través de app.core.clock.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime
from typing import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import reset_clock, set_simulated_time
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.session import LogSeguridad, Sesion
from app.models.user import Rol, Usuario

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/lis_test"),
)

_connect_args = {}
if "postgresql" in TEST_DATABASE_URL:
    _connect_args["options"] = "-csearch_path=laboratorio,public"

test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class IntegrationTestCase(unittest.TestCase):
    """
    Clase base para pruebas de integración con PostgreSQL real.
    Falla explícitamente si la base de datos no está disponible o el esquema está incompleto.
    """

    db: Session
    client: TestClient

    @classmethod
    def setUpClass(cls) -> None:
        # 1. Comprobar conectividad con PostgreSQL real (solo capturando OperationalError)
        try:
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except OperationalError as exc:
            raise AssertionError(
                f"La base de datos de pruebas no responde en '{TEST_DATABASE_URL}': {exc}. "
                "Asegúrese de levantar la base de datos (ej. podman compose up -d db) "
                "y definir la variable TEST_DATABASE_URL correctamente."
            ) from exc

        # 2. Verificar que existan las tablas requeridas y el trigger en el esquema 'laboratorio'
        tablas_requeridas = {"usuarios", "sesiones", "log_seguridad", "informes", "folios"}
        with test_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'laboratorio'"
            ))
            tablas_existentes = {row[0] for row in result}
            faltantes = tablas_requeridas - tablas_existentes
            if faltantes:
                raise AssertionError(
                    f"Esquema de BD incompleto en 'laboratorio'. Faltan las tablas: {sorted(faltantes)}. "
                    "Ejecute 'scripts/crear_bd_test.sh' para recrear la BD de pruebas con el esquema oficial."
                )

            res_trg = conn.execute(text(
                "SELECT 1 FROM information_schema.triggers "
                "WHERE trigger_schema = 'laboratorio' AND trigger_name = 'trg_proteger_informe'"
            )).first()
            if not res_trg:
                raise AssertionError(
                    "No se encontró el trigger 'trg_proteger_informe' en el esquema 'laboratorio'. "
                    "Ejecute 'scripts/crear_bd_test.sh' para aplicar 001_schema.sql en la BD de pruebas."
                )

        # 3. Sembrar roles básicos si no existen
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
