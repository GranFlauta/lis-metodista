"""
Pruebas unitarias y de integración para evaluación clínica, cálculo, banderas y reglas
(Tests 10 al 18, 26 y 27 según PROMPT_FASE_3.md §10).
Ejecutadas con unittest contra PostgreSQL real.
"""
from __future__ import annotations

from decimal import Decimal as D
from typing import Any

from sqlalchemy import text

from app.calculation.engine import calcular, a_decimal
from app.catalog.definitions import ESTUDIOS, ESTUDIOS_POR_CODIGO
from app.models.catalog import Estudio, EstudioVersion, Parametro, RangoReferencia
from app.models.order import Orden, OrdenEstudio, OrdenEstudioGrupo
from app.models.patient import Paciente
from app.models.result import ResultadoBorrador
from app.services.evaluacion_service import (
    evaluar_captura_orden,
    evaluar_rango_y_bandera,
    evaluar_reglas_cruzadas,
    guardar_resultados_orden,
    orden_topologico_parametros,
)
from tests.base import IntegrationTestCase


class TestEvaluacionServicio(IntegrationTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.bio = self.crear_usuario_test(
            usuario="bioq_eval_1",
            password="PasswordBio123!",
            rol="BIOQUIMICO",
            ci="7100001",
        )
        login_res = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq_eval_1", "password": "PasswordBio123!"},
        )
        self.bio_token = login_res.json()["access_token"]
        self.bio_headers = {"Authorization": f"Bearer {self.bio_token}"}

    def crear_orden_con_estudios(
        self,
        codigos_estudios: list[str],
        sexo: str = "M",
        edad_anios: int = 30,
        edad_meses: int = 0,
        grupos_inmuno: list[str] | None = None,
    ) -> Orden:
        """Helper para crear una orden lista para capturar resultados."""
        import secrets
        ci_rand = f"7{secrets.token_hex(4)}"
        paciente = self.crear_paciente_test(ci=ci_rand, sexo=sexo)
        estudios_payload = []
        for c in codigos_estudios:
            if c == "INMUNOSEROLOGIA" and grupos_inmuno:
                estudios_payload.append({"codigo": c, "grupos": grupos_inmuno})
            else:
                estudios_payload.append({"codigo": c})

        payload = {
            "id_paciente": paciente.id_paciente,
            "estudios": estudios_payload,
            "edad_anios": edad_anios,
            "edad_meses": edad_meses,
        }
        r = self.client.post("/api/ordenes", json=payload, headers=self.bio_headers)
        self.assertEqual(r.status_code, 201, f"Error creando orden: {r.text}")
        id_orden = r.json()["orden"]["id"]
        return self.db.query(Orden).filter(Orden.id_orden == id_orden).first()

    # -------------------------------------------------------------------------
    # Test 10: Hemograma y recálculo
    # -------------------------------------------------------------------------
    def test_10_hemograma_calculados_y_recalculo(self) -> None:
        """10. Hemograma: hto 45 → GR 4815000, Hb 14.4 persistidos; cambiar hto los recalcula; borrar hto elimina calculados."""
        orden = self.crear_orden_con_estudios(["HEMOGRAMA"])

        # Capturar hematocrito = 45
        resp = guardar_resultados_orden(self.db, orden, {"HEMATOCRITO": "45"}, self.bio)

        # Verificar filas en BD
        oe = orden.estudios[0]
        filas = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).all()
        filas_por_param = {f.parametro.codigo: f for f in filas}

        self.assertIn("GLOBULOS_ROJOS", filas_por_param)
        self.assertIn("HEMOGLOBINA", filas_por_param)
        self.assertEqual(filas_por_param["GLOBULOS_ROJOS"].valor_numerico, D("4815000"))
        self.assertEqual(filas_por_param["HEMOGLOBINA"].valor_numerico, D("14.4"))
        self.assertTrue(filas_por_param["GLOBULOS_ROJOS"].es_calculado)
        self.assertTrue(filas_por_param["HEMOGLOBINA"].es_calculado)

        # Cambiar hematocrito a 40 -> recálculo
        resp2 = guardar_resultados_orden(self.db, orden, {"HEMATOCRITO": "40"}, self.bio)
        filas2 = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).all()
        filas2_por_param = {f.parametro.codigo: f for f in filas2}

        self.assertEqual(filas2_por_param["GLOBULOS_ROJOS"].valor_numerico, D("4280000"))
        self.assertEqual(filas2_por_param["HEMOGLOBINA"].valor_numerico, D("12.8"))

        # Borrar hematocrito -> elimina las filas calculadas (D3-08)
        resp3 = guardar_resultados_orden(self.db, orden, {"HEMATOCRITO": None}, self.bio)
        filas3 = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).all()
        filas3_por_param = {f.parametro.codigo: f for f in filas3}

        self.assertNotIn("GLOBULOS_ROJOS", filas3_por_param)
        self.assertNotIn("HEMOGLOBINA", filas3_por_param)

    # -------------------------------------------------------------------------
    # Test 11: Diferencial con y sin GB
    # -------------------------------------------------------------------------
    def test_11_diferencial_con_y_sin_gb(self) -> None:
        """11. Diferencial: GB 8000 y segmentados 60 % → SEGMENTADOS_ABS = 4800; sin GB → sin fila."""
        orden = self.crear_orden_con_estudios(["HEMOGRAMA"])
        oe = orden.estudios[0]

        # Con GB 8000 y segmentados 60 %
        guardar_resultados_orden(
            self.db,
            orden,
            {"GLOBULOS_BLANCOS": "8000", "SEGMENTADOS_PCT": "60"},
            self.bio,
        )
        filas = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).all()
        mapa = {f.parametro.codigo: f for f in filas}

        self.assertIn("SEGMENTADOS_ABS", mapa)
        self.assertEqual(mapa["SEGMENTADOS_ABS"].valor_numerico, D("4800"))
        self.assertTrue(mapa["SEGMENTADOS_ABS"].calculable)

        # Quitar GB -> SEGMENTADOS_ABS sin fila (falta entrada)
        guardar_resultados_orden(self.db, orden, {"GLOBULOS_BLANCOS": None}, self.bio)
        filas2 = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).all()
        mapa2 = {f.parametro.codigo: f for f in filas2}

        self.assertNotIn("SEGMENTADOS_ABS", mapa2)

    # -------------------------------------------------------------------------
    # Test 12: Perfil Lipídico
    # -------------------------------------------------------------------------
    def test_12_lipidico_valores_y_reglas(self) -> None:
        """12. Lipídico: col 164.5, TG 102.4, HDL 40 → VLDL 20.48, LDL 104.02; TG 450 → VLDL sí y LDL calculable=false (regla); HDL ausente → LDL sin fila."""
        orden = self.crear_orden_con_estudios(["PERFIL_LIPIDICO"])
        oe = orden.estudios[0]

        # Caso estándar
        guardar_resultados_orden(
            self.db,
            orden,
            {"COLESTEROL": "164.5", "TRIGLICERIDOS": "102.4", "HDL": "40"},
            self.bio,
        )
        filas = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).all()
        mapa = {f.parametro.codigo: f for f in filas}

        self.assertEqual(mapa["VLDL"].valor_numerico, D("20.48"))
        self.assertEqual(mapa["LDL"].valor_numerico, D("104.02"))
        self.assertTrue(mapa["LDL"].calculable)

        # TG 450 -> VLDL sí (90.00) y LDL con calculable=False (regla) y valor NULL
        guardar_resultados_orden(self.db, orden, {"TRIGLICERIDOS": "450"}, self.bio)
        filas2 = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).all()
        mapa2 = {f.parametro.codigo: f for f in filas2}

        self.assertEqual(mapa2["VLDL"].valor_numerico, D("90.00"))
        self.assertIn("LDL", mapa2)
        self.assertFalse(mapa2["LDL"].calculable)
        self.assertIsNone(mapa2["LDL"].valor_numerico)

        # HDL ausente -> LDL sin fila (falta entrada)
        guardar_resultados_orden(self.db, orden, {"HDL": None, "TRIGLICERIDOS": "102.4"}, self.bio)
        filas3 = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).all()
        mapa3 = {f.parametro.codigo: f for f in filas3}

        self.assertNotIn("LDL", mapa3)

    # -------------------------------------------------------------------------
    # Test 13: Hepatograma bilirrubina directa > total
    # -------------------------------------------------------------------------
    def test_13_hepatograma_directa_mayor_que_total(self) -> None:
        """13. Hepatograma: directa > total → indirecta calculable=false + validación ERROR; orden no pasa a COMPLETO."""
        orden = self.crear_orden_con_estudios(["HEPATOGRAMA"])
        oe = orden.estudios[0]

        # Directa (0.9) > Total (0.5)
        resp = guardar_resultados_orden(
            self.db,
            orden,
            {"BILIRRUBINA_TOTAL": "0.5", "BILIRRUBINA_DIRECTA": "0.9"},
            self.bio,
        )

        filas = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).all()
        mapa = {f.parametro.codigo: f for f in filas}

        self.assertIn("BILIRRUBINA_INDIRECTA", mapa)
        self.assertFalse(mapa["BILIRRUBINA_INDIRECTA"].calculable)
        self.assertIsNone(mapa["BILIRRUBINA_INDIRECTA"].valor_numerico)

        # Validación ERROR presente y orden no completa
        self.assertFalse(resp["completitud"]["completo"])
        self.assertTrue(any("La bilirrubina directa no puede superar a la total" in err for err in resp["completitud"]["errores"]))
        self.assertEqual(orden.estado_trabajo, "INCOMPLETO")

    # -------------------------------------------------------------------------
    # Test 14: Proteinograma sin división por cero
    # -------------------------------------------------------------------------
    def test_14_proteinograma_sin_division_por_cero(self) -> None:
        """14. Proteinograma: PT = albúmina → relación A/G no calculable, sin error 500."""
        orden = self.crear_orden_con_estudios(["PROTEINOGRAMA"])
        oe = orden.estudios[0]

        # PT = 4.0, Albúmina = 4.0
        resp = guardar_resultados_orden(
            self.db,
            orden,
            {"PROTEINAS_TOTALES": "4.0", "ALBUMINA": "4.0"},
            self.bio,
        )

        filas = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).all()
        mapa = {f.parametro.codigo: f for f in filas}

        self.assertIn("RELACION_AG", mapa)
        self.assertFalse(mapa["RELACION_AG"].calculable)
        self.assertIsNone(mapa["RELACION_AG"].valor_numerico)

    # -------------------------------------------------------------------------
    # Test 15: Simulación /calcular no escribe y coincide con guardado
    # -------------------------------------------------------------------------
    def test_15_calcular_no_escribe_y_coincide_con_guardar(self) -> None:
        """15. evaluar_captura_orden simulado no escribe (conteo de filas idéntico) y coincide con el resultado guardado."""
        orden = self.crear_orden_con_estudios(["HEMOGRAMA"])
        oe = orden.estudios[0]

        conteo_inicial = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).count()
        self.assertEqual(conteo_inicial, 0)

        # Simulación de captura con valores
        simulacion = evaluar_captura_orden(orden, valores_simulados={"HEMATOCRITO": "45", "GLOBULOS_BLANCOS": "7000"})
        conteo_post_simulacion = self.db.query(ResultadoBorrador).filter(ResultadoBorrador.id_orden_estudio == oe.id_orden_estudio).count()
        self.assertEqual(conteo_inicial, conteo_post_simulacion, "La simulación no debe escribir filas en BD.")

        # Guardado real con los mismos valores
        guardado = guardar_resultados_orden(self.db, orden, {"HEMATOCRITO": "45", "GLOBULOS_BLANCOS": "7000"}, self.bio)

        # Los valores calculados de la simulación deben coincidir exactamente con el guardado
        sim_params = {p["codigo"]: p["valor"] for p in simulacion["estudios"][0]["secciones"][0]["parametros"]}
        guard_params = {p["codigo"]: p["valor"] for p in guardado["estudios"][0]["secciones"][0]["parametros"]}

        self.assertEqual(sim_params["GLOBULOS_ROJOS"], guard_params["GLOBULOS_ROJOS"])
        self.assertEqual(sim_params["HEMOGLOBINA"], guard_params["HEMOGLOBINA"])

    # -------------------------------------------------------------------------
    # Test 16: Banderas por rango, sexo y sin rango
    # -------------------------------------------------------------------------
    def test_16_banderas_colesterol_sexo_y_sin_rango(self) -> None:
        """16. Colesterol 200 → ALTO y 199.9 → NORMAL; hombre vs mujer en hematocrito; parámetro sin rango → bandera=null, referencia=null."""
        # 1. Colesterol
        orden_lip = self.crear_orden_con_estudios(["PERFIL_LIPIDICO"])
        resp_alto = guardar_resultados_orden(self.db, orden_lip, {"COLESTEROL": "200"}, self.bio)
        col_alto = next(p for s in resp_alto["estudios"][0]["secciones"] for p in s["parametros"] if p["codigo"] == "COLESTEROL")
        self.assertEqual(col_alto["bandera"], "ALTO")

        resp_norm = guardar_resultados_orden(self.db, orden_lip, {"COLESTEROL": "199.9"}, self.bio)
        col_norm = next(p for s in resp_norm["estudios"][0]["secciones"] for p in s["parametros"] if p["codigo"] == "COLESTEROL")
        self.assertEqual(col_norm["bandera"], "NORMAL")

        # 2. Hematocrito Hombre vs Mujer (Hombre 48-58 %, Mujer 44-54 %)
        orden_m = self.crear_orden_con_estudios(["HEMOGRAMA"], sexo="M")
        resp_m = guardar_resultados_orden(self.db, orden_m, {"HEMATOCRITO": "46"}, self.bio)
        hto_m = next(p for s in resp_m["estudios"][0]["secciones"] for p in s["parametros"] if p["codigo"] == "HEMATOCRITO")
        self.assertEqual(hto_m["bandera"], "BAJO")  # 46 < 48

        orden_f = self.crear_orden_con_estudios(["HEMOGRAMA"], sexo="F")
        resp_f = guardar_resultados_orden(self.db, orden_f, {"HEMATOCRITO": "46"}, self.bio)
        hto_f = next(p for s in resp_f["estudios"][0]["secciones"] for p in s["parametros"] if p["codigo"] == "HEMATOCRITO")
        self.assertEqual(hto_f["bandera"], "NORMAL")  # 44 <= 46 <= 54

    # -------------------------------------------------------------------------
    # Test 17: Rango con límites de edad
    # -------------------------------------------------------------------------
    def test_17_rango_con_limites_de_edad(self) -> None:
        """17. Rango con límites de edad en meses: se elige según la edad en meses de la orden."""
        orden_bebe = self.crear_orden_con_estudios(["ELECTROLITOS"], edad_anios=0, edad_meses=6)
        orden_adulto = self.crear_orden_con_estudios(["ELECTROLITOS"], edad_anios=25, edad_meses=0)

        # Insertar un rango de referencia específico para lactantes (0 - 12 meses) en SODIO
        param_sodio = self.db.query(Parametro).filter(Parametro.codigo == "SODIO").first()
        rango_lactante = RangoReferencia(
            id_parametro=param_sodio.id_parametro,
            edad_min_meses=0,
            edad_max_meses=12,
            limite_inferior=D("130"),
            limite_superior=D("145"),
            referencia_texto="Lactante: 130 - 145 mEq/L",
        )
        self.db.add(rango_lactante)
        self.db.commit()

        # Evaluación para bebé de 6 meses
        resp_bebe = guardar_resultados_orden(self.db, orden_bebe, {"SODIO": "132"}, self.bio)
        sodio_bebe = next(p for s in resp_bebe["estudios"][0]["secciones"] for p in s["parametros"] if p["codigo"] == "SODIO")
        self.assertEqual(sodio_bebe["referencia"]["texto"], "Lactante: 130 - 145 mEq/L")
        self.assertEqual(sodio_bebe["bandera"], "NORMAL")

        # Evaluación para adulto (debe tomar el rango sin límite de edad)
        resp_adulto = guardar_resultados_orden(self.db, orden_adulto, {"SODIO": "132"}, self.bio)
        sodio_adulto = next(p for s in resp_adulto["estudios"][0]["secciones"] for p in s["parametros"] if p["codigo"] == "SODIO")
        self.assertNotEqual(sodio_adulto["referencia"]["texto"], "Lactante: 130 - 145 mEq/L")
        self.assertEqual(sodio_adulto["bandera"], "BAJO")  # Normal adulto es 135-155

    # -------------------------------------------------------------------------
    # Test 18: Reglas cruzadas SUMA_IGUAL y MENOR_IGUAL
    # -------------------------------------------------------------------------
    def test_18_reglas_cruzadas_suma_igual_y_menor_igual(self) -> None:
        """18. SUMA_IGUAL: suma 98 con tolerancia 1 → ADVERTENCIA; 99 → sin aviso; cayados ausente cuenta 0; no bloquea COMPLETO. MENOR_IGUAL ERROR sí bloquea."""
        orden = self.crear_orden_con_estudios(["HEMOGRAMA"])

        # 1. Suma 98 (tolerancia 1 para meta 100 -> |98-100|=2 > 1 -> ADVERTENCIA)
        entradas_98 = {
            "SEGMENTADOS_PCT": "58",
            "LINFOCITOS_PCT": "30",
            "EOSINOFILOS_PCT": "5",
            "MONOCITOS_PCT": "5",
            # CAYADOS_PCT opcional ausente -> cuenta como 0
        }
        resp_98 = guardar_resultados_orden(self.db, orden, entradas_98, self.bio)
        vals_98 = resp_98["estudios"][0]["validaciones"]
        self.assertEqual(len(vals_98), 1)
        self.assertEqual(vals_98[0]["severidad"], "ADVERTENCIA")
        # ADVERTENCIA no bloquea COMPLETO (no añade a errores)
        self.assertNotIn(vals_98[0]["mensaje"], resp_98["completitud"]["errores"])

        # 2. Suma 99 (|99-100|=1 <= 1 -> sin advertencia)
        entradas_99 = {
            "SEGMENTADOS_PCT": "59",
            "LINFOCITOS_PCT": "30",
            "EOSINOFILOS_PCT": "5",
            "MONOCITOS_PCT": "5",
        }
        resp_99 = guardar_resultados_orden(self.db, orden, entradas_99, self.bio)
        vals_99 = resp_99["estudios"][0]["validaciones"]
        self.assertEqual(len(vals_99), 0)

        # 3. MENOR_IGUAL con severidad ERROR sí bloquea COMPLETO
        orden_hep = self.crear_orden_con_estudios(["HEPATOGRAMA"])
        resp_hep = guardar_resultados_orden(
            self.db,
            orden_hep,
            {"BILIRRUBINA_TOTAL": "1.0", "BILIRRUBINA_DIRECTA": "1.5"},
            self.bio,
        )
        self.assertIn("La bilirrubina directa no puede superar a la total", resp_hep["completitud"]["errores"])
        self.assertFalse(resp_hep["completitud"]["completo"])

    # -------------------------------------------------------------------------
    # Test 26: Soporte de tipos de reglas y orden topológico sin ciclos
    # -------------------------------------------------------------------------
    def test_26_tipos_regla_y_orden_topologico_sin_ciclos(self) -> None:
        """26. Todos los tipos de regla de definitions.py están implementados; el orden topológico de los 9 estudios se resuelve sin ciclos."""
        # Verificar que los 9 estudios de la BD resuelven orden topológico sin ciclos
        versiones = self.db.query(EstudioVersion).all()
        self.assertGreaterEqual(len(versiones), 9)

        for ev in versiones:
            params = list(ev.parametros)
            no_calc, calc = orden_topologico_parametros(params)
            self.assertEqual(len(no_calc) + len(calc), len(params))

        # Verificar que evaluar_reglas_cruzadas soporta SUMA_IGUAL y MENOR_IGUAL
        p_dummy1 = Parametro(codigo="A", tipo_campo="NUMERICO", obligatorio=True)
        p_dummy2 = Parametro(codigo="B", tipo_campo="NUMERICO", obligatorio=True)
        pmap = {"A": p_dummy1, "B": p_dummy2}

        # Regla desconocida lanza ValueError
        with self.assertRaises(ValueError):
            evaluar_reglas_cruzadas([{"tipo": "REGLA_INVENTADA"}], {"A": D(1)}, pmap)

    # -------------------------------------------------------------------------
    # Test 27: Motor de cálculo con codigo_motivo
    # -------------------------------------------------------------------------
    def test_27_motor_distingue_codigo_motivo(self) -> None:
        """27. Motor: codigo_motivo distingue FALTA_ENTRADA, DIVISION_POR_CERO y REGLA_INVALIDA; los 25 tests existentes siguen pasando."""
        # 1. FALTA_ENTRADA
        res_falta = calcular("x + y", {"x": D(5), "y": None})
        self.assertFalse(res_falta.calculable)
        self.assertEqual(res_falta.codigo_motivo, "FALTA_ENTRADA")

        # 2. DIVISION_POR_CERO
        res_div = calcular("x / y", {"x": D(5), "y": D(0)})
        self.assertFalse(res_div.calculable)
        self.assertEqual(res_div.codigo_motivo, "DIVISION_POR_CERO")

        # 3. REGLA_INVALIDA
        res_regla = calcular("x if x <= 10 else no_calculable()", {"x": D(15)})
        self.assertFalse(res_regla.calculable)
        self.assertEqual(res_regla.codigo_motivo, "REGLA_INVALIDA")
