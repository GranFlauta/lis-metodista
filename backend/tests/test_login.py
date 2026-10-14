"""
Pruebas obligatorias de Login, Bloqueo y Arranque (Tests 5–9 y 27 según PROMPT_FASE_1.md §10).
"""

from __future__ import annotations

import unittest
from datetime import timedelta

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.clock import ahora, set_simulated_time
from app.core.config import Settings
from app.main import app
from app.models.session import LogSeguridad, Sesion
from tests.base import IntegrationTestCase


class TestLoginYBloqueo(IntegrationTestCase):
    def test_05_login_correcto_devuelve_token_cookie_y_sesion(self) -> None:
        """5. Login correcto devuelve token, cookie httpOnly+SameSite=Strict+Path=/api/auth y crea sesión."""
        u = self.crear_usuario_test(usuario="operador", password="PasswordValido123!")

        resp = self.client.post("/api/auth/login", json={"usuario": "operador", "password": "PasswordValido123!"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertIn("expires_in", data)
        self.assertEqual(data["usuario"]["usuario"], "operador")

        # Verificar cookie de refresh
        cookie = resp.cookies.get("refresh_token")
        self.assertIsNotNone(cookie)

        raw_cookie = resp.headers.get("set-cookie", "").lower()
        self.assertIn("path=/api/auth", raw_cookie)
        self.assertIn("httponly", raw_cookie)
        self.assertIn("samesite=strict", raw_cookie)

        # Verificar sesión creada en base de datos
        sesion = self.db.query(Sesion).filter(Sesion.id_usuario == u.id_usuario).first()
        self.assertIsNotNone(sesion)
        self.assertIsNone(sesion.revocada_en)

    def test_06_usuario_inexistente_clave_erronea_e_inactivo_mismo_401(self) -> None:
        """6. Usuario inexistente, clave incorrecta y usuario inactivo → mismo 401 y mismo mensaje."""
        self.crear_usuario_test(usuario="activo", password="Password123!", activo=True)
        self.crear_usuario_test(usuario="inactivo", password="Password123!", activo=False)

        # 1. Inexistente
        r1 = self.client.post("/api/auth/login", json={"usuario": "fantasma", "password": "Password123!"})
        # 2. Clave incorrecta
        r2 = self.client.post("/api/auth/login", json={"usuario": "activo", "password": "ClaveEquivocada!"})
        # 3. Usuario inactivo
        r3 = self.client.post("/api/auth/login", json={"usuario": "inactivo", "password": "Password123!"})

        self.assertEqual(r1.status_code, 401)
        self.assertEqual(r2.status_code, 401)
        self.assertEqual(r3.status_code, 401)

        d1, d2, d3 = r1.json(), r2.json(), r3.json()
        self.assertEqual(d1["codigo"], "CREDENCIALES_INVALIDAS")
        self.assertEqual(d2["codigo"], "CREDENCIALES_INVALIDAS")
        self.assertEqual(d3["codigo"], "CREDENCIALES_INVALIDAS")

        self.assertEqual(d1["mensaje"], "Usuario o contraseña incorrectos")
        self.assertEqual(d2["mensaje"], "Usuario o contraseña incorrectos")
        self.assertEqual(d3["mensaje"], "Usuario o contraseña incorrectos")

    def test_07_bloqueo_por_cinco_fallos_y_desbloqueo_temporal(self) -> None:
        """7. 5 fallos seguidos → el 6.º intento da 423 con minutos_restantes; pasado LOCKOUT_MINUTES vuelve a funcionar."""
        self.crear_usuario_test(usuario="victima", password="PasswordSeguro123!")

        # 5 intentos fallidos
        for _ in range(5):
            r = self.client.post("/api/auth/login", json={"usuario": "victima", "password": "ClaveErronea!"})
            self.assertEqual(r.status_code, 401)

        # 6.º intento (incluso con la clave correcta) -> 423 CUENTA_BLOQUEADA
        r6 = self.client.post("/api/auth/login", json={"usuario": "victima", "password": "PasswordSeguro123!"})
        self.assertEqual(r6.status_code, 423)
        data6 = r6.json()
        self.assertEqual(data6["codigo"], "CUENTA_BLOQUEADA")
        self.assertIn("minutos_restantes", data6)
        self.assertGreaterEqual(data6["minutos_restantes"], 1)

        # Avanzar el reloj simulado 16 minutos (LOCKOUT_MINUTES = 15)
        tiempo_actual = ahora()
        set_simulated_time(tiempo_actual + timedelta(minutes=16))

        # El login debe volver a funcionar
        r_desbloqueado = self.client.post("/api/auth/login", json={"usuario": "victima", "password": "PasswordSeguro123!"})
        self.assertEqual(r_desbloqueado.status_code, 200)

    def test_08_login_correcto_reinicia_intentos_fallidos(self) -> None:
        """8. Login correcto reinicia intentos_fallidos."""
        u = self.crear_usuario_test(usuario="olvidadizo", password="PasswordSeguro123!")

        # 3 fallos
        for _ in range(3):
            self.client.post("/api/auth/login", json={"usuario": "olvidadizo", "password": "ClaveErronea!"})

        self.db.refresh(u)
        self.assertEqual(u.intentos_fallidos, 3)

        # Login exitoso
        r = self.client.post("/api/auth/login", json={"usuario": "olvidadizo", "password": "PasswordSeguro123!"})
        self.assertEqual(r.status_code, 200)

        self.db.refresh(u)
        self.assertEqual(u.intentos_fallidos, 0)
        self.assertIsNone(u.bloqueado_hasta)

    def test_09_registro_eventos_login_con_ip_y_sin_password(self) -> None:
        """9. Se registran LOGIN_OK y LOGIN_FALLIDO con IP; la contraseña no aparece en ningún registro."""
        self.crear_usuario_test(usuario="auditable", password="PasswordSeguro123!")

        # A4 / D35-01: la IP real la resuelve uvicorn (--proxy-headers, solo detrás de Caddy) y llega
        # en request.client. Se simula esa IP ya resuelta; la app NO debe confiar en X-Forwarded-For.
        cliente_lab = TestClient(app, client=("192.168.1.100", 50000))
        cabecera_falsa = {"X-Forwarded-For": "10.6.6.6"}

        # Fallido
        cliente_lab.post(
            "/api/auth/login",
            json={"usuario": "auditable", "password": "ClaveSecretaErronea!"},
            headers=cabecera_falsa,
        )
        # Exitoso
        cliente_lab.post(
            "/api/auth/login",
            json={"usuario": "auditable", "password": "PasswordSeguro123!"},
            headers=cabecera_falsa,
        )

        logs = self.db.query(LogSeguridad).order_by(LogSeguridad.id_log.asc()).all()
        acciones = [l.accion for l in logs]
        self.assertIn("LOGIN_FALLIDO", acciones)
        self.assertIn("LOGIN_OK", acciones)

        for l in logs:
            self.assertEqual(str(l.ip), "192.168.1.100")
            detalle_str = str(l.detalle or "")
            self.assertNotIn("ClaveSecretaErronea!", detalle_str)
            self.assertNotIn("PasswordSeguro123!", detalle_str)


class TestArranqueConfiguracion(unittest.TestCase):
    def test_27_arranque_rechaza_jwt_secret_inseguro(self) -> None:
        """27. La app no arranca con JWT_SECRET corto o que empiece por CAMBIAR."""
        # Secreto corto (< 32 caracteres)
        with self.assertRaises(ValidationError):
            Settings(
                database_url="postgresql+psycopg://user:pass@localhost:5432/db",
                jwt_secret="demasiado_corto",
            )

        # Secreto que empieza con CAMBIAR
        with self.assertRaises(ValidationError):
            Settings(
                database_url="postgresql+psycopg://user:pass@localhost:5432/db",
                jwt_secret="CAMBIAR_ESTE_SECRETO_POR_UNO_SEGURO_1234567890",
            )


class TestSuperficieDeRed(unittest.TestCase):
    """Fase 3.5 T1 (hallazgos A1, A2, A4; D35-01). No requieren base de datos."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_t1a_preflight_desde_origen_ajeno_sin_cabeceras_cors(self) -> None:
        """T1-a. OPTIONS con Origin ajeno a /api/auth/login no devuelve access-control-allow-origin."""
        resp = self.client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertNotIn("access-control-allow-origin", resp.headers)
        self.assertNotIn("access-control-allow-credentials", resp.headers)

    def test_t1b_docs_y_openapi_desactivados_por_defecto(self) -> None:
        """T1-b. GET /docs y GET /openapi.json responden 404 con la configuración por defecto."""
        self.assertEqual(self.client.get("/docs").status_code, 404)
        self.assertEqual(self.client.get("/openapi.json").status_code, 404)

    def test_t1c_raiz_no_sirve_frontend_ni_info_del_sistema(self) -> None:
        """T1-c. GET / no devuelve el frontend ni información del sistema."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 404)
        cuerpo = resp.text.lower()
        self.assertNotIn("<html", cuerpo)
        self.assertNotIn("sistema", cuerpo)
        self.assertNotIn("/docs", cuerpo)
        self.assertNotIn("/api/health", cuerpo)
