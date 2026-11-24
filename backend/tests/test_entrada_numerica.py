"""Regresiones de captura decimal, sin conexión a base de datos."""
from decimal import Decimal
import unittest

from app.core.errors import ValidacionError
from app.models.catalog import Parametro
from app.services.evaluacion_service import normalizar_y_validar_valor_entrada


class EntradaNumericaTests(unittest.TestCase):
    def test_decimales_en_campos_con_precision_de_presentacion_cero(self):
        for codigo in ("GLOBULOS_BLANCOS", "VES", "PLAQUETAS", "GOT_AST", "GPT_ALT", "FOSFATASA_ALCALINA", "GGT"):
            parametro = Parametro(codigo=codigo, tipo_campo="NUMERICO", decimales=0)
            for entrada in ("2.2", "2,2"):
                with self.subTest(codigo=codigo, entrada=entrada):
                    self.assertEqual(normalizar_y_validar_valor_entrada(parametro, entrada), (Decimal("2.2"), None))

    def test_no_redondea_ni_cambia_la_escala_de_la_entrada(self):
        parametro = Parametro(codigo="PLAQUETAS", tipo_campo="NUMERICO", decimales=0)
        for entrada in ("1234567", "1234567.123456", "2.200", "0", "0.00"):
            with self.subTest(entrada=entrada):
                valor, texto = normalizar_y_validar_valor_entrada(parametro, entrada)
                self.assertEqual(valor, Decimal(entrada))
                self.assertIsNone(texto)

    def test_vacio_sigue_siendo_ausencia(self):
        parametro = Parametro(codigo="VES", tipo_campo="NUMERICO", decimales=0)
        for entrada in (None, "", "   "):
            self.assertEqual(normalizar_y_validar_valor_entrada(parametro, entrada), (None, None))

    def test_rechaza_no_finitos_negativos_y_precision_excesiva(self):
        parametro = Parametro(codigo="GOT_AST", tipo_campo="NUMERICO", decimales=0)
        for entrada in ("-2.2", "NaN", "Infinity", "2.1234567", "1e-7", "1.234.567"):
            with self.subTest(entrada=entrada), self.assertRaises(ValidacionError):
                normalizar_y_validar_valor_entrada(parametro, entrada)
