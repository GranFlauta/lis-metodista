"""Unidades de coagulación por borrador, con números clínicos separados."""
from decimal import Decimal
import unittest

from app.core.errors import ValidacionError
from app.models.catalog import Parametro
from app.models.result import ResultadoBorrador
from app.reports.pdf import renderizar_html_informe
from app.reports.presentation import estudios_para_informe
from app.services.coagulacion_service import normalizar_unidad_coagulacion, unidad_coagulacion_editable
from tests.test_grupo_sanguineo import CoagulogramaApiTestCase, PARAMETROS
from tests.test_pdf_report import documento_aprobado


class UnidadesCoagulacionTests(unittest.TestCase):
    def test_distingue_unidad_borrada_y_restauracion_del_catalogo(self):
        self.assertIsNone(normalizar_unidad_coagulacion(None))
        for valor in ("", " ", "--"):
            self.assertEqual(normalizar_unidad_coagulacion(valor), "")
        self.assertEqual(normalizar_unidad_coagulacion(" seg "), "seg")
        for valor in ("x" * 31, 0, False, ["min"]):
            with self.subTest(valor=valor), self.assertRaises(ValidacionError):
                normalizar_unidad_coagulacion(valor)

    def test_solo_son_editables_los_numericos_del_grupo_coagulacion(self):
        for definicion in PARAMETROS.values():
            parametro = Parametro(grupo=definicion.grupo, tipo_campo=definicion.tipo)
            self.assertEqual(unidad_coagulacion_editable("COAGULOGRAMA", parametro), definicion.grupo == "COAGULACION")
            self.assertFalse(unidad_coagulacion_editable("OTRO_ESTUDIO", parametro))


class CoagulacionApiTests(CoagulogramaApiTestCase):
    def fila(self, codigo):
        self.db.expire_all()
        return self.db.query(ResultadoBorrador).join(Parametro).filter(Parametro.codigo == codigo).one()

    def test_unidades_iniciales_provienen_del_catalogo_y_no_completan_resultados(self):
        captura = self.captura()
        parametros = self.parametros(captura)
        for codigo, definicion in PARAMETROS.items():
            if definicion.grupo != "COAGULACION":
                continue
            parametro = parametros[codigo]
            self.assertEqual(parametro["unidad"], definicion.unidad)
            self.assertTrue(parametro["unidad_editable"])
            self.assertFalse(parametro["unidad_modificada"])
            self.assertIsNone(parametro["valor"])
        self.assertIsNone(parametros["INR"]["unidad"])
        self.assertFalse(captura["completitud"]["completo"])
        self.assertEqual(self.db.query(ResultadoBorrador).count(), 0)

    def test_todas_las_unidades_se_guardan_sin_alterar_numeros_rangos_ni_banderas(self):
        valores = {"T_COAGULACION": "7.250001", "T_SANGRIA": "3.5", "T_PROTROMBINA": "12.2",
                   "ACTIVIDAD": "90.12", "INR": "1.13", "TPTA": "30"}
        inicial = self.guardar(valores)
        self.assertEqual(inicial.status_code, 200, inicial.text)
        antes = self.parametros(inicial.json())
        unidades = {codigo: "Unidad ficticia " + str(indice) for indice, codigo in enumerate(valores)}
        guardada = self.guardar(unidades=unidades)
        self.assertEqual(guardada.status_code, 200, guardada.text)
        despues = self.parametros(self.captura())
        for codigo, valor in valores.items():
            self.assertEqual(despues[codigo]["unidad"], unidades[codigo])
            self.assertTrue(despues[codigo]["unidad_modificada"])
            for campo in ("valor", "referencia", "bandera", "calculable"):
                self.assertEqual(despues[codigo][campo], antes[codigo][campo])
            fila = self.fila(codigo)
            self.assertEqual(fila.valor_numerico, Decimal(valor))
            self.assertIsNone(fila.valor_texto)
            self.assertEqual(fila.unidad_override, unidades[codigo])

    def test_borrar_restaurar_y_editar_valor_conserva_la_unidad_correcta(self):
        self.assertEqual(self.guardar({"T_COAGULACION": "7"}, {"T_COAGULACION": ""}).status_code, 200)
        parametro = self.parametros(self.captura())["T_COAGULACION"]
        self.assertIsNone(parametro["unidad"])
        self.assertTrue(parametro["unidad_modificada"])
        self.assertEqual(self.guardar({"T_COAGULACION": "8"}).status_code, 200)
        self.assertIsNone(self.parametros(self.captura())["T_COAGULACION"]["unidad"])
        self.assertEqual(self.guardar(unidades={"T_COAGULACION": None}).status_code, 200)
        parametro = self.parametros(self.captura())["T_COAGULACION"]
        self.assertEqual(parametro["unidad"], PARAMETROS["T_COAGULACION"].unidad)
        self.assertFalse(parametro["unidad_modificada"])
        for unidad in ("Unidad INR", None):
            self.assertEqual(self.guardar(unidades={"INR": unidad}).status_code, 200)
            self.assertEqual(self.parametros(self.captura())["INR"]["unidad"], unidad)
        self.assertIsNone(self.fila("T_COAGULACION").unidad_override)

    def test_unidad_sola_no_inventa_valor_y_se_conserva_al_borrar_el_numero(self):
        guardada = self.guardar(unidades={"T_COAGULACION": "Unidad ficticia"})
        self.assertEqual(guardada.status_code, 200, guardada.text)
        self.assertFalse(guardada.json()["completitud"]["completo"])
        self.assertEqual(estudios_para_informe(guardada.json()["estudios"]), [])
        fila = self.fila("T_COAGULACION")
        self.assertIsNone(fila.valor_numerico)
        self.assertIsNone(fila.valor_texto)
        self.assertEqual(self.client.post(f"/api/ordenes/{self.orden}/publicar", headers=self.headers).status_code, 400)
        self.assertEqual(self.guardar({"T_COAGULACION": "0"}).status_code, 200)
        self.assertTrue(self.captura()["completitud"]["completo"])
        self.assertEqual(self.guardar({"T_COAGULACION": None}).status_code, 200)
        self.assertEqual(self.parametros(self.captura())["T_COAGULACION"]["unidad"], "Unidad ficticia")
        self.assertEqual(self.guardar(unidades={"T_COAGULACION": None}).status_code, 200)
        self.assertEqual(self.db.query(ResultadoBorrador).count(), 0)

    def test_restaurar_referencia_no_elimina_una_unidad_sin_resultado(self):
        guardada = self.guardar(unidades={"T_COAGULACION": "Unidad ficticia"},
            rangos_override={"T_COAGULACION": {"limite_inferior": "5", "limite_superior": "10", "texto": "Referencia ficticia"}})
        self.assertEqual(guardada.status_code, 200, guardada.text)
        restaurada = self.guardar(rangos_override={"T_COAGULACION": {"reestablecer": True}})
        self.assertEqual(restaurada.status_code, 200, restaurada.text)
        self.assertEqual(self.fila("T_COAGULACION").unidad_override, "Unidad ficticia")
        self.assertFalse(self.captura()["completitud"]["completo"])

    def test_simulacion_y_vista_previa_no_persisten_la_unidad(self):
        self.assertEqual(self.guardar({"T_COAGULACION": "7"}, {"T_COAGULACION": "Unidad guardada"}).status_code, 200)
        body = {"valores": {}, "unidades_override": {"T_COAGULACION": "Unidad simulada"}}
        simulada = self.client.post(f"/api/ordenes/{self.orden}/calcular", headers=self.headers, json=body)
        self.assertEqual(simulada.status_code, 200, simulada.text)
        self.assertEqual(self.parametros(simulada.json())["T_COAGULACION"]["unidad"], "Unidad simulada")
        previa = self.client.post(f"/api/ordenes/{self.orden}/vista-previa", headers=self.headers, json=body)
        self.assertEqual(previa.status_code, 200, previa.text)
        self.assertGreater(len(previa.json()["paginas"]), 0)
        self.assertEqual(self.parametros(self.captura())["T_COAGULACION"]["unidad"], "Unidad guardada")

    def test_publicacion_congela_unidades_y_no_admite_modificarlas(self):
        guardada = self.guardar({"T_COAGULACION": "7.25", "INR": "1.12", "GRUPO_SANGUINEO": "A"},
                                {"T_COAGULACION": "<u> & ficticia", "INR": ""})
        self.assertEqual(guardada.status_code, 200, guardada.text)
        publicada = self.client.post(f"/api/ordenes/{self.orden}/publicar", headers=self.headers)
        self.assertEqual(publicada.status_code, 201, publicada.text)
        folio = publicada.json()["folio"]
        snapshot = self.client.get(f"/api/informes/{folio}", headers=self.headers).json()["snapshot_json"]
        parametros = self.parametros(snapshot)
        self.assertEqual(parametros["T_COAGULACION"]["unidad"], "<u> & ficticia")
        self.assertIsNone(parametros["INR"]["unidad"])
        self.assertIsNone(parametros["GRUPO_SANGUINEO"]["unidad"])
        documento = documento_aprobado(True)
        documento["estudios"] = snapshot["estudios"]
        self.assertIn("&lt;u&gt; &amp; ficticia", renderizar_html_informe(documento))
        pdf = self.client.get(f"/api/informes/{folio}/pdf", headers=self.headers)
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertEqual(self.guardar(unidades={"T_COAGULACION": "Otra"}).status_code, 409)
        despues = self.client.get(f"/api/informes/{folio}", headers=self.headers).json()["snapshot_json"]
        self.assertEqual(despues, snapshot)

    def test_valida_alcance_y_longitud_antes_de_cambiar_resultados(self):
        self.assertEqual(self.guardar({"T_COAGULACION": "7"}).status_code, 200)
        for unidades in ({"INR": "x" * 31}, {"INR": 0}, {"INR": False},
                         {"GRUPO_SANGUINEO": "Ficticia"}, {"GLICEMIA": "Ficticia"}, {"INEXISTENTE": "Ficticia"}):
            with self.subTest(unidades=unidades):
                respuesta = self.guardar({"T_COAGULACION": "9"}, unidades)
                self.assertEqual(respuesta.status_code, 400, respuesta.text)
                self.assertEqual(self.parametros(self.captura())["T_COAGULACION"]["valor"], "7")

    def test_admin_y_profesional_ajeno_no_modifican_unidades(self):
        for rol, esperado in (("ADMIN", 403), ("BIOQUIMICO", 404)):
            usuario = self.crear_usuario_test(usuario="otro_coag_" + rol.lower(), rol=rol)
            token = self.client.post("/api/auth/login", json={"usuario": usuario.usuario, "password": "ClaveSegura123!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            for ruta in ("resultados", "calcular", "vista-previa"):
                respuesta = self.client.request("PUT" if ruta == "resultados" else "POST",
                    f"/api/ordenes/{self.orden}/{ruta}", headers=headers,
                    json={"valores": {}, "unidades_override": {"INR": "Unidad ficticia"}})
                self.assertEqual(respuesta.status_code, esperado, respuesta.text)

