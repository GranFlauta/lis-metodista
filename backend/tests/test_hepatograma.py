"""Referencias de Hepatograma: Hasta 40 inclusivo y preservación de informes."""
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.catalog.definitions import HEPATOGRAMA
from app.models.catalog import Parametro, RangoReferencia
from app.models.result import ResultadoBorrador
from app.services.evaluacion_service import evaluar_rango_y_bandera
from tests.base import IntegrationTestCase


CODIGOS = ("GOT_AST", "GPT_ALT")
DEFINICIONES = {p.codigo: p for p in HEPATOGRAMA.parametros}


class ReferenciasHepatogramaTests(unittest.TestCase):
    def test_catalogo_confirma_hasta_cuarenta_para_ambos_parametros(self):
        for codigo in CODIGOS:
            parametro = DEFINICIONES[codigo]
            self.assertEqual(parametro.unidad, "UI/L")
            self.assertEqual(len(parametro.rangos), 1)
            rango = parametro.rangos[0]
            self.assertIsNone(rango.inferior)
            self.assertEqual(rango.superior, 40)
            self.assertTrue(rango.superior_incl)
            self.assertEqual(rango.texto, "VR: Hasta 40")
            self.assertFalse(rango.validar)

    def test_limite_inclusivo_con_decimal_y_vacio_sin_bandera(self):
        for codigo in CODIGOS:
            rango = DEFINICIONES[codigo].rangos[0]
            parametro = Parametro(codigo=codigo, tipo_campo="NUMERICO", rangos_referencia=[
                RangoReferencia(limite_superior=Decimal(str(rango.superior)), superior_inclusivo=rango.superior_incl,
                                referencia_texto=rango.texto, inferior_inclusivo=True),
            ])
            for valor, esperado in ((None, None), ("0", "NORMAL"), ("39.999999", "NORMAL"), ("40", "NORMAL"), ("40.000001", "ALTO")):
                with self.subTest(codigo=codigo, valor=valor):
                    referencia, bandera = evaluar_rango_y_bandera(parametro, Decimal(valor) if valor is not None else None, "F", 360)
                    self.assertEqual(referencia["superior"], "40")
                    self.assertEqual(bandera, esperado)


class HepatogramaApiTests(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.bio = self.crear_usuario_test(usuario="hepatico_ficticio", rol="BIOQUIMICO")
        token = self.client.post("/api/auth/login", json={"usuario": self.bio.usuario, "password": "ClaveSegura123!"}).json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}"}
        self.paciente = self.crear_paciente_test(ci="FICTICIO-HEPATICO-01", creado_por=self.bio.id_usuario)

    def crear(self):
        respuesta = self.client.post("/api/ordenes", headers=self.headers, json={
            "id_paciente": self.paciente.id_paciente, "edad_anios": 30, "estudios": [{"codigo": "HEPATOGRAMA"}],
        })
        self.assertEqual(respuesta.status_code, 201, respuesta.text)
        return respuesta.json()["orden"]["id"]

    def guardar(self, orden, valores, rangos=None):
        return self.client.put(f"/api/ordenes/{orden}/resultados", headers=self.headers,
                               json={"valores": valores, "rangos_override": rangos})

    def captura(self, orden):
        respuesta = self.client.get(f"/api/ordenes/{orden}/captura", headers=self.headers)
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        return {p["codigo"]: p for e in respuesta.json()["estudios"] for s in e["secciones"] for p in s["parametros"]}

    def test_captura_y_calculo_usan_cuarenta_sin_redondear_la_entrada(self):
        orden = self.crear()
        for codigo in CODIGOS:
            self.assertEqual(self.captura(orden)[codigo]["referencia"]["texto"], "VR: Hasta 40")
        for valor, bandera in (("40", "NORMAL"), ("40.000001", "ALTO")):
            guardada = self.guardar(orden, {codigo: valor for codigo in CODIGOS})
            self.assertEqual(guardada.status_code, 200, guardada.text)
            for codigo in CODIGOS:
                parametro = self.captura(orden)[codigo]
                self.assertEqual(parametro["valor"], valor)
                self.assertEqual(parametro["bandera"], bandera)
                self.assertEqual(parametro["referencia"]["superior"], "40")

    def test_referencia_personalizada_se_conserva_y_se_puede_restaurar(self):
        orden = self.crear()
        guardada = self.guardar(orden, {codigo: "41" for codigo in CODIGOS},
                               {codigo: {"limite_superior": "42", "texto": "Referencia propia hasta 42"} for codigo in CODIGOS})
        self.assertEqual(guardada.status_code, 200, guardada.text)
        for codigo in CODIGOS:
            parametro = self.captura(orden)[codigo]
            self.assertEqual(parametro["referencia"]["superior"], "42")
            self.assertTrue(parametro["referencia"]["modificada"])
            self.assertEqual(parametro["bandera"], "NORMAL")
        restaurada = self.guardar(orden, {}, {codigo: {"reestablecer": True} for codigo in CODIGOS})
        self.assertEqual(restaurada.status_code, 200, restaurada.text)
        for codigo in CODIGOS:
            parametro = self.captura(orden)[codigo]
            self.assertEqual(parametro["referencia"]["texto"], "VR: Hasta 40")
            self.assertEqual(parametro["bandera"], "ALTO")

    def test_migracion_conserva_valores_overrides_y_snapshot_anterior(self):
        ruta = Path(__file__).parents[1] / "alembic/versions/0022_referencias_hepatograma.py"
        spec = importlib.util.spec_from_file_location("migracion_hepatograma", ruta)
        migracion = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migracion)

        def aplicar():
            with Operations.context(MigrationContext.configure(self.db.connection())):
                migracion.upgrade()
            self.db.commit()

        try:
            for codigo, limite in (("GOT_AST", 37), ("GPT_ALT", 45)):
                self.db.execute(text("""
                    UPDATE laboratorio.rangos_referencia AS r
                    SET limite_superior = :limite, referencia_texto = :texto, requiere_validacion = TRUE
                    FROM laboratorio.parametros AS p
                    JOIN laboratorio.estudio_versiones AS ev USING (id_estudio_version)
                    JOIN laboratorio.estudios AS e USING (id_estudio)
                    WHERE r.id_parametro = p.id_parametro AND e.codigo = 'HEPATOGRAMA'
                      AND p.codigo = :codigo AND r.sexo IS NULL
                      AND r.edad_min_meses IS NULL AND r.edad_max_meses IS NULL
                """), {"codigo": codigo, "limite": limite, "texto": f"VR: Hasta {limite}"})
            self.db.commit()
            valores = {"GOT_AST": "38", "GPT_ALT": "44"}
            oficial = self.crear()
            self.assertEqual(self.guardar(oficial, valores).status_code, 200)
            publicada = self.client.post(f"/api/ordenes/{oficial}/publicar", headers=self.headers)
            self.assertEqual(publicada.status_code, 201, publicada.text)
            folio = publicada.json()["folio"]
            original = self.client.get(f"/api/informes/{folio}", headers=self.headers).json()
            borrador = self.crear()
            propio = self.crear()
            self.assertEqual(self.guardar(borrador, valores).status_code, 200)
            self.assertEqual(self.guardar(propio, valores, {codigo: {"limite_superior": "46", "texto": "Referencia propia hasta 46"} for codigo in CODIGOS}).status_code, 200)
            guardados = self.db.query(ResultadoBorrador).order_by(ResultadoBorrador.id_resultado).all()
            antes = [(r.id_resultado, r.valor_numerico, r.valor_texto, r.ref_superior_override, r.ref_modificada) for r in guardados]
            for _ in range(2):
                aplicar()
            for codigo in CODIGOS:
                parametro = self.captura(borrador)[codigo]
                self.assertEqual(parametro["valor"], valores[codigo])
                self.assertEqual(parametro["referencia"]["texto"], "VR: Hasta 40")
                self.assertEqual(parametro["bandera"], "NORMAL" if codigo == "GOT_AST" else "ALTO")
                personalizado = self.captura(propio)[codigo]
                self.assertEqual(personalizado["referencia"]["texto"], "Referencia propia hasta 46")
                self.assertTrue(personalizado["referencia"]["modificada"])
                self.assertEqual(personalizado["bandera"], "NORMAL")
            self.db.expire_all()
            despues = self.db.query(ResultadoBorrador).order_by(ResultadoBorrador.id_resultado).all()
            self.assertEqual([(r.id_resultado, r.valor_numerico, r.valor_texto, r.ref_superior_override, r.ref_modificada) for r in despues], antes)
            actual = self.client.get(f"/api/informes/{folio}", headers=self.headers).json()
            self.assertEqual(actual["snapshot_json"], original["snapshot_json"])
            self.assertEqual(actual["snapshot_sha256"], original["snapshot_sha256"])
        finally:
            self.db.rollback()
            aplicar()

