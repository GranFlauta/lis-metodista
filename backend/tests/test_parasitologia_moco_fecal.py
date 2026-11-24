"""Captura libre de Moco fecal y compatibilidad del catálogo anterior."""
import importlib.util
from pathlib import Path
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
import pypdfium2 as pdfium

from app.catalog.definitions import MOCO_FECAL_CAMPOS, PARASITOLOGIA
from app.core.errors import ValidacionError
from app.models.catalog import EstudioVersion, Parametro
from app.reports.pdf import generar_informe_pdf, renderizar_html_informe
from app.services.evaluacion_service import normalizar_y_validar_valor_entrada
from tests.base import IntegrationTestCase
from tests.test_pdf_report import documento_aprobado


class MocoFecalTextoTests(unittest.TestCase):
    def test_orden_de_los_diez_campos_y_sin_selecciones(self):
        campos = [p for p in PARASITOLOGIA.parametros if p.grupo == "MOCO_FECAL"]
        self.assertEqual([p.nombre for p in campos], [
            "ASPECTO:", "RESTOS ALIMENTICIOS:", "PH:", "MOCO FECAL:", "FLORA BACTERIANA:",
            "ERITROCITOS:", "LEUCOCITOS:", "POLIMORFONUCLEARES:", "MONONUCLEARES:", "COPROPARASITOLOGÍA:",
        ])
        self.assertTrue(all(p.tipo == "TEXTO_LIBRE" and p.opciones is None and not p.obligatorio for p in campos))
        self.assertEqual([p.codigo for p in PARASITOLOGIA.parametros[-2:]], ["COPROPARASITOLOGICO_SIMPLE", "COPROPARASITOLOGICO_SERIADO"])
        self.assertTrue(all(p.tipo == "TEXTO_LIBRE" and p.opciones is None for p in PARASITOLOGIA.parametros[-2:]))

    def test_textos_extensos_vacios_y_cero_explicito(self):
        version = EstudioVersion(configuracion_json={"captura": PARASITOLOGIA.captura})
        largo = "Observación ficticia áéíóú.\n" * 2500
        for codigo, _ in MOCO_FECAL_CAMPOS:
            parametro = Parametro(codigo=codigo, tipo_campo="TEXTO_LIBRE", estudio_version=version)
            self.assertEqual(normalizar_y_validar_valor_entrada(parametro, largo), (None, largo.strip()))
            self.assertEqual(normalizar_y_validar_valor_entrada(parametro, "0"), (None, "0"))
            self.assertEqual(normalizar_y_validar_valor_entrada(parametro, "  "), (None, None))
        otro = Parametro(codigo="OTRA_OBSERVACION", tipo_campo="TEXTO_LIBRE", estudio_version=version)
        with self.assertRaises(ValidacionError):
            normalizar_y_validar_valor_entrada(otro, "x" * 501)

    def test_pdf_conserva_texto_extenso_hasta_la_ultima_pagina(self):
        largo = "Texto ficticio para verificar paginación. " * 1000 + "FIN_VERIFICABLE_MOCO"
        documento = documento_aprobado(True)
        documento["estudios"] = [{"codigo": "PARASITOLOGIA", "nombre": "Parasitología", "secciones": [{
            "grupo": "MOCO_FECAL", "formato": "LISTA_TEXTO", "parametros": [{
                "codigo": "MOCO_FECAL_ASPECTO", "nombre": "ASPECTO:", "valor": largo, "tipo_campo": "TEXTO_LIBRE",
            }],
        }]}]
        pdf = pdfium.PdfDocument(generar_informe_pdf(documento))
        try:
            self.assertGreater(len(pdf), 1)
            pagina = pdf[len(pdf) - 1]
            try:
                texto = pagina.get_textpage()
                try:
                    self.assertIn("FIN_VERIFICABLE_MOCO", texto.get_text_range())
                finally:
                    texto.close()
            finally:
                pagina.close()
        finally:
            pdf.close()


class MocoFecalApiTests(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.bio = self.crear_usuario_test(usuario="moco_ficticio", rol="BIOQUIMICO")
        token = self.client.post("/api/auth/login", json={"usuario": self.bio.usuario, "password": "ClaveSegura123!"}).json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}", "X-LIS-Client": "web"}
        paciente = self.crear_paciente_test(ci="FICTICIO-MOCO-001", creado_por=self.bio.id_usuario)
        respuesta = self.client.post("/api/ordenes", headers=self.headers,
            json={"id_paciente": paciente.id_paciente, "edad_anios": 30, "estudios": [{"codigo": "PARASITOLOGIA"}]})
        self.assertEqual(respuesta.status_code, 201, respuesta.text)
        self.orden = respuesta.json()["orden"]["id"]

    def captura(self):
        respuesta = self.client.get(f"/api/ordenes/{self.orden}/captura", headers=self.headers)
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        return respuesta.json()

    def test_guarda_reabre_y_publica_texto_largo_sin_truncar(self):
        inicial = self.captura()["estudios"][0]
        self.assertEqual([s["grupo"] for s in inicial["secciones"]], [
            None, "MOCO_FECAL", "COPROPARASITOLOGICO_SIMPLE", "COPROPARASITOLOGICO_SERIADO",
        ])
        seccion = inicial["secciones"][1]
        self.assertEqual(seccion["formato"], "LISTA_TEXTO")
        self.assertTrue(all(p["texto_sin_limite"] and p["valor"] is None for p in seccion["parametros"]))
        largo = "Descripción ficticia extensa. " * 200 + "FIN DEL TEXTO"
        valores = {"MOCO_FECAL_ASPECTO": largo, "MOCO_FECAL": "Positivo", "MOCO_FECAL_PH": "0",
                   "MOCO_FECAL_FLORA_BACTERIANA": "Prueba <script>sin ejecución</script> & texto", "MOCO_FECAL_ERITROCITOS": " "}
        respuesta = self.client.put(f"/api/ordenes/{self.orden}/resultados", headers=self.headers, json={"valores": valores})
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        reabierta = self.captura()
        campos = {p["codigo"]: p for p in reabierta["estudios"][0]["secciones"][1]["parametros"]}
        for codigo, valor in valores.items():
            self.assertEqual(campos[codigo]["valor"], valor if valor.strip() else None)
        publicada = self.client.post(f"/api/ordenes/{self.orden}/publicar", headers=self.headers)
        self.assertEqual(publicada.status_code, 201, publicada.text)
        detalle = self.client.get(f"/api/informes/{publicada.json()['folio']}", headers=self.headers).json()
        estudio = detalle["snapshot_json"]["estudios"][0]
        publicados = {p["codigo"]: p for s in estudio["secciones"] for p in s["parametros"]}
        self.assertEqual(publicados["MOCO_FECAL_ASPECTO"]["valor"], largo)
        self.assertNotIn("MOCO_FECAL_ERITROCITOS", publicados)
        documento = documento_aprobado(False)
        documento["estudios"] = [estudio]
        html = renderizar_html_informe(documento)
        self.assertIn('<table class="text-list"', html)
        self.assertIn("FIN DEL TEXTO", html)
        self.assertIn("&lt;script&gt;sin ejecución&lt;/script&gt; &amp; texto", html)
        self.assertNotIn("<script>sin ejecución</script>", html)

    def test_migracion_conserva_valores_previos_e_informe_publicado(self):
        version, parametro_id = self.db.execute(text("""
            SELECT p.id_estudio_version, p.id_parametro FROM laboratorio.parametros p
            JOIN laboratorio.orden_estudios oe USING (id_estudio_version)
            WHERE oe.id_orden = :orden AND p.codigo = 'MOCO_FECAL'
        """), {"orden": self.orden}).one()
        self.db.execute(text("UPDATE laboratorio.parametros SET tipo_campo='SELECCION', opciones='[\"Negativo\",\"Positivo\"]'::jsonb, grupo=NULL, nombre='Moco fecal' WHERE id_parametro=:id"), {"id": parametro_id})
        self.db.commit()
        guardado = self.client.put(f"/api/ordenes/{self.orden}/resultados", headers=self.headers, json={"valores": {"MOCO_FECAL": "Negativo"}})
        self.assertEqual(guardado.status_code, 200, guardado.text)
        publicada = self.client.post(f"/api/ordenes/{self.orden}/publicar", headers=self.headers)
        self.assertEqual(publicada.status_code, 201, publicada.text)
        folio = publicada.json()["folio"]
        original = self.client.get(f"/api/informes/{folio}", headers=self.headers).json()
        ruta = Path(__file__).parents[1] / "alembic/versions/0012_moco_fecal_texto_libre.py"
        spec = importlib.util.spec_from_file_location("migracion_moco_fecal", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        try:
            for _ in range(2):
                with Operations.context(MigrationContext.configure(self.db.connection())):
                    modulo.upgrade()
                self.db.commit()
            actual = self.captura()["estudios"][0]["secciones"][1]
            self.assertEqual([p["codigo"] for p in actual["parametros"]], [codigo for codigo, _ in MOCO_FECAL_CAMPOS])
            moco = next(p for p in actual["parametros"] if p["codigo"] == "MOCO_FECAL")
            self.assertEqual((moco["valor"], moco["tipo_campo"], moco["opciones"]), ("Negativo", "TEXTO_LIBRE", None))
            self.assertEqual(self.db.execute(text("SELECT id_parametro FROM laboratorio.parametros WHERE id_estudio_version=:version AND codigo='MOCO_FECAL'"), {"version": version}).scalar_one(), parametro_id)
            vigente = self.client.get(f"/api/informes/{folio}", headers=self.headers).json()
            self.assertEqual(vigente["snapshot_json"], original["snapshot_json"])
            self.assertEqual(vigente["snapshot_sha256"], original["snapshot_sha256"])
        finally:
            self.db.rollback()
            with Operations.context(MigrationContext.configure(self.db.connection())):
                modulo.upgrade()
            self.db.commit()
