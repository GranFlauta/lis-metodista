"""Resultados por muestra, confirmación explícita y compatibilidad del seriado."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from datetime import datetime, timezone

from app.catalog.definitions import PARASITOLOGIA
from app.core.clock import reset_clock, set_simulated_time
from app.core.errors import ValidacionError
from app.models.catalog import EstudioVersion, Parametro
from app.reports.pdf import renderizar_html_informe
from app.reports.presentation import estudios_para_informe
from app.services.coproparasitologia_service import normalizar_muestras, presentar_muestras
from app.services.evaluacion_service import normalizar_y_validar_valor_entrada
from tests.base import IntegrationTestCase
from tests.test_pdf_report import documento_aprobado

CODIGO = "COPROPARASITOLOGICO_SERIADO"
SIMPLE = "COPROPARASITOLOGICO_SIMPLE"
CONFIG = PARASITOLOGIA.captura["muestras_seriadas"][CODIGO]


class CoproparasitologicosTests(unittest.TestCase):
    def test_tres_muestras_vacias_no_confirman_la_sugerencia(self):
        presentacion = presentar_muestras(None, CONFIG)
        self.assertEqual([m["numero"] for m in presentacion["muestras"]], [1, 2, 3])
        self.assertTrue(all(m["fecha"] is None and m["resultado"] is None for m in presentacion["muestras"]))
        self.assertFalse(presentacion["utilizado"])
        self.assertIsNone(presentacion["resultado"])
        self.assertEqual(CONFIG["sugerencia"], "No se observan formas parasitarias")

    def test_texto_simple_y_resultado_seriado_sin_truncar(self):
        largo = "Descripción ficticia.\n" * 3000
        version = EstudioVersion(configuracion_json={"captura": PARASITOLOGIA.captura})
        parametro = Parametro(codigo=SIMPLE, tipo_campo="TEXTO_LIBRE", estudio_version=version)
        self.assertEqual(normalizar_y_validar_valor_entrada(parametro, largo), (None, largo.strip()))
        normalizado = normalizar_muestras({"muestras": [{"fecha": "2026-11-20", "resultado": largo}]}, CONFIG)
        muestras = json.loads(normalizado)["muestras"]
        self.assertEqual(muestras[0]["resultado"], largo.strip())
        self.assertEqual(len(muestras), 3)
        self.assertTrue(presentar_muestras(normalizado, CONFIG)["completo"])

    def test_filas_adicionales_e_identidad_se_conservan(self):
        entrada = {"muestras": [{"numero": n, "fecha": "2026-11-20" if n in (1, 4) else None,
            "resultado": "0" if n in (1, 4) else None} for n in range(1, 7)]}
        salida = presentar_muestras(normalizar_muestras(entrada, CONFIG), CONFIG)
        self.assertEqual(len(salida["muestras"]), 6)
        self.assertEqual([m["numero"] for m in salida["muestras"]], list(range(1, 7)))
        self.assertIn("4.ª muestra", salida["resultado"])
        self.assertNotIn("2.ª muestra", salida["resultado"])
        self.assertTrue(salida["completo"])

    def test_valida_fechas_numeracion_y_estructura_en_backend(self):
        casos = [
            {"muestras": [{"fecha": "2999-01-01", "resultado": "Ficticio"}]},
            {"muestras": [{"fecha": "2026-02-30", "resultado": "Ficticio"}]},
            {"muestras": [{"fecha": "20/11/2026", "resultado": "Ficticio"}]},
            {"muestras": [{"numero": 2, "resultado": "Ficticio"}]},
            {"muestras": [{"numero": True, "resultado": "Ficticio"}]},
            {"muestras": [{"resultado": 0}]},
            {"muestras": [{"fecha": False}]},
            {"muestras": [], "confirmado": True},
            {"muestras": [{"resultado": "Ficticio", "bandera": "NORMAL"}]},
            {"muestras": [{"fecha": "2026-11-20", "hora": "25:00", "resultado": "Ficticio"}]},
            {"muestras": [{"fecha": "2026-11-20", "turno": "MEDIODÍA", "resultado": "Ficticio"}]},
        ]
        for caso in casos:
            with self.subTest(caso=caso), self.assertRaises(ValidacionError):
                normalizar_muestras(caso, CONFIG)
        with self.assertRaises(ValidacionError):
            normalizar_muestras("Negativo", CONFIG)
        self.assertEqual(normalizar_muestras("Negativo", CONFIG, "Negativo"), "Negativo")

    def test_hora_y_turno_opcionales_no_pueden_ser_futuros(self):
        set_simulated_time(datetime(2026, 11, 24, 16, 0, tzinfo=timezone.utc))
        try:
            with self.assertRaises(ValidacionError):
                normalizar_muestras({"muestras": [{"fecha": "2026-11-24", "hora": "13:00", "resultado": "Ficticio"}]}, CONFIG)
            normalizado = normalizar_muestras({"muestras": [{
                "fecha": "2026-11-24", "hora": "11:30", "turno": "mañana", "resultado": "Ficticio",
            }]}, CONFIG)
        finally:
            reset_clock()
        muestra = json.loads(normalizado)["muestras"][0]
        self.assertEqual((muestra["hora"], muestra["turno"]), ("11:30", "MAÑANA"))
        self.assertIsNone(json.loads(normalizado)["muestras"][1]["hora"])


class CoproparasitologicosApiTests(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        bio = self.crear_usuario_test(usuario="copro_ficticio", rol="BIOQUIMICO")
        token = self.client.post("/api/auth/login", json={"usuario": bio.usuario, "password": "ClaveSegura123!"}).json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}", "X-LIS-Client": "web"}
        paciente = self.crear_paciente_test(ci="FICTICIO-COPRO-01", creado_por=bio.id_usuario)
        respuesta = self.client.post("/api/ordenes", headers=self.headers, json={
            "id_paciente": paciente.id_paciente, "edad_anios": 30, "estudios": [{"codigo": "PARASITOLOGIA"}],
        })
        self.assertEqual(respuesta.status_code, 201, respuesta.text)
        self.orden = respuesta.json()["orden"]["id"]

    def guardar(self, valores):
        return self.client.put(f"/api/ordenes/{self.orden}/resultados", headers=self.headers, json={"valores": valores})

    def captura(self):
        respuesta = self.client.get(f"/api/ordenes/{self.orden}/captura", headers=self.headers)
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        return respuesta.json()

    def serie(self, captura):
        return next(p for e in captura["estudios"] for s in e["secciones"] for p in s["parametros"] if p["codigo"] == CODIGO)

    def test_guarda_reabre_y_publica_muestras_y_simple(self):
        inicial = self.captura()
        parametro = self.serie(inicial)
        self.assertEqual(parametro["tipo_campo"], "TEXTO_LIBRE")
        self.assertIsNone(parametro["valor"])
        self.assertEqual(len(parametro["muestras_seriadas"]["muestras"]), 3)
        self.assertFalse(inicial["completitud"]["completo"])
        muestras = [
            {"numero": 1, "fecha": "2026-11-18", "hora": "08:30", "turno": "MAÑANA", "resultado": CONFIG["sugerencia"]},
            {"numero": 2, "fecha": None, "hora": None, "turno": None, "resultado": None},
            {"numero": 3, "fecha": "2026-11-20", "hora": None, "turno": "NOCHE", "resultado": "Hallazgo ficticio <ejemplo> & descripción"},
            {"numero": 4, "fecha": "2026-11-21", "hora": "16:05", "turno": None, "resultado": "Cuarta muestra ficticia"},
            {"numero": 5, "fecha": None, "hora": None, "turno": None, "resultado": None},
        ]
        simple = "Resultado simple ficticio. " * 100
        guardada = self.guardar({SIMPLE: simple, CODIGO: {"muestras": muestras}})
        self.assertEqual(guardada.status_code, 200, guardada.text)
        reabierta = self.captura()
        self.assertEqual(json.loads(self.serie(reabierta)["valor"])["muestras"], muestras)
        self.assertTrue(reabierta["completitud"]["completo"])
        publicada = self.client.post(f"/api/ordenes/{self.orden}/publicar", headers=self.headers)
        self.assertEqual(publicada.status_code, 201, publicada.text)
        detalle = self.client.get(f"/api/informes/{publicada.json()['folio']}", headers=self.headers).json()
        estudio = detalle["snapshot_json"]["estudios"][0]
        congelados = {p["codigo"]: p for s in estudio["secciones"] for p in s["parametros"]}
        self.assertEqual(congelados[SIMPLE]["valor"], simple.strip())
        self.assertEqual(congelados[CODIGO]["muestras_seriadas"]["muestras"], muestras)
        documento = documento_aprobado(True)
        documento["estudios"] = [estudio]
        html = renderizar_html_informe(documento)
        tabla = re.search(r'<table class="text-list samples-list".*?</table>', html, re.S).group()
        self.assertEqual(len(re.findall(r'<th(?:\s[^>]*)?>', tabla)), 4)
        for numero in (1, 3, 4):
            self.assertIn(f"{numero}.ª MUESTRA", tabla)
        for numero in (2, 5):
            self.assertNotIn(f"{numero}.ª MUESTRA", tabla)
        for texto in ("Unidad", "V. Ref.", "Bandera", '"muestras"'):
            self.assertNotIn(texto, tabla)
        self.assertIn("18/11/2026 08:30", tabla)
        self.assertIn("21/11/2026 16:05", tabla)
        self.assertIn("MAÑANA", tabla)
        self.assertIn("NOCHE", tabla)
        simple_tabla = re.search(r'COPROPARASITOLOGICO SIMPLE</h3>\s*<table class="text-list solo-resultado".*?</table>', html, re.S)
        self.assertIsNotNone(simple_tabla)
        self.assertNotIn("Coproparasitológico simple", simple_tabla.group())
        self.assertIn("Resultado simple ficticio", simple_tabla.group())
        self.assertIn("&lt;ejemplo&gt; &amp; descripción", tabla)

    def test_fecha_y_resultado_parciales_se_guardan_pero_no_se_publican(self):
        for muestra in ({"fecha": "2026-11-20", "resultado": None}, {"fecha": None, "resultado": CONFIG["sugerencia"]}):
            guardada = self.guardar({CODIGO: {"muestras": [muestra]}})
            self.assertEqual(guardada.status_code, 200, guardada.text)
            self.assertFalse(guardada.json()["completitud"]["completo"])
            respuesta = self.client.post(f"/api/ordenes/{self.orden}/publicar", headers=self.headers)
            self.assertEqual(respuesta.status_code, 400, respuesta.text)
            self.assertEqual(self.db.execute(text("SELECT count(*) FROM laboratorio.folios")).scalar_one(), 0)
        guardada = self.guardar({CODIGO: {"muestras": [{"fecha": "2026-11-20", "resultado": CONFIG["sugerencia"]}]}})
        self.assertTrue(guardada.json()["completitud"]["completo"])

    def test_filas_vacias_y_agregar_cuarta_no_crean_resultados(self):
        guardada = self.guardar({CODIGO: {"muestras": [{"numero": n} for n in range(1, 5)]}})
        self.assertEqual(guardada.status_code, 200, guardada.text)
        captura = self.captura()
        self.assertFalse(captura["completitud"]["completo"])
        self.assertEqual(len(self.serie(captura)["muestras_seriadas"]["muestras"]), 4)
        self.assertEqual(estudios_para_informe(captura["estudios"]), [])
        guardada = self.guardar({"MOCO_FECAL_ASPECTO": "Ficticio"})
        self.assertTrue(guardada.json()["completitud"]["completo"])
        publicados = estudios_para_informe(guardada.json()["estudios"])
        self.assertFalse(any(p["codigo"] == CODIGO for e in publicados for s in e["secciones"] for p in s["parametros"]))

    def test_fecha_futura_rechaza_toda_la_operacion(self):
        respuesta = self.guardar({SIMPLE: "No debe guardarse", CODIGO: {"muestras": [{"fecha": "2999-01-01", "resultado": "Ficticio"}]}})
        self.assertEqual(respuesta.status_code, 400, respuesta.text)
        self.assertTrue(all(p["valor"] is None for e in self.captura()["estudios"] for s in e["secciones"] for p in s["parametros"]))

    def test_migracion_conserva_datos_antiguos_y_snapshot(self):
        filas = self.db.execute(text("""
            SELECT p.codigo, p.id_parametro, p.id_estudio_version FROM laboratorio.parametros p
            JOIN laboratorio.orden_estudios oe USING (id_estudio_version)
            WHERE oe.id_orden=:orden AND p.codigo IN (:simple, :seriado)
        """), dict(orden=self.orden, simple=SIMPLE, seriado=CODIGO)).all()
        ids = {fila.codigo: fila.id_parametro for fila in filas}
        version = filas[0].id_estudio_version
        self.db.execute(text("""
            UPDATE laboratorio.parametros SET tipo_campo='SELECCION', grupo='COPROPARASITOLOGICO',
                opciones='["Negativo","Positivo"]'::jsonb
            WHERE id_estudio_version=:version AND codigo IN (:simple,:seriado)
        """), dict(version=version, simple=SIMPLE, seriado=CODIGO))
        self.db.execute(text("UPDATE laboratorio.estudio_versiones SET configuracion_json=jsonb_set(configuracion_json,'{captura}', (configuracion_json->'captura') - 'muestras_seriadas') WHERE id_estudio_version=:version"), dict(version=version))
        self.db.commit()
        guardada = self.guardar({SIMPLE: "Negativo", CODIGO: "Positivo"})
        self.assertEqual(guardada.status_code, 200, guardada.text)
        publicada = self.client.post(f"/api/ordenes/{self.orden}/publicar", headers=self.headers)
        self.assertEqual(publicada.status_code, 201, publicada.text)
        folio = publicada.json()["folio"]
        original = self.client.get(f"/api/informes/{folio}", headers=self.headers).json()
        spec = importlib.util.spec_from_file_location("migracion_copro", Path(__file__).parents[1]/"alembic/versions/0013_coproparasitologicos.py")
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        try:
            for _ in range(2):
                with Operations.context(MigrationContext.configure(self.db.connection())):
                    modulo.upgrade()
                self.db.commit()
            actual = self.captura()
            seriado = self.serie(actual)
            self.assertEqual(seriado["valor"], "Positivo")
            self.assertEqual(seriado["muestras_seriadas"]["resultado_anterior"], "Positivo")
            self.assertTrue(all(m["fecha"] is None for m in seriado["muestras_seriadas"]["muestras"]))
            ids_actuales = dict(self.db.execute(text("SELECT codigo,id_parametro FROM laboratorio.parametros WHERE id_estudio_version=:version AND codigo IN (:simple,:seriado)"),dict(version=version,simple=SIMPLE,seriado=CODIGO)).all())
            self.assertEqual(ids_actuales, ids)
            vigente = self.client.get(f"/api/informes/{folio}", headers=self.headers).json()
            self.assertEqual(vigente["snapshot_json"], original["snapshot_json"])
            self.assertEqual(vigente["snapshot_sha256"], original["snapshot_sha256"])
        finally:
            self.db.rollback()
            with Operations.context(MigrationContext.configure(self.db.connection())):
                modulo.upgrade()
            self.db.commit()
