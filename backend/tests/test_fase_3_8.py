"""
Pruebas para Fase 3.8:
- Gestión dinámica de estudios en la orden (POST, DELETE, PUT grupos).
- Auto-cancelación y descarte si se eliminan todos los estudios.
- Overrides de rangos de referencia y reestablecimiento.
- Observaciones por estudio y generales de la orden.
"""
from __future__ import annotations

from typing import Any
from sqlalchemy import text

from app.models.catalog import Estudio
from app.models.order import Orden
from app.models.patient import Paciente
from tests.base import IntegrationTestCase


class TestFase38GestionYRangos(IntegrationTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.bio = self.crear_usuario_test(
            usuario="bioq_f38",
            password="PasswordBio123!",
            rol="BIOQUIMICO",
            ci="8200001",
        )
        login_res = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq_f38", "password": "PasswordBio123!"},
        )
        self.bio_token = login_res.json()["access_token"]
        self.bio_headers = {"Authorization": f"Bearer {self.bio_token}", "X-LIS-Client": "web"}

        # Crear paciente
        pac = Paciente(
            ci="9200001",
            nombres="Carlos",
            apellido_paterno="Medina",
            sexo="M",
            creado_por=self.bio.id_usuario,
        )
        self.db.add(pac)
        self.db.commit()
        self.id_paciente = pac.id_paciente

    def crear_orden_test(self, codigos_estudios: list[str], grupos_inmuno: list[str] | None = None) -> int:
        estudios_payload = []
        for c in codigos_estudios:
            if c == "INMUNOSEROLOGIA" and grupos_inmuno:
                estudios_payload.append({"codigo": c, "grupos": grupos_inmuno})
            else:
                estudios_payload.append({"codigo": c})

        res = self.client.post(
            "/api/ordenes",
            headers=self.bio_headers,
            json={
                "id_paciente": self.id_paciente,
                "estudios": estudios_payload,
                "edad_anios": 35,
                "edad_meses": 0,
            },
        )
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()["orden"]["id"]

    def test_01_agregar_estudio_a_orden(self) -> None:
        """Añadir un estudio nuevo a una orden existente en borrador."""
        id_orden = self.crear_orden_test(["QUIMICA_SANGUINEA"])

        # Añadir HEMOGRAMA
        res = self.client.post(
            f"/api/ordenes/{id_orden}/estudios",
            headers=self.bio_headers,
            json={"codigo": "HEMOGRAMA"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        codigos = [e["codigo"] for e in res.json()["estudios"]]
        self.assertIn("HEMOGRAMA", codigos)
        self.assertIn("QUIMICA_SANGUINEA", codigos)

        # Verificar en captura
        cap_res = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        self.assertEqual(cap_res.status_code, 200)
        cap_codigos = [e["codigo"] for e in cap_res.json()["estudios"]]
        self.assertIn("HEMOGRAMA", cap_codigos)

    def test_02_modificar_grupos_inmunoserologia(self) -> None:
        """Modificar subestudios de Inmunoserología en caliente."""
        id_orden = self.crear_orden_test(["INMUNOSEROLOGIA"], grupos_inmuno=["VIH"])

        # Obtener id_estudio de Inmunoserología
        cap_res = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        est_inmuno = next(e for e in cap_res.json()["estudios"] if e["codigo"] == "INMUNOSEROLOGIA")
        id_estudio = est_inmuno["id_estudio"]

        # Actualizar grupos a VIH y PCR_SEMICUANT
        res = self.client.put(
            f"/api/ordenes/{id_orden}/estudios/{id_estudio}/grupos",
            headers=self.bio_headers,
            json={"grupos": ["VIH", "PCR_SEMICUANT"]},
        )
        self.assertEqual(res.status_code, 200, res.text)

        # Verificar que ahora incluye parámetros de ambos grupos
        cap_act = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        est_act = next(e for e in cap_act.json()["estudios"] if e["codigo"] == "INMUNOSEROLOGIA")
        grupos_act = est_act["grupos_seleccionados"]
        self.assertIn("VIH", grupos_act)
        self.assertIn("PCR_SEMICUANT", grupos_act)

    def test_03_eliminar_estudio_parcial(self) -> None:
        """Eliminar un estudio de una orden con múltiples estudios."""
        id_orden = self.crear_orden_test(["QUIMICA_SANGUINEA", "HEMOGRAMA"])

        cap_res = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        est_hemo = next(e for e in cap_res.json()["estudios"] if e["codigo"] == "HEMOGRAMA")
        id_estudio = est_hemo["id_estudio"]

        # Eliminar HEMOGRAMA
        res = self.client.delete(
            f"/api/ordenes/{id_orden}/estudios/{id_estudio}",
            headers=self.bio_headers,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertFalse(res.json().get("orden_descartada", False))

        # Verificar que solo queda QUIMICA_SANGUINEA
        cap_act = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        codigos_restantes = [e["codigo"] for e in cap_act.json()["estudios"]]
        self.assertNotIn("HEMOGRAMA", codigos_restantes)
        self.assertIn("QUIMICA_SANGUINEA", codigos_restantes)

    def test_04_eliminar_ultimo_estudio_descarta_orden(self) -> None:
        """Eliminar el único estudio de una orden auto-cancela y descarta la orden."""
        id_orden = self.crear_orden_test(["QUIMICA_SANGUINEA"])

        cap_res = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        id_estudio = cap_res.json()["estudios"][0]["id_estudio"]

        # Eliminar el único estudio
        res = self.client.delete(
            f"/api/ordenes/{id_orden}/estudios/{id_estudio}",
            headers=self.bio_headers,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json().get("orden_descartada", False))

        # Comprobar que la orden ya no existe como borrador activo (responde 404)
        get_res = self.client.get(f"/api/ordenes/{id_orden}", headers=self.bio_headers)
        self.assertEqual(get_res.status_code, 404)

        # Verificar en base de datos que se registró en borradores_descartados
        self.db.expire_all()
        fila_desc = self.db.execute(
            text("SELECT * FROM laboratorio.borradores_descartados WHERE id_orden = :id"),
            {"id": id_orden},
        ).first()
        self.assertIsNotNone(fila_desc)

    def test_05_rango_override_y_bandera_dinamica(self) -> None:
        """Un rango de referencia modificado evalúa la bandera contra los nuevos límites."""
        id_orden = self.crear_orden_test(["QUIMICA_SANGUINEA"])

        # GLICEMIA normal en catálogo: 70 - 110 mg/dL.
        # Si el bioquímico establece override a: límite inferior = 80, superior = 120
        # Un valor de 75 (que en catálogo sería NORMAL) debe ser evaluado como BAJO (< 80).
        put_res = self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            headers=self.bio_headers,
            json={
                "valores": {"GLICEMIA": "75"},
                "rangos_override": {
                    "GLICEMIA": {
                        "limite_inferior": 80,
                        "limite_superior": 120,
                        "texto": "80 - 120 mg/dL",
                        "reestablecer": False,
                    }
                },
            },
        )
        self.assertEqual(put_res.status_code, 200, put_res.text)

        # Verificar en captura
        cap_res = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        est_qmc = next(e for e in cap_res.json()["estudios"] if e["codigo"] == "QUIMICA_SANGUINEA")
        param_glu = next(p for s in est_qmc["secciones"] for p in s["parametros"] if p["codigo"] == "GLICEMIA")

        self.assertEqual(param_glu["bandera"], "BAJO")
        self.assertTrue(param_glu["referencia"]["modificada"])
        self.assertEqual(param_glu["referencia"]["inferior"], "80")

    def test_06_reestablecer_rango(self) -> None:
        """Reestablecer el rango borra el override y vuelve a evaluar con el catálogo."""
        id_orden = self.crear_orden_test(["QUIMICA_SANGUINEA"])

        # 1. Establecer override
        self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            headers=self.bio_headers,
            json={
                "valores": {"GLICEMIA": "75"},
                "rangos_override": {
                    "GLICEMIA": {
                        "limite_inferior": 80,
                        "limite_superior": 120,
                        "reestablecer": False,
                    }
                },
            },
        )

        # 2. Reestablecer al catálogo
        put_reset = self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            headers=self.bio_headers,
            json={
                "valores": {},
                "rangos_override": {
                    "GLICEMIA": {
                        "reestablecer": True,
                    }
                },
            },
        )
        self.assertEqual(put_reset.status_code, 200, put_reset.text)

        # Ahora 75 está entre 70 y 110 -> NORMAL
        cap_res = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        est_qmc = next(e for e in cap_res.json()["estudios"] if e["codigo"] == "QUIMICA_SANGUINEA")
        param_glu = next(p for s in est_qmc["secciones"] for p in s["parametros"] if p["codigo"] == "GLICEMIA")

        self.assertEqual(param_glu["bandera"], "NORMAL")
        self.assertFalse(param_glu["referencia"]["modificada"])

    def test_07_observaciones_estudio_y_orden(self) -> None:
        """Persistencia de observaciones específicas de estudio y generales de orden."""
        id_orden = self.crear_orden_test(["QUIMICA_SANGUINEA"])

        obs_est = "Muestra ligeramente hemolizada, procesada por duplicado."
        obs_ord = "Paciente en ayuno estricto de 12 horas. Repetir perfil en 3 meses."

        put_res = self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            headers=self.bio_headers,
            json={
                "valores": {"GLICEMIA": "90"},
                "observaciones_estudios": {"QUIMICA_SANGUINEA": obs_est},
                "observaciones_orden": obs_ord,
            },
        )
        self.assertEqual(put_res.status_code, 200, put_res.text)

        # Verificar en captura
        cap_res = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        data = cap_res.json()
        self.assertEqual(data["orden"]["observaciones"], obs_ord)

        est_qmc = next(e for e in data["estudios"] if e["codigo"] == "QUIMICA_SANGUINEA")
        self.assertEqual(est_qmc["observaciones"], obs_est)
