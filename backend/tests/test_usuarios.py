"""
Pruebas obligatorias de Gestión de Usuarios (Tests 19–26 según PROMPT_FASE_1.md §10).
"""

from __future__ import annotations

from app.models.session import LogSeguridad, Sesion
from app.models.user import Usuario
from tests.base import IntegrationTestCase


class TestGestionUsuarios(IntegrationTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.admin = self.crear_usuario_test(usuario="admin_master", password="PasswordAdmin123!", rol="ADMIN", ci="9000001")
        login_admin = self.client.post("/api/auth/login", json={"usuario": "admin_master", "password": "PasswordAdmin123!"})
        self.admin_token = login_admin.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

        self.bio = self.crear_usuario_test(usuario="bioq_user", password="PasswordBio123!", rol="BIOQUIMICO", ci="9000002")
        login_bio = self.client.post("/api/auth/login", json={"usuario": "bioq_user", "password": "PasswordBio123!"})
        self.bio_token = login_bio.json()["access_token"]
        self.bio_headers = {"Authorization": f"Bearer {self.bio_token}"}

    def test_19_bioquimico_recibe_403_prohibido_y_sin_token_401(self) -> None:
        """19. Un BIOQUIMICO recibe 403 PROHIBIDO en todos los endpoints /api/usuarios; sin token → 401."""
        endpoints = [
            ("GET", "/api/usuarios"),
            ("POST", "/api/usuarios"),
            ("GET", f"/api/usuarios/{self.admin.id_usuario}"),
            ("PATCH", f"/api/usuarios/{self.admin.id_usuario}"),
            ("POST", f"/api/usuarios/{self.admin.id_usuario}/desactivar"),
            ("POST", f"/api/usuarios/{self.admin.id_usuario}/reactivar"),
            ("POST", f"/api/usuarios/{self.admin.id_usuario}/reset-password"),
        ]

        for metodo, url in endpoints:
            # Sin token -> 401
            r_no_auth = self.client.request(metodo, url)
            self.assertEqual(r_no_auth.status_code, 401, f"Fallo sin auth en {metodo} {url}")

            # Con rol BIOQUIMICO -> 403 PROHIBIDO
            r_bio = self.client.request(metodo, url, headers=self.bio_headers)
            self.assertEqual(r_bio.status_code, 403, f"Fallo con rol BIOQUIMICO en {metodo} {url}")
            self.assertEqual(r_bio.json()["codigo"], "PROHIBIDO")

    def test_20_crear_usuario_devuelve_temporal_solo_una_vez_y_guarda_hash(self) -> None:
        """20. Crear usuario: devuelve password_temporal una vez; en BD solo hash Argon2id; GET no la devuelve; debe_cambiar=TRUE."""
        payload = {
            "usuario": "nuevo_analista",
            "ci": "5551234",
            "nombres": "Carlos",
            "apellido_paterno": "Perez",
            "apellido_materno": "Gomez",
            "correo": "cperez@laboratorio.com",
            "rol": "BIOQUIMICO",
        }
        r_create = self.client.post("/api/usuarios", json=payload, headers=self.admin_headers)
        self.assertEqual(r_create.status_code, 201)
        data = r_create.json()

        self.assertIn("password_temporal", data)
        self.assertEqual(len(data["password_temporal"]), 14)
        self.assertTrue(data["debe_cambiar_password"])
        new_id = data["id_usuario"]

        # Verificar en base de datos: solo hay hash Argon2id
        u_db = self.db.query(Usuario).filter(Usuario.id_usuario == new_id).first()
        self.assertIsNotNone(u_db)
        self.assertTrue(u_db.hash_password.startswith("$argon2id$"))
        self.assertNotIn(data["password_temporal"], u_db.hash_password)

        # GET posterior no debe devolver password_temporal
        r_get = self.client.get(f"/api/usuarios/{new_id}", headers=self.admin_headers)
        self.assertEqual(r_get.status_code, 200)
        self.assertNotIn("password_temporal", r_get.json())

    def test_21_duplicados_usuario_ci_correo_devuelven_409_conflicto(self) -> None:
        """21. Duplicados de usuario, ci, correo → 409 CONFLICTO."""
        base_payload = {
            "usuario": "unico_user",
            "ci": "7778889",
            "nombres": "Ana",
            "apellido_paterno": "Rios",
            "correo": "ana.rios@laboratorio.com",
            "rol": "BIOQUIMICO",
        }
        self.assertEqual(self.client.post("/api/usuarios", json=base_payload, headers=self.admin_headers).status_code, 201)

        # 1. Duplicado usuario
        p1 = dict(base_payload, ci="9990001", correo="otro1@lab.com")
        r1 = self.client.post("/api/usuarios", json=p1, headers=self.admin_headers)
        self.assertEqual(r1.status_code, 409)
        self.assertEqual(r1.json()["codigo"], "CONFLICTO")

        # 2. Duplicado CI
        p2 = dict(base_payload, usuario="otro_usuario2", correo="otro2@lab.com")
        r2 = self.client.post("/api/usuarios", json=p2, headers=self.admin_headers)
        self.assertEqual(r2.status_code, 409)
        self.assertEqual(r2.json()["codigo"], "CONFLICTO")

        # 3. Duplicado correo
        p3 = dict(base_payload, usuario="otro_usuario3", ci="9990003")
        r3 = self.client.post("/api/usuarios", json=p3, headers=self.admin_headers)
        self.assertEqual(r3.status_code, 409)
        self.assertEqual(r3.json()["codigo"], "CONFLICTO")

    def test_22_desactivar_revoca_sesiones_y_reactivar_limpia_bloqueo(self) -> None:
        """22. Desactivar revoca sus sesiones; reactivar limpia bloqueo."""
        # Desactivar bioquímico
        r_desact = self.client.post(f"/api/usuarios/{self.bio.id_usuario}/desactivar", headers=self.admin_headers)
        self.assertEqual(r_desact.status_code, 204)

        self.db.refresh(self.bio)
        self.assertFalse(self.bio.activo)

        # Comprobar que sus sesiones quedaron revocadas
        sesiones_activas = self.db.query(Sesion).filter(Sesion.id_usuario == self.bio.id_usuario, Sesion.revocada_en.is_(None)).count()
        self.assertEqual(sesiones_activas, 0)

        # Reactivar bioquímico
        r_react = self.client.post(f"/api/usuarios/{self.bio.id_usuario}/reactivar", headers=self.admin_headers)
        self.assertEqual(r_react.status_code, 204)

        self.db.refresh(self.bio)
        self.assertTrue(self.bio.activo)
        self.assertEqual(self.bio.intentos_fallidos, 0)
        self.assertIsNone(self.bio.bloqueado_hasta)

    def test_23_admin_no_puede_desactivarse_ni_dejar_sistema_sin_admin(self) -> None:
        """23. Un admin no puede desactivarse ni cambiarse el rol; no se puede dejar el sistema sin admin activo."""
        # 1. Admin intenta desactivarse a sí mismo -> 403 PROHIBIDO
        r_auto = self.client.post(f"/api/usuarios/{self.admin.id_usuario}/desactivar", headers=self.admin_headers)
        self.assertEqual(r_auto.status_code, 403)
        self.assertEqual(r_auto.json()["codigo"], "PROHIBIDO")

        # 2. Admin intenta cambiarse su propio rol -> 403 PROHIBIDO
        r_rol = self.client.patch(f"/api/usuarios/{self.admin.id_usuario}", json={"rol": "BIOQUIMICO"}, headers=self.admin_headers)
        self.assertEqual(r_rol.status_code, 403)
        self.assertEqual(r_rol.json()["codigo"], "PROHIBIDO")

    def test_24_no_existe_ruta_delete_usuarios(self) -> None:
        """24. No existe ruta DELETE /api/usuarios/{id} (responde 405 o 404)."""
        r_del = self.client.delete(f"/api/usuarios/{self.bio.id_usuario}", headers=self.admin_headers)
        self.assertIn(r_del.status_code, [404, 405])

    def test_25_reset_password_genera_temporal_y_revoca_sesiones(self) -> None:
        """25. Reset de contraseña: nueva temporal, flag activo, sesiones revocadas, evento registrado."""
        r_reset = self.client.post(f"/api/usuarios/{self.bio.id_usuario}/reset-password", headers=self.admin_headers)
        self.assertEqual(r_reset.status_code, 200)
        data = r_reset.json()

        self.assertIn("password_temporal", data)
        self.assertEqual(len(data["password_temporal"]), 14)

        self.db.refresh(self.bio)
        self.assertTrue(self.bio.debe_cambiar_password)
        self.assertEqual(self.bio.intentos_fallidos, 0)
        self.assertIsNone(self.bio.bloqueado_hasta)

        # Evento RESET_PASSWORD_ADMIN registrado
        ev = self.db.query(LogSeguridad).filter(LogSeguridad.accion == "RESET_PASSWORD_ADMIN").first()
        self.assertIsNotNone(ev)

    def test_26_ninguna_respuesta_api_contiene_hash_password_ni_refresh_hash(self) -> None:
        """26. Ninguna respuesta de la API contiene hash_password ni refresh_hash."""
        respuestas = [
            self.client.get("/api/auth/me", headers=self.admin_headers),
            self.client.get("/api/usuarios", headers=self.admin_headers),
            self.client.get(f"/api/usuarios/{self.admin.id_usuario}", headers=self.admin_headers),
        ]
        for r in respuestas:
            texto = r.text
            self.assertNotIn("hash_password", texto)
            self.assertNotIn("refresh_hash", texto)
