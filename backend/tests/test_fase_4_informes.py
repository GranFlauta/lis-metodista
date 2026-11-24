"""
Pruebas exhaustivas para Fase 4:
- Publicación oficial de órdenes con folio secuencial inmutable AAAA-NNNNNN.
- Publicación con observaciones opcionales y sólo campos utilizados.
- Snapshot JSON canónico y hash criptográfico SHA-256.
- Papelera lógica auditada con justificativo obligatorio.
- Restauración de papelera a estado RECICLAJE (bloqueo de impresión).
- Versionado formal V1 -> V2 -> V3 y tope de 3 versiones.
- Traza de auditoría append-only en informe_eventos.
- Inmutabilidad estricta garantizada por triggers de PostgreSQL.
"""
from __future__ import annotations

import re
from typing import Any
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models.order import Orden
from app.models.patient import Paciente
from app.models.report import Informe, InformeEvento
from app.models.result import LaboratorioConfig
from tests.base import IntegrationTestCase


class TestFase4PublicacionYPapelera(IntegrationTestCase):
    def test_separador_decimal_se_congela_al_publicar(self) -> None:
        import pypdfium2 as pdfium

        config = self.db.query(LaboratorioConfig).filter_by(clave="separador_decimal").one()
        original = config.valor
        try:
            config.valor = "."
            self.db.commit()
            id_orden = self.crear_y_completar_orden()
            publicada = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers)
            self.assertEqual(publicada.status_code, 201, publicada.text)
            folio = publicada.json()["folio"]
            self.db.expire_all()
            informe = self.db.query(Informe).filter_by(folio=folio).one()
            self.assertEqual(informe.snapshot_json["separador_decimal"], ".")
            config.valor = ","
            self.db.commit()
            respuesta = self.client.get(f"/api/informes/{folio}/pdf", headers=self.bio_headers)
            self.assertEqual(respuesta.status_code, 200)
            pdf = pdfium.PdfDocument(respuesta.content)
            try:
                pagina = pdf[0]
                try:
                    texto = pagina.get_textpage()
                    try:
                        self.assertIn("4.2", texto.get_text_range())
                    finally:
                        texto.close()
                finally:
                    pagina.close()
            finally:
                pdf.close()
        finally:
            config.valor = original
            self.db.commit()

    def setUp(self) -> None:
        super().setUp()
        self.bio = self.crear_usuario_test(
            usuario="bioq_f4",
            password="PasswordBio123!",
            rol="BIOQUIMICO",
            ci="8300001",
        )
        login_res = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq_f4", "password": "PasswordBio123!"},
        )
        self.bio_token = login_res.json()["access_token"]
        self.bio_headers = {"Authorization": f"Bearer {self.bio_token}", "X-LIS-Client": "web"}

        # Crear segundo bioquímico
        self.bio2 = self.crear_usuario_test(
            usuario="bioq2_f4",
            password="PasswordBio2_123!",
            rol="BIOQUIMICO",
            ci="8300002",
        )
        login2_res = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq2_f4", "password": "PasswordBio2_123!"},
        )
        self.bio2_token = login2_res.json()["access_token"]
        self.bio2_headers = {"Authorization": f"Bearer {self.bio2_token}", "X-LIS-Client": "web"}

        # Crear paciente
        pac = Paciente(
            ci="9300001",
            nombres="Elena",
            apellido_paterno="Rios",
            sexo="F",
            creado_por=self.bio.id_usuario,
        )
        self.db.add(pac)
        self.db.commit()
        self.id_paciente = pac.id_paciente

    def crear_y_completar_orden(self, observaciones_orden: str | None = "Informe validado y firmado electrónicamente.") -> int:
        """Crea una orden con estudio ELECTROLITOS y captura todos los resultados."""
        res_orden = self.client.post(
            "/api/ordenes",
            headers=self.bio_headers,
            json={
                "id_paciente": self.id_paciente,
                "estudios": [{"codigo": "ELECTROLITOS"}],
                "edad_anios": 28,
                "edad_meses": 0,
            },
        )
        self.assertEqual(res_orden.status_code, 201, res_orden.text)
        id_orden = res_orden.json()["orden"]["id"]

        # Cargar valores completos de ELECTROLITOS
        # SODIO (135-155), POTASIO (3.5-5.3), CLORO (98-106), CALCIO (8.5-10.5), MAGNESIO (1.7-2.5), FOSFORO (2.5-5.0)
        valores = {
            "SODIO": "140",
            "POTASIO": "4.2",
            "CLORO": "102",
            "CALCIO": "9.5",
            "MAGNESIO": "2.1",
            "FOSFORO": "3.8",
        }
        put_res = self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            headers=self.bio_headers,
            json={
                "valores": valores,
                "observaciones_orden": observaciones_orden,
            },
        )
        self.assertEqual(put_res.status_code, 200, put_res.text)
        return id_orden

    def test_01_publicar_orden_exitoso_genera_folio_y_snapshot(self) -> None:
        """Una orden completa con observaciones se publica con folio AAAA-NNNNNN y hash SHA-256."""
        id_orden = self.crear_y_completar_orden()

        # Publicar orden
        pub_res = self.client.post(
            f"/api/ordenes/{id_orden}/publicar",
            headers=self.bio_headers,
        )
        self.assertEqual(pub_res.status_code, 201, pub_res.text)
        data = pub_res.json()

        folio = data["folio"]
        self.assertTrue(re.match(r"^\d{4}-\d{6}$", folio), f"Folio inválido: {folio}")
        self.assertEqual(data["numero_version"], 1)
        self.assertEqual(data["estado"], "VIGENTE")
        self.assertEqual(len(data["snapshot_sha256"]), 64)

        # Verificar en base de datos estado PUBLICADA
        self.db.expire_all()
        orden_db = self.db.query(Orden).filter(Orden.id_orden == id_orden).first()
        self.assertIsNotNone(orden_db)
        self.assertEqual(orden_db.estado_trabajo, "PUBLICADA")

        # Verificar en informe_eventos
        evento_db = self.db.query(InformeEvento).filter(InformeEvento.folio == folio, InformeEvento.accion == "PUBLICACION").first()
        self.assertIsNotNone(evento_db)
        self.assertEqual(evento_db.id_usuario, self.bio.id_usuario)

    def test_02_publicar_sin_observaciones_finales(self) -> None:
        """Las observaciones opcionales no obligan a inventar texto para publicar."""
        id_orden = self.crear_y_completar_orden(observaciones_orden=None)

        pub_res = self.client.post(
            f"/api/ordenes/{id_orden}/publicar",
            headers=self.bio_headers,
        )
        self.assertEqual(pub_res.status_code, 201, pub_res.text)
        detalle = self.client.get(f"/api/informes/{pub_res.json()['folio']}", headers=self.bio_headers).json()
        self.assertIsNone(detalle["snapshot_json"]["orden"]["observaciones"])

    def test_borrador_de_catalogo_anterior_publica_un_solo_campo_sin_observaciones(self) -> None:
        respuesta = self.client.post("/api/ordenes", headers=self.bio_headers, json={
            "id_paciente": self.id_paciente, "edad_anios": 28,
            "estudios": [{"codigo": "ELECTROLITOS"}, {"codigo": "EGO"}],
        })
        self.assertEqual(respuesta.status_code, 201, respuesta.text)
        id_orden = respuesta.json()["orden"]["id"]
        orden = self.db.query(Orden).filter_by(id_orden=id_orden).one()
        configuraciones = [(oe.estudio_version, oe.estudio_version.configuracion_json) for oe in orden.estudios]
        try:
            for version, config in configuraciones:
                anterior = dict(config or {})
                anterior.pop("seleccion_campos", None)
                version.configuracion_json = anterior
            self.db.commit()
            captura = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers).json()
            self.assertFalse(captura["completitud"]["completo"])
            self.assertTrue(all(p["valor"] is None for e in captura["estudios"] for s in e["secciones"] for p in s["parametros"]))
            self.assertEqual(self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers).status_code, 400)
            guardado = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.bio_headers, json={"valores": {"SODIO": "140.25"}})
            self.assertTrue(guardado.json()["completitud"]["completo"], guardado.text)
            publicada = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers)
            self.assertEqual(publicada.status_code, 201, publicada.text)
            detalle = self.client.get(f"/api/informes/{publicada.json()['folio']}", headers=self.bio_headers).json()
            codigos = [p["codigo"] for e in detalle["snapshot_json"]["estudios"] for s in e["secciones"] for p in s["parametros"]]
            self.assertEqual(codigos, ["SODIO"])
            self.assertTrue(detalle["snapshot_json"]["orden"]["creado_en"])
        finally:
            for version, config in configuraciones:
                version.configuracion_json = config
            self.db.commit()

    def test_03_publicar_solo_campos_utilizados(self) -> None:
        """Publicar con un resultado utilizado omite los restantes campos vacíos."""
        res_orden = self.client.post(
            "/api/ordenes",
            headers=self.bio_headers,
            json={
                "id_paciente": self.id_paciente,
                "estudios": [{"codigo": "ELECTROLITOS"}],
                "edad_anios": 28,
                "edad_meses": 0,
            },
        )
        id_orden = res_orden.json()["orden"]["id"]

        # Solo capturar 1 de los 6 parámetros
        self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            headers=self.bio_headers,
            json={
                "valores": {"SODIO": "140"},
                "observaciones_orden": "Observaciones listas",
            },
        )

        pub_res = self.client.post(
            f"/api/ordenes/{id_orden}/publicar",
            headers=self.bio_headers,
        )
        self.assertEqual(pub_res.status_code, 201, pub_res.text)
        detalle = self.client.get(f"/api/informes/{pub_res.json()['folio']}", headers=self.bio_headers).json()
        parametros = [p["codigo"] for e in detalle["estudios_informe"] for sec in e["secciones"] for p in sec["parametros"]]
        self.assertEqual(parametros, ["SODIO"])

    def test_04_mover_a_papelera_y_consultar_papelera(self) -> None:
        """Solo el firmante puede enviar a papelera con justificativo; se lista en la papelera."""
        id_orden = self.crear_y_completar_orden()
        pub_res = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers)
        folio = pub_res.json()["folio"]

        # Intento de otro bioquímico -> 403 PROHIBIDO
        res_ajeno = self.client.post(
            f"/api/informes/{folio}/papelera",
            headers=self.bio2_headers,
            json={"justificativo": "Muestra presuntamente derramada."},
        )
        self.assertEqual(res_ajeno.status_code, 403)

        # Intento sin justificativo (< 5 caracteres) -> 422 o 400
        res_sin_just = self.client.post(
            f"/api/informes/{folio}/papelera",
            headers=self.bio_headers,
            json={"justificativo": "no"},
        )
        self.assertIn(res_sin_just.status_code, [400, 422])

        # Envío válido a papelera por el firmante
        motivo = "Muestra con sospecha de hemólisis no declarada en toma."
        res_pap = self.client.post(
            f"/api/informes/{folio}/papelera",
            headers=self.bio_headers,
            json={"justificativo": motivo},
        )
        self.assertEqual(res_pap.status_code, 200, res_pap.text)
        self.assertEqual(res_pap.json()["estado"], "PAPELERA")

        # Consultar papelera
        res_lista_pap = self.client.get("/api/informes/papelera", headers=self.bio_headers)
        self.assertEqual(res_lista_pap.status_code, 200)
        folios_en_papelera = [item["folio"] for item in res_lista_pap.json()]
        self.assertIn(folio, folios_en_papelera)

    def test_05_restaurar_de_papelera_a_reciclaje(self) -> None:
        """Restaurar de la papelera cambia el estado a RECICLAJE con justificativo y evento."""
        id_orden = self.crear_y_completar_orden()
        pub_res = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers)
        folio = pub_res.json()["folio"]

        # Mover a papelera
        self.client.post(
            f"/api/informes/{folio}/papelera",
            headers=self.bio_headers,
            json={"justificativo": "Error en identificación de tubo secundario."},
        )

        # Restaurar
        motivo_rest = "Se verificó la cadena de custodia con el tubo primario sin anomalías."
        res_rest = self.client.post(
            f"/api/informes/{folio}/restaurar",
            headers=self.bio_headers,
            json={"justificativo": motivo_rest},
        )
        self.assertEqual(res_rest.status_code, 200, res_rest.text)
        self.assertEqual(res_rest.json()["estado"], "RECICLAJE")

        # Comprobar evento RESTAURACION
        eventos_res = self.client.get(f"/api/informes/{folio}/historial", headers=self.bio_headers)
        self.assertEqual(eventos_res.status_code, 200)
        acciones = [e["accion"] for e in eventos_res.json()]
        self.assertIn("RESTAURACION", acciones)

    def test_06_versionado_v1_a_v2_y_v3_y_tope_v4(self) -> None:
        """Emisión de V2 y V3 desplaza versiones anteriores; intento de V4 es bloqueado (D-71)."""
        id_orden = self.crear_y_completar_orden()
        pub_res = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers)
        folio = pub_res.json()["folio"]

        # 1. Crear V2
        res_v2 = self.client.post(
            f"/api/informes/{folio}/versiones",
            headers=self.bio_headers,
            json={"justificativo": "Corrección de valor de potasio por repetición."},
        )
        self.assertEqual(res_v2.status_code, 201, res_v2.text)
        self.assertEqual(res_v2.json()["numero_version"], 2)
        self.assertEqual(res_v2.json()["estado"], "VIGENTE")

        # Verificar que V1 quedó en DESPLAZADO
        det_res = self.client.get(f"/api/informes/{folio}", headers=self.bio_headers)
        versiones = det_res.json()["versiones_disponibles"]
        v1 = next(v for v in versiones if v["numero_version"] == 1)
        v2 = next(v for v in versiones if v["numero_version"] == 2)
        self.assertEqual(v1["estado"], "DESPLAZADO")
        self.assertEqual(v2["estado"], "VIGENTE")

        # 2. Crear V3
        res_v3 = self.client.post(
            f"/api/informes/{folio}/versiones",
            headers=self.bio_headers,
            json={"justificativo": "Ajuste de observaciones clínicas por interconsulta."},
        )
        self.assertEqual(res_v3.status_code, 201)
        self.assertEqual(res_v3.json()["numero_version"], 3)

        # 3. Intento de V4 -> 409 CONFLICTO (Candado D-71)
        res_v4 = self.client.post(
            f"/api/informes/{folio}/versiones",
            headers=self.bio_headers,
            json={"justificativo": "Intento de cuarta versión no permitida."},
        )
        self.assertEqual(res_v4.status_code, 409)

    def test_07_traza_auditoria_completa(self) -> None:
        """La traza cronológica registra todas las etapas del ciclo de vida del informe."""
        id_orden = self.crear_y_completar_orden()
        pub_res = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers)
        folio = pub_res.json()["folio"]

        self.client.post(
            f"/api/informes/{folio}/versiones",
            headers=self.bio_headers,
            json={"justificativo": "Emisión de segunda versión aclaratoria."},
        )
        self.client.post(
            f"/api/informes/{folio}/papelera",
            headers=self.bio_headers,
            json={"justificativo": "Solicitud médica de anulación por cambio de diagnóstico."},
        )

        hist_res = self.client.get(f"/api/informes/{folio}/historial", headers=self.bio_headers)
        self.assertEqual(hist_res.status_code, 200)
        acciones = [ev["accion"] for ev in hist_res.json()]
        self.assertEqual(acciones, ["PUBLICACION", "EDICION_V2", "PAPELERA"])

    def test_pdf_solo_para_informe_vigente_y_con_evento_de_emision(self) -> None:
        id_orden = self.crear_y_completar_orden()
        folio = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers).json()["folio"]
        ruta = f"/api/informes/{folio}/pdf"
        respuesta = self.client.get(ruta, headers=self.bio_headers)
        self.assertEqual(respuesta.status_code, 200, respuesta.text[:100] if respuesta.status_code != 200 else "")
        self.assertTrue(respuesta.content.startswith(b"%PDF-"))
        self.assertEqual(respuesta.headers["content-type"], "application/pdf")
        eventos = self.client.get(f"/api/informes/{folio}/historial", headers=self.bio_headers).json()
        self.assertIn("IMPRESION", [evento["accion"] for evento in eventos])
        self.client.post(f"/api/informes/{folio}/papelera", headers=self.bio_headers, json={"justificativo": "Anulación de prueba ficticia"})
        self.assertEqual(self.client.get(ruta, headers=self.bio_headers).status_code, 403)
        self.client.post(f"/api/informes/{folio}/restaurar", headers=self.bio_headers, json={"justificativo": "Restauración de prueba ficticia"})
        self.assertEqual(self.client.get(ruta, headers=self.bio_headers).status_code, 403)

    def test_consulta_de_paginas_no_habilita_pdf_de_version_desplazada(self) -> None:
        id_orden = self.crear_y_completar_orden()
        folio = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers).json()["folio"]
        ruta = f"/api/informes/{folio}/vista-previa?version=1"
        self.assertEqual(self.client.get(ruta).status_code, 401)
        original = self.client.get(f"/api/informes/{folio}", headers=self.bio_headers).json()
        respuesta = self.client.get(ruta, headers=self.bio_headers)
        self.assertEqual(respuesta.status_code, 200, respuesta.text[:100] if respuesta.status_code != 200 else "")
        self.assertEqual(respuesta.json()["formato"], "Carta")
        self.assertTrue(respuesta.json()["paginas"][0]["imagen"].startswith("data:image/png;base64,"))
        self.assertIn("no-store", respuesta.headers["cache-control"])
        self.client.post(f"/api/informes/{folio}/versiones", headers=self.bio_headers, json={"justificativo": "Corrección de prueba ficticia"})
        self.assertEqual(self.client.get(ruta, headers=self.bio_headers).status_code, 200)
        self.assertEqual(self.client.get(f"/api/informes/{folio}/pdf?version=1", headers=self.bio_headers).status_code, 403)
        detalle = self.client.get(f"/api/informes/{folio}?version=1", headers=self.bio_headers).json()
        self.assertEqual(detalle["snapshot_sha256"], original["snapshot_sha256"])
        self.assertEqual(detalle["snapshot_json"], original["snapshot_json"])
        self.assertNotIn("IMPRESION", [e["accion"] for e in detalle["eventos"]])

    def test_pdf_no_expone_hash_matricula_ni_version_impresa(self) -> None:
        import pypdfium2 as pdfium

        self.bio.matricula_profesional = "REGISTRO_FICTICIO_NO_IMPRIMIR"
        self.db.commit()
        id_orden = self.crear_y_completar_orden(observaciones_orden=None)
        publicada = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers).json()
        respuesta = self.client.get(f"/api/informes/{publicada['folio']}/pdf", headers=self.bio_headers)
        self.assertEqual(respuesta.status_code, 200)
        with pdfium.PdfDocument(respuesta.content) as pdf:
            pagina = pdf[0]
            texto = pagina.get_textpage()
            contenido = texto.get_text_range()
            texto.close()
            pagina.close()
        self.assertIn("LIC. Test Usuario", contenido)
        self.assertIn("Hora de entrega de resultado:", contenido)
        for excluido in ("REGISTRO_FICTICIO_NO_IMPRIMIR", publicada["snapshot_sha256"], "SHA-256", "Versión V"):
            self.assertNotIn(excluido, contenido)
    def test_08_inmutabilidad_trigger_bd(self) -> None:
        """Trigger de PostgreSQL protege informes de DELETE y modificaciones indebidas de contenido."""
        id_orden = self.crear_y_completar_orden()
        pub_res = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers)
        folio = pub_res.json()["folio"]

        # Intento de DELETE SQL directo sobre el informe oficial
        with self.assertRaises(DBAPIError):
            self.db.execute(
                text("DELETE FROM laboratorio.informes WHERE folio = :f"),
                {"f": folio},
            )
            self.db.commit()
        self.db.rollback()
