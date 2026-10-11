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
    def test_son_9_estudios(self):
        self.assertEqual(len(ESTUDIOS), 9)

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
        self.assertEqual(usados, set(ESTUDIOS_POR_CODIGO))

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


if __name__ == "__main__":
    unittest.main()
