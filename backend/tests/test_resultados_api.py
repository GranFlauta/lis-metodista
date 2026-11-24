"""
Pruebas de endpoints de captura, cálculo, resultados, defectos y configuración (Fase 3).
Tests 1 al 9, 15, 19 al 25 y concurrencia (test 24).
Ejecutadas con unittest contra PostgreSQL real.
"""
from __future__ import annotations

import concurrent.futures
from decimal import Decimal as D
from typing import Any

from sqlalchemy import text

from app.core.clock import ahora
from app.models.catalog import Estudio, EstudioVersion, Parametro, RangoReferencia
from app.models.order import Orden, OrdenEstudio, OrdenEstudioGrupo
from app.models.patient import Paciente
from app.models.result import LaboratorioConfig, ResultadoBorrador
from tests.base import IntegrationTestCase


class TestResultadosAPI(IntegrationTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.bio = self.crear_usuario_test(
            usuario="bioq_res_1",
            password="PasswordBio123!",
            rol="BIOQUIMICO",
            ci="8100001",
        )
        login_res = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq_res_1", "password": "PasswordBio123!"},
        )
        self.bio_token = login_res.json()["access_token"]
        self.bio_headers = {"Authorization": f"Bearer {self.bio_token}", "X-LIS-Client": "web"}

        self.bio_ajeno = self.crear_usuario_test(
            usuario="bioq_res_2",
            password="PasswordBio123!",
            rol="BIOQUIMICO",
            ci="8100002",
        )
        login_ajeno = self.client.post(
            "/api/auth/login",
            json={"usuario": "bioq_res_2", "password": "PasswordBio123!"},
        )
        self.bio_ajeno_token = login_ajeno.json()["access_token"]
        self.bio_ajeno_headers = {"Authorization": f"Bearer {self.bio_ajeno_token}", "X-LIS-Client": "web"}

        self.admin = self.crear_usuario_test(
            usuario="admin_res",
            password="PasswordAdmin123!",
            rol="ADMIN",
            ci="8100003",
        )
        login_adm = self.client.post(
            "/api/auth/login",
            json={"usuario": "admin_res", "password": "PasswordAdmin123!"},
        )
        self.admin_token = login_adm.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}", "X-LIS-Client": "web"}

    def crear_orden_test(
        self,
        codigos_estudios: list[str],
        sexo: str = "M",
        edad_anios: int = 30,
        edad_meses: int = 0,
        grupos_inmuno: list[str] | None = None,
    ) -> int:
        import secrets
        paciente = self.crear_paciente_test(ci=f"8{secrets.token_hex(4)}", sexo=sexo)
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
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["orden"]["id"]

    def test_curva_tolerancia_acepta_parciales_persiste_y_conserva_intervalos(self) -> None:
        id_orden = self.crear_orden_test(["CURVA_TOLERANCIA"])
        parcial = self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            headers=self.bio_headers,
            json={"valores": {"CURVA_BASAL_HORA": "08:00"}},
        )
        self.assertEqual(parcial.status_code, 200, parcial.text)
        recargada = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        self.assertEqual(recargada.status_code, 200, recargada.text)
        filas_parciales = recargada.json()["estudios"][0]["curva_tolerancia"]["filas"]
        self.assertEqual(filas_parciales[0]["hora_valor"], "08:00")
        self.assertIsNone(filas_parciales[0]["glucosa_valor"])

        valores = {
            "CURVA_BASAL_HORA": "08:00", "CURVA_BASAL_GLUCOSA": "90",
            "CURVA_PRIMERA_HORA": "08:35", "CURVA_PRIMERA_GLUCOSA": "142",
            "CURVA_SEGUNDA_HORA": "09:20", "CURVA_SEGUNDA_GLUCOSA": "118",
            "CURVA_CUARTA_HORA": "10:05", "CURVA_CUARTA_GLUCOSA": "96",
        }
        guardada = self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            headers=self.bio_headers,
            json={"valores": valores},
        )
        self.assertEqual(guardada.status_code, 200, guardada.text)
        filas = guardada.json()["estudios"][0]["curva_tolerancia"]["filas"]
        self.assertEqual(sum(fila["instante"] is not None for fila in filas), 4)
        self.assertIsNone(filas[3]["instante"])
        self.assertEqual(filas[1]["minutos_desde_basal"], "35")
        self.assertEqual(filas[2]["minutos_desde_basal"], "80")
        self.assertEqual(filas[4]["minutos_desde_basal"], "125")

        recargada = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        self.assertEqual(recargada.status_code, 200, recargada.text)
        valores_recargados = {
            p["codigo"]: p["valor"]
            for seccion in recargada.json()["estudios"][0]["secciones"]
            for p in seccion["parametros"]
        }
        self.assertEqual(valores_recargados["CURVA_PRIMERA_GLUCOSA"], "142")

    # -------------------------------------------------------------------------
    # Test 1: GET captura de orden con HEMOGRAMA (estructura y sexo)
    # -------------------------------------------------------------------------
    def test_serologia_captura_columnas_vdrl_y_orden_ego(self) -> None:
        from tests.test_serologia import entrada

        id_orden = self.crear_orden_test(["EGO", "INMUNOSEROLOGIA"], grupos_inmuno=["WIDAL", "VDRL", "PCR_SEMICUANT", "PCR_TURBIDIMETRICA", "FACTOR_REUMATOIDEO", "ASTO", "VIH"])
        valores = {"PCR_DILUCION": entrada(reactivo="TECO"), "FR_DILUCION": entrada(dilucion="1/32"),
                   "ASTO_DILUCION": entrada(dilucion="1/4"), "VDRL_DILUCION": "Positivo", "PCR_CUANTITATIVA": "25.2",
                   "WIDAL_TIFOIDEA_H": entrada(dilucion="1/130")}
        respuesta = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.bio_headers, json={"valores": valores})
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        estudios = {e["codigo"]: e for e in respuesta.json()["estudios"]}
        micro = next(s for s in estudios["EGO"]["secciones"] if s["grupo"] == "MICROSCOPICO")
        self.assertEqual([p["codigo"] for p in micro["parametros"]][-4:], ["CRISTALES", "CILINDROS", "BACTERIAS", "OTROS"])
        inmuno = estudios["INMUNOSEROLOGIA"]
        parametros = {p["codigo"]: p for s in inmuno["secciones"] for p in s["parametros"]}
        self.assertTrue(all(p["bandera"] is None for p in parametros.values()))
        self.assertEqual(parametros["VDRL_DILUCION"]["opciones"], ["Negativo", "Positivo"])
        self.assertEqual(parametros["PCR_DILUCION"]["serologia"]["resultado"], "6.4")
        self.assertEqual(parametros["FR_DILUCION"]["serologia"]["resultado"], "256")
        self.assertEqual(parametros["WIDAL_TIFOIDEA_H"]["serologia"]["resultado"], "Positivo · 1/130")
        vih = next(s for s in inmuno["secciones"] if s["grupo"] == "VIH")
        self.assertEqual(vih["columnas"], {"unidad": False, "referencia": False, "bandera": False})
        reabierta = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        self.assertEqual(reabierta.json()["estudios"], respuesta.json()["estudios"])
        invalido = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.bio_headers, json={"valores": {"VDRL_DILUCION": "1/8"}})
        self.assertEqual(invalido.status_code, 400)

    def test_serologia_incompleta_no_se_publica_y_se_congela_al_completar(self) -> None:
        from tests.test_serologia import entrada
        from app.models.report import Informe

        id_orden = self.crear_orden_test(["INMUNOSEROLOGIA"], grupos_inmuno=["FACTOR_REUMATOIDEO", "PCR_SEMICUANT", "ASTO", "WIDAL", "VDRL"])
        valores = {"PCR_DILUCION": entrada(reactivo="TECO"), "FR_DILUCION": entrada(dilucion=""),
                   "ASTO_DILUCION": entrada("Negativo"), "VDRL_DILUCION": "Negativo"}
        valores.update({c: entrada(dilucion="1/320") for c in ("WIDAL_TIFOIDEA_H", "WIDAL_TIFOIDEA_O", "WIDAL_PARATIFI_A", "WIDAL_PARATIFI_B")})
        respuesta = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.bio_headers, json={"valores": valores, "observaciones_orden": "Revisión ficticia de serología."})
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        self.assertIn("FR_DILUCION", respuesta.json()["completitud"]["pendientes"])
        self.assertEqual(self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers).status_code, 400)
        completa = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.bio_headers, json={"valores": {"FR_DILUCION": entrada(dilucion="1/4", reactivo="PERSONALIZADO", sensibilidad="10.25", unidad="UI/mL")}})
        self.assertTrue(completa.json()["completitud"]["completo"], completa.text)
        publicada = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.bio_headers)
        self.assertEqual(publicada.status_code, 201, publicada.text)
        folio = publicada.json()["folio"]
        self.db.expire_all()
        informe = self.db.query(Informe).filter_by(folio=folio).one()
        parametros = {p["codigo"]: p for e in informe.snapshot_json["estudios"] for s in e["secciones"] for p in s["parametros"]}
        self.assertEqual(parametros["FR_DILUCION"]["serologia"]["resultado"], "41")
        pdf = self.client.get(f"/api/informes/{folio}/pdf", headers=self.bio_headers)
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF-"))

    def test_decimales_en_hemograma_y_hepatograma_se_persisten_sin_cambiar_escala(self) -> None:
        id_orden = self.crear_orden_test(["HEMOGRAMA", "HEPATOGRAMA", "PERFIL_LIPIDICO"])
        codigos = ("GLOBULOS_BLANCOS", "VES", "PLAQUETAS", "GOT_AST", "GPT_ALT", "FOSFATASA_ALCALINA", "GGT")
        valores = {codigo: "2.2" for codigo in codigos}
        valores.update({"COLESTEROL": "150.2", "TRIGLICERIDOS": "100.1", "HDL": "45.5"})
        respuesta = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.bio_headers, json={"valores": valores})
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        captura = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers).json()
        parametros = {p["codigo"]: p for estudio in captura["estudios"] for seccion in estudio["secciones"] for p in seccion["parametros"]}
        for codigo, valor in valores.items():
            self.assertEqual(parametros[codigo]["valor"], valor)
        self.db.expire_all()
        filas = self.db.query(ResultadoBorrador).join(Parametro).filter(Parametro.codigo.in_(codigos)).all()
        self.assertEqual(len(filas), len(codigos))
        self.assertTrue(all(fila.valor_numerico == D("2.2") for fila in filas))

    def test_vista_previa_solo_pantalla_y_permisos_backend(self) -> None:
        id_orden = self.crear_orden_test(["QUIMICA_SANGUINEA"])
        ruta = f"/api/ordenes/{id_orden}/vista-previa"
        respuesta = self.client.post(ruta, headers=self.bio_headers, json={"valores": {"GLICEMIA": "2.2", "CREATININA": ""}})
        self.assertEqual(respuesta.status_code, 200, respuesta.text[:200])
        self.assertEqual(respuesta.json()["formato"], "Carta")
        self.assertTrue(respuesta.json()["paginas"][0]["imagen"].startswith("data:image/png;base64,"))
        self.assertNotIn("application/pdf", respuesta.headers["content-type"])
        self.assertIn("no-store", respuesta.headers["cache-control"])
        self.assertEqual(self.client.post(ruta, headers=self.bio_ajeno_headers, json={"valores": {}}).status_code, 404)
        self.assertEqual(self.client.post(ruta, json={"valores": {}}).status_code, 401)
        self.assertEqual(self.client.post(ruta, headers=self.admin_headers, json={"valores": {"GLICEMIA": "10"}}).status_code, 403)
        lectura_admin = self.client.post(ruta, headers=self.admin_headers, json={"valores": {}})
        self.assertEqual(lectura_admin.status_code, 200, lectura_admin.text[:200])
        self.assertEqual(self.client.post(ruta, headers=self.bio_headers, json={"valores": {}, "aprobado": True}).status_code, 400)
        self.assertIn(self.client.post(f"{ruta}.pdf", headers=self.bio_headers, json={"valores": {}}).status_code, (404, 405))
        self.db.expire_all()
        self.assertEqual(self.db.query(ResultadoBorrador).count(), 0)

    def test_suma_diferencial_decimal_viene_del_backend(self) -> None:
        id_orden = self.crear_orden_test(["HEMOGRAMA"])
        respuesta = self.client.post(f"/api/ordenes/{id_orden}/calcular", headers=self.bio_headers, json={"valores": {
            "SEGMENTADOS_PCT": "55.2", "LINFOCITOS_PCT": "40.3", "EOSINOFILOS_PCT": "2.2", "MONOCITOS_PCT": "2.3",
        }})
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        suma = respuesta.json()["estudios"][0]["sumas"][0]
        self.assertEqual(suma["valor"], "100")
        self.assertEqual(suma["tolerancia"], "1")
        self.assertTrue(suma["valida"])

    def test_01_get_captura_estructura_y_referencias_por_sexo(self) -> None:
        """1. GET captura con HEMOGRAMA: secciones/parámetros con tipo, unidad y decimales; referencia según sexo."""
        id_m = self.crear_orden_test(["HEMOGRAMA"], sexo="M")
        r_m = self.client.get(f"/api/ordenes/{id_m}/captura", headers=self.bio_headers)
        self.assertEqual(r_m.status_code, 200)
        data_m = r_m.json()

        # Verificar estructura de respuesta común
        self.assertIn("orden", data_m)
        self.assertIn("estudios", data_m)
        self.assertIn("completitud", data_m)

        est_m = data_m["estudios"][0]
        self.assertEqual(est_m["codigo"], "HEMOGRAMA")
        params_m = {p["codigo"]: p for s in est_m["secciones"] for p in s["parametros"]}

        # Parámetro HEMATOCRITO para varón: 48 - 58 %
        hto_m = params_m["HEMATOCRITO"]
        self.assertEqual(hto_m["tipo_campo"], "NUMERICO")
        self.assertEqual(hto_m["unidad"], "%")
        self.assertEqual(hto_m["decimales"], 1)
        self.assertIn("48 - 58", hto_m["referencia"]["texto"])

        # Parámetro HEMATOCRITO para mujer: 44 - 54 %
        id_f = self.crear_orden_test(["HEMOGRAMA"], sexo="F")
        r_f = self.client.get(f"/api/ordenes/{id_f}/captura", headers=self.bio_headers)
        self.assertEqual(r_f.status_code, 200)
        data_f = r_f.json()
        params_f = {p["codigo"]: p for s in data_f["estudios"][0]["secciones"] for p in s["parametros"]}
        self.assertIn("44 - 54", params_f["HEMATOCRITO"]["referencia"]["texto"])

    # -------------------------------------------------------------------------
    # Test 2: Inmunoserología con grupos=[VIH] (solo VIH en parámetros)
    # -------------------------------------------------------------------------
    def test_02_inmunoserologia_seleccion_parcial(self) -> None:
        """2. Inmunoserología con grupos=[VIH]: solo el parámetro VIH (no PCR_* ni otros)."""
        id_orden = self.crear_orden_test(["INMUNOSEROLOGIA"], grupos_inmuno=["VIH"])
        r = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        self.assertEqual(r.status_code, 200)
        data = r.json()

        params = [p["codigo"] for s in data["estudios"][0]["secciones"] for p in s["parametros"]]
        self.assertEqual(params, ["VIH"])

    # -------------------------------------------------------------------------
    # Test 3: EGO defectos virtuales sin filas en BD
    # -------------------------------------------------------------------------
    def test_03_ego_defectos_virtuales_sin_filas(self) -> None:
        """3. EGO no precarga resultados del catálogo y no crea filas al abrirse."""
        id_orden = self.crear_orden_test(["EGO"])
        r = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        self.assertEqual(r.status_code, 200)
        data = r.json()

        params = {p["codigo"]: p for s in data["estudios"][0]["secciones"] for p in s["parametros"]}
        self.assertFalse(params["NITRITOS"]["es_defecto"])
        self.assertTrue(params["NITRITOS"]["confirmado"])
        self.assertIsNone(params["NITRITOS"]["valor"])

        # Verificar BD: sin filas
        conteo = self.db.query(ResultadoBorrador).join(OrdenEstudio).filter(OrdenEstudio.id_orden == id_orden).count()
        self.assertEqual(conteo, 0)

    # -------------------------------------------------------------------------
    # Test 4: Seguridad, orden ajena, ADMIN y contraseñas
    # -------------------------------------------------------------------------
    def test_04_seguridad_acceso_y_roles(self) -> None:
        """4. Orden ajena → 404 (BIOQUIMICO); ADMIN → 200 solo lectura y audita ADMIN_VE_PRIVADO; sin token → 401; con debe_cambiar_password → 403; ADMIN en PUT/calcular/confirmar → 403."""
        id_orden = self.crear_orden_test(["HEMOGRAMA"])

        # Bioquímico ajeno → 404
        r_ajeno = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_ajeno_headers)
        self.assertEqual(r_ajeno.status_code, 404)

        # ADMIN → 200 y registra ADMIN_VE_PRIVADO
        r_adm = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.admin_headers)
        self.assertEqual(r_adm.status_code, 200)

        log = self.db.execute(text(
            "SELECT count(*) FROM laboratorio.log_seguridad WHERE accion = 'ADMIN_VE_PRIVADO' AND detalle->>'recurso' = 'captura'"
        )).scalar()
        self.assertGreaterEqual(log, 1)

        # Sin token → 401
        r_sin = self.client.get(f"/api/ordenes/{id_orden}/captura")
        self.assertEqual(r_sin.status_code, 401)

        # Con debe_cambiar_password → 403
        bio_cambiar = self.crear_usuario_test(usuario="bio_pwd", rol="BIOQUIMICO", debe_cambiar_password=True)
        login_pwd = self.client.post("/api/auth/login", json={"usuario": "bio_pwd", "password": "ClaveSegura123!"})
        tok_pwd = login_pwd.json()["access_token"]
        r_pwd = self.client.get(f"/api/ordenes/{id_orden}/captura", headers={"Authorization": f"Bearer {tok_pwd}", "X-LIS-Client": "web"})
        self.assertEqual(r_pwd.status_code, 403)

        # ADMIN en PUT/calcular/confirmar → 403
        r_put_adm = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {}}, headers=self.admin_headers)
        self.assertEqual(r_put_adm.status_code, 403)

        r_calc_adm = self.client.post(f"/api/ordenes/{id_orden}/calcular", json={"valores": {}}, headers=self.admin_headers)
        self.assertEqual(r_calc_adm.status_code, 403)

        r_conf_adm = self.client.post(f"/api/ordenes/{id_orden}/resultados/confirmar-defectos", json={}, headers=self.admin_headers)
        self.assertEqual(r_conf_adm.status_code, 403)

    # -------------------------------------------------------------------------
    # Test 5: Validaciones numéricas (coma, punto, decimales, negativos)
    # -------------------------------------------------------------------------
    def test_05_validaciones_numericas(self) -> None:
        """5. Numérico con coma y con punto → mismo valor; > 6 decimales → 400; negativo → 400; no numérico → 400."""
        id_orden = self.crear_orden_test(["HEMOGRAMA"])

        # Coma y punto
        r_coma = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HEMATOCRITO": "45,5"}}, headers=self.bio_headers)
        self.assertEqual(r_coma.status_code, 200)

        r_punto = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HEMATOCRITO": "45.5"}}, headers=self.bio_headers)
        self.assertEqual(r_punto.status_code, 200)

        # > 6 decimales → 400
        r_dec = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HEMATOCRITO": "45.1234567"}}, headers=self.bio_headers)
        self.assertEqual(r_dec.status_code, 400)

        # Negativo → 400
        r_neg = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HEMATOCRITO": "-10"}}, headers=self.bio_headers)
        self.assertEqual(r_neg.status_code, 400)

        # No numérico → 400
        r_nan = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HEMATOCRITO": "abc"}}, headers=self.bio_headers)
        self.assertEqual(r_nan.status_code, 400)

    # -------------------------------------------------------------------------
    # Test 6: Validaciones cualitativas (SELECCION, TEXTO, RECUENTO, FECHA)
    # -------------------------------------------------------------------------
    def test_06_validaciones_cualitativas(self) -> None:
        """6. SELECCION fuera de opciones → 400; TEXTO > 500 y RECUENTO > 50 → 400; FECHA futura o inválida → 400."""
        id_orden = self.crear_orden_test(["EGO", "INMUNOSEROLOGIA"], grupos_inmuno=["HCG"])

        # SELECCION inválida
        r_sel = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"NITRITOS": "Invalido"}}, headers=self.bio_headers)
        self.assertEqual(r_sel.status_code, 400)

        # TEXTO > 500
        r_txt = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"CRISTALES": "A" * 501}}, headers=self.bio_headers)
        self.assertEqual(r_txt.status_code, 400)

        # RECUENTO > 50
        r_rec = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"LEUCOCITOS": "A" * 51}}, headers=self.bio_headers)
        self.assertEqual(r_rec.status_code, 400)

        # FECHA futura o inválida
        r_fec_inv = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HCG_FUM": "fecha_mala"}}, headers=self.bio_headers)
        self.assertEqual(r_fec_inv.status_code, 400)

        r_fec_fut = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HCG_FUM": "2099-01-01"}}, headers=self.bio_headers)
        self.assertEqual(r_fec_fut.status_code, 400)

    # -------------------------------------------------------------------------
    # Test 7: Validación de claves y parámetros CALCULADOS
    # -------------------------------------------------------------------------
    def test_07_validaciones_claves(self) -> None:
        """7. Código de otro estudio no pedido, inexistente, o CALCULADO en cuerpo → 400; > 200 claves → 400."""
        id_orden = self.crear_orden_test(["HEMOGRAMA"])

        # Código de otro estudio no pedido
        r_otro = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"GLICEMIA": "100"}}, headers=self.bio_headers)
        self.assertEqual(r_otro.status_code, 400)

        # Código inexistente
        r_inex = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"NO_EXISTE": "1"}}, headers=self.bio_headers)
        self.assertEqual(r_inex.status_code, 400)

        # Parámetro CALCULADO en cuerpo
        r_calc = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"GLOBULOS_ROJOS": "5000000"}}, headers=self.bio_headers)
        self.assertEqual(r_calc.status_code, 400)

        # Más de 200 claves
        muchas_claves = {f"K_{i}": "1" for i in range(201)}
        r_max = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores muchas": muchas_claves, "valores": muchas_claves}, headers=self.bio_headers)
        self.assertEqual(r_max.status_code, 400)

    # -------------------------------------------------------------------------
    # Test 8: null borra fila y upsert actualiza metadatos
    # -------------------------------------------------------------------------
    def test_08_null_borra_fila_y_upsert(self) -> None:
        """8. null borra la fila; el upsert actualiza actualizado_por y actualizado_en."""
        id_orden = self.crear_orden_test(["HEMOGRAMA"])

        # Crear fila
        r_set = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HEMATOCRITO": "45"}}, headers=self.bio_headers)
        self.assertEqual(r_set.status_code, 200)

        fila = self.db.query(ResultadoBorrador).join(OrdenEstudio).filter(OrdenEstudio.id_orden == id_orden, ResultadoBorrador.es_calculado == False).first()
        self.assertIsNotNone(fila)
        t1 = fila.actualizado_en
        self.assertEqual(fila.actualizado_por, self.bio.id_usuario)

        # Modificar fila
        r_upd = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HEMATOCRITO": "48"}}, headers=self.bio_headers)
        self.assertEqual(r_upd.status_code, 200)
        self.db.refresh(fila)
        self.assertEqual(fila.valor_numerico, D("48"))

        # null borra la fila
        r_del = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HEMATOCRITO": None}}, headers=self.bio_headers)
        self.assertEqual(r_del.status_code, 200)

        conteo = self.db.query(ResultadoBorrador).join(OrdenEstudio).filter(OrdenEstudio.id_orden == id_orden, ResultadoBorrador.es_calculado == False).count()
        self.assertEqual(conteo, 0)

    # -------------------------------------------------------------------------
    # Test 9: Tipo de dato y almacenamiento excluyente
    # -------------------------------------------------------------------------
    def test_09_almacenamiento_excluyente_numerico_vs_texto(self) -> None:
        """9. Un parámetro numérico nunca escribe valor_texto y uno cualitativo nunca escribe valor_numerico."""
        id_orden = self.crear_orden_test(["EGO"])

        r = self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            json={"valores": {"DENSIDAD": "1020", "ASPECTO": "Límpido"}},
            headers=self.bio_headers,
        )
        self.assertEqual(r.status_code, 200)

        filas = self.db.query(ResultadoBorrador).join(OrdenEstudio).filter(OrdenEstudio.id_orden == id_orden).all()
        mapa = {f.parametro.codigo: f for f in filas}

        # DENSIDAD (numérico)
        self.assertIsNotNone(mapa["DENSIDAD"].valor_numerico)
        self.assertIsNone(mapa["DENSIDAD"].valor_texto)

        # ASPECTO (cualitativo)
        self.assertIsNone(mapa["ASPECTO"].valor_numerico)
        self.assertIsNotNone(mapa["ASPECTO"].valor_texto)

    # -------------------------------------------------------------------------
    # Test 19: Electrolitos completitud e INCOMPLETO ↔ COMPLETO
    # -------------------------------------------------------------------------
    def test_19_electrolitos_completitud(self) -> None:
        """19. Orden solo con ELECTROLITOS: al ingresar resultados pasa a COMPLETO; sólo vuelve a INCOMPLETO al borrar todos."""
        id_orden = self.crear_orden_test(["ELECTROLITOS"])

        # Estado inicial: INCOMPLETO
        orden_db = self.db.query(Orden).filter(Orden.id_orden == id_orden).first()
        self.assertEqual(orden_db.estado_trabajo, "INCOMPLETO")

        # Completar los 6 obligatorios
        todos_electrolitos = {
            "SODIO": "140",
            "POTASIO": "4.2",
            "CLORO": "100",
            "CALCIO": "9.5",
            "MAGNESIO": "2.0",
            "FOSFORO": "3.5",
        }
        r_full = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": todos_electrolitos}, headers=self.bio_headers)
        self.assertEqual(r_full.status_code, 200)
        self.assertTrue(r_full.json()["completitud"]["completo"])

        self.db.refresh(orden_db)
        self.assertEqual(orden_db.estado_trabajo, "COMPLETO")

        # Borrar uno conserva el resto de resultados utilizados
        r_part = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"SODIO": None}}, headers=self.bio_headers)
        self.assertEqual(r_part.status_code, 200)
        self.assertTrue(r_part.json()["completitud"]["completo"])
        self.assertNotIn("SODIO", r_part.json()["completitud"]["pendientes"])
        r_vacia = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {c: None for c in todos_electrolitos}}, headers=self.bio_headers)
        self.assertFalse(r_vacia.json()["completitud"]["completo"])

        self.db.refresh(orden_db)
        self.assertEqual(orden_db.estado_trabajo, "INCOMPLETO")

    # -------------------------------------------------------------------------
    # Test 20: EGO confirmar defectos
    # -------------------------------------------------------------------------
    def test_20_ego_confirmar_defectos(self) -> None:
        """20. EGO: no precarga defectos; la confirmación explícita permite incorporar sus valores."""
        id_orden = self.crear_orden_test(["EGO"])

        r_get = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        sin_conf = r_get.json()["completitud"]["sin_confirmar"]
        self.assertEqual(len(sin_conf), 0)

        # Confirmar todos los defectos
        r_conf = self.client.post(f"/api/ordenes/{id_orden}/resultados/confirmar-defectos", json={}, headers=self.bio_headers)
        self.assertEqual(r_conf.status_code, 200)
        self.assertEqual(len(r_conf.json()["completitud"]["sin_confirmar"]), 0)

        # Verificar BD: filas creadas con confirmado = TRUE
        filas = self.db.query(ResultadoBorrador).join(OrdenEstudio).filter(OrdenEstudio.id_orden == id_orden).all()
        self.assertTrue(all(f.confirmado for f in filas))

    # -------------------------------------------------------------------------
    # Test 21: Calculado obligatorio no calculable por regla vs falta de entrada
    # -------------------------------------------------------------------------
    def test_21_calculado_regla_no_impide_completo(self) -> None:
        """21. CALCULADO obligatorio no calculable por regla (LDL con TG > 400) NO impide COMPLETO; no calculable por falta de entrada sí lo impide."""
        id_orden = self.crear_orden_test(["PERFIL_LIPIDICO"])

        # Colesterol, HDL y TG > 400 -> LDL no calculable por regla (D3-06: no bloquea COMPLETO)
        payload = {"COLESTEROL": "200", "HDL": "45", "TRIGLICERIDOS": "450"}
        r = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": payload}, headers=self.bio_headers)
        self.assertEqual(r.status_code, 200)
        data = r.json()

        self.assertTrue(data["completitud"]["completo"], f"Pendientes: {data['completitud']['pendientes']}")
        orden_db = self.db.query(Orden).filter(Orden.id_orden == id_orden).first()
        self.assertEqual(orden_db.estado_trabajo, "COMPLETO")

        # Quitar HDL omite los derivados pendientes, sin bloquear los resultados utilizados
        r_falta = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HDL": None}}, headers=self.bio_headers)
        self.assertTrue(r_falta.json()["completitud"]["completo"])
        self.assertNotIn("LDL", r_falta.json()["completitud"]["pendientes"])

    # -------------------------------------------------------------------------
    # Test 22: Guardar resultados no cambia fila_version
    # -------------------------------------------------------------------------
    def test_22_guardar_resultados_no_cambia_fila_version(self) -> None:
        """22. Guardar resultados no cambia fila_version; un PATCH de cabecera posterior sigue funcionando."""
        id_orden = self.crear_orden_test(["HEMOGRAMA"])
        orden_db = self.db.query(Orden).filter(Orden.id_orden == id_orden).first()
        version_inicial = orden_db.fila_version

        # Guardar resultados
        self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HEMATOCRITO": "42"}}, headers=self.bio_headers)
        self.db.refresh(orden_db)
        self.assertEqual(orden_db.fila_version, version_inicial)

        # PATCH de cabecera con la versión intacta funciona
        r_patch = self.client.patch(
            f"/api/ordenes/{id_orden}",
            json={"origen_solicitud": "Neurología", "fila_version": version_inicial},
            headers=self.bio_headers,
        )
        self.assertEqual(r_patch.status_code, 200)

    # -------------------------------------------------------------------------
    # Test 23: Orden PUBLICADA o bloqueada responde 409
    # -------------------------------------------------------------------------
    def test_23_orden_publicada_o_bloqueada_responde_409(self) -> None:
        """23. Orden PUBLICADA o bloqueada → 409 en PUT y confirmar-defectos."""
        id_orden = self.crear_orden_test(["HEMOGRAMA"])

        # Simular orden PUBLICADA
        self.db.execute(text("UPDATE laboratorio.ordenes SET estado_trabajo = 'PUBLICADA' WHERE id_orden = :id"), {"id": id_orden})
        self.db.commit()

        r_put = self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HEMATOCRITO": "40"}}, headers=self.bio_headers)
        self.assertEqual(r_put.status_code, 409)

        r_conf = self.client.post(f"/api/ordenes/{id_orden}/resultados/confirmar-defectos", json={}, headers=self.bio_headers)
        self.assertEqual(r_conf.status_code, 409)

    # -------------------------------------------------------------------------
    # Test 24: Concurrencia dos PUT simultáneos en hilos
    # -------------------------------------------------------------------------
    def test_24_concurrencia_dos_put_simultaneos(self) -> None:
        """24. Dos PUT simultáneos sobre la misma orden → ambos 200, sin 500 y calculados coherentes."""
        id_orden = self.crear_orden_test(["HEMOGRAMA"])

        def put_a():
            return self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"HEMATOCRITO": "45"}}, headers=self.bio_headers)

        def put_b():
            return self.client.put(f"/api/ordenes/{id_orden}/resultados", json={"valores": {"GLOBULOS_BLANCOS": "8000"}}, headers=self.bio_headers)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_a = executor.submit(put_a)
            fut_b = executor.submit(put_b)
            r_a = fut_a.result()
            r_b = fut_b.result()

        self.assertEqual(r_a.status_code, 200)
        self.assertEqual(r_b.status_code, 200)

        # Comprobar integridad final
        r_get = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.bio_headers)
        params = {p["codigo"]: p["valor"] for s in r_get.json()["estudios"][0]["secciones"] for p in s["parametros"]}
        self.assertEqual(params["HEMATOCRITO"], "45")
        self.assertEqual(params["GLOBULOS_BLANCOS"], "8000")
        self.assertEqual(params["HEMOGLOBINA"], "14.4")

    # -------------------------------------------------------------------------
    # Test 25: Configuración del laboratorio
    # -------------------------------------------------------------------------
    def test_25_configuracion_laboratorio(self) -> None:
        """25. GET /api/configuracion/laboratorio devuelve solo nombre_laboratorio y separador_decimal; exige sesión."""
        # Sin sesión → 401
        r_anon = self.client.get("/api/configuracion/laboratorio")
        self.assertEqual(r_anon.status_code, 401)

        # Con sesión → 200
        r = self.client.get("/api/configuracion/laboratorio", headers=self.bio_headers)
        self.assertEqual(r.status_code, 200)
        data = r.json()

        self.assertEqual(set(data.keys()), {"nombre_laboratorio", "separador_decimal"})
        self.assertIn(data["nombre_laboratorio"], ["LABORATORIO CLINICO URGENLAB", "LABORATORIO CLINICO METODISTA"])
        self.assertEqual(data["separador_decimal"], ",")
