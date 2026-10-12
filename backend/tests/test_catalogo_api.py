"""
Pruebas obligatorias del Catálogo Clínico (Tests 9–11 según PROMPT_FASE_2.md §10).
Ejecutadas con unittest contra PostgreSQL real.
"""
from __future__ import annotations

from app.catalog.definitions import PERFILES
from app.models.catalog import Estudio
from tests.base import IntegrationTestCase


class TestCatalogoAPI(IntegrationTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.bio = self.crear_usuario_test(
            usuario="bioq_catalogo",
            password="PasswordBio123!",
            rol="BIOQUIMICO",
            ci="8000001",
        )
        login_bio = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq_catalogo", "password": "PasswordBio123!"},
        )
        self.bio_token = login_bio.json()["access_token"]
        self.bio_headers = {"Authorization": f"Bearer {self.bio_token}"}

        self.admin = self.crear_usuario_test(
            usuario="admin_catalogo",
            password="PasswordAdmin123!",
            rol="ADMIN",
            ci="8000002",
        )
        login_admin = self.client.post(
            "/api/auth/login",
            json={"usuario": "admin_catalogo", "password": "PasswordAdmin123!"},
        )
        self.admin_token = login_admin.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

    def test_09_estudios_activos_y_seleccion_parcial(self) -> None:
        """
        9. Devuelve exactamente los 9 estudios activos; solo Inmunoserología tiene
        seleccion_parcial y grupos (incluye VIH y PCR_SEMICUANT); los demás grupos = null.
        """
        resp = self.client.get("/api/catalogo/estudios", headers=self.bio_headers)
        self.assertEqual(resp.status_code, 200)

        estudios = resp.json()
        self.assertEqual(len(estudios), 9, f"Se esperaban 9 estudios activos, llegaron {len(estudios)}")

        estudios_por_codigo = {e["codigo"]: e for e in estudios}
        self.assertIn("INMUNOSEROLOGIA", estudios_por_codigo)

        for codigo, e in estudios_por_codigo.items():
            self.assertIn("codigo", e)
            self.assertIn("nombre", e)
            self.assertIn("categoria", e)
            self.assertIn("seleccion_parcial", e)
            self.assertIn("grupos", e)

            if codigo == "INMUNOSEROLOGIA":
                self.assertTrue(e["seleccion_parcial"])
                self.assertIsInstance(e["grupos"], list)
                self.assertGreater(len(e["grupos"]), 0)

                # Verificar grupos y sus parámetros
                grupos_codigos = [g["codigo"] for g in e["grupos"]]
                self.assertIn("VIH", grupos_codigos)
                self.assertIn("PCR_SEMICUANT", grupos_codigos)

                for g in e["grupos"]:
                    self.assertIn("codigo", g)
                    self.assertIn("parametros", g)
                    self.assertIsInstance(g["parametros"], list)
                    self.assertGreater(len(g["parametros"]), 0)
                    for p in g["parametros"]:
                        self.assertIn("codigo", p)
                        self.assertIn("nombre", p)
            else:
                self.assertFalse(e["seleccion_parcial"], f"Estudio {codigo} no debe tener seleccion_parcial")
                self.assertIsNone(e["grupos"], f"Estudio {codigo} debe tener grupos = null")

    def test_10_perfiles_coinciden_con_definiciones(self) -> None:
        """
        10. Los 2 perfiles coinciden con PERFILES de definitions.py
        (mismos estudios, mismo orden, mismos grupos).
        """
        resp = self.client.get("/api/catalogo/perfiles", headers=self.bio_headers)
        self.assertEqual(resp.status_code, 200)

        perfiles_api = resp.json()
        self.assertEqual(len(perfiles_api), len(PERFILES), "La cantidad de perfiles no coincide con definitions.py")
        self.assertEqual(len(perfiles_api), 2)

        perfiles_api_dict = {p["codigo"]: p for p in perfiles_api}

        for perfil_def in PERFILES:
            self.assertIn(perfil_def.codigo, perfiles_api_dict)
            p_api = perfiles_api_dict[perfil_def.codigo]
            self.assertEqual(p_api["nombre"], perfil_def.nombre)

            # Verificar estudios, orden y grupos
            estudios_def = perfil_def.estudios
            estudios_api = p_api["estudios"]
            self.assertEqual(
                len(estudios_api),
                len(estudios_def),
                f"La cantidad de estudios del perfil {perfil_def.codigo} difiere",
            )

            for idx, (cod_def, grupos_def) in enumerate(estudios_def):
                e_api = estudios_api[idx]
                self.assertEqual(e_api["codigo"], cod_def)
                self.assertEqual(
                    e_api["grupos"],
                    grupos_def,
                    f"Los grupos para {cod_def} en perfil {perfil_def.codigo} no coinciden",
                )

    def test_11_autenticacion_y_estudio_inactivo_oculto(self) -> None:
        """
        11. Exige autenticación; un estudio con activo = FALSE no aparece.
        Accesible a cualquier usuario autenticado (ADMIN y BIOQUIMICO).
        """
        # 1. Sin autenticación -> 401
        r_no_auth_est = self.client.get("/api/catalogo/estudios")
        self.assertEqual(r_no_auth_est.status_code, 401)
        r_no_auth_perf = self.client.get("/api/catalogo/perfiles")
        self.assertEqual(r_no_auth_perf.status_code, 401)

        # 2. Con ADMIN -> 200
        r_admin_est = self.client.get("/api/catalogo/estudios", headers=self.admin_headers)
        self.assertEqual(r_admin_est.status_code, 200)
        r_admin_perf = self.client.get("/api/catalogo/perfiles", headers=self.admin_headers)
        self.assertEqual(r_admin_perf.status_code, 200)

        # 3. Con BIOQUIMICO -> 200
        r_bio_est = self.client.get("/api/catalogo/estudios", headers=self.bio_headers)
        self.assertEqual(r_bio_est.status_code, 200)
        r_bio_perf = self.client.get("/api/catalogo/perfiles", headers=self.bio_headers)
        self.assertEqual(r_bio_perf.status_code, 200)

        # 4. Con debe_cambiar_password = True -> 403 DEBE_CAMBIAR_PASSWORD
        user_pending = self.crear_usuario_test(
            usuario="user_pending_cat",
            password="PasswordPend123!",
            rol="BIOQUIMICO",
            ci="8000003",
            debe_cambiar_password=True,
        )
        login_pending = self.client.post(
            "/api/auth/login",
            json={"usuario": "user_pending_cat", "password": "PasswordPend123!"},
        )
        token_pending = login_pending.json()["access_token"]
        headers_pending = {"Authorization": f"Bearer {token_pending}"}

        r_pend_est = self.client.get("/api/catalogo/estudios", headers=headers_pending)
        self.assertEqual(r_pend_est.status_code, 403)
        self.assertEqual(r_pend_est.json()["codigo"], "DEBE_CAMBIAR_PASSWORD")

        # 5. Estudio con activo = FALSE no aparece en el listado
        estudio_target = self.db.query(Estudio).filter(Estudio.codigo == "QUIMICA_SANGUINEA").first()
        self.assertIsNotNone(estudio_target)
        try:
            estudio_target.activo = False
            self.db.commit()

            resp = self.client.get("/api/catalogo/estudios", headers=self.bio_headers)
            self.assertEqual(resp.status_code, 200)
            codigos_visibles = [e["codigo"] for e in resp.json()]
            self.assertEqual(len(codigos_visibles), 8)
            self.assertNotIn("QUIMICA_SANGUINEA", codigos_visibles)
        finally:
            estudio_target.activo = True
            self.db.commit()

        # Al reactivar, vuelve a aparecer
        resp_restaurado = self.client.get("/api/catalogo/estudios", headers=self.bio_headers)
        self.assertEqual(resp_restaurado.status_code, 200)
        codigos_restaurados = [e["codigo"] for e in resp_restaurado.json()]
        self.assertEqual(len(codigos_restaurados), 9)
        self.assertIn("QUIMICA_SANGUINEA", codigos_restaurados)
