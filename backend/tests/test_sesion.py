"""
Pruebas obligatorias de Ciclo de Vida de Sesión (Tests 10–18 según PROMPT_FASE_1.md §10).
"""

from __future__ import annotations

from datetime import timedelta

from app.core.clock import ahora, set_simulated_time
from app.models.session import LogSeguridad, Sesion
from tests.base import IntegrationTestCase


class TestCicloVidaSesion(IntegrationTestCase):
    def test_10_sesion_muere_sin_latido_tras_150_segundos(self) -> None:
        """10. Sesión muere con SESSION_DEAD_AFTER_SECONDS sin latido (401 SESION_EXPIRADA) y queda revocada."""
        self.crear_usuario_test(usuario="medico", password="PasswordSeguro123!")
        login_resp = self.client.post("/api/auth/login", json={"usuario": "medico", "password": "PasswordSeguro123!"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Comprobar llamada normal viva
        r_inicial = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(r_inicial.status_code, 200)

        # Avanzar el reloj 151 segundos (sin latido)
        set_simulated_time(ahora() + timedelta(seconds=151))

        # La sesión debe estar muerta
        r_muerta = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(r_muerta.status_code, 401)
        self.assertEqual(r_muerta.json()["codigo"], "SESION_EXPIRADA")

        # Comprobar que en base de datos quedó revocada y se registró evento SESION_EXPIRADA
        sesion = self.db.query(Sesion).first()
        self.assertIsNotNone(sesion.revocada_en)

        evento = self.db.query(LogSeguridad).filter(LogSeguridad.accion == "SESION_EXPIRADA").first()
        self.assertIsNotNone(evento)

    def test_11_con_latidos_pero_sin_actividad_muere_por_idle_timeout(self) -> None:
        """11. Con latidos pero sin actividad durante IDLE_TIMEOUT_MINUTES → muere (el latido no cuenta como actividad)."""
        self.crear_usuario_test(usuario="bioq", password="PasswordSeguro123!")
        login_resp = self.client.post("/api/auth/login", json={"usuario": "bioq", "password": "PasswordSeguro123!"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Simular latidos periódicos cada 25 segundos durante 31 minutos
        t0 = ahora()
        for i in range(1, 75):  # 75 * 25s = 1875s (> 30 min)
            t_latido = t0 + timedelta(seconds=i * 25)
            set_simulated_time(t_latido)
            r_beat = self.client.post("/api/auth/heartbeat", headers=headers)
            if t_latido - t0 > timedelta(minutes=30):
                # Tras 30 min sin actividad, el heartbeat u otra llamada debe fallar
                break

        # Cualquier petición normal debe recibir 401 SESION_EXPIRADA
        r_act = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(r_act.status_code, 401)
        self.assertEqual(r_act.json()["codigo"], "SESION_EXPIRADA")

    def test_12_peticion_normal_renueva_actividad_pero_latido_no(self) -> None:
        """12. Una petición normal renueva ultima_actividad; el latido no."""
        self.crear_usuario_test(usuario="operador", password="PasswordSeguro123!")
        login_resp = self.client.post("/api/auth/login", json={"usuario": "operador", "password": "PasswordSeguro123!"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        sesion = self.db.query(Sesion).first()
        actividad_inicial = sesion.ultima_actividad

        # Avanzar reloj y enviar latido
        set_simulated_time(ahora() + timedelta(seconds=20))
        r_beat = self.client.post("/api/auth/heartbeat", headers=headers)
        self.assertEqual(r_beat.status_code, 204)

        self.db.refresh(sesion)
        self.assertEqual(sesion.ultima_actividad, actividad_inicial)
        self.assertGreater(sesion.ultimo_latido, actividad_inicial)

        # Enviar petición normal
        set_simulated_time(ahora() + timedelta(seconds=20))
        r_me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(r_me.status_code, 200)

        self.db.refresh(sesion)
        self.assertGreater(sesion.ultima_actividad, actividad_inicial)

    def test_13_muere_al_superar_tope_absoluto_de_12_horas(self) -> None:
        """13. Muere al superar ABSOLUTE_SESSION_HOURS aunque haya latidos y actividad."""
        self.crear_usuario_test(usuario="largo", password="PasswordSeguro123!")
        login_resp = self.client.post("/api/auth/login", json={"usuario": "largo", "password": "PasswordSeguro123!"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Avanzar el reloj a 12 horas y 1 minuto
        t_futuro = ahora() + timedelta(hours=12, minutes=1)
        set_simulated_time(t_futuro)

        # Actualizar ultimo_latido y ultima_actividad para simular presencia continua
        sesion = self.db.query(Sesion).first()
        sesion.ultimo_latido = t_futuro
        sesion.ultima_actividad = t_futuro
        self.db.commit()

        r = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["codigo"], "SESION_EXPIRADA")

    def test_14_refresh_comportamiento_cabecera_y_sesion(self) -> None:
        """14. refresh sin cabecera X-LIS-Client → 400; con sesión muerta → 401 y limpia cookie; con viva → 200 y cookie no cambia."""
        self.crear_usuario_test(usuario="refresher", password="PasswordSeguro123!")
        login_resp = self.client.post("/api/auth/login", json={"usuario": "refresher", "password": "PasswordSeguro123!"})
        cookie_val = login_resp.cookies.get("refresh_token")

        # 1. Sin cabecera X-LIS-Client: web -> 400 VALIDACION
        r_no_header = self.client.post("/api/auth/refresh", cookies={"refresh_token": cookie_val})
        self.assertEqual(r_no_header.status_code, 400)
        self.assertEqual(r_no_header.json()["codigo"], "VALIDACION")

        # 2. Con cabecera y sesión viva -> 200
        r_ok = self.client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": cookie_val},
            headers={"X-LIS-Client": "web"},
        )
        self.assertEqual(r_ok.status_code, 200)
        self.assertIn("access_token", r_ok.json())

        # 3. Avanzar tiempo más allá de sesión muerta (160 s sin latido) -> 401 y borra cookie
        set_simulated_time(ahora() + timedelta(seconds=160))
        r_muerta = self.client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": cookie_val},
            headers={"X-LIS-Client": "web"},
        )
        self.assertEqual(r_muerta.status_code, 401)
        self.assertEqual(r_muerta.json()["codigo"], "SESION_EXPIRADA")
        self.assertIn('refresh_token=""', r_muerta.headers.get("set-cookie", ""))

    def test_15_logout_revoca_sesion_e_invalida_token(self) -> None:
        """15. logout revoca la sesión; usar el access token después → 401; logout repetido → 204."""
        self.crear_usuario_test(usuario="saliente", password="PasswordSeguro123!")
        login_resp = self.client.post("/api/auth/login", json={"usuario": "saliente", "password": "PasswordSeguro123!"})
        token = login_resp.json()["access_token"]
        cookie_val = login_resp.cookies.get("refresh_token")

        # Logout exitoso (204)
        r_logout = self.client.post(
            "/api/auth/logout",
            cookies={"refresh_token": cookie_val},
            headers={"X-LIS-Client": "web"},
        )
        self.assertEqual(r_logout.status_code, 204)

        # Usar el access token posterior debe dar 401
        r_post = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r_post.status_code, 401)

        # Logout repetido (idempotente) -> 204
        r_logout2 = self.client.post(
            "/api/auth/logout",
            cookies={"refresh_token": cookie_val},
            headers={"X-LIS-Client": "web"},
        )
        self.assertEqual(r_logout2.status_code, 204)

    def test_16_debe_cambiar_password_bloquea_rutas_fuera_de_whitelist(self) -> None:
        """16. Con debe_cambiar_password = TRUE, cualquier endpoint fuera de la lista blanca → 403 DEBE_CAMBIAR_PASSWORD."""
        self.crear_usuario_test(
            usuario="nuevito",
            password="PasswordSeguro123!",
            debe_cambiar_password=True,
            rol="ADMIN",
        )
        login_resp = self.client.post("/api/auth/login", json={"usuario": "nuevito", "password": "PasswordSeguro123!"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Whitelist permitida: /me, /heartbeat
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/heartbeat", headers=headers).status_code, 204)

        # Endpoint protegido fuera de la whitelist: /api/usuarios -> 403 DEBE_CAMBIAR_PASSWORD
        r_bloqueado = self.client.get("/api/usuarios", headers=headers)
        self.assertEqual(r_bloqueado.status_code, 403)
        self.assertEqual(r_bloqueado.json()["codigo"], "DEBE_CAMBIAR_PASSWORD")

    def test_17_cambiar_password_correcto_y_rechazo_con_clave_erronea(self) -> None:
        """17. cambiar-password correcto: baja flag, revoca otras sesiones, conserva actual; con clave actual errónea rechaza."""
        u = self.crear_usuario_test(
            usuario="cambiador",
            password="PasswordInicial123!",
            debe_cambiar_password=True,
        )
        login1 = self.client.post("/api/auth/login", json={"usuario": "cambiador", "password": "PasswordInicial123!"})
        token1 = login1.json()["access_token"]

        login2 = self.client.post("/api/auth/login", json={"usuario": "cambiador", "password": "PasswordInicial123!"})
        token2 = login2.json()["access_token"]

        headers2 = {"Authorization": f"Bearer {token2}"}

        # 1. Clave actual incorrecta -> 400 VALIDACION
        r_err = self.client.post(
            "/api/auth/cambiar-password",
            json={"password_actual": "ClaveFalsa!", "password_nueva": "NuevaClaveValida999!"},
            headers=headers2,
        )
        self.assertEqual(r_err.status_code, 400)

        # 2. Clave nueva débil (ej. en lista prohibida 'password') -> 422 PASSWORD_DEBIL
        r_debil = self.client.post(
            "/api/auth/cambiar-password",
            json={"password_actual": "PasswordInicial123!", "password_nueva": "password123456"},
            headers=headers2,
        )
        self.assertEqual(r_debil.status_code, 422)
        self.assertEqual(r_debil.json()["codigo"], "PASSWORD_DEBIL")

        # 3. Cambio exitoso
        r_ok = self.client.post(
            "/api/auth/cambiar-password",
            json={"password_actual": "PasswordInicial123!", "password_nueva": "NuevaClaveValida999!"},
            headers=headers2,
        )
        self.assertEqual(r_ok.status_code, 204)

        self.db.refresh(u)
        self.assertFalse(u.debe_cambiar_password)

        # La sesión 2 sigue viva
        self.assertEqual(self.client.get("/api/auth/me", headers=headers2).status_code, 200)

        # La sesión 1 anterior quedó revocada
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token1}"}).status_code, 401)

    def test_18_usuario_desactivado_invalida_token_de_inmediato(self) -> None:
        """18. Un token cuyo usuario fue desactivado deja de funcionar de inmediato."""
        u = self.crear_usuario_test(usuario="desactivable", password="PasswordSeguro123!")
        login_resp = self.client.post("/api/auth/login", json={"usuario": "desactivable", "password": "PasswordSeguro123!"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)

        # Desactivar usuario en base de datos
        u.activo = False
        self.db.commit()

        # Debe responder 401 SESION_EXPIRADA
        r_post = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(r_post.status_code, 401)
        self.assertEqual(r_post.json()["codigo"], "SESION_EXPIRADA")
