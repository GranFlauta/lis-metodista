"""Ejecutar:  cd backend && python -m unittest discover -s tests -v"""
import unittest
from decimal import Decimal as D

from app.calculation.engine import a_decimal, calcular, variables_de
from app.catalog.definitions import (
    CALCULADO, ESTUDIOS, ESTUDIOS_POR_CODIGO, PERFILES, SELECCION,
)


def calc_estudio(codigo, entradas):
    """Calcula todos los CALCULADOS de un estudio en orden de dependencia."""
    est = ESTUDIOS_POR_CODIGO[codigo]
    ctx = {k.lower(): (None if v is None else D(str(v))) for k, v in entradas.items()}
    pendientes = [p for p in est.parametros if p.tipo == CALCULADO]
    for _ in range(len(pendientes) + 1):
        for p in list(pendientes):
            if all(v in ctx or v in {x.codigo.lower() for x in pendientes}
                   for v in variables_de(p.formula)):
                ctx[p.codigo.lower()] = calcular(p.formula, ctx, p.decimales).valor
                pendientes.remove(p)
    return ctx


class TestFormulas(unittest.TestCase):
    def test_hemograma_estimados(self):
        r = calc_estudio("HEMOGRAMA", {"hematocrito": 45})
        self.assertEqual(r["globulos_rojos"], D("4815000"))
        self.assertEqual(r["hemoglobina"], D("14.4"))

    def test_vacio_no_es_cero(self):
        # El Excel mostraba 0 con hematocrito vacío. Aquí debe ser NO calculable.
        r = calc_estudio("HEMOGRAMA", {"hematocrito": None})
        self.assertIsNone(r["globulos_rojos"])
        self.assertIsNone(r["hemoglobina"])

    def test_diferencial_porcentaje_a_absoluto(self):
        r = calc_estudio("HEMOGRAMA", {"globulos_blancos": 8000, "segmentados_pct": 60})
        self.assertEqual(r["segmentados_abs"], D("4800"))

    def test_diferencial_sin_gb_no_calculable(self):
        r = calc_estudio("HEMOGRAMA", {"globulos_blancos": None, "segmentados_pct": 60})
        self.assertIsNone(r["segmentados_abs"])

    def test_lipidico_valores_del_excel(self):
        # Colesterol 164.5, TG 102.4 (Excel) con un HDL real de 40
        r = calc_estudio("PERFIL_LIPIDICO", {"colesterol": "164.5", "trigliceridos": "102.4", "hdl": 40})
        self.assertEqual(r["vldl"], D("20.48"))
        self.assertEqual(r["ldl"], D("104.02"))

    def test_lipidico_excel_calculaba_ldl_sin_hdl(self):
        # El Excel dio LDL=144.02 con HDL vacío (error). Aquí no se calcula.
        r = calc_estudio("PERFIL_LIPIDICO", {"colesterol": "164.5", "trigliceridos": "102.4", "hdl": None})
        self.assertIsNone(r["ldl"])

    def test_friedewald_invalido_con_tg_mayor_400(self):
        r = calc_estudio("PERFIL_LIPIDICO", {"colesterol": 250, "trigliceridos": 450, "hdl": 40})
        self.assertIsNone(r["ldl"])
        self.assertEqual(r["vldl"], D("90.00"))

    def test_friedewald_limite_400_si_calcula(self):
        r = calc_estudio("PERFIL_LIPIDICO", {"colesterol": 250, "trigliceridos": 400, "hdl": 40})
        self.assertEqual(r["ldl"], D("130.00"))

    def test_hepatograma_bilirrubina_indirecta(self):
        r = calc_estudio("HEPATOGRAMA", {"bilirrubina_total": "1.2", "bilirrubina_directa": "0.4"})
        self.assertEqual(r["bilirrubina_indirecta"], D("0.80"))

    def test_hepatograma_directa_mayor_que_total(self):
        r = calc_estudio("HEPATOGRAMA", {"bilirrubina_total": "0.5", "bilirrubina_directa": "0.9"})
        self.assertIsNone(r["bilirrubina_indirecta"])

    def test_proteinograma(self):
        r = calc_estudio("PROTEINOGRAMA", {"proteinas_totales": 7, "albumina": 4})
        self.assertEqual(r["globulina"], D("3.00"))
        self.assertEqual(r["relacion_ag"], D("1.33"))

    def test_proteinograma_sin_division_por_cero(self):
        # El Excel mostraba #DIV/0!
        r = calc_estudio("PROTEINOGRAMA", {"proteinas_totales": 4, "albumina": 4})
        self.assertIsNone(r["relacion_ag"])

    def test_proteinograma_albumina_mayor_que_total(self):
        r = calc_estudio("PROTEINOGRAMA", {"proteinas_totales": 3, "albumina": 4})
        self.assertIsNone(r["globulina"])
        self.assertIsNone(r["relacion_ag"])

    def test_coma_decimal(self):
        self.assertEqual(a_decimal("5,4"), D("5.4"))
        self.assertIsNone(a_decimal("  "))
        with self.assertRaises(ValueError):
            a_decimal("abc")

    def test_redondeo_half_up(self):
        self.assertEqual(calcular("x / 1", {"x": D("2.345")}, 2).valor, D("2.35"))


class TestSeguridadEvaluador(unittest.TestCase):
    def test_rechaza_codigo_arbitrario(self):
        for malo in ("__import__('os').system('id')", "x.__class__", "(lambda: 1)()",
                     "[1,2]", "'texto'", "x ** 2", "open('f')", "x if True else y.z"):
            with self.assertRaises((ValueError, SyntaxError), msg=malo):
                calcular(malo, {"x": D(1), "y": D(1)})

    def test_parametro_desconocido(self):
        with self.assertRaises(ValueError):
            calcular("inexistente * 2", {"x": D(1)})


class TestCatalogo(unittest.TestCase):
    def test_parasitologia_y_subestudios_cualitativos_de_inmunoserologia(self):
        parasitologia = ESTUDIOS_POR_CODIGO["PARASITOLOGIA"].parametros
        parasitologia_codigos = {p.codigo for p in parasitologia}
        self.assertNotIn("H_PYLORI_SUERO", parasitologia_codigos)
        self.assertTrue({"H_PYLORI_HECES", "SANGRE_OCULTA_HECES"} <= parasitologia_codigos)

        inmuno = ESTUDIOS_POR_CODIGO["INMUNOSEROLOGIA"].parametros
        inmuno_parasito = [p for p in inmuno if p.grupo == "PARASITOLOGIA"]
        self.assertEqual({p.codigo for p in inmuno_parasito}, {
            "H_PYLORI_SUERO", "H_PYLORI_HECES_INMUNO", "SANGRE_OCULTA_HECES_INMUNO",
        })
        self.assertFalse(parasitologia_codigos & {p.codigo for p in inmuno_parasito})
        valores_esperados = {
            "H_PYLORI_SUERO": ("HELICOBACTER PYLORI", ["Negativo", "Positivo"], "Suero"),
            "H_PYLORI_HECES_INMUNO": ("HELICOBACTER PYLORI", ["No reactivo", "Reactivo"], "Heces"),
            "SANGRE_OCULTA_HECES_INMUNO": ("Sangre oculta en heces", ["No reactivo", "Reactivo"], "Heces"),
        }
        for parametro in inmuno_parasito:
            with self.subTest(codigo=parametro.codigo):
                nombre, opciones, muestra = valores_esperados[parametro.codigo]
                self.assertEqual(parametro.nombre, nombre)
                self.assertEqual(parametro.opciones, opciones)
                self.assertEqual(parametro.muestra, muestra)
                self.assertEqual(parametro.metodo, "Inmunocromatografico")
                self.assertEqual(parametro.tipo, SELECCION)
                self.assertIsNone(parametro.unidad)
                self.assertFalse(parametro.rangos)

        for parametro in [
            p for p in parasitologia if p.codigo in {"H_PYLORI_HECES", "SANGRE_OCULTA_HECES"}
        ]:
            with self.subTest(codigo=parametro.codigo):
                self.assertEqual(parametro.tipo, SELECCION)
                self.assertEqual(parametro.opciones, ["Negativo", "Positivo"])
                self.assertIsNone(parametro.unidad)
                self.assertFalse(parametro.rangos)

    def test_ldh_en_quimica_y_cardio_y_troponina_cualitativa(self):
        ldh_quimica = next(p for p in ESTUDIOS_POR_CODIGO["QUIMICA_SANGUINEA"].parametros if p.nombre == "LDH")
        ldh_cardiaco = next(p for p in ESTUDIOS_POR_CODIGO["PERFIL_CARDIACO"].parametros if p.nombre == "LDH")
        for parametro in (ldh_quimica, ldh_cardiaco):
            with self.subTest(codigo=parametro.codigo):
                self.assertEqual(parametro.unidad, "UI/L")
                self.assertEqual(len(parametro.rangos), 1)
                rango = parametro.rangos[0]
                self.assertEqual((rango.inferior, rango.superior, rango.texto), (200, 400, "200-400 UI/L"))
                self.assertTrue(rango.inferior_incl and rango.superior_incl)
        self.assertNotEqual(ldh_quimica.codigo, ldh_cardiaco.codigo)

        troponina = next(p for p in ESTUDIOS_POR_CODIGO["PERFIL_CARDIACO"].parametros if p.codigo == "TROPONINA_CARDIACA")
        self.assertEqual(troponina.grupo, "TROPONINA")
        self.assertEqual((troponina.tipo, troponina.unidad, troponina.rangos, troponina.opciones),
                         (SELECCION, None, (), ["Negativo", "Positivo"]))

    def test_perfil_pancreatico_orden_y_referencias(self):
        parametros = ESTUDIOS_POR_CODIGO["PERFIL_PANCREATICO"].parametros
        primero, segundo = parametros
        self.assertEqual([p.codigo for p in parametros], ["AMILASA_SERICA", "LIPASA_SERICA"])
        self.assertEqual([(p.nombre, p.unidad) for p in parametros], [
            ("Lipasa sérica", "UI/L"),
            ("Amilasa sérica", "UA/dL"),
        ])
        rango_ui, rango_ua = primero.rangos[0], segundo.rangos[0]
        self.assertEqual((rango_ui.inferior, rango_ui.superior, rango_ui.texto), (10, 150, "10-150 UI/L"))
        self.assertIsNone(rango_ua.inferior)
        self.assertEqual((rango_ua.superior, rango_ua.texto), (120, "Hasta 120 UA/dL"))
        self.assertTrue(rango_ui.inferior_incl and rango_ui.superior_incl and rango_ua.superior_incl)

    def test_perfil_lipidico_ubica_ldl_antes_de_vldl(self):
        parametros = ESTUDIOS_POR_CODIGO["PERFIL_LIPIDICO"].parametros
        self.assertEqual(
            [p.codigo for p in parametros],
            ["COLESTEROL", "TRIGLICERIDOS", "HDL", "LDL", "VLDL"],
        )

    def test_son_13_estudios(self):
        self.assertEqual(len(ESTUDIOS), 13)

    def test_codigos_unicos_por_estudio(self):
        for est in ESTUDIOS:
            codigos = [p.codigo for p in est.parametros]
            self.assertEqual(len(codigos), len(set(codigos)), est.codigo)

    def test_formulas_usan_solo_parametros_del_mismo_estudio(self):
        for est in ESTUDIOS:
            codigos = {p.codigo.lower() for p in est.parametros}
            for p in est.parametros:
                if p.tipo == CALCULADO:
                    self.assertTrue(p.formula, f"{est.codigo}.{p.codigo} sin fórmula")
                    self.assertLessEqual(variables_de(p.formula), codigos, f"{est.codigo}.{p.codigo}")
                else:
                    self.assertIsNone(p.formula, f"{est.codigo}.{p.codigo} tiene fórmula pero no es CALCULADO")

    def test_selecciones_tienen_opciones_y_defectos_validos(self):
        for est in ESTUDIOS:
            for p in est.parametros:
                if p.tipo == SELECCION:
                    self.assertTrue(p.opciones, f"{est.codigo}.{p.codigo}")
                if p.defecto and p.opciones:
                    self.assertIn(p.defecto, p.opciones, f"{est.codigo}.{p.codigo}")
                if p.confirmar:
                    self.assertTrue(p.defecto, f"{p.codigo}: confirmar sin valor por defecto")

    def test_perfiles_cubren_los_9_estudios(self):
        usados = {c for perfil in PERFILES for c, _ in perfil.estudios}
        self.assertEqual(usados, set(ESTUDIOS_POR_CODIGO) - {
            "PERFIL_CARDIACO", "PERFIL_PANCREATICO", "PARASITOLOGIA", "CURVA_TOLERANCIA",
        })

    def test_grupos_de_perfil_existen(self):
        for perfil in PERFILES:
            for codigo, grupos in perfil.estudios:
                if grupos:
                    existentes = {p.grupo for p in ESTUDIOS_POR_CODIGO[codigo].parametros}
                    self.assertLessEqual(set(grupos), existentes, f"{perfil.codigo}/{codigo}")

    def test_rangos_coherentes(self):
        for est in ESTUDIOS:
            for p in est.parametros:
                for r in p.rangos:
                    if r.inferior is not None and r.superior is not None:
                        self.assertLessEqual(r.inferior, r.superior, f"{est.codigo}.{p.codigo}")
                    self.assertIn(r.sexo, (None, "M", "F"))

    def test_reglas_referencian_parametros_existentes(self):
        for est in ESTUDIOS:
            codigos = {p.codigo for p in est.parametros}
            for regla in est.reglas:
                self.assertLessEqual(set(regla["parametros"]), codigos, est.codigo)

    def test_ego_quimica_opciones_enriquecidas(self):
        from app.catalog.definitions import EGO
        from app.services.evaluacion_service import _es_seleccion_simple, normalizar_y_validar_valor_entrada
        from app.models.catalog import Parametro

        params_quimicos = {p.codigo: p for p in EGO.parametros if p.grupo == "QUIMICO"}
        self.assertIn("+ 30 mg/dL", params_quimicos["PROTEINAS"].opciones)
        self.assertIn("Trazas (50 mg/dL)", params_quimicos["GLUCOSA"].opciones)
        self.assertIn("++++ 160 mg/dL", params_quimicos["CETONAS"].opciones)
        self.assertIn("+ 70 Leu/µL", params_quimicos["ESTERASA_LEUCOCITARIA"].opciones)
        self.assertIn("Trazas (0.5 mg/dL)", params_quimicos["PIGMENTOS_BILIARES"].opciones)
        self.assertIn("+++ 200 Eri/µL", params_quimicos["SANGRE"].opciones)

        # SELECCION_SIMPLE debe ser True para la sección química de EGO
        dummy_params = [{"tipo_campo": "SELECCION", "unidad": None, "referencia": None} for _ in range(8)]
        self.assertTrue(_es_seleccion_simple("EGO", dummy_params))

        # Texto editable libre para EGO químico debe normalizar correctamente
        p_dummy = Parametro(codigo="PROTEINAS", tipo_campo="SELECCION", opciones=params_quimicos["PROTEINAS"].opciones)
        _, txt = normalizar_y_validar_valor_entrada(p_dummy, "+ 30 mg/dL (moderado)")
        self.assertEqual(txt, "+ 30 mg/dL (moderado)")


if __name__ == "__main__":
    unittest.main()
