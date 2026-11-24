import json
import unittest

from app.catalog.definitions import EGO, INMUNOSEROLOGIA
from app.core.errors import ValidacionError
from app.reports.pdf import renderizar_html_informe
from app.services.serologia_service import columnas_serologia, normalizar_entrada, presentar_serologia
from tests.test_pdf_report import documento_aprobado


def entrada(reactividad="Positivo", dilucion="1/8", **extras):
    return json.dumps({"reactividad": reactividad, "dilucion": dilucion, **extras})


class SerologiaTests(unittest.TestCase):
    def presentar(self, codigo, valor):
        config = INMUNOSEROLOGIA.captura[codigo]
        return presentar_serologia(normalizar_entrada(valor, config), config)

    def test_orden_final_microscopico_ego(self):
        codigos = [p.codigo for p in EGO.parametros if p.grupo == "MICROSCOPICO"]
        self.assertEqual(codigos[-4:], ["CRISTALES", "CILINDROS", "BACTERIAS", "OTROS"])

    def test_pcr_teco_se_calcula_con_decimal_y_referencia_de_marca(self):
        resultado = self.presentar("PCR_DILUCION", entrada(reactivo="TECO"))
        self.assertEqual(resultado["resultado"], "6.4")
        self.assertEqual(resultado["unidad"], "mg/dL")
        self.assertEqual(resultado["referencia"], "TECO <0.8 mg/dL")
        self.assertTrue(resultado["completo"])
        monlab = self.presentar("PCR_DILUCION", entrada(reactivo="MONLAB"))
        self.assertEqual(monlab["resultado"], "48")
        propio = self.presentar("PCR_DILUCION", entrada(reactivo="PERSONALIZADO", sensibilidad="0,125", unidad="mg/L"))
        self.assertEqual(propio["resultado"], "1")

    def test_fr_ocho_y_sensibilidad_personalizada(self):
        resultado = self.presentar("FR_DILUCION", entrada(dilucion="1/32", reactivo="Estándar"))
        self.assertEqual(resultado["resultado"], "256")
        self.assertEqual(resultado["unidad"], "UI/mL")
        propio = self.presentar("FR_DILUCION", entrada(dilucion="1/4", reactivo="PERSONALIZADO", sensibilidad="10.25", unidad="UI/mL"))
        self.assertEqual(propio["resultado"], "41")

    def test_asto_conserva_calculo_y_acepta_nombres_positivo_negativo(self):
        resultado = self.presentar("ASTO_DILUCION", entrada(dilucion="1/32"))
        self.assertEqual(resultado["resultado"], "6400")
        sin_dilucion = self.presentar("ASTO_DILUCION", entrada(dilucion=""))
        self.assertEqual(sin_dilucion["resultado"], "≥200")
        propio = self.presentar("ASTO_DILUCION", entrada(
            dilucion="", reactivo="PERSONALIZADO", sensibilidad="250", unidad="UI/mL",
        ))
        self.assertEqual(propio["resultado"], "≥250")
        self.assertEqual(propio["referencia"], "Propio <250 UI/mL")
        negativo = self.presentar("ASTO_DILUCION", entrada("Negativo"))
        self.assertEqual(negativo["resultado"], "Negativo")
        self.assertEqual(negativo["entrada"]["reactividad"], "Negativo")
        self.assertEqual(negativo["entrada"]["dilucion"], "")

    def test_chagas_es_subestudio_cualitativo_y_sangre_oculta_va_en_mayusculas(self):
        chagas = next(p for p in INMUNOSEROLOGIA.parametros if p.codigo == "CHAGAS")
        sangre_oculta = next(p for p in INMUNOSEROLOGIA.parametros if p.codigo == "SANGRE_OCULTA_HECES_INMUNO")
        self.assertEqual((chagas.grupo, chagas.nombre, chagas.opciones), ("CHAGAS", "CHAGAS", ["Negativo", "Positivo"]))
        self.assertEqual(sangre_oculta.nombre, "SANGRE OCULTA EN HECES")

    def test_widal_solo_informa_titulo_sin_concentracion(self):
        for codigo, config in INMUNOSEROLOGIA.captura.items():
            if config["modo"] != "TITULO":
                continue
            self.assertEqual(config["diluciones"], ["1/20", "1/40", "1/80", "1/160", "1/320"])
            for titulo in ("1/20", "1/320", "1/130"):
                resultado = self.presentar(codigo, entrada(dilucion=titulo))
                self.assertEqual(resultado["resultado"], f"Positivo · {titulo}")
                self.assertEqual(resultado["unidad"], "")
                self.assertEqual(resultado["referencia"], "")
            self.assertEqual(self.presentar(codigo, entrada("Negativo"))["resultado"], "Negativo")

    def test_no_inventa_resultados_para_entradas_incompletas_o_invalidas(self):
        for dilucion in ("", "1/0", "abc"):
            resultado = self.presentar("FR_DILUCION", entrada(dilucion=dilucion))
            self.assertIsNone(resultado["resultado"])
            self.assertFalse(resultado["completo"])
        for sensibilidad in ("", "NaN", "-8", "0"):
            resultado = self.presentar("FR_DILUCION", entrada(reactivo="PERSONALIZADO", sensibilidad=sensibilidad, unidad="UI/mL"))
            self.assertFalse(resultado["completo"])
        self.assertIsNone(self.presentar("PCR_DILUCION", entrada(""))["resultado"])

    def test_rechaza_resultados_fabricados_reactivos_y_unidades_ajenos(self):
        config = INMUNOSEROLOGIA.captura["PCR_DILUCION"]
        for valor in (entrada(resultado="999"), entrada(reactivo="Inventado"), entrada(unidad="kg")):
            with self.assertRaises(ValidacionError):
                normalizar_entrada(valor, config)

    def test_columnas_segun_tipo_y_sin_banderas(self):
        self.assertEqual(columnas_serologia([{"codigo": "VIH", "unidad": None}]), {"unidad": False, "referencia": False, "bandera": False})
        self.assertEqual(columnas_serologia([{"codigo": "PCR_CUANTITATIVA", "unidad": "mg/L"}]), {"unidad": True, "referencia": False, "bandera": False})
        self.assertTrue(columnas_serologia([{"codigo": "PCR_DILUCION"}])["referencia"])
        self.assertFalse(columnas_serologia([{"codigo": "WIDAL_TIFOIDEA_H", "unidad": "título"}])["unidad"])
        self.assertFalse(columnas_serologia([{"codigo": "WIDAL_TIFOIDEA_H"}])["referencia"])

    def test_presenta_borradores_anteriores_sin_perder_su_resultado(self):
        valor = "Reactivo 1/32: 256 UI/mL; sensibilidad 8 UI/mL; lote FICTICIO; controles + Conforme"
        resultado = presentar_serologia(valor, INMUNOSEROLOGIA.captura["FR_DILUCION"])
        self.assertEqual(resultado["resultado"], "256")
        self.assertEqual(resultado["entrada"]["reactividad"], "Positivo")
        self.assertEqual(resultado["entrada"]["dilucion"], "1/32")
        self.assertNotIn("lote", str(resultado))
        pcr = presentar_serologia("Positivo 1/8 (80 mg/L)", INMUNOSEROLOGIA.captura["PCR_DILUCION"], "Propio <10 mg/L")
        self.assertEqual(pcr["entrada"]["reactivo"], "PERSONALIZADO")
        self.assertEqual(pcr["entrada"]["sensibilidad"], "10")
        self.assertEqual(pcr["referencia"], "Propio <10 mg/L")
        self.assertEqual(pcr["resultado"], "80")

    def test_pdf_cualitativo_sin_columnas_inutiles_y_calculo_con_resultado_final(self):
        documento = documento_aprobado(False)
        documento["estudios"] = [{"codigo": "INMUNOSEROLOGIA", "nombre": "Inmunoserología", "secciones": [
            {"grupo": "VIH", "parametros": [{"codigo": "VIH", "nombre": "VIH", "valor": "No reactivo"}]},
        ]}]
        html = renderizar_html_informe(documento)
        self.assertNotIn(">Unidad<", html)
        self.assertNotIn(">V. Ref.<", html)
        self.assertNotIn(">Bandera<", html)
        parametro = {"codigo": "PCR_DILUCION", "nombre": "PCR", "valor": entrada(reactivo="TECO"),
                     "captura_serologia": INMUNOSEROLOGIA.captura["PCR_DILUCION"],
                     "serologia": self.presentar("PCR_DILUCION", entrada(reactivo="TECO"))}
        documento["estudios"][0]["secciones"] = [{"grupo": "PCR", "parametros": [parametro]}]
        for aprobado in (True, False):
            documento["aprobado"] = aprobado
            html = renderizar_html_informe(documento)
            self.assertIn("TECO &lt;0.8 mg/dL", html)
            self.assertIn('class="numeric">6,4<', html)
            self.assertLess(html.index(">V. Ref.<"), html.index('>Resultado<'))
            self.assertNotIn('reactividad', html)
            self.assertNotIn(">Bandera<", html)
