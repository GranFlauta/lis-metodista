"""
Pruebas obligatorias para el módulo de Pacientes (Tests 1–8 según PROMPT_FASE_2.md §10).
Ejecutadas con unittest contra PostgreSQL real.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.core.clock import ahora
from app.models.order import Orden
from app.models.patient import Paciente
from app.models.session import LogSeguridad
from tests.base import IntegrationTestCase


class TestPacientesAPI(IntegrationTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.bio = self.crear_usuario_test(
            usuario="bioq_pacientes",
            password="PasswordBio123!",
            rol="BIOQUIMICO",
            ci="7100001",
        )
        login_bio = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq_pacientes", "password": "PasswordBio123!"},
        )
        self.bio_token = login_bio.json()["access_token"]
        self.bio_headers = {"Authorization": f"Bearer {self.bio_token}"}

        self.admin = self.crear_usuario_test(
            usuario="admin_pacientes",
            password="PasswordAdmin123!",
            rol="ADMIN",
            ci="7100002",
        )
        login_admin = self.client.post(
            "/api/auth/login",
            json={"usuario": "admin_pacientes", "password": "PasswordAdmin123!"},
        )
        self.admin_token = login_admin.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

    def test_01_alta_con_ci_normaliza_datos(self) -> None:
        """1. Alta con CI → 201; normaliza (mayúsculas, espacios)."""
        payload = {
            "ci": " 4567890 a ",
            "ci_complemento": " 1b ",
            "sin_ci": False,
            "nombres": "  Maria   Elena  ",
            "apellido_paterno": "  Montes  ",
            "apellido_materno": "  Suarez  ",
            "fecha_nacimiento": "1992-04-10",
            "sexo": "f",
            "telefono": " 77654321 ",
        }
        resp = self.client.post("/api/pacientes", json=payload, headers=self.bio_headers)
        self.assertEqual(resp.status_code, 201, f"Fallo al crear paciente: {resp.text}")
        data = resp.json()

        self.assertIn("id", data)
        self.assertEqual(data["ci"], "4567890A")
        self.assertEqual(data["ci_complemento"], "1B")
        self.assertFalse(data["sin_ci"])
        self.assertEqual(data["nombres"], "Maria Elena")
        self.assertEqual(data["apellido_paterno"], "Montes")
        self.assertEqual(data["apellido_materno"], "Suarez")
        self.assertEqual(data["sexo"], "F")
        self.assertEqual(data["telefono"], "77654321")
        self.assertEqual(data["fecha_nacimiento"], "1992-04-10")
        self.assertIn("creado_en", data)

        # Verificar persistencia en base de datos
        p_db = self.db.query(Paciente).filter(Paciente.id_paciente == data["id"]).first()
        self.assertIsNotNone(p_db)
        self.assertEqual(p_db.ci, "4567890A")
        self.assertEqual(p_db.ci_complemento, "1B")
        self.assertEqual(p_db.nombres, "Maria Elena")
        self.assertEqual(p_db.apellido_paterno, "Montes")
        self.assertEqual(p_db.apellido_materno, "Suarez")
        self.assertEqual(p_db.sexo, "F")

    def test_02_regla_excluyente_ci_vs_sin_ci(self) -> None:
        """2. sin_ci=true con ci, o sin_ci=false sin ci → 400."""
        # 1. sin_ci=true con ci -> 400
        p_invalido_1 = {
            "ci": "1234567",
            "sin_ci": True,
            "nombres": "Pedro",
            "apellido_paterno": "Gomez",
            "sexo": "M",
        }
        r1 = self.client.post("/api/pacientes", json=p_invalido_1, headers=self.bio_headers)
        self.assertEqual(r1.status_code, 400)
        self.assertEqual(r1.json()["codigo"], "VALIDACION")

        # 2. sin_ci=false sin ci -> 400
        p_invalido_2 = {
            "ci": None,
            "sin_ci": False,
            "nombres": "Pedro",
            "apellido_paterno": "Gomez",
            "sexo": "M",
        }
        r2 = self.client.post("/api/pacientes", json=p_invalido_2, headers=self.bio_headers)
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.json()["codigo"], "VALIDACION")

        # 3. sin_ci=true sin ci -> 201 válido
        p_valido_sin_ci = {
            "ci": None,
            "sin_ci": True,
            "nombres": "Recien Nacido",
            "apellido_paterno": "Perez",
            "sexo": "M",
        }
        r3 = self.client.post("/api/pacientes", json=p_valido_sin_ci, headers=self.bio_headers)
        self.assertEqual(r3.status_code, 201)
        self.assertTrue(r3.json()["sin_ci"])
        self.assertIsNone(r3.json()["ci"])

    def test_03_ci_duplicado_y_complemento(self) -> None:
        """
        3. CI duplicado → 409 con paciente_existente_id; mismo CI con otro complemento → 201;
        complemento "" equivale a NULL.
        """
        # Crear primer paciente
        p1 = {
            "ci": "5551234",
            "ci_complemento": None,
            "sin_ci": False,
            "nombres": "Juan",
            "apellido_paterno": "Mamani",
            "sexo": "M",
        }
        r1 = self.client.post("/api/pacientes", json=p1, headers=self.bio_headers)
        self.assertEqual(r1.status_code, 201)
        id_existente = r1.json()["id"]

        # Intentar duplicar con el mismo CI y complemento None -> 409 con paciente_existente_id
        p_dup = {
            "ci": "5551234",
            "ci_complemento": None,
            "sin_ci": False,
            "nombres": "Juan Segundo",
            "apellido_paterno": "Mamani",
            "sexo": "M",
        }
        r_dup = self.client.post("/api/pacientes", json=p_dup, headers=self.bio_headers)
        self.assertEqual(r_dup.status_code, 409)
        self.assertEqual(r_dup.json()["codigo"], "CONFLICTO")
        self.assertEqual(r_dup.json().get("paciente_existente_id"), id_existente)

        # Complemento "" equivale a NULL -> también da 409
        p_dup_vacio = {
            "ci": "5551234",
            "ci_complemento": "",
            "sin_ci": False,
            "nombres": "Juan Tercero",
            "apellido_paterno": "Mamani",
            "sexo": "M",
        }
        r_dup_vacio = self.client.post("/api/pacientes", json=p_dup_vacio, headers=self.bio_headers)
        self.assertEqual(r_dup_vacio.status_code, 409)
        self.assertEqual(r_dup_vacio.json()["codigo"], "CONFLICTO")
        self.assertEqual(r_dup_vacio.json().get("paciente_existente_id"), id_existente)

        # Mismo CI con OTRO complemento distinto -> 201 permitido
        p_otro_comp = {
            "ci": "5551234",
            "ci_complemento": "1B",
            "sin_ci": False,
            "nombres": "Juan",
            "apellido_paterno": "Mamani",
            "sexo": "M",
        }
        r_otro = self.client.post("/api/pacientes", json=p_otro_comp, headers=self.bio_headers)
        self.assertEqual(r_otro.status_code, 201)
        self.assertEqual(r_otro.json()["ci"], "5551234")
        self.assertEqual(r_otro.json()["ci_complemento"], "1B")

    def test_04_fecha_nacimiento_limites(self) -> None:
        """4. Fecha de nacimiento futura o de hace > 130 años → 400."""
        hoy = ahora().date()

        # Futura
        futura = hoy + timedelta(days=1)
        p_futura = {
            "ci": "6661234",
            "sin_ci": False,
            "nombres": "Futuro",
            "apellido_paterno": "Test",
            "fecha_nacimiento": futura.isoformat(),
            "sexo": "M",
        }
        r_futura = self.client.post("/api/pacientes", json=p_futura, headers=self.bio_headers)
        self.assertEqual(r_futura.status_code, 400)
        self.assertEqual(r_futura.json()["codigo"], "VALIDACION")

        # Hace > 130 años
        muy_antigua = date(hoy.year - 131, hoy.month, min(hoy.day, 28))
        p_antigua = {
            "ci": "6661234",
            "sin_ci": False,
            "nombres": "Antiguo",
            "apellido_paterno": "Test",
            "fecha_nacimiento": muy_antigua.isoformat(),
            "sexo": "M",
        }
        r_antigua = self.client.post("/api/pacientes", json=p_antigua, headers=self.bio_headers)
        self.assertEqual(r_antigua.status_code, 400)
        self.assertEqual(r_antigua.json()["codigo"], "VALIDACION")

        # Fecha válida (ej. 30 años atrás) -> 201
        valida = date(hoy.year - 30, hoy.month, min(hoy.day, 28))
        p_valida = {
            "ci": "6661234",
            "sin_ci": False,
            "nombres": "Valido",
            "apellido_paterno": "Test",
            "fecha_nacimiento": valida.isoformat(),
            "sexo": "M",
        }
        r_valida = self.client.post("/api/pacientes", json=p_valida, headers=self.bio_headers)
        self.assertEqual(r_valida.status_code, 201)

    def test_05_permisos_y_estados_autenticacion(self) -> None:
        """5. ADMIN puede GET; POST/PATCH → 403. Sin token → 401. Con debe_cambiar_password → 403."""
        paciente = self.crear_paciente_test(ci="7771234", nombres="Target", apellido_paterno="Permisos")

        # ADMIN: GET /api/pacientes -> 200
        r_admin_list = self.client.get("/api/pacientes", headers=self.admin_headers)
        self.assertEqual(r_admin_list.status_code, 200)

        # ADMIN: GET /api/pacientes/{id} -> 200
        r_admin_get = self.client.get(f"/api/pacientes/{paciente.id_paciente}", headers=self.admin_headers)
        self.assertEqual(r_admin_get.status_code, 200)

        # ADMIN: POST /api/pacientes -> 403 PROHIBIDO
        r_admin_post = self.client.post(
            "/api/pacientes",
            json={"ci": "7778889", "sin_ci": False, "nombres": "AdminCreando", "apellido_paterno": "X", "sexo": "M"},
            headers=self.admin_headers,
        )
        self.assertEqual(r_admin_post.status_code, 403)
        self.assertEqual(r_admin_post.json()["codigo"], "PROHIBIDO")

        # ADMIN: PATCH /api/pacientes/{id} -> 403 PROHIBIDO
        r_admin_patch = self.client.patch(
            f"/api/pacientes/{paciente.id_paciente}",
            json={"telefono": "78889999"},
            headers=self.admin_headers,
        )
        self.assertEqual(r_admin_patch.status_code, 403)
        self.assertEqual(r_admin_patch.json()["codigo"], "PROHIBIDO")

        # Sin token -> 401
        self.assertEqual(self.client.get("/api/pacientes").status_code, 401)
        self.assertEqual(self.client.get(f"/api/pacientes/{paciente.id_paciente}").status_code, 401)
        self.assertEqual(self.client.post("/api/pacientes", json={}).status_code, 401)
        self.assertEqual(self.client.patch(f"/api/pacientes/{paciente.id_paciente}", json={}).status_code, 401)

        # Con debe_cambiar_password = True -> 403 DEBE_CAMBIAR_PASSWORD
        user_pending = self.crear_usuario_test(
            usuario="bio_bloqueado_clave",
            password="ClaveTemporal123!",
            rol="BIOQUIMICO",
            ci="7779999",
            debe_cambiar_password=True,
        )
        login_pending = self.client.post(
            "/api/auth/login",
            json={"usuario": "bio_bloqueado_clave", "password": "ClaveTemporal123!"},
        )
        token_pending = login_pending.json()["access_token"]
        headers_pending = {"Authorization": f"Bearer {token_pending}"}

        r_pend_list = self.client.get("/api/pacientes", headers=headers_pending)
        self.assertEqual(r_pend_list.status_code, 403)
        self.assertEqual(r_pend_list.json()["codigo"], "DEBE_CAMBIAR_PASSWORD")

        r_pend_post = self.client.post(
            "/api/pacientes",
            json={"ci": "7770001", "sin_ci": False, "nombres": "A", "apellido_paterno": "B", "sexo": "M"},
            headers=headers_pending,
        )
        self.assertEqual(r_pend_post.status_code, 403)
        self.assertEqual(r_pend_post.json()["codigo"], "DEBE_CAMBIAR_PASSWORD")

    def test_06_busqueda_paginacion_y_limites(self) -> None:
        """6. Búsqueda q por CI, apellido y nombre (parcial, sin distinguir mayúsculas); paginación y total; limit=101 → 400."""
        # Crear pacientes con datos reconocibles
        self.crear_paciente_test(ci="8880010", nombres="Andrea Beatriz", apellido_paterno="Alvarez", apellido_materno="Paz")
        self.crear_paciente_test(ci="8880020", nombres="Bernardo", apellido_paterno="Benitez", apellido_materno="Rios")
        self.crear_paciente_test(ci="8880030", nombres="Carlos", apellido_paterno="Castro", apellido_materno="Alvarez")

        # limit=101 -> 400
        r_lim = self.client.get("/api/pacientes?limit=101", headers=self.bio_headers)
        self.assertEqual(r_lim.status_code, 400)
        self.assertEqual(r_lim.json()["codigo"], "VALIDACION")

        # offset=-1 -> 400
        r_off = self.client.get("/api/pacientes?offset=-1", headers=self.bio_headers)
        self.assertEqual(r_off.status_code, 400)
        self.assertEqual(r_off.json()["codigo"], "VALIDACION")

        # Búsqueda por nombre parcial insensible a mayúsculas
        r_q_nom = self.client.get("/api/pacientes?q=beatriz", headers=self.bio_headers)
        self.assertEqual(r_q_nom.status_code, 200)
        data_nom = r_q_nom.json()
        self.assertEqual(data_nom["total"], 1)
        self.assertEqual(data_nom["items"][0]["nombres"], "Andrea Beatriz")

        # Búsqueda por apellido (coincide en 2 pacientes: Alvarez como paterno y como materno)
        r_q_ape = self.client.get("/api/pacientes?q=alvarez", headers=self.bio_headers)
        self.assertEqual(r_q_ape.status_code, 200)
        self.assertEqual(r_q_ape.json()["total"], 2)

        # Búsqueda por CI parcial
        r_q_ci = self.client.get("/api/pacientes?q=888002", headers=self.bio_headers)
        self.assertEqual(r_q_ci.status_code, 200)
        self.assertEqual(r_q_ci.json()["total"], 1)
        self.assertEqual(r_q_ci.json()["items"][0]["ci"], "8880020")

        # Paginación (limit=2, offset=0 y offset=2)
        r_page1 = self.client.get("/api/pacientes?limit=2&offset=0", headers=self.bio_headers)
        self.assertEqual(r_page1.status_code, 200)
        data_p1 = r_page1.json()
        self.assertEqual(len(data_p1["items"]), 2)
        self.assertEqual(data_p1["limit"], 2)
        self.assertEqual(data_p1["offset"], 0)
        self.assertGreaterEqual(data_p1["total"], 3)

        r_page2 = self.client.get("/api/pacientes?limit=2&offset=2", headers=self.bio_headers)
        self.assertEqual(r_page2.status_code, 200)
        data_p2 = r_page2.json()
        self.assertGreaterEqual(len(data_p2["items"]), 1)
        self.assertEqual(data_p2["offset"], 2)

    def test_07_patch_edicion_unicidad_y_campo_desconocido(self) -> None:
        """7. PATCH edita campos y respeta unicidad de CI (409); campo desconocido → 400."""
        paciente_a = self.crear_paciente_test(ci="9991111", nombres="Original", apellido_paterno="Uno")
        paciente_b = self.crear_paciente_test(ci="9992222", nombres="Original", apellido_paterno="Dos")

        # Edición exitosa de teléfono y nombres
        r_patch = self.client.patch(
            f"/api/pacientes/{paciente_a.id_paciente}",
            json={"nombres": "Nombre Actualizado", "telefono": "70099887"},
            headers=self.bio_headers,
        )
        self.assertEqual(r_patch.status_code, 200)
        data_patch = r_patch.json()
        self.assertEqual(data_patch["nombres"], "Nombre Actualizado")
        self.assertEqual(data_patch["telefono"], "70099887")

        # Intento de colisión de CI con paciente B -> 409 CONFLICTO con paciente_existente_id
        r_colision = self.client.patch(
            f"/api/pacientes/{paciente_a.id_paciente}",
            json={"ci": "9992222"},
            headers=self.bio_headers,
        )
        self.assertEqual(r_colision.status_code, 409)
        self.assertEqual(r_colision.json()["codigo"], "CONFLICTO")
        self.assertEqual(r_colision.json().get("paciente_existente_id"), paciente_b.id_paciente)

        # Enviar campo desconocido -> 400 VALIDACION
        r_desconocido = self.client.patch(
            f"/api/pacientes/{paciente_a.id_paciente}",
            json={"campo_inexistente": "valor_no_permitido"},
            headers=self.bio_headers,
        )
        self.assertEqual(r_desconocido.status_code, 400)
        self.assertEqual(r_desconocido.json()["codigo"], "VALIDACION")

    def test_08_no_existe_delete_pacientes(self) -> None:
        """8. No existe DELETE /api/pacientes/{id}."""
        paciente = self.crear_paciente_test(ci="9993333", nombres="No", apellido_paterno="Borrable")

        # Intentar DELETE como BIOQUIMICO y como ADMIN
        r_del_bio = self.client.delete(f"/api/pacientes/{paciente.id_paciente}", headers=self.bio_headers)
        self.assertIn(r_del_bio.status_code, (404, 405), f"Respondió código inesperado: {r_del_bio.status_code}")

        r_del_admin = self.client.delete(f"/api/pacientes/{paciente.id_paciente}", headers=self.admin_headers)
        self.assertIn(r_del_admin.status_code, (404, 405), f"Respondió código inesperado: {r_del_admin.status_code}")

        # Comprobar que sigue existiendo en BD
        p_db = self.db.query(Paciente).filter(Paciente.id_paciente == paciente.id_paciente).first()
        self.assertIsNotNone(p_db)

    # -------------------------------------------------------------
    # Tests Fase 3.6 - B1 (Tests 1 - 5)
    # -------------------------------------------------------------
    def test_b1_01_filtro_sexo_y_fechas_creacion(self) -> None:
        """1. Filtro sexo y rango de fechas de creación."""
        self.crear_paciente_test(ci="1110001", nombres="Masculino", sexo="M")
        self.crear_paciente_test(ci="1110002", nombres="Femenino", sexo="F")

        # Modificar fechas de creación para probar rango de fechas
        p_antiguo = self.crear_paciente_test(ci="1110003", nombres="Antiguo", sexo="M")
        p_reciente = self.crear_paciente_test(ci="1110004", nombres="Reciente", sexo="F")

        p_antiguo.creado_en = datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        p_reciente.creado_en = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        self.db.commit()

        # Filtro por sexo M
        res_m = self.client.get("/api/pacientes?sexo=M", headers=self.bio_headers)
        self.assertEqual(res_m.status_code, 200)
        sexos_m = [item["sexo"] for item in res_m.json()["items"]]
        self.assertTrue(all(s == "M" for s in sexos_m))
        self.assertIn("1110001", [item["ci"] for item in res_m.json()["items"]])
        self.assertNotIn("1110002", [item["ci"] for item in res_m.json()["items"]])

        # Filtro por sexo F
        res_f = self.client.get("/api/pacientes?sexo=f", headers=self.bio_headers)
        self.assertEqual(res_f.status_code, 200)
        sexos_f = [item["sexo"] for item in res_f.json()["items"]]
        self.assertTrue(all(s == "F" for s in sexos_f))
        self.assertIn("1110002", [item["ci"] for item in res_f.json()["items"]])
        self.assertNotIn("1110001", [item["ci"] for item in res_f.json()["items"]])

        # Filtro por rango de fechas (2025-01-01 a 2025-01-31)
        res_rango = self.client.get(
            "/api/pacientes?creado_desde=2025-01-01&creado_hasta=2025-01-31",
            headers=self.bio_headers,
        )
        self.assertEqual(res_rango.status_code, 200)
        cis_rango = [item["ci"] for item in res_rango.json()["items"]]
        self.assertIn("1110003", cis_rango)
        self.assertNotIn("1110004", cis_rango)

    def test_b1_02_con_pendientes_devuelve_solo_propios(self) -> None:
        """2. con_pendientes=true devuelve solo pacientes con pendientes propios."""
        bio2 = self.crear_usuario_test(
            usuario="bioq_pacientes_2",
            password="PasswordBio123!",
            rol="BIOQUIMICO",
            ci="7100099",
        )
        login_bio2 = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq_pacientes_2", "password": "PasswordBio123!"},
        )
        bio2_headers = {"Authorization": f"Bearer {login_bio2.json()['access_token']}"}

        p1 = self.crear_paciente_test(ci="2220001", nombres="PacienteBio1")
        p2 = self.crear_paciente_test(ci="2220002", nombres="PacienteBio2")
        self.crear_paciente_test(ci="2220003", nombres="PacienteSinOrdenes")

        # Bio 1 crea orden en p1
        r_ord1 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": p1.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 30},
            headers=self.bio_headers,
        )
        self.assertEqual(r_ord1.status_code, 201)

        # Bio 2 crea orden en p2
        r_ord2 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": p2.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 30},
            headers=bio2_headers,
        )
        self.assertEqual(r_ord2.status_code, 201)

        # Bio 1 consulta con_pendientes=true: solo debe ver p1
        r_bio1 = self.client.get("/api/pacientes?con_pendientes=true", headers=self.bio_headers)
        self.assertEqual(r_bio1.status_code, 200)
        items_bio1 = r_bio1.json()["items"]
        cis_bio1 = [it["ci"] for it in items_bio1]
        self.assertIn("2220001", cis_bio1)
        self.assertNotIn("2220002", cis_bio1)
        self.assertNotIn("2220003", cis_bio1)
        p1_item = next(it for it in items_bio1 if it["ci"] == "2220001")
        self.assertEqual(p1_item["pendientes"], 1)

        # Bio 2 consulta con_pendientes=true: solo debe ver p2
        r_bio2 = self.client.get("/api/pacientes?con_pendientes=true", headers=bio2_headers)
        self.assertEqual(r_bio2.status_code, 200)
        items_bio2 = r_bio2.json()["items"]
        cis_bio2 = [it["ci"] for it in items_bio2]
        self.assertIn("2220002", cis_bio2)
        self.assertNotIn("2220001", cis_bio2)

    def test_b1_03_pendientes_cuenta_incompleto_completo_no_publicada(self) -> None:
        """3. pendientes cuenta solo INCOMPLETO/COMPLETO (no PUBLICADA) y solo las propias."""
        bio2 = self.crear_usuario_test(
            usuario="bioq_pacientes_3",
            password="PasswordBio123!",
            rol="BIOQUIMICO",
            ci="7100098",
        )
        login_bio2 = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq_pacientes_3", "password": "PasswordBio123!"},
        )
        bio2_headers = {"Authorization": f"Bearer {login_bio2.json()['access_token']}"}

        paciente = self.crear_paciente_test(ci="3330001", nombres="MultiplesEstados")

        # 1. Orden INCOMPLETO de Bio 1
        r1 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 35},
            headers=self.bio_headers,
        )
        self.assertEqual(r1.status_code, 201)

        # 2. Orden COMPLETO de Bio 1
        r2 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "COAGULOGRAMA"}], "edad_anios": 35},
            headers=self.bio_headers,
        )
        self.assertEqual(r2.status_code, 201)
        id_ord2 = r2.json()["orden"]["id"]
        o2_db = self.db.query(Orden).filter(Orden.id_orden == id_ord2).first()
        o2_db.estado_trabajo = "COMPLETO"

        # 3. Orden PUBLICADA de Bio 1 (no debe contarse como pendiente)
        r3 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "QUIMICA_SANGUINEA"}], "edad_anios": 35},
            headers=self.bio_headers,
        )
        self.assertEqual(r3.status_code, 201)
        id_ord3 = r3.json()["orden"]["id"]
        o3_db = self.db.query(Orden).filter(Orden.id_orden == id_ord3).first()
        o3_db.estado_trabajo = "PUBLICADA"

        # 4. Orden INCOMPLETO de Bio 2 (ajena, no debe contarse para Bio 1)
        r4 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "ELECTROLITOS"}], "edad_anios": 35},
            headers=bio2_headers,
        )
        self.assertEqual(r4.status_code, 201)

        self.db.commit()

        # Bio 1 consulta paciente
        r_list = self.client.get(f"/api/pacientes?q={paciente.ci}", headers=self.bio_headers)
        self.assertEqual(r_list.status_code, 200)
        items = r_list.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["pendientes"], 2)  # INCOMPLETO + COMPLETO propios

    def test_b1_04_admin_pendientes_de_todos_y_audita_una_vez(self) -> None:
        """4. ADMIN: pendientes de todos y un solo ADMIN_VE_PRIVADO; sin pendientes no audita."""
        p_con = self.crear_paciente_test(ci="4440001", nombres="ConPendientes")
        p_sin = self.crear_paciente_test(ci="4440002", nombres="SinPendientes")

        # Crear orden para p_con
        r_ord = self.client.post(
            "/api/ordenes",
            json={"id_paciente": p_con.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 40},
            headers=self.bio_headers,
        )
        self.assertEqual(r_ord.status_code, 201)

        # 1. Caso sin pendientes: ADMIN busca p_sin expresamente
        self.db.query(LogSeguridad).delete()
        self.db.commit()

        r_sin = self.client.get(f"/api/pacientes?q={p_sin.ci}", headers=self.admin_headers)
        self.assertEqual(r_sin.status_code, 200)
        items_sin = r_sin.json()["items"]
        self.assertEqual(len(items_sin), 1)
        self.assertEqual(items_sin[0]["pendientes"], 0)

        logs_sin = self.db.query(LogSeguridad).filter(LogSeguridad.accion == "ADMIN_VE_PRIVADO").count()
        self.assertEqual(logs_sin, 0)  # Sin pendientes no audita

        # 2. Caso con pendientes: ADMIN lista y devuelve pacientes con pendientes > 0
        r_con = self.client.get("/api/pacientes", headers=self.admin_headers)
        self.assertEqual(r_con.status_code, 200)
        items_con = r_con.json()["items"]
        self.assertTrue(any(it["pendientes"] > 0 for it in items_con))

        logs_con = self.db.query(LogSeguridad).filter(LogSeguridad.accion == "ADMIN_VE_PRIVADO").all()
        self.assertEqual(len(logs_con), 1)  # Registra un solo evento
        self.assertEqual(logs_con[0].detalle.get("recurso"), "pacientes_pendientes")

    def test_b1_05_filtros_invalidos_devuelven_400(self) -> None:
        """5. Filtros inválidos → 400."""
        # Sexo inválido
        r1 = self.client.get("/api/pacientes?sexo=X", headers=self.bio_headers)
        self.assertEqual(r1.status_code, 400)
        self.assertEqual(r1.json()["codigo"], "VALIDACION")

        # creado_desde inválido
        r2 = self.client.get("/api/pacientes?creado_desde=invalido", headers=self.bio_headers)
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.json()["codigo"], "VALIDACION")

        # creado_hasta inválido
        r3 = self.client.get("/api/pacientes?creado_hasta=2026-99-99", headers=self.bio_headers)
        self.assertEqual(r3.status_code, 400)
        self.assertEqual(r3.json()["codigo"], "VALIDACION")

        # creado_desde posterior a creado_hasta
        r4 = self.client.get(
            "/api/pacientes?creado_desde=2026-10-15&creado_hasta=2026-10-10",
            headers=self.bio_headers,
        )
        self.assertEqual(r4.status_code, 400)
        self.assertEqual(r4.json()["codigo"], "VALIDACION")

        # con_pendientes inválido
        r5 = self.client.get("/api/pacientes?con_pendientes=quizas", headers=self.bio_headers)
        self.assertEqual(r5.status_code, 400)
        self.assertEqual(r5.json()["codigo"], "VALIDACION")
