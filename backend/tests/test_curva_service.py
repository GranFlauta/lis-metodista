from datetime import date, datetime
from decimal import Decimal
import unittest

from app.catalog.definitions import CURVA_TOLERANCIA
from app.core.errors import ValidacionError
from app.reports.curva import preparar_curva
from app.services.curva_service import construir_curva


class TestCurvaTolerancia(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CURVA_TOLERANCIA.captura["curva_tolerancia"]

    def test_curva_temporal_con_intervalos_irregulares_y_hueco(self) -> None:
        valores = {
            "CURVA_BASAL_HORA": "08:00",
            "CURVA_BASAL_GLUCOSA": "90",
            "CURVA_PRIMERA_HORA": "08:35",
            "CURVA_PRIMERA_GLUCOSA": "142",
            "CURVA_SEGUNDA_HORA": "09:20",
            "CURVA_SEGUNDA_GLUCOSA": "118",
            "CURVA_CUARTA_HORA": "10:05",
            "CURVA_CUARTA_GLUCOSA": "96",
        }
        curva = construir_curva(self.config, valores, date(2025, 1, 1))

        self.assertEqual(len([fila for fila in curva["filas"] if fila["instante"]]), 4)
        instantes = [datetime.fromisoformat(curva["filas"][indice]["instante"]) for indice in (0, 1, 2, 4)]
        self.assertEqual((instantes[1] - instantes[0]).total_seconds() // 60, 35)
        self.assertEqual((instantes[2] - instantes[1]).total_seconds() // 60, 45)
        self.assertIsNone(curva["filas"][3]["instante"])
        self.assertEqual(curva["filas"][1]["minutos_desde_basal"], "35")

        preparado = preparar_curva(curva, ",")
        self.assertEqual(preparado["alto"], 300)
        self.assertEqual(len(preparado["puntos"]), 4)
        self.assertEqual(len(preparado["segmentos"]), 1)
        self.assertEqual(preparado["segmentos"][0]["path"].count("L"), 2)
        self.assertEqual([tick["valor"] for tick in preparado["ticks_y"]], [str(valor) for valor in range(0, 201, 20)])
        self.assertEqual([tick["hora"] for tick in preparado["ticks_x"]], ["08:00", "08:35", "09:20", "10:05"])
        x0, x1, x2 = (Decimal(preparado["puntos"][indice]["x"]) for indice in range(3))
        self.assertLess(abs((x1 - x0) / (x2 - x1) - Decimal(35) / Decimal(45)), Decimal("0.02"))
        y_top, y_bottom = Decimal(preparado["ticks_y"][-1]["y"]), Decimal(preparado["ticks_y"][0]["y"])
        self.assertEqual(y_top, Decimal(preparado["arriba"]))
        self.assertEqual(y_bottom, Decimal(preparado["alto"] - preparado["abajo"]))

    def test_cruce_de_medianoche_requiere_fecha_explicita_y_calcula_intervalo(self) -> None:
        valores = {
            "CURVA_BASAL_HORA": "23:50",
            "CURVA_BASAL_GLUCOSA": "90",
            "CURVA_PRIMERA_HORA": "00:25",
            "CURVA_PRIMERA_GLUCOSA": "100",
            "CURVA_PRIMERA_FECHA": "2025-01-02",
        }
        sin_fecha = construir_curva(self.config, {k: v for k, v in valores.items() if k != "CURVA_PRIMERA_FECHA"}, date(2025, 1, 1))
        self.assertIsNotNone(sin_fecha["filas"][1]["error"])
        self.assertIsNone(sin_fecha["filas"][1]["instante"])

        con_fecha = construir_curva(self.config, valores, date(2025, 1, 1))
        self.assertEqual(con_fecha["filas"][1]["minutos_desde_basal"], "35")

    def test_guarda_toma_parcial_sin_convertir_cero_en_vacio(self) -> None:
        curva = construir_curva(self.config, {
            "CURVA_BASAL_HORA": "08:00",
            "CURVA_BASAL_GLUCOSA": "0",
        }, date(2025, 1, 1))
        self.assertEqual(curva["filas"][0]["glucosa_valor"], "0")
        self.assertIsNone(curva["filas"][0]["error"])

        parcial = construir_curva(self.config, {"CURVA_BASAL_HORA": "08:00"}, date(2025, 1, 1))
        self.assertEqual(parcial["filas"][0]["hora_valor"], "08:00")
        self.assertIsNone(parcial["filas"][0]["instante"])
        self.assertIsNotNone(parcial["filas"][0]["error"])

    def test_hora_invalida_se_rechaza_y_puntos_coincidentes_no_dividen_por_cero(self) -> None:
        with self.assertRaises(ValidacionError):
            construir_curva(self.config, {"CURVA_BASAL_HORA": "8:00"}, date(2025, 1, 1))

        curva = construir_curva(self.config, {
            "CURVA_BASAL_HORA": "08:00",
            "CURVA_BASAL_GLUCOSA": "90",
            "CURVA_PRIMERA_HORA": "08:00",
            "CURVA_PRIMERA_GLUCOSA": "90",
        }, date(2025, 1, 1))
        preparado = preparar_curva(curva, ",")
        self.assertEqual(len(preparado["puntos"]), 2)
        self.assertEqual(preparado["puntos"][0]["x"], preparado["puntos"][1]["x"])
        self.assertEqual(preparado["puntos"][0]["y"], preparado["puntos"][1]["y"])

    def test_resultado_fuera_de_escala_se_mantiene_exactamente_y_se_indica(self) -> None:
        curva = construir_curva(self.config, {
            "CURVA_BASAL_HORA": "08:00",
            "CURVA_BASAL_GLUCOSA": "230",
        }, date(2025, 1, 1))

        preparado = preparar_curva(curva, ",")

        self.assertEqual(preparado["filas"][0]["glucosa"], "230")
        self.assertEqual(preparado["puntos"][0]["glucosa"], Decimal("230"))
        self.assertTrue(preparado["puntos"][0]["fuera_de_escala"])
        self.assertLess(Decimal(preparado["puntos"][0]["y"]), Decimal(preparado["arriba"]))


if __name__ == "__main__":
    unittest.main()
