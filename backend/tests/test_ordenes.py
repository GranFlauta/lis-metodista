"""
Pruebas obligatorias de Órdenes en borrador, concurrencia y privacidad
(Tests 12 al 36 según PROMPT_FASE_2.md §10).
Ejecutadas con unittest contra PostgreSQL real.
"""
from __future__ import annotations

import concurrent.futures
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text

from app.core.clock import ahora, set_simulated_time
from app.models.catalog import Estudio, EstudioVersion
from app.models.order import BorradorDescartado, Orden, OrdenEstudio, OrdenEstudioGrupo
from app.models.patient import Paciente
from app.models.session import LogSeguridad
from tests.base import IntegrationTestCase


class TestOrdenesAPI(IntegrationTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.bio = self.crear_usuario_test(
            usuario="bioq_ordenes_1",
            password="PasswordBio123!",
            rol="BIOQUIMICO",
            ci="6100001",
        )
        login_bio = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq_ordenes_1", "password": "PasswordBio123!"},
        )
        self.bio_token = login_bio.json()["access_token"]
        self.bio_headers = {"Authorization": f"Bearer {self.bio_token}"}

        self.bio2 = self.crear_usuario_test(
            usuario="bioq_ordenes_2",
            password="PasswordBio123!",
            rol="BIOQUIMICO",
            ci="6100002",
        )
        login_bio2 = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq_ordenes_2", "password": "PasswordBio123!"},
        )
        self.bio2_token = login_bio2.json()["access_token"]
        self.bio2_headers = {"Authorization": f"Bearer {self.bio2_token}"}

        self.admin = self.crear_usuario_test(
            usuario="admin_ordenes",
            password="PasswordAdmin123!",
            rol="ADMIN",
            ci="6100003",
        )
        login_admin = self.client.post(
            "/api/auth/login",
            json={"usuario": "admin_ordenes", "password": "PasswordAdmin123!"},
        )
        self.admin_token = login_admin.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

    def crear_informe_bloqueo(self, id_orden: int, id_usuario: int) -> int:
        """Crea un informe mínimo para satisfacer la FK y CHECK de órdenes bloqueadas."""
        folio = self.db.execute(text("SELECT laboratorio.siguiente_folio()")).scalar()
        id_inf = self.db.execute(
            text(
                """
                INSERT INTO laboratorio.informes (
                    folio, numero_version, id_orden, estado,
                    id_usuario_firmante, id_usuario_publicador,
                    es_urgencia, snapshot_json, snapshot_sha256
                ) VALUES (
                    :folio, 1, :id_orden, 'VIGENTE',
                    :id_user, :id_user,
                    FALSE, '{}'::jsonb, repeat('a', 64)
                ) RETURNING id_informe
                """
            ),
            {"folio": folio, "id_orden": id_orden, "id_user": id_usuario},
        ).scalar()
        self.db.commit()
        return id_inf

    # -------------------------------------------------------------
    # Creación de órdenes (Tests 12 - 22)
    # -------------------------------------------------------------
    def test_12_orden_paciente_existente_numeracion_correlativa(self) -> None:
        """12. Orden para paciente existente → 201, INCOMPLETO, autor correcto, numero_orden_paciente 1 y luego 2."""
        paciente = self.crear_paciente_test(ci="1212121", nombres="Juan", apellido_paterno="Perez")

        payload1 = {
            "id_paciente": paciente.id_paciente,
            "estudios": [{"codigo": "HEMOGRAMA"}],
            "edad_anios": 25,
        }
        r1 = self.client.post("/api/ordenes", json=payload1, headers=self.bio_headers)
        self.assertEqual(r1.status_code, 201)
        data1 = r1.json()["orden"]
        self.assertEqual(data1["numero_orden_paciente"], 1)
        self.assertEqual(data1["estado_trabajo"], "INCOMPLETO")
        self.assertEqual(data1["autor"]["id"], self.bio.id_usuario)

        payload2 = {
            "id_paciente": paciente.id_paciente,
            "estudios": [{"codigo": "COAGULOGRAMA"}],
            "edad_anios": 25,
        }
        r2 = self.client.post("/api/ordenes", json=payload2, headers=self.bio_headers)
        self.assertEqual(r2.status_code, 201)
        data2 = r2.json()["orden"]
        self.assertEqual(data2["numero_orden_paciente"], 2)

    def test_13_alta_paciente_mas_orden_atomica_revierte_si_falla(self) -> None:
        """13. Alta de paciente + orden en una transacción; si la orden es inválida no queda el paciente."""
        payload_invalido = {
            "paciente": {
                "ci": "1313131",
                "sin_ci": False,
                "nombres": "Paciente",
                "apellido_paterno": "Atomico",
                "sexo": "M",
            },
            "estudios": [{"codigo": "ESTUDIO_FANTASMA_NO_EXISTE"}],  # Inválido
            "edad_anios": 30,
        }
        resp = self.client.post("/api/ordenes", json=payload_invalido, headers=self.bio_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["codigo"], "VALIDACION")

        # Comprobar que el paciente NO fue persistido
        p_db = self.db.query(Paciente).filter(Paciente.ci == "1313131").first()
        self.assertIsNone(p_db, "El paciente no debió persistirse tras fallar la orden")

        # Alta válida paciente + orden
        payload_valido = {
            "paciente": {
                "ci": "1313131",
                "sin_ci": False,
                "nombres": "Paciente",
                "apellido_paterno": "Atomico",
                "sexo": "M",
            },
            "estudios": [{"codigo": "HEMOGRAMA"}],
            "edad_anios": 30,
        }
        r_ok = self.client.post("/api/ordenes", json=payload_valido, headers=self.bio_headers)
        self.assertEqual(r_ok.status_code, 201)
        p_creado = self.db.query(Paciente).filter(Paciente.ci == "1313131").first()
        self.assertIsNotNone(p_creado)

    def test_14_xor_id_paciente_y_paciente(self) -> None:
        """14. id_paciente y paciente a la vez, o ninguno → 400."""
        # Ambos
        p1 = {
            "id_paciente": 1,
            "paciente": {"ci": "1414141", "sin_ci": False, "nombres": "A", "apellido_paterno": "B", "sexo": "M"},
            "estudios": [{"codigo": "HEMOGRAMA"}],
        }
        r1 = self.client.post("/api/ordenes", json=p1, headers=self.bio_headers)
        self.assertEqual(r1.status_code, 400)
        self.assertEqual(r1.json()["codigo"], "VALIDACION")

        # Ninguno
        p2 = {
            "estudios": [{"codigo": "HEMOGRAMA"}],
        }
        r2 = self.client.post("/api/ordenes", json=p2, headers=self.bio_headers)
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.json()["codigo"], "VALIDACION")

    def test_15_validaciones_de_estudios(self) -> None:
        """15. Sin estudios, estudio repetido, código inexistente, estudio inactivo → 400."""
        paciente = self.crear_paciente_test(ci="1515151")

        # Sin estudios
        r1 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [], "edad_anios": 20},
            headers=self.bio_headers,
        )
        self.assertEqual(r1.status_code, 400)

        # Estudio repetido
        r2 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "estudios": [{"codigo": "HEMOGRAMA"}, {"codigo": "HEMOGRAMA"}],
                "edad_anios": 20,
            },
            headers=self.bio_headers,
        )
        self.assertEqual(r2.status_code, 400)

        # Código inexistente
        r3 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "estudios": [{"codigo": "NO_EXISTE_123"}],
                "edad_anios": 20,
            },
            headers=self.bio_headers,
        )
        self.assertEqual(r3.status_code, 400)

        # Estudio inactivo
        est_target = self.db.query(Estudio).filter(Estudio.codigo == "ELECTROLITOS").first()
        self.assertIsNotNone(est_target)
        try:
            est_target.activo = False
            self.db.commit()

            r4 = self.client.post(
                "/api/ordenes",
                json={
                    "id_paciente": paciente.id_paciente,
                    "estudios": [{"codigo": "ELECTROLITOS"}],
                    "edad_anios": 20,
                },
                headers=self.bio_headers,
            )
            self.assertEqual(r4.status_code, 400)
        finally:
            est_target.activo = True
            self.db.commit()

    def test_16_validaciones_de_grupos(self) -> None:
        """16. grupos en estudio no parcial → 400; estudio parcial sin grupos → 400; grupo inexistente → 400."""
        paciente = self.crear_paciente_test(ci="1616161")

        # grupos en estudio no parcial (HEMOGRAMA) -> 400
        r1 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "estudios": [{"codigo": "HEMOGRAMA", "grupos": ["DIFERENCIAL"]}],
                "edad_anios": 20,
            },
            headers=self.bio_headers,
        )
        self.assertEqual(r1.status_code, 400)

        # estudio parcial (INMUNOSEROLOGIA) sin grupos -> 400
        r2 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "estudios": [{"codigo": "INMUNOSEROLOGIA"}],
                "edad_anios": 20,
            },
            headers=self.bio_headers,
        )
        self.assertEqual(r2.status_code, 400)

        # grupo inexistente -> 400
        r3 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "estudios": [{"codigo": "INMUNOSEROLOGIA", "grupos": ["GRUPO_NO_EXISTENTE"]}],
                "edad_anios": 20,
            },
            headers=self.bio_headers,
        )
        self.assertEqual(r3.status_code, 400)

    def test_17_congelamiento_version_y_orden_estudio_grupos(self) -> None:
        """17. Se guarda id_estudio_version activa y las filas de orden_estudio_grupos."""
        paciente = self.crear_paciente_test(ci="1717171")
        version_inmuno = (
            self.db.query(EstudioVersion)
            .join(Estudio)
            .filter(Estudio.codigo == "INMUNOSEROLOGIA", EstudioVersion.activa == True)
            .first()
        )
        self.assertIsNotNone(version_inmuno)

        payload = {
            "id_paciente": paciente.id_paciente,
            "estudios": [
                {"codigo": "INMUNOSEROLOGIA", "grupos": ["VIH", "PCR_SEMICUANT"]},
            ],
            "edad_anios": 22,
        }
        resp = self.client.post("/api/ordenes", json=payload, headers=self.bio_headers)
        self.assertEqual(resp.status_code, 201)
        id_orden = resp.json()["orden"]["id"]

        oe = self.db.query(OrdenEstudio).filter(OrdenEstudio.id_orden == id_orden).first()
        self.assertIsNotNone(oe)
        self.assertEqual(oe.id_estudio_version, version_inmuno.id_estudio_version)

        grupos_db = self.db.query(OrdenEstudioGrupo).filter(OrdenEstudioGrupo.id_orden_estudio == oe.id_orden_estudio).all()
        nombres_grupos = {g.grupo for g in grupos_db}
        self.assertEqual(nombres_grupos, {"VIH", "PCR_SEMICUANT"})

    def test_18_calculo_edad_con_reloj_y_validaciones(self) -> None:
        """18. Edad calculada con fecha de nacimiento (reloj simulado) e ignorando la enviada; sin fecha de nacimiento y sin edad_anios → 400; edad_meses fuera de 0–11 → 400."""
        # Fijar reloj simulado a 2026-10-11
        set_simulated_time(date(2026, 10, 11))

        # Paciente con fecha_nacimiento = 2000-05-11 (exactamente 26 años, 5 meses)
        paciente = self.crear_paciente_test(ci="1818181", fecha_nacimiento=date(2000, 5, 11))

        # El cliente envía edad_anios errónea (ej. 99), el servidor debe IGNORARLA y calcular 26 años, 5 meses
        payload = {
            "id_paciente": paciente.id_paciente,
            "estudios": [{"codigo": "HEMOGRAMA"}],
            "edad_anios": 99,
            "edad_meses": 9,
        }
        resp = self.client.post("/api/ordenes", json=payload, headers=self.bio_headers)
        self.assertEqual(resp.status_code, 201)
        orden_data = resp.json()["orden"]
        self.assertEqual(orden_data["edad_anios"], 26)
        self.assertEqual(orden_data["edad_meses"], 5)

        # Paciente SIN fecha de nacimiento
        paciente_sin_fn = self.crear_paciente_test(ci="1818182", fecha_nacimiento=None)

        # Sin edad_anios -> 400
        r_no_edad = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente_sin_fn.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}]},
            headers=self.bio_headers,
        )
        self.assertEqual(r_no_edad.status_code, 400)

        # edad_meses fuera de rango (12) -> 400
        r_mes_inv = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente_sin_fn.id_paciente,
                "estudios": [{"codigo": "HEMOGRAMA"}],
                "edad_anios": 30,
                "edad_meses": 12,
            },
            headers=self.bio_headers,
        )
        self.assertEqual(r_mes_inv.status_code, 400)

    def test_19_perfil_inexistente_y_perfil_con_estudios_distintos(self) -> None:
        """19. perfil inexistente → 400; perfil válido se guarda aunque estudios difiera."""
        paciente = self.crear_paciente_test(ci="1919191")

        # Perfil inexistente -> 400
        r1 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "perfil": "PERFIL_INEXISTENTE",
                "estudios": [{"codigo": "HEMOGRAMA"}],
                "edad_anios": 25,
            },
            headers=self.bio_headers,
        )
        self.assertEqual(r1.status_code, 400)

        # Perfil válido guardado aunque estudios difieran del perfil
        r2 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "perfil": "HC-QMC-SEROL-EGO",
                "estudios": [{"codigo": "HEMOGRAMA"}],  # Solo 1 estudio en lugar de los 8 del perfil
                "edad_anios": 25,
            },
            headers=self.bio_headers,
        )
        self.assertEqual(r2.status_code, 201)
        orden_data = r2.json()["orden"]
        self.assertIsNotNone(orden_data["perfil"])
        self.assertEqual(orden_data["perfil"]["codigo"], "HC-QMC-SEROL-EGO")

    def test_20_admin_no_puede_crear_ordenes(self) -> None:
        """20. ADMIN no puede crear → 403."""
        paciente = self.crear_paciente_test(ci="2020202")
        resp = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.admin_headers,
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["codigo"], "PROHIBIDO")

    def test_21_concurrencia_creacion_mismo_paciente(self) -> None:
        """21. Dos creaciones concurrentes (hilos) para el mismo paciente → números 1 y 2, sin error 500 ni repetidos."""
        paciente = self.crear_paciente_test(ci="2121212")

        def crear_orden_hilo(estudio_cod: str) -> dict[str, Any]:
            c = self.client
            res = c.post(
                "/api/ordenes",
                json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": estudio_cod}], "edad_anios": 25},
                headers=self.bio_headers,
            )
            return {"status": res.status_code, "data": res.json()}

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(crear_orden_hilo, "HEMOGRAMA")
            fut2 = executor.submit(crear_orden_hilo, "COAGULOGRAMA")
            r1 = fut1.result()
            r2 = fut2.result()

        self.assertEqual(r1["status"], 201)
        self.assertEqual(r2["status"], 201)

        num1 = r1["data"]["orden"]["numero_orden_paciente"]
        num2 = r2["data"]["orden"]["numero_orden_paciente"]
        self.assertEqual({num1, num2}, {1, 2})

    def test_22_toma_muestra_futura(self) -> None:
        """22. Toma de muestra futura (> 5 min) → 400."""
        paciente = self.crear_paciente_test(ci="2222222")
        futura = ahora() + timedelta(minutes=10)

        resp = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "estudios": [{"codigo": "HEMOGRAMA"}],
                "edad_anios": 20,
                "fecha_hora_toma_muestra": futura.isoformat(),
            },
            headers=self.bio_headers,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["codigo"], "VALIDACION")

    # -------------------------------------------------------------
    # Detección de duplicados (Tests 23 - 28)
    # -------------------------------------------------------------
    def test_23_estudios_disjuntos_sin_advertencias(self) -> None:
        """23. Estudios disjuntos con borrador ajeno → 201, sin advertencias."""
        paciente = self.crear_paciente_test(ci="2323232")

        # Bio 1 crea orden con HEMOGRAMA
        r1 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )
        self.assertEqual(r1.status_code, 201)

        # Bio 2 crea orden para el mismo paciente con COAGULOGRAMA (disjunto)
        r2 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "COAGULOGRAMA"}], "edad_anios": 20},
            headers=self.bio2_headers,
        )
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(len(r2.json()["advertencias"]), 0)

    def test_24_solapamiento_parcial_emite_advertencia(self) -> None:
        """24. Solapamiento parcial → 201 con advertencias (autor + códigos, sin id de orden)."""
        paciente = self.crear_paciente_test(ci="2424242")

        # Bio 1 crea con HEMOGRAMA
        self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )

        # Bio 2 crea con HEMOGRAMA + COAGULOGRAMA (no es subconjunto, hay solapamiento parcial)
        r2 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "estudios": [{"codigo": "HEMOGRAMA"}, {"codigo": "COAGULOGRAMA"}],
                "edad_anios": 20,
            },
            headers=self.bio2_headers,
        )
        self.assertEqual(r2.status_code, 201)
        adv = r2.json()["advertencias"]
        self.assertEqual(len(adv), 1)
        self.assertEqual(adv[0]["tipo"], "SOLAPAMIENTO")
        self.assertEqual(adv[0]["autor"]["nombres"], self.bio.nombres)
        self.assertEqual(adv[0]["autor"]["apellido_paterno"], self.bio.apellido_paterno)
        self.assertEqual(adv[0]["estudios"], ["HEMOGRAMA"])
        self.assertNotIn("id_orden", str(adv[0]))

    def test_25_subconjunto_bloquea_409_orden_duplicada_en_curso(self) -> None:
        """25. Nueva ⊆ borrador ajeno → 409 ORDEN_DUPLICADA_EN_CURSO con detalle; no se crea paciente ni orden."""
        # Bio 1 tiene borrador con HEMOGRAMA y COAGULOGRAMA
        r_bio1 = self.client.post(
            "/api/ordenes",
            json={
                "paciente": {"ci": "2525251", "sin_ci": False, "nombres": "Pedro", "apellido_paterno": "Vargas", "sexo": "M"},
                "estudios": [{"codigo": "HEMOGRAMA"}, {"codigo": "COAGULOGRAMA"}],
                "edad_anios": 20,
            },
            headers=self.bio_headers,
        )
        self.assertEqual(r_bio1.status_code, 201)
        paciente_id = r_bio1.json()["orden"]["paciente"]["id"]

        # Bio 2 intenta crear orden con solo HEMOGRAMA (nueva ⊆ ajena)
        r_bio2 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente_id, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio2_headers,
        )
        self.assertEqual(r_bio2.status_code, 409)
        self.assertEqual(r_bio2.json()["codigo"], "ORDEN_DUPLICADA_EN_CURSO")
        detalle = r_bio2.json()["detalle"]
        self.assertEqual(detalle["autor"]["nombres"], self.bio.nombres)
        self.assertEqual(detalle["autor"]["apellido_paterno"], self.bio.apellido_paterno)
        self.assertEqual(detalle["estudios"], ["HEMOGRAMA"])
        self.assertNotIn("id_orden", str(detalle))

    def test_26_no_bloquea_si_es_propio_bloqueada_publicada_o_distinto_paciente(self) -> None:
        """26. No bloquea si el borrador es propio, está bloqueada, está PUBLICADA, o es de otro paciente."""
        paciente_a = self.crear_paciente_test(ci="2626261")
        paciente_b = self.crear_paciente_test(ci="2626262")

        # 1. Borrador propio: Bio 1 crea orden 1 con HEMOGRAMA, y luego orden 2 con HEMOGRAMA
        r_propia_1 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente_a.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )
        self.assertEqual(r_propia_1.status_code, 201)

        r_propia_2 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente_a.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )
        self.assertEqual(r_propia_2.status_code, 201, "No debe bloquear si el borrador existente es del mismo autor")

        # 2. Distinto paciente: Bio 2 crea con HEMOGRAMA para paciente B -> sin bloqueo ni advertencia
        r_otro_pac = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente_b.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio2_headers,
        )
        self.assertEqual(r_otro_pac.status_code, 201)
        self.assertEqual(len(r_otro_pac.json()["advertencias"]), 0)

        # 3. Borrador ajeno pero bloqueada = TRUE
        orden_a_bio1 = self.db.query(Orden).filter(Orden.id_orden == r_propia_1.json()["orden"]["id"]).first()
        self.assertIsNotNone(orden_a_bio1)
        id_inf = self.crear_informe_bloqueo(orden_a_bio1.id_orden, self.bio.id_usuario)
        orden_a_bio1.bloqueada = True
        orden_a_bio1.bloqueada_en = ahora()
        orden_a_bio1.bloqueada_por_informe = id_inf
        # Eliminar temporalmente orden 2 para que no influya
        self.db.query(Orden).filter(Orden.id_orden == r_propia_2.json()["orden"]["id"]).delete()
        self.db.commit()

        r_bio2_bloq = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente_a.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio2_headers,
        )
        self.assertEqual(r_bio2_bloq.status_code, 201)

    def test_27_granularidad_por_grupo(self) -> None:
        """27. Granularidad por grupo: INMUNOSEROLOGIA:VIH vs INMUNOSEROLOGIA:PCR_SEMICUANT son disjuntos (201); VIH vs VIH bloquea."""
        paciente = self.crear_paciente_test(ci="2727271")

        # Bio 1 crea orden con VIH
        r1 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "estudios": [{"codigo": "INMUNOSEROLOGIA", "grupos": ["VIH"]}],
                "edad_anios": 20,
            },
            headers=self.bio_headers,
        )
        self.assertEqual(r1.status_code, 201)

        # Bio 2 pide PCR_SEMICUANT -> disjunto, 201, sin advertencias
        r2 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "estudios": [{"codigo": "INMUNOSEROLOGIA", "grupos": ["PCR_SEMICUANT"]}],
                "edad_anios": 20,
            },
            headers=self.bio2_headers,
        )
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(len(r2.json()["advertencias"]), 0)

        # Bio 2 pide VIH -> subconjunto de la orden de Bio 1 -> 409 ORDEN_DUPLICADA_EN_CURSO
        r3 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "estudios": [{"codigo": "INMUNOSEROLOGIA", "grupos": ["VIH"]}],
                "edad_anios": 20,
            },
            headers=self.bio2_headers,
        )
        self.assertEqual(r3.status_code, 409)
        self.assertEqual(r3.json()["codigo"], "ORDEN_DUPLICADA_EN_CURSO")

    def test_28_cubierta_solo_por_union_de_dos_borradores_no_bloquea(self) -> None:
        """28. Nueva ⊄ ningún borrador individual (cubierta solo por la unión de dos ajenos) → no bloquea (solo advertencias)."""
        paciente = self.crear_paciente_test(ci="2828281")

        # Bio 1 crea borrador con HEMOGRAMA
        self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )

        # Bio 2 crea borrador con COAGULOGRAMA
        self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "COAGULOGRAMA"}], "edad_anios": 20},
            headers=self.bio2_headers,
        )

        # Un tercer bioquímico Bio 3 pide HEMOGRAMA + COAGULOGRAMA
        bio3 = self.crear_usuario_test(usuario="bioq_3", rol="BIOQUIMICO", ci="2828283")
        login_bio3 = self.client.post("/api/auth/login", json={"usuario": "bioq_3", "password": "ClaveSegura123!"})
        headers_bio3 = {"Authorization": f"Bearer {login_bio3.json()['access_token']}"}

        r3 = self.client.post(
            "/api/ordenes",
            json={
                "id_paciente": paciente.id_paciente,
                "estudios": [{"codigo": "HEMOGRAMA"}, {"codigo": "COAGULOGRAMA"}],
                "edad_anios": 20,
            },
            headers=headers_bio3,
        )
        # No debe bloquear: debe dar 201 y 2 advertencias (una por cada borrador solapado)
        self.assertEqual(r3.status_code, 201)
        adv = r3.json()["advertencias"]
        self.assertEqual(len(adv), 2)

    # -------------------------------------------------------------
    # Lectura y privacidad (Tests 29 - 32)
    # -------------------------------------------------------------
    def test_29_bioquimico_lista_solo_sus_ordenes_y_filtros(self) -> None:
        """29. BIOQUIMICO lista solo sus órdenes; filtros estado e id_paciente."""
        paciente_1 = self.crear_paciente_test(ci="2929291")
        paciente_2 = self.crear_paciente_test(ci="2929292")

        # Bio 1 crea orden en paciente 1
        r_b1 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente_1.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )
        # Bio 2 crea orden en paciente 2
        r_b2 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente_2.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio2_headers,
        )

        # Bio 1 lista: solo debe ver su orden
        r_list = self.client.get("/api/ordenes", headers=self.bio_headers)
        self.assertEqual(r_list.status_code, 200)
        items = r_list.json()["items"]
        ids = [it["id"] for it in items]
        self.assertIn(r_b1.json()["orden"]["id"], ids)
        self.assertNotIn(r_b2.json()["orden"]["id"], ids)

        # Filtro id_paciente
        r_filtro_pac = self.client.get(f"/api/ordenes?id_paciente={paciente_1.id_paciente}", headers=self.bio_headers)
        self.assertEqual(r_filtro_pac.json()["total"], 1)

    def test_30_get_orden_ajena_responde_404_para_bioquimico(self) -> None:
        """30. GET /api/ordenes/{id} de orden ajena → 404 para BIOQUIMICO."""
        paciente = self.crear_paciente_test(ci="3030301")
        r_b1 = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )
        id_orden = r_b1.json()["orden"]["id"]

        # Bio 2 intenta consultar la orden de Bio 1 -> 404 (D2-07)
        r_ajena = self.client.get(f"/api/ordenes/{id_orden}", headers=self.bio2_headers)
        self.assertEqual(r_ajena.status_code, 404)
        self.assertEqual(r_ajena.json()["codigo"], "NO_ENCONTRADO")

    def test_31_admin_lista_todas_y_audita_admin_ve_privado(self) -> None:
        """31. ADMIN lista todas y se registra un ADMIN_VE_PRIVADO por petición (con cantidad); GET ajena registra id_objetivo=autor; lista vacía no registra."""
        # Limpiar log de seguridad previo
        self.db.query(LogSeguridad).delete()
        self.db.commit()

        # Lista vacía para ADMIN -> no debe registrar evento
        r_vacia = self.client.get("/api/ordenes", headers=self.admin_headers)
        self.assertEqual(r_vacia.status_code, 200)
        self.assertEqual(r_vacia.json()["total"], 0)
        eventos_vacios = self.db.query(LogSeguridad).filter(LogSeguridad.accion == "ADMIN_VE_PRIVADO").count()
        self.assertEqual(eventos_vacios, 0)

        # Crear orden como Bio 1
        paciente = self.crear_paciente_test(ci="3131311")
        r_ord = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )
        id_orden = r_ord.json()["orden"]["id"]

        # ADMIN lista órdenes (con cantidad >= 1) -> 1 evento ADMIN_VE_PRIVADO
        r_admin_list = self.client.get("/api/ordenes", headers=self.admin_headers)
        self.assertEqual(r_admin_list.status_code, 200)
        self.assertGreaterEqual(r_admin_list.json()["total"], 1)

        evento_list = (
            self.db.query(LogSeguridad)
            .filter(LogSeguridad.accion == "ADMIN_VE_PRIVADO", LogSeguridad.id_objetivo == None)
            .first()
        )
        self.assertIsNotNone(evento_list)
        self.assertEqual(evento_list.detalle["recurso"], "ordenes")
        self.assertGreaterEqual(evento_list.detalle["cantidad"], 1)

        # ADMIN hace GET de orden ajena -> evento con id_objetivo = autor
        r_admin_get = self.client.get(f"/api/ordenes/{id_orden}", headers=self.admin_headers)
        self.assertEqual(r_admin_get.status_code, 200)

        evento_get = (
            self.db.query(LogSeguridad)
            .filter(LogSeguridad.accion == "ADMIN_VE_PRIVADO", LogSeguridad.id_objetivo == self.bio.id_usuario)
            .first()
        )
        self.assertIsNotNone(evento_get)
        self.assertEqual(evento_get.detalle["recurso"], "orden")
        self.assertEqual(evento_get.detalle["id_orden"], id_orden)

    def test_32_admin_no_puede_patch_ni_delete(self) -> None:
        """32. ADMIN no puede PATCH ni DELETE → 403."""
        paciente = self.crear_paciente_test(ci="3232321")
        r_ord = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )
        id_orden = r_ord.json()["orden"]["id"]

        r_patch = self.client.patch(
            f"/api/ordenes/{id_orden}",
            json={"fila_version": 1, "origen_solicitud": "Clinica"},
            headers=self.admin_headers,
        )
        self.assertEqual(r_patch.status_code, 403)
        self.assertEqual(r_patch.json()["codigo"], "PROHIBIDO")

        r_del = self.client.delete(f"/api/ordenes/{id_orden}", headers=self.admin_headers)
        self.assertEqual(r_del.status_code, 403)
        self.assertEqual(r_del.json()["codigo"], "PROHIBIDO")

    # -------------------------------------------------------------
    # Edición y descarte (Tests 33 - 36)
    # -------------------------------------------------------------
    def test_33_patch_fila_version_y_concurrencia_optimista(self) -> None:
        """33. PATCH con fila_version correcta la incrementa; incorrecta → 409 CONFLICTO_VERSION; dos PATCH simultáneos → uno gana y otro 409."""
        paciente = self.crear_paciente_test(ci="3333331")
        r_ord = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )
        id_orden = r_ord.json()["orden"]["id"]

        # Versión incorrecta (ej. 99) -> 409 CONFLICTO_VERSION
        r_err = self.client.patch(
            f"/api/ordenes/{id_orden}",
            json={"fila_version": 99, "origen_solicitud": "Emergencia"},
            headers=self.bio_headers,
        )
        self.assertEqual(r_err.status_code, 409)
        self.assertEqual(r_err.json()["codigo"], "CONFLICTO_VERSION")

        # Versión correcta (1) -> 200, fila_version pasa a 2
        r_ok = self.client.patch(
            f"/api/ordenes/{id_orden}",
            json={"fila_version": 1, "origen_solicitud": "Emergencia"},
            headers=self.bio_headers,
        )
        self.assertEqual(r_ok.status_code, 200)
        self.assertEqual(r_ok.json()["fila_version"], 2)

        # Concurrencia de 2 PATCH con la misma versión (2)
        def enviar_patch(origen: str) -> int:
            c = self.client
            res = c.patch(
                f"/api/ordenes/{id_orden}",
                json={"fila_version": 2, "origen_solicitud": origen},
                headers=self.bio_headers,
            )
            return res.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(enviar_patch, "Sala A")
            fut2 = executor.submit(enviar_patch, "Sala B")
            st1 = fut1.result()
            st2 = fut2.result()

        # Uno gana (200) y el otro recibe 409
        self.assertEqual({st1, st2}, {200, 409})

    def test_34_patch_campos_prohibidos(self) -> None:
        """34. PATCH con estudios, estado o id_paciente → 400."""
        paciente = self.crear_paciente_test(ci="3434341")
        r_ord = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )
        id_orden = r_ord.json()["orden"]["id"]

        # Intentar modificar estudios
        r1 = self.client.patch(
            f"/api/ordenes/{id_orden}",
            json={"fila_version": 1, "estudios": [{"codigo": "COAGULOGRAMA"}]},
            headers=self.bio_headers,
        )
        self.assertEqual(r1.status_code, 400)
        self.assertEqual(r1.json()["codigo"], "VALIDACION")

        # Intentar modificar estado_trabajo
        r2 = self.client.patch(
            f"/api/ordenes/{id_orden}",
            json={"fila_version": 1, "estado_trabajo": "COMPLETO"},
            headers=self.bio_headers,
        )
        self.assertEqual(r2.status_code, 400)

        # Intentar modificar id_paciente
        r3 = self.client.patch(
            f"/api/ordenes/{id_orden}",
            json={"fila_version": 1, "id_paciente": 999},
            headers=self.bio_headers,
        )
        self.assertEqual(r3.status_code, 400)

    def test_35_delete_descarte_de_borrador_y_registro_historico(self) -> None:
        """35. DELETE por el autor → 204, desaparecen orden y filas hijas, aparece fila en borradores_descartados con estado_trabajo y estaba_bloqueada correctos; otro BIOQUIMICO → 404; ADMIN → 403; orden PUBLICADA → 409."""
        paciente = self.crear_paciente_test(ci="3535351")
        r_ord = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "HEMOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )
        id_orden = r_ord.json()["orden"]["id"]

        # Otro bioquímico -> 404
        r_otro = self.client.delete(f"/api/ordenes/{id_orden}", headers=self.bio2_headers)
        self.assertEqual(r_otro.status_code, 404)

        # ADMIN -> 403
        r_adm = self.client.delete(f"/api/ordenes/{id_orden}", headers=self.admin_headers)
        self.assertEqual(r_adm.status_code, 403)

        # Orden PUBLICADA (forzada por SQL) -> 409
        self.db.execute(text("UPDATE laboratorio.ordenes SET estado_trabajo = 'PUBLICADA' WHERE id_orden = :id"), {"id": id_orden})
        self.db.commit()

        r_pub = self.client.delete(f"/api/ordenes/{id_orden}", headers=self.bio_headers)
        self.assertEqual(r_pub.status_code, 409)
        self.assertEqual(r_pub.json()["codigo"], "CONFLICTO")

        # Regresar a INCOMPLETO y marcar bloqueada = True para validar flag en descarte
        # Usamos una orden dummy para el informe para evitar restricción de FK al borrar id_orden
        r_dummy = self.client.post(
            "/api/ordenes",
            json={"id_paciente": paciente.id_paciente, "estudios": [{"codigo": "COAGULOGRAMA"}], "edad_anios": 20},
            headers=self.bio_headers,
        )
        id_dummy = r_dummy.json()["orden"]["id"]
        id_inf = self.crear_informe_bloqueo(id_dummy, self.bio.id_usuario)
        now_dt = ahora()
        self.db.execute(
            text(
                "UPDATE laboratorio.ordenes SET estado_trabajo = 'INCOMPLETO', bloqueada = TRUE, bloqueada_en = :now, bloqueada_por_informe = :id_inf WHERE id_orden = :id"
            ),
            {"id": id_orden, "now": now_dt, "id_inf": id_inf},
        )
        self.db.commit()

        # DELETE por el autor -> 204
        r_del = self.client.delete(f"/api/ordenes/{id_orden}", headers=self.bio_headers)
        self.assertEqual(r_del.status_code, 204)

        # Verificar que la orden desapareció de BD y en cascada
        self.assertIsNone(self.db.query(Orden).filter(Orden.id_orden == id_orden).first())
        self.assertEqual(self.db.query(OrdenEstudio).filter(OrdenEstudio.id_orden == id_orden).count(), 0)

        # Verificar fila en borradores_descartados
        descarte = self.db.query(BorradorDescartado).filter(BorradorDescartado.id_orden == id_orden).first()
        self.assertIsNotNone(descarte)
        self.assertEqual(descarte.id_paciente, paciente.id_paciente)
        self.assertEqual(descarte.id_usuario, self.bio.id_usuario)
        self.assertEqual(descarte.estado_trabajo, "INCOMPLETO")
        self.assertTrue(descarte.estaba_bloqueada)
        self.assertIsNone(descarte.folio_causa)

    def test_36_trigger_orden_requiere_estudios_a_nivel_bd(self) -> None:
        """36. A nivel de BD: insertar una orden sin estudios y confirmar la transacción falla (constraint trigger del esquema)."""
        paciente = self.crear_paciente_test(ci="3636361")
        now = ahora()

        # Intentar insertar una orden sin hijos en orden_estudios
        orden_huerfana = Orden(
            id_paciente=paciente.id_paciente,
            numero_orden_paciente=999,
            id_usuario_autor=self.bio.id_usuario,
            estado_trabajo="INCOMPLETO",
            bloqueada=False,
            fecha_solicitud=now.date(),
            creado_en=now,
            actualizado_en=now,
        )
        self.db.add(orden_huerfana)

        # Al hacer commit debe dispararse el constraint trigger trg_orden_requiere_estudios
        with self.assertRaises(Exception):
            self.db.commit()

        self.db.rollback()
