import unittest
import base64
from copy import deepcopy
from datetime import date
from io import BytesIO

from PIL import Image
import pypdfium2 as pdfium
from pydantic import ValidationError
from weasyprint import HTML

from app.catalog.definitions import CURVA_TOLERANCIA
from app.reports.pdf import ASSETS_DIR, generar_informe_pdf, generar_vista_previa, renderizar_html_informe
from app.schemas.resultado import VistaPreviaRequest
from app.services.curva_service import construir_curva


def documento_aprobado(aprobado: bool, filas: int = 2) -> dict:
    parametros = [
        {
            "codigo": f"RESULTADO_{idx}",
            "nombre": f"Parámetro clínico {idx}",
            "valor": f"{idx + 1}",
            "unidad": "mg/dL",
            "referencia": {"texto": "0 - 10"},
            "bandera": "NORMAL",
            "es_calculado": False,
            "calculable": True,
        }
        for idx in range(filas)
    ]
    return {
        "aprobado": aprobado,
        "folio": "2026-000001" if aprobado else None,
        "numero_orden": 7,
        "numero_version": 1 if aprobado else None,
        "publicado_en": "2026-11-12",
        "snapshot_sha256": "a" * 64,
        "paciente": {"nombre_completo": "Paciente Ficticio", "ci": "1234567", "sexo_texto": "Femenino", "edad": "35 años"},
        "orden": {"id_orden": 7, "medico_solicitante": "Dra. Ejemplo", "observaciones": ""},
        "firmante": {"nombre_completo": "Bioquímico de Prueba", "matricula": "MAT-001"},
        "estudios": [{"codigo": "QUIMICA", "nombre": "Química", "secciones": [{"grupo": "GENERAL", "parametros": parametros}]}],
    }


class InformePDFTests(unittest.TestCase):
    def test_troponina_cardíaca_se_imprime_sin_columnas_clinicas_numericas(self):
        documento = documento_aprobado(True)
        documento["estudios"] = [{
            "codigo": "PERFIL_CARDIACO",
            "nombre": "Perfil Cardíaco",
            "secciones": [{
                "grupo": "TROPONINA",
                "formato": "SELECCION_SIMPLE",
                "parametros": [{
                    "codigo": "TROPONINA_CARDIACA",
                    "nombre": "Troponina",
                    "tipo_campo": "SELECCION",
                    "valor": "Positivo",
                    "unidad": None,
                    "referencia": None,
                    "bandera": None,
                }],
            }],
        }]

        html = renderizar_html_informe(documento)

        self.assertIn(">Troponina<", html)
        self.assertIn(">Positivo<", html)
        for encabezado in (">Unidad</th>", ">V. Ref.</th>", ">Bandera</th>"):
            self.assertNotIn(encabezado, html)

    def test_selecciones_cualitativas_de_parasitologia_se_imprimen_sin_metadatos(self):
        documento = documento_aprobado(True)
        documento["estudios"] = [{
            "codigo": "PARASITOLOGIA",
            "nombre": "Parasitología",
            "secciones": [{
                "grupo": "GENERAL",
                "formato": "SELECCION_SIMPLE",
                "parametros": [
                    {"codigo": "H_PYLORI_HECES", "nombre": "Helicobacter pylori (heces)", "valor": "Negativo"},
                    {"codigo": "SANGRE_OCULTA_HECES", "nombre": "Sangre oculta en heces", "valor": "Positivo"},
                ],
            }],
        }]

        html = renderizar_html_informe(documento)

        self.assertIn(">Helicobacter pylori (heces)<", html)
        self.assertIn(">Sangre oculta en heces<", html)
        self.assertIn(">Negativo<", html)
        self.assertIn(">Positivo<", html)
        for encabezado in (">Unidad</th>", ">V. Ref.</th>", ">Bandera</th>"):
            self.assertNotIn(encabezado, html)

    def test_serologia_inmuno_imprime_muestra_y_metodo_en_informe(self):
        documento = documento_aprobado(False)
        documento["estudios"] = [{
            "codigo": "INMUNOSEROLOGIA",
            "nombre": "Inmunoserología",
            "secciones": [{
                "grupo": "PARASITOLOGIA",
                "columnas": {"muestra": True, "metodo": True},
                "parametros": [
                    {"codigo": "H_PYLORI_SUERO", "nombre": "HELICOBACTER PYLORI", "valor": "Positivo",
                     "muestra": "Suero", "metodo": "Inmunocromatografico"},
                    {"codigo": "SANGRE_OCULTA_HECES_INMUNO", "nombre": "Sangre oculta en heces", "valor": "Reactivo",
                     "muestra": "Heces", "metodo": "Inmunocromatografico"},
                ],
            }],
        }]

        html = renderizar_html_informe(documento)

        self.assertIn(">SEROLOGIA<", html)
        self.assertIn(">SANGRE OCULTA EN HECES<", html)
        self.assertNotIn(">Sangre oculta en heces<", html)
        self.assertIn(">Muestra<", html)
        self.assertIn(">Método<", html)
        self.assertIn(">Suero<", html)
        self.assertIn(">Heces<", html)
        self.assertIn(">Inmunocromatografico<", html)

    def test_informe_historico_de_serologia_conserva_presentacion_sin_metadatos(self):
        documento = documento_aprobado(True)
        documento["estudios"] = [{
            "codigo": "INMUNOSEROLOGIA",
            "nombre": "Inmunoserología",
            "secciones": [{
                "grupo": "PARASITOLOGIA",
                "parametros": [{
                    "codigo": "H_PYLORI_SUERO",
                    "nombre": "HELICOBACTER PYLORI",
                    "valor": "Positivo",
                    "muestra": "Suero",
                    "metodo": "Inmunocromatografico",
                }],
            }],
        }]

        html = renderizar_html_informe(documento)

        self.assertIn(">PARASITOLOGÍA<", html)
        self.assertNotIn(">SEROLOGIA<", html)
        self.assertNotIn(">Muestra<", html)
        self.assertNotIn(">Método<", html)

    def test_curva_en_previa_imprime_ejes_fijos_e_intervalos_temporales(self):
        curva = construir_curva(CURVA_TOLERANCIA.captura["curva_tolerancia"], {
            "CURVA_BASAL_HORA": "08:00",
            "CURVA_BASAL_GLUCOSA": "90",
            "CURVA_PRIMERA_HORA": "08:35",
            "CURVA_PRIMERA_GLUCOSA": "142",
            "CURVA_SEGUNDA_HORA": "09:20",
            "CURVA_SEGUNDA_GLUCOSA": "118",
            "CURVA_CUARTA_HORA": "10:05",
            "CURVA_CUARTA_GLUCOSA": "96",
        }, date(2025, 1, 1))
        documento = documento_aprobado(True)
        documento["estudios"] = [{
            "codigo": "CURVA_TOLERANCIA",
            "nombre": "Curva de tolerancia",
            "secciones": [{"grupo": "GENERAL", "parametros": [{"codigo": "CURVA", "nombre": "Glucosa", "valor": "90"}]}],
            "curva_tolerancia": curva,
        }]

        html = renderizar_html_informe(documento)
        self.assertEqual(html.count('class="curva-chart-grid"'), 11)
        self.assertEqual(html.count('class="curva-chart-grid-x"'), 4)
        self.assertIn('viewBox="0 0 720 300"', html)
        self.assertIn('class="curva-chart-line" fill="none" stroke="#d12b40" stroke-width="2"', html)
        self.assertIn('class="curva-chart-point" fill="#fff" stroke="#d12b40" stroke-width="2"', html)
        self.assertIn('class="curva-chart-grid" fill="none" stroke="#d3d3d3" stroke-width="1"', html)
        self.assertIn('transform="translate(6 ', html)
        self.assertNotIn(".curva-chart-line, .curva-chart-point { stroke: #333; }", html)
        for hora in ("08:00", "08:35", "09:20", "10:05"):
            self.assertIn(f">{hora}</text>", html)
        self.assertIn(">142<", html)
        self.assertEqual(len(HTML(string=html, base_url=f"{ASSETS_DIR.resolve().as_uri()}/").render().pages), 1)

    def test_curva_fuera_de_escala_conserva_el_valor_y_marca_el_borde(self):
        curva = construir_curva(CURVA_TOLERANCIA.captura["curva_tolerancia"], {
            "CURVA_BASAL_HORA": "08:00",
            "CURVA_BASAL_GLUCOSA": "230",
        }, date(2025, 1, 1))
        documento = documento_aprobado(True)
        documento["estudios"] = [{
            "codigo": "CURVA_TOLERANCIA",
            "nombre": "Curva de tolerancia",
            "secciones": [{"grupo": "GENERAL", "parametros": [{"codigo": "CURVA", "nombre": "Glucosa", "valor": "230"}]}],
            "curva_tolerancia": curva,
        }]

        html = renderizar_html_informe(documento)

        self.assertIn(">230<", html)
        self.assertIn('class="curva-chart-point-outside"', html)
        self.assertIn("fuera de escala 0–200 mg/dL; valor exacto en la tabla", html)
        self.assertEqual(len(HTML(string=html, base_url=f"{ASSETS_DIR.resolve().as_uri()}/").render().pages), 1)

    def test_fechas_horas_y_responsable_sin_hash_version_ni_matricula(self):
        documento = documento_aprobado(True)
        documento["publicado_en"] = "2026-11-20T02:10:11+00:00"
        documento["orden"]["fecha_hora_toma_muestra"] = "2026-11-19T16:05:00+00:00"
        original = deepcopy(documento)
        html = renderizar_html_informe(documento)
        for esperado in ("19/11/2026", "12:05", "22:10", "Hora de toma de muestra:", "Hora de entrega de resultado:", "LIC. Bioquímico de Prueba"):
            self.assertIn(esperado, html)
        for excluido in ("SHA-256", "a" * 64, "MAT-001", "Mat.", "Versión V", documento["publicado_en"]):
            self.assertNotIn(excluido, html)
        self.assertEqual(documento, original)

    def test_hora_toma_recurre_a_creacion_y_previa_no_inventa_hora_entrega(self):
        documento = documento_aprobado(False)
        documento["orden"]["creado_en"] = "2026-11-19T15:20:00Z"
        documento["firmante"]["nombre_completo"] = "Lic. Bioquímico de Prueba"
        html = renderizar_html_informe(documento)
        self.assertIn("19/11/2026", html)
        self.assertIn("11:20", html)
        self.assertIn("Pendiente de publicación", html)
        self.assertNotIn("LIC. Lic.", html)
        documento["orden"] = {"fecha_solicitud": "2026-11-19"}
        html = renderizar_html_informe(documento)
        self.assertIn("No registrada", html)
        self.assertNotIn(">00:00<", html)

    def test_firma_se_repite_abajo_en_todas_las_paginas_sin_invadir_resultados(self):
        documento = documento_aprobado(True, filas=100)
        paginas = HTML(string=renderizar_html_informe(documento), base_url=f"{ASSETS_DIR.resolve().as_uri()}/").render().pages
        self.assertGreater(len(paginas), 1)
        for pagina in paginas:
            firmas = [caja for caja in pagina._page_box.descendants() if caja.element is not None
                      and "page-signature" in (caja.element.get("class") or "").split()]
            filas = [caja for caja in pagina._page_box.descendants() if caja.element_tag == "tr"]
            self.assertTrue(firmas)
            self.assertGreater(firmas[0].position_y, pagina.height * 0.80)
            self.assertTrue(all(fila.position_y + fila.height <= firmas[0].position_y for fila in filas))

    def _paginas_con_dos_estudios(self, primero: int, segundo: int):
        documento = documento_aprobado(True, filas=primero)
        documento["estudios"][0]["nombre"] = "Estudio primero ficticio"
        otro = documento_aprobado(True, filas=segundo)["estudios"][0]
        otro["nombre"] = "Estudio segundo ficticio"
        otro["codigo"] = "OTRO_ESTUDIO"
        documento["estudios"].append(otro)
        paginas = HTML(string=renderizar_html_informe(documento), base_url=f"{ASSETS_DIR.resolve().as_uri()}/").render().pages
        titulos = []
        for pagina in paginas:
            titulos.append({caja.text.casefold() for caja in pagina._page_box.descendants() if caja.element_tag == "h2" and hasattr(caja, "text")})
        return paginas, titulos

    def test_estudio_corto_comparte_hoja_si_cabe_completo(self):
        paginas, titulos = self._paginas_con_dos_estudios(2, 2)
        self.assertEqual(len(paginas), 1)
        self.assertEqual(titulos[0], {"estudio primero ficticio", "estudio segundo ficticio"})

    def test_estudio_que_no_cabe_empieza_completo_en_otra_hoja(self):
        paginas, titulos = self._paginas_con_dos_estudios(12, 20)
        self.assertEqual(len(paginas), 2)
        self.assertNotIn("estudio segundo ficticio", titulos[0])
        self.assertIn("estudio segundo ficticio", titulos[1])

    def test_estudio_mayor_a_una_hoja_tambien_inicia_en_hoja_nueva(self):
        paginas, titulos = self._paginas_con_dos_estudios(3, 90)
        self.assertGreater(len(paginas), 2)
        self.assertNotIn("estudio segundo ficticio", titulos[0])
        self.assertIn("estudio segundo ficticio", titulos[1])

    def test_logo_del_hospital_se_encuentra_centrado(self):
        documento = documento_aprobado(True)
        pagina = HTML(string=renderizar_html_informe(documento), base_url=f"{ASSETS_DIR.resolve().as_uri()}/").render().pages[0]
        logos = [caja for caja in pagina._page_box.descendants() if caja.element is not None
                 and caja.element.get("class") == "logo-metodista"]
        self.assertTrue(logos)
        self.assertAlmostEqual(logos[0].content_box_x() + logos[0].width / 2, pagina.width / 2, delta=2)

    def test_inmunoserologia_larga_continua_sin_perder_filas_ni_invadir_firma(self):
        documento = documento_aprobado(True, filas=90)
        documento["estudios"][0].update(codigo="INMUNOSEROLOGIA", nombre="Inmunoserología ficticia")
        pdf_bytes = generar_informe_pdf(documento)
        textos = []
        with pdfium.PdfDocument(pdf_bytes) as pdf:
            self.assertGreater(len(pdf), 1)
            for indice in range(len(pdf)):
                pagina = pdf[indice]
                texto = pagina.get_textpage()
                contenido = texto.get_text_range()
                self.assertIn("LIC. Bioquímico de Prueba", contenido)
                self.assertIn("Parámetro", contenido)
                textos.append(contenido)
                texto.close()
                pagina.close()
        contenido_total = "\n".join(textos)
        for indice in range(90):
            self.assertRegex(contenido_total, rf"Parámetro clínico {indice}(?!\d)")

    def test_marca_no_aprobado_se_genera_solo_para_preliminares(self):
        preliminar = renderizar_html_informe(documento_aprobado(False))
        aprobado = renderizar_html_informe(documento_aprobado(True))
        self.assertIn("marca-agua-no-aprobado.svg", preliminar)
        self.assertIn("NO APROBADO", preliminar)
        self.assertNotIn("marca-agua-no-aprobado.svg", aprobado)
        self.assertIn("marca-agua-institucional.svg", aprobado)

    def test_resultado_largo_se_divide_en_paginas_letter(self):
        documento = documento_aprobado(True, filas=100)
        html = renderizar_html_informe(documento)
        paginas = HTML(string=html, base_url=f"{ASSETS_DIR.resolve().as_uri()}/").render().pages
        pdf = generar_informe_pdf(documento)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreaterEqual(len(paginas), 2)

    def test_no_imprime_parametros_vacios_y_formatea_fr(self):
        documento = documento_aprobado(True)
        documento["estudios"] = [{
            "codigo": "INMUNOSEROLOGIA", "nombre": "Inmunoserología", "secciones": [{"grupo": "FACTOR_REUMATOIDEO", "parametros": [
                {"codigo": "FR_DILUCION", "nombre": "Factor reumatoideo", "valor": "Reactivo 1/32: 256 UI/mL; sensibilidad 8 UI/mL; lote LOTE-7; controles + Conforme", "unidad": "dilución", "referencia": {"texto": "< 8 UI/mL"}},
                {"codigo": "OTRO_CAMPO", "nombre": "Campo sin resultado", "valor": None, "unidad": None},
            ]}]
        }]
        html = renderizar_html_informe(documento)
        self.assertIn("Reactivo · 1/32 · 256 UI/mL", html)
        self.assertNotIn("sensibilidad 8 UI/mL", html)
        self.assertNotIn("Campo sin resultado", html)

    def test_distingue_vacios_cero_defectos_y_no_calculables(self):
        documento = documento_aprobado(False)
        documento["estudios"][0]["secciones"][0]["parametros"] = [
            {"codigo": "VACIO", "nombre": "Vacío omitido", "valor": "  "},
            {"codigo": "CERO", "nombre": "Cero capturado", "valor": "0", "tipo_campo": "NUMERICO"},
            {"codigo": "DECIMAL", "nombre": "Decimal capturado", "valor": "1234567.22", "tipo_campo": "NUMERICO"},
            {"codigo": "DEFECTO", "nombre": "Defecto sin confirmar", "valor": "Negativo", "es_defecto": True, "confirmado": False},
            {"codigo": "CONFIRMADO", "nombre": "Defecto confirmado", "valor": "Negativo", "es_defecto": True, "confirmado": True},
            {"codigo": "FALTA", "nombre": "Calculado pendiente", "valor": None, "es_calculado": True, "calculable": False, "codigo_motivo_no_calculable": "FALTA_ENTRADA"},
            {"codigo": "LDL", "nombre": "LDL inválido por regla", "valor": None, "es_calculado": True, "calculable": False, "codigo_motivo_no_calculable": "REGLA_INVALIDA"},
        ]
        documento["estudios"].append({"codigo": "VACIO", "nombre": "Estudio vacío omitido", "secciones": [{"parametros": [{"valor": None}]}]})
        original = deepcopy(documento)
        html = renderizar_html_informe(documento)
        for omitido in ("Vacío omitido", "Defecto sin confirmar", "Calculado pendiente", "Estudio vacío omitido"):
            self.assertNotIn(omitido, html)
        for visible in ("Cero capturado", ">0<", "1.234.567,22", "Defecto confirmado", "LDL inválido por regla", "No calculable"):
            self.assertIn(visible, html)
        self.assertEqual(documento, original)

    def test_todas_las_paginas_son_carta_y_repiten_membrete(self):
        pdf = pdfium.PdfDocument(generar_informe_pdf(documento_aprobado(True, filas=100)))
        try:
            self.assertGreater(len(pdf), 1)
            for indice in range(len(pdf)):
                pagina = pdf[indice]
                try:
                    self.assertEqual(pagina.get_size(), (612.0, 792.0))
                    texto = pagina.get_textpage()
                    try:
                        contenido = texto.get_text_range()
                        self.assertIn("LABORATORIO CLÍNICO", contenido)
                        self.assertIn("14 de Septiembre", contenido)
                        self.assertIn(f"Página {indice + 1} de {len(pdf)}", contenido)
                    finally:
                        texto.close()
                finally:
                    pagina.close()
        finally:
            pdf.close()

    def test_vista_previa_entrega_imagenes_carta_sin_pdf(self):
        vista = generar_vista_previa(documento_aprobado(False))
        self.assertEqual(vista["formato"], "Carta")
        self.assertEqual(len(vista["paginas"]), 1)
        pagina = vista["paginas"][0]
        self.assertEqual((pagina["ancho"], pagina["alto"]), (1224, 1584))
        self.assertTrue(pagina["imagen"].startswith("data:image/png;base64,"))
        contenido = base64.b64decode(pagina["imagen"].split(",", 1)[1])
        self.assertFalse(contenido.startswith(b"%PDF"))
        with Image.open(BytesIO(contenido)) as imagen:
            self.assertEqual(imagen.size, (1224, 1584))

    def test_no_se_puede_aprobar_desde_el_cuerpo_de_vista_previa(self):
        with self.assertRaises(ValidationError):
            VistaPreviaRequest.model_validate({"valores": {}, "aprobado": True})


if __name__ == "__main__":
    unittest.main()
