import unittest

from weasyprint import HTML

from app.reports.pdf import ASSETS_DIR, generar_informe_pdf, renderizar_html_informe


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


if __name__ == "__main__":
    unittest.main()
