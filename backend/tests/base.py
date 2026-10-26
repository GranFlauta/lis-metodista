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
from datetime import date, datetime
from typing import Any, Generator

from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import reset_clock, set_simulated_time
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.order import BorradorDescartado, Orden, OrdenEstudio, OrdenEstudioGrupo
from app.models.result import ResultadoBorrador
from app.models.patient import Paciente
from app.models.session import LogSeguridad, Sesion
from app.models.user import Rol, Usuario
from app.services.sesion_config_service import invalidar_cache_config_sesion


def validar_database_url_test(url: str | None) -> str:
    """
    Valida que TEST_DATABASE_URL esté definida y que el nombre de la base de datos
    termine estrictamente en '_test' para evitar el borrado accidental de datos reales (D35-04 / A3).
    Si no está definida o no cumple, aborta con ValueError explicando cómo definirla.
    """
    if not url or not url.strip():
        raise ValueError(
            "TEST_DATABASE_URL no está definida. Defina la variable de entorno para ejecutar pruebas con base de datos, "
            "por ejemplo: export TEST_DATABASE_URL='postgresql+psycopg://lis_app:<PASSWORD>@127.0.0.1:5432/lis_test'"
        )

    url_limpia = url.strip()
    parsed = urlsplit(url_limpia)
    db_name = parsed.path.lstrip("/").split("?")[0].split("/")[0].strip()

    if not db_name or not db_name.endswith("_test"):
        raise ValueError(
            f"Guarda de seguridad de pruebas (D35-04 / A3): La base de datos de pruebas debe terminar en '_test' "
            f"para evitar el borrado accidental de datos reales. Base detectada: '{db_name or '(vacía)'}' en '{url_limpia}'."
        )

    return url_limpia


_test_database_url: str | None = None
_test_engine = None
_TestingSessionLocal = None


def get_test_database_url() -> str:
    """Obtiene y valida la URL de la base de datos de prueba desde TEST_DATABASE_URL."""
    global _test_database_url
    if _test_database_url is None:
        _test_database_url = validar_database_url_test(os.environ.get("TEST_DATABASE_URL"))
    return _test_database_url


def get_test_engine():
    """Obtiene o inicializa el motor de base de datos de pruebas."""
    global _test_engine
    if _test_engine is None:
        url = get_test_database_url()
        connect_args = {}
        if "postgresql" in url:
            connect_args["options"] = "-csearch_path=laboratorio,public"
        _test_engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    return _test_engine


def get_testing_session_local():
    """Obtiene o inicializa la fábrica de sesiones para pruebas."""
    global _TestingSessionLocal
    if _TestingSessionLocal is None:
        _TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_test_engine())
    return _TestingSessionLocal


def __getattr__(name: str) -> Any:
    if name == "test_engine":
        return get_test_engine()
    if name == "TestingSessionLocal":
        return get_testing_session_local()
    if name == "TEST_DATABASE_URL":
        return get_test_database_url()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


class IntegrationTestCase(unittest.TestCase):
    """
    Clase base para pruebas de integración con PostgreSQL real.
    Falla explícitamente si la base de datos no está disponible o el esquema está incompleto.
    """

    db: Session
    client: TestClient

    @classmethod
    def setUpClass(cls) -> None:
        engine = get_test_engine()
        session_factory = get_testing_session_local()

        # 1. Comprobar conectividad con PostgreSQL real (solo capturando OperationalError)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except OperationalError as exc:
            url = get_test_database_url()
            raise AssertionError(
                f"La base de datos de pruebas no responde en '{url}': {exc}. "
                "Asegúrese de levantar la base de datos (ej. podman compose up -d db) "
                "y definir la variable TEST_DATABASE_URL correctamente."
            ) from exc

        # 2. Verificar que existan las tablas requeridas y el trigger en el esquema 'laboratorio'
        tablas_requeridas = {"usuarios", "sesiones", "log_seguridad", "informes", "folios"}
        with engine.connect() as conn:
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

            # Verificar las 4 claves de configuración de sesión (D35-02 / T4)
            claves_sesion_requeridas = {
                "sesion_intervalo_latido_seg",
                "sesion_muerta_tras_seg",
                "sesion_inactividad_min",
                "sesion_tope_absoluto_horas",
            }
            res_cfg = conn.execute(text(
                "SELECT clave FROM laboratorio.laboratorio_config WHERE clave LIKE 'sesion_%'"
            ))
            claves_existentes = {row[0] for row in res_cfg}
            claves_faltantes = claves_sesion_requeridas - claves_existentes
            if claves_faltantes:
                raise AssertionError(
                    f"Faltan claves de configuración de sesión en 'laboratorio_config': {sorted(claves_faltantes)}. "
                    "Ejecute 'alembic upgrade head' en la BD de pruebas (migración 0002_config_sesion)."
                )

        # 4. Sembrar roles básicos si no existen
        with session_factory() as session:
            admin_rol = session.query(Rol).filter(Rol.nombre == "ADMIN").first()
            if not admin_rol:
                session.add(Rol(nombre="ADMIN", descripcion="Administrador"))
            bio_rol = session.query(Rol).filter(Rol.nombre == "BIOQUIMICO").first()
            if not bio_rol:
                session.add(Rol(nombre="BIOQUIMICO", descripcion="Bioquímico"))
            session.commit()

    def setUp(self) -> None:
        reset_clock()
        session_factory = get_testing_session_local()
        self.db = session_factory()

        # Limpiar datos transaccionales entre pruebas en orden estricto de dependencias
        self.db.execute(text("SET session_replication_role = 'replica'"))
        self.db.execute(text("DELETE FROM laboratorio.informe_eventos"))
        self.db.execute(text("DELETE FROM laboratorio.ediciones_informe"))
        self.db.execute(text("DELETE FROM laboratorio.colaboracion_cambios"))
        self.db.execute(text("DELETE FROM laboratorio.delegaciones"))
        self.db.execute(text("DELETE FROM laboratorio.informes"))
        self.db.execute(text("DELETE FROM laboratorio.folios"))
        self.db.execute(text("SET session_replication_role = 'origin'"))
        self.db.query(BorradorDescartado).delete()
        self.db.query(ResultadoBorrador).delete()
        self.db.query(OrdenEstudioGrupo).delete()
        self.db.query(OrdenEstudio).delete()
        self.db.query(Orden).delete()
        self.db.query(Paciente).delete()
        self.db.query(LogSeguridad).delete()
        self.db.query(Sesion).delete()
        self.db.query(Usuario).delete()

        # Resetear configuración de sesión por defecto y su caché (D35-02 / T4 / T5)
        self.db.execute(text("""
            INSERT INTO laboratorio.laboratorio_config (clave, valor)
            VALUES 
                ('sesion_intervalo_latido_seg', '30'),
                ('sesion_muerta_tras_seg', '150'),
                ('sesion_inactividad_min', '30'),
                ('sesion_tope_absoluto_horas', '12')
            ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor
        """))
        self.db.commit()
        invalidar_cache_config_sesion()

        def override_get_db() -> Generator[Session, None, None]:
            db_session = session_factory()
            try:
                yield db_session
            finally:
                db_session.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        invalidar_cache_config_sesion()
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

    def crear_paciente_test(
        self,
        ci: str | None = "1000001",
        ci_complemento: str | None = None,
        sin_ci: bool = False,
        nombres: str = "Paciente",
        apellido_paterno: str = "Prueba",
        apellido_materno: str | None = "Clinico",
        fecha_nacimiento: Any | None = None,
        sexo: str = "M",
        telefono: str | None = "71234567",
        creado_por: int | None = None,
    ) -> Paciente:
        """Crea un paciente ficticio para pruebas."""
        import secrets
        from app.core.clock import ahora

        if creado_por is None:
            u = self.crear_usuario_test(usuario=f"bio_{secrets.token_hex(4)}", rol="BIOQUIMICO")
            creado_por = u.id_usuario

        p = Paciente(
            ci=ci,
            ci_complemento=ci_complemento,
            sin_ci=sin_ci,
            nombres=nombres,
            apellido_paterno=apellido_paterno,
            apellido_materno=apellido_materno,
            fecha_nacimiento=fecha_nacimiento,
            sexo=sexo,
            telefono=telefono,
            creado_por=creado_por,
            creado_en=ahora(),
            actualizado_en=ahora(),
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return p
