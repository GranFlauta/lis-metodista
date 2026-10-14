"""
Pruebas obligatorias de Ciclo de Vida de Sesión (Tests 10–18 según PROMPT_FASE_1.md §10).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
        self.assertEqual(r_beat.status_code, 200)

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
        self.assertEqual(self.client.post("/api/auth/heartbeat", headers=headers).status_code, 200)

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

    # -------------------------------------------------------------------------
    # Tests de Fase 3.5 T5 (Sesión dinámica, latido con actividad, endpoints admin)
    # -------------------------------------------------------------------------

    def test_t5_01_latido_con_actividad_false_no_evita_expiracion_con_true_si(self) -> None:
        """1. Latido con actividad=false durante 40 min no evita la expiración por inactividad; con actividad=true sí."""
        from datetime import timezone
        from app.core.security import create_access_token

        t0 = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
        set_simulated_time(t0)
        u_inactivo = self.crear_usuario_test(usuario="bio_inactivo", password="PasswordSeguro123!")
        self.client.post("/api/auth/login", json={"usuario": "bio_inactivo", "password": "PasswordSeguro123!"})
        sesion_inactiva = self.db.query(Sesion).filter(Sesion.id_usuario == u_inactivo.id_usuario).first()
        token_inactivo = create_access_token(
            subject=u_inactivo.id_usuario,
            session_id=str(sesion_inactiva.id_sesion),
            role="BIOQUIMICO",
            expires_delta=timedelta(hours=2),
        )
        h_inactivo = {"Authorization": f"Bearer {token_inactivo}"}

        for i in range(1, 85):  # 84 * 25s = 2100s = 35 min (> 30 min)
            t_i = t0 + timedelta(seconds=i * 25)
            set_simulated_time(t_i)
            r_beat = self.client.post("/api/auth/heartbeat", json={"actividad": False}, headers=h_inactivo)
            if (t_i - t0) > timedelta(minutes=30):
                self.assertEqual(r_beat.status_code, 401)
                self.assertEqual(r_beat.json()["codigo"], "SESION_EXPIRADA")
                break
            else:
                self.assertEqual(r_beat.status_code, 200)

        # Tras expirar por inactividad, endpoint normal da 401
        r_me_inactivo = self.client.get("/api/auth/me", headers=h_inactivo)
        self.assertEqual(r_me_inactivo.status_code, 401)
        self.assertEqual(r_me_inactivo.json()["codigo"], "SESION_EXPIRADA")

        # Caso B: con actividad=True cada latido durante 40 min -> la sesión sigue viva
        t1 = datetime(2026, 10, 14, 14, 0, 0, tzinfo=timezone.utc)
        set_simulated_time(t1)
        u_activo = self.crear_usuario_test(usuario="bio_activo", password="PasswordSeguro123!")
        self.client.post("/api/auth/login", json={"usuario": "bio_activo", "password": "PasswordSeguro123!"})
        sesion_activa = self.db.query(Sesion).filter(Sesion.id_usuario == u_activo.id_usuario).first()
        token_activo = create_access_token(
            subject=u_activo.id_usuario,
            session_id=str(sesion_activa.id_sesion),
            role="BIOQUIMICO",
            expires_delta=timedelta(hours=2),
        )
        h_activo = {"Authorization": f"Bearer {token_activo}"}

        for i in range(1, 81):  # 80 * 30s = 2400s = 40 min
            t_i = t1 + timedelta(seconds=i * 30)
            set_simulated_time(t_i)
            r_b = self.client.post("/api/auth/heartbeat", json={"actividad": True}, headers=h_activo)
            self.assertEqual(r_b.status_code, 200)

        # Tras 40 min con actividad activa, sigue respondiendo 200
        r_me_activo = self.client.get("/api/auth/me", headers=h_activo)
        self.assertEqual(r_me_activo.status_code, 200)

    def test_t5_02_latido_sin_cuerpo_se_comporta_como_actividad_false(self) -> None:
        """2. Latido sin cuerpo se comporta como actividad=false."""
        self.crear_usuario_test(usuario="sin_cuerpo", password="PasswordSeguro123!")
        login_resp = self.client.post("/api/auth/login", json={"usuario": "sin_cuerpo", "password": "PasswordSeguro123!"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        sesion = self.db.query(Sesion).first()
        actividad_inicial = sesion.ultima_actividad
        latido_inicial = sesion.ultimo_latido

        # Avanzar tiempo y enviar heartbeat sin cuerpo
        t_latido = ahora() + timedelta(seconds=20)
        set_simulated_time(t_latido)
        r = self.client.post("/api/auth/heartbeat", headers=headers)
        self.assertEqual(r.status_code, 200)

        self.db.refresh(sesion)
        # ultimo_latido se actualiza pero ultima_actividad NO cambia
        self.assertGreater(sesion.ultimo_latido, latido_inicial)
        self.assertEqual(sesion.ultima_actividad, actividad_inicial)

    def test_t5_03_cambiar_config_afecta_sesiones_ya_abiertas(self) -> None:
        """3. Cambiar sesion_muerta_tras_seg y sesion_inactividad_min por la API cambia el comportamiento de sesiones ya abiertas."""
        from app.services.sesion_config_service import invalidar_cache_config_sesion

        self.crear_usuario_test(usuario="admin_cfg", password="PasswordSeguro123!", rol="ADMIN")
        login_admin = self.client.post("/api/auth/login", json={"usuario": "admin_cfg", "password": "PasswordSeguro123!"})
        token_admin = login_admin.json()["access_token"]
        h_admin = {"Authorization": f"Bearer {token_admin}"}

        self.crear_usuario_test(usuario="usuario_abierto", password="PasswordSeguro123!")
        login_user = self.client.post("/api/auth/login", json={"usuario": "usuario_abierto", "password": "PasswordSeguro123!"})
        token_user = login_user.json()["access_token"]
        h_user = {"Authorization": f"Bearer {token_user}"}

        # Cambiar configuración por API: muerta tras 60 s (en lugar de 150), inactividad 10 min (en lugar de 30)
        r_put = self.client.put(
            "/api/admin/configuracion/sesion",
            json={
                "sesion_intervalo_latido_seg": 20,
                "sesion_muerta_tras_seg": 60,
                "sesion_inactividad_min": 10,
                "sesion_tope_absoluto_horas": 12,
            },
            headers=h_admin,
        )
        self.assertEqual(r_put.status_code, 200)
        invalidar_cache_config_sesion()

        # Avanzar tiempo 65 segundos sin latido para la sesión del usuario (65 > 60 s)
        set_simulated_time(ahora() + timedelta(seconds=65))

        r_check = self.client.get("/api/auth/me", headers=h_user)
        self.assertEqual(r_check.status_code, 401)
        self.assertEqual(r_check.json()["codigo"], "SESION_EXPIRADA")

    def test_t5_04_tope_absoluto_nuevo_se_aplica_a_sesiones_posteriores(self) -> None:
        """4. El tope absoluto nuevo se aplica a sesiones creadas después del cambio, no a las existentes."""
        from app.services.sesion_config_service import invalidar_cache_config_sesion

        self.crear_usuario_test(usuario="admin_tope", password="PasswordSeguro123!", rol="ADMIN")
        login_admin = self.client.post("/api/auth/login", json={"usuario": "admin_tope", "password": "PasswordSeguro123!"})
        token_admin = login_admin.json()["access_token"]
        h_admin = {"Authorization": f"Bearer {token_admin}"}

        # Sesión A creada con tope inicial de 12 horas
        self.crear_usuario_test(usuario="user_a", password="PasswordSeguro123!")
        login_a = self.client.post("/api/auth/login", json={"usuario": "user_a", "password": "PasswordSeguro123!"})
        sesion_a = self.db.query(Sesion).filter(Sesion.id_usuario == login_a.json()["usuario"]["id_usuario"]).first()
        expira_a = sesion_a.expira_en

        # Cambiar tope a 4 horas por la API
        r_put = self.client.put(
            "/api/admin/configuracion/sesion",
            json={
                "sesion_intervalo_latido_seg": 30,
                "sesion_muerta_tras_seg": 150,
                "sesion_inactividad_min": 30,
                "sesion_tope_absoluto_horas": 4,
            },
            headers=h_admin,
        )
        self.assertEqual(r_put.status_code, 200)
        invalidar_cache_config_sesion()

        # Sesión A conserva su expira_en de 12h
        self.db.refresh(sesion_a)
        self.assertEqual(sesion_a.expira_en, expira_a)

        # Sesión B creada después del cambio -> expira_en debe ser ahora + 4h
        self.crear_usuario_test(usuario="user_b", password="PasswordSeguro123!")
        login_b = self.client.post("/api/auth/login", json={"usuario": "user_b", "password": "PasswordSeguro123!"})
        sesion_b = self.db.query(Sesion).filter(Sesion.id_usuario == login_b.json()["usuario"]["id_usuario"]).first()
        esperado_b = ahora() + timedelta(hours=4)
        self.assertAlmostEqual(sesion_b.expira_en.timestamp(), esperado_b.timestamp(), delta=2)

    def test_t5_05_validaciones_de_rango_configuracion_sesion(self) -> None:
        """5. Rangos: intervalo 9 y 121 → 400; muerta < 3× intervalo → 400; inactividad 4 y 481 → 400; tope 0 y 25 → 400."""
        self.crear_usuario_test(usuario="admin_rangos", password="PasswordSeguro123!", rol="ADMIN")
        login_admin = self.client.post("/api/auth/login", json={"usuario": "admin_rangos", "password": "PasswordSeguro123!"})
        h_admin = {"Authorization": f"Bearer {login_admin.json()['access_token']}"}

        base_valida = {
            "sesion_intervalo_latido_seg": 30,
            "sesion_muerta_tras_seg": 150,
            "sesion_inactividad_min": 30,
            "sesion_tope_absoluto_horas": 12,
        }

        casos_invalidos = [
            ({"sesion_intervalo_latido_seg": 9}, "intervalo 9 < 10"),
            ({"sesion_intervalo_latido_seg": 121}, "intervalo 121 > 120"),
            ({"sesion_intervalo_latido_seg": 30, "sesion_muerta_tras_seg": 89}, "muerta 89 < 3*30"),
            ({"sesion_inactividad_min": 4}, "inactividad 4 < 5"),
            ({"sesion_inactividad_min": 481}, "inactividad 481 > 480"),
            ({"sesion_tope_absoluto_horas": 0}, "tope 0 < 1"),
            ({"sesion_tope_absoluto_horas": 25}, "tope 25 > 24"),
        ]

        for modif, descripcion in casos_invalidos:
            payload = {**base_valida, **modif}
            r = self.client.put("/api/admin/configuracion/sesion", json=payload, headers=h_admin)
            self.assertEqual(r.status_code, 400, f"Fallo al validar: {descripcion}")
            self.assertEqual(r.json()["codigo"], "VALIDACION", f"Código incorrecto para: {descripcion}")

    def test_t5_06_control_de_acceso_roles_y_autenticacion(self) -> None:
        """6. BIOQUIMICO → 403 en ambos endpoints; sin token → 401."""
        self.crear_usuario_test(usuario="bio_restringido", password="PasswordSeguro123!", rol="BIOQUIMICO")
        login_bio = self.client.post("/api/auth/login", json={"usuario": "bio_restringido", "password": "PasswordSeguro123!"})
        h_bio = {"Authorization": f"Bearer {login_bio.json()['access_token']}"}

        # 1. Sin token -> 401
        self.assertEqual(self.client.get("/api/admin/configuracion/sesion").status_code, 401)
        self.assertEqual(self.client.put("/api/admin/configuracion/sesion", json={}).status_code, 401)

        # 2. Con rol BIOQUIMICO -> 403
        r_get_bio = self.client.get("/api/admin/configuracion/sesion", headers=h_bio)
        self.assertEqual(r_get_bio.status_code, 403)
        self.assertEqual(r_get_bio.json()["codigo"], "PROHIBIDO")

        r_put_bio = self.client.put(
            "/api/admin/configuracion/sesion",
            json={
                "sesion_intervalo_latido_seg": 30,
                "sesion_muerta_tras_seg": 150,
                "sesion_inactividad_min": 30,
                "sesion_tope_absoluto_horas": 12,
            },
            headers=h_bio,
        )
        self.assertEqual(r_put_bio.status_code, 403)
        self.assertEqual(r_put_bio.json()["codigo"], "PROHIBIDO")

    def test_t5_07_put_registra_evento_y_usa_settings_si_falta_en_bd(self) -> None:
        """7. El PUT registra CONFIG_SESION_EDITADA con antes/después; clave ausente en BD → usa settings."""
        from app.models.result import LaboratorioConfig

        # Eliminar una clave de la BD para comprobar que 'antes' toma el valor de settings
        self.db.query(LaboratorioConfig).filter(LaboratorioConfig.clave == "sesion_intervalo_latido_seg").delete()
        self.db.commit()

        self.crear_usuario_test(usuario="admin_auditor", password="PasswordSeguro123!", rol="ADMIN")
        login_admin = self.client.post("/api/auth/login", json={"usuario": "admin_auditor", "password": "PasswordSeguro123!"})
        h_admin = {"Authorization": f"Bearer {login_admin.json()['access_token']}"}

        r_put = self.client.put(
            "/api/admin/configuracion/sesion",
            json={
                "sesion_intervalo_latido_seg": 45,
                "sesion_muerta_tras_seg": 180,
                "sesion_inactividad_min": 40,
                "sesion_tope_absoluto_horas": 8,
            },
            headers=h_admin,
        )
        self.assertEqual(r_put.status_code, 200)

        # Verificar que se registró CONFIG_SESION_EDITADA
        evento = (
            self.db.query(LogSeguridad)
            .filter(LogSeguridad.accion == "CONFIG_SESION_EDITADA")
            .order_by(LogSeguridad.id_log.desc())
            .first()
        )
        self.assertIsNotNone(evento)
        detalle = evento.detalle
        self.assertIn("sesion_intervalo_latido_seg", detalle)
        # La clave que faltaba en BD tomó antes = 30 (settings) y despues = 45
        self.assertEqual(detalle["sesion_intervalo_latido_seg"]["antes"], 30)
        self.assertEqual(detalle["sesion_intervalo_latido_seg"]["despues"], 45)
        self.assertEqual(detalle["sesion_tope_absoluto_horas"]["despues"], 8)

    def test_t5_08_login_refresh_devuelven_config_y_heartbeat_segundos_restantes(self) -> None:
        """8. login/refresh devuelven config_sesion; el heartbeat devuelve segundos_restantes_inactividad coherente."""
        self.crear_usuario_test(usuario="contrato_sesion", password="PasswordSeguro123!")

        # 1. Login devuelve config_sesion
        r_login = self.client.post("/api/auth/login", json={"usuario": "contrato_sesion", "password": "PasswordSeguro123!"})
        self.assertEqual(r_login.status_code, 200)
        data_login = r_login.json()
        self.assertIn("config_sesion", data_login)
        self.assertIn("intervalo_latido_seg", data_login["config_sesion"])
        self.assertIn("inactividad_min", data_login["config_sesion"])
        cookie_val = r_login.cookies.get("refresh_token")
        token = data_login["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Refresh devuelve config_sesion
        r_ref = self.client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": cookie_val},
            headers={"X-LIS-Client": "web"},
        )
        self.assertEqual(r_ref.status_code, 200)
        data_ref = r_ref.json()
        self.assertIn("config_sesion", data_ref)
        self.assertEqual(data_ref["config_sesion"]["intervalo_latido_seg"], data_login["config_sesion"]["intervalo_latido_seg"])

        # 3. Heartbeat devuelve segundos_restantes_inactividad coherente
        # Simular 5 minutos enviando latidos cada 30s con actividad=False
        t_base = ahora()
        for s in range(30, 301, 30):
            set_simulated_time(t_base + timedelta(seconds=s))
            r_beat = self.client.post("/api/auth/heartbeat", json={"actividad": False}, headers=headers)
            self.assertEqual(r_beat.status_code, 200)

        data_beat = r_beat.json()
        self.assertIn("intervalo_latido_seg", data_beat)
        self.assertIn("segundos_restantes_inactividad", data_beat)
        # Inactividad total = 30 min (1800 s); tras 5 min (300 s) sin actividad, deben quedar ~1500 s
        self.assertAlmostEqual(data_beat["segundos_restantes_inactividad"], 1500, delta=5)

    def test_t5_09_contrato_latido_y_compatibilidad(self) -> None:
        """9. Los tests de sesión previos (10–13 y 14 de Fase 1) se actualizan al nuevo contrato del latido y siguen cubriendo lo mismo."""
        self.crear_usuario_test(usuario="user_contrato", password="PasswordSeguro123!")
        login_resp = self.client.post("/api/auth/login", json={"usuario": "user_contrato", "password": "PasswordSeguro123!"})
        headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

        # Con actividad=true responde 200 con campos esperados
        r1 = self.client.post("/api/auth/heartbeat", json={"actividad": True}, headers=headers)
        self.assertEqual(r1.status_code, 200)
        self.assertIn("intervalo_latido_seg", r1.json())
        self.assertIn("segundos_restantes_inactividad", r1.json())

        # Con actividad=false responde 200
        r2 = self.client.post("/api/auth/heartbeat", json={"actividad": False}, headers=headers)
        self.assertEqual(r2.status_code, 200)

        # Sin cuerpo responde 200
        r3 = self.client.post("/api/auth/heartbeat", headers=headers)
        self.assertEqual(r3.status_code, 200)
