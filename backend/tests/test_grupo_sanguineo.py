"""Grupo sanguíneo sin unidad y compatibilidad de los borradores anteriores."""
import json
import unittest

from app.catalog.definitions import COAGULOGRAMA
from app.core.errors import ValidacionError
from app.models.catalog import Parametro
from app.models.order import OrdenEstudio
from app.models.result import ResultadoBorrador
from app.reports.pdf import renderizar_html_informe
from app.reports.presentation import estudios_para_informe
from app.services.evaluacion_service import normalizar_y_validar_valor_entrada
from tests.base import IntegrationTestCase
from tests.test_pdf_report import documento_aprobado


PARAMETROS = {p.codigo: p for p in COAGULOGRAMA.parametros}


def parametro_grupo(codigo="GRUPO_SANGUINEO"):
    definicion = PARAMETROS[codigo]
    return Parametro(codigo=codigo, grupo=definicion.grupo,
                     tipo_campo=definicion.tipo, opciones=definicion.opciones)


class EntradaGrupoSanguineoTests(unittest.TestCase):
    def test_conserva_todas_las_opciones_del_catalogo_y_el_texto_anterior(self):
        for codigo in ("GRUPO_SANGUINEO", "FACTOR_RH"):
            for opcion in PARAMETROS[codigo].opciones:
                with self.subTest(codigo=codigo, opcion=opcion):
                    self.assertEqual(normalizar_y_validar_valor_entrada(parametro_grupo(codigo), opcion), (None, opcion))

    def test_captura_anterior_con_unidad_conserva_solo_la_seleccion(self):
        for entrada, esperado in (({"valor": " AB ", "unidad": "Unidad anterior"}, "AB"),
                                  ({"valor": "", "unidad": "Unidad anterior"}, None)):
            for valor in (entrada, json.dumps(entrada)):
                self.assertEqual(normalizar_y_validar_valor_entrada(parametro_grupo(), valor), (None, esperado))

    def test_vacios_no_inventan_grupo_ni_rh(self):
        for valor in (None, "", "  ", {"valor": "", "unidad": ""}, {"valor": "--", "unidad": "--"}):
            with self.subTest(valor=valor):
                self.assertEqual(normalizar_y_validar_valor_entrada(parametro_grupo(), valor), (None, None))

    def test_valida_seleccion_y_estructura_en_el_backend(self):
        for valor in ("C", {"valor": "C"}, {"valor": 0}, {"valor": "A", "unidad": False},
                      {"valor": "A", "bandera": "NORMAL"}, "{invalido}", ["A"]):
            with self.subTest(valor=valor), self.assertRaises(ValidacionError):
                normalizar_y_validar_valor_entrada(parametro_grupo(), valor)

    def test_informes_historicos_conservan_su_presentacion_y_unidades(self):
        for columnas in (None, {"unidad": True, "referencia": False, "bandera": False}):
            documento = documento_aprobado(True)
            documento["estudios"] = [{"codigo": "COAGULOGRAMA", "nombre": COAGULOGRAMA.nombre,
                "secciones": [{"grupo": "GRUPO_SANGUINEO", "columnas": columnas, "parametros": [
                    {"codigo": "GRUPO_SANGUINEO", "nombre": "Grupo", "valor": "A", "unidad": "Unidad anterior"},
                ]}]}]
            original = json.dumps(documento, sort_keys=True)
            html = renderizar_html_informe(documento)
            self.assertIn(">Unidad</th>", html)
            self.assertIn("Unidad anterior", html)
            self.assertIn(">A<", html)
            self.assertEqual(json.dumps(documento, sort_keys=True), original)
            if columnas is None:
                self.assertIn(">Valor de referencia</th>", html)


class CoagulogramaApiTestCase(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        bio = self.crear_usuario_test(usuario="coag_ficticio", rol="BIOQUIMICO")
        token = self.client.post("/api/auth/login", json={"usuario": bio.usuario, "password": "ClaveSegura123!"}).json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}"}
        paciente = self.crear_paciente_test(ci="FICTICIO-COAG-01", creado_por=bio.id_usuario)
        respuesta = self.client.post("/api/ordenes", headers=self.headers, json={
            "id_paciente": paciente.id_paciente, "edad_anios": 30, "estudios": [{"codigo": "COAGULOGRAMA"}],
        })
        self.assertEqual(respuesta.status_code, 201, respuesta.text)
        self.orden = respuesta.json()["orden"]["id"]

    def guardar(self, valores=None, unidades=None, **otros):
        return self.client.put(f"/api/ordenes/{self.orden}/resultados", headers=self.headers,
                               json={"valores": valores or {}, "unidades_override": unidades, **otros})

    def captura(self):
        respuesta = self.client.get(f"/api/ordenes/{self.orden}/captura", headers=self.headers)
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        return respuesta.json()

    @staticmethod
    def parametros(captura):
        return {p["codigo"]: p for e in captura["estudios"] for s in e["secciones"] for p in s["parametros"]}


class GrupoSanguineoApiTests(CoagulogramaApiTestCase):
    def test_selecciones_sin_unidad_se_guardan_reabren_y_publican(self):
        for codigo in ("GRUPO_SANGUINEO", "FACTOR_RH"):
            parametro = self.parametros(self.captura())[codigo]
            self.assertIsNone(parametro["valor"])
            self.assertIsNone(parametro["unidad"])
            self.assertFalse(parametro.get("unidad_editable", False))
            self.assertNotIn("valor_captura", parametro)
            self.assertEqual(parametro["opciones"], PARAMETROS[codigo].opciones)
        valores = {"GRUPO_SANGUINEO": "AB", "FACTOR_RH": "Negativo (-)"}
        guardada = self.guardar(valores)
        self.assertEqual(guardada.status_code, 200, guardada.text)
        for codigo, valor in valores.items():
            parametro = self.parametros(self.captura())[codigo]
            self.assertEqual(parametro["valor"], valor)
            self.assertIsNone(parametro["unidad"])
        publicada = self.client.post(f"/api/ordenes/{self.orden}/publicar", headers=self.headers)
        self.assertEqual(publicada.status_code, 201, publicada.text)
        snapshot = self.client.get(f"/api/informes/{publicada.json()['folio']}", headers=self.headers).json()["snapshot_json"]
        documento = documento_aprobado(True)
        documento["estudios"] = snapshot["estudios"]
        html = renderizar_html_informe(documento)
        self.assertIn(">AB<", html)
        self.assertIn(">Negativo (-)<", html)
        for encabezado in (">Unidad</th>", ">Valor de referencia</th>", ">Bandera</th>"):
            self.assertNotIn(encabezado, html)

    def test_lee_borrador_anterior_sin_reutilizar_la_unidad(self):
        oe = self.db.query(OrdenEstudio).filter_by(id_orden=self.orden).one()
        parametro = next(p for p in oe.estudio_version.parametros if p.codigo == "GRUPO_SANGUINEO")
        texto_anterior = json.dumps({"valor": "A", "unidad": "Unidad anterior"})
        self.db.add(ResultadoBorrador(id_orden_estudio=oe.id_orden_estudio, id_parametro=parametro.id_parametro,
                    valor_texto=texto_anterior, es_calculado=False, calculable=True, confirmado=True,
                    actualizado_por=oe.orden.id_usuario_autor))
        self.db.commit()
        actual = self.parametros(self.captura())["GRUPO_SANGUINEO"]
        self.assertEqual(actual["valor"], "A")
        self.assertIsNone(actual["unidad"])
        self.assertNotIn("valor_captura", actual)
        documento = documento_aprobado(False)
        documento["estudios"] = self.captura()["estudios"]
        self.assertNotIn("Unidad anterior", renderizar_html_informe(documento))
        guardada = self.guardar({"GRUPO_SANGUINEO": texto_anterior})
        self.assertEqual(guardada.status_code, 200, guardada.text)
        self.db.expire_all()
        self.assertEqual(self.db.query(ResultadoBorrador).one().valor_texto, "A")

    def test_unidad_anterior_sin_seleccion_no_cuenta_como_resultado(self):
        guardada = self.guardar({"GRUPO_SANGUINEO": {"valor": "", "unidad": "Unidad anterior"}})
        self.assertEqual(guardada.status_code, 200, guardada.text)
        self.assertFalse(guardada.json()["completitud"]["completo"])
        self.assertEqual(estudios_para_informe(guardada.json()["estudios"]), [])
        self.assertEqual(self.client.post(f"/api/ordenes/{self.orden}/publicar", headers=self.headers).status_code, 400)
        self.assertEqual(self.db.query(ResultadoBorrador).count(), 0)

    def test_backend_rechaza_editar_unidad_del_grupo(self):
        for ruta in ("resultados", "calcular", "vista-previa"):
            respuesta = self.client.request("PUT" if ruta == "resultados" else "POST",
                f"/api/ordenes/{self.orden}/{ruta}", headers=self.headers,
                json={"valores": {}, "unidades_override": {"GRUPO_SANGUINEO": "Ficticia"}})
            self.assertEqual(respuesta.status_code, 400, respuesta.text)

