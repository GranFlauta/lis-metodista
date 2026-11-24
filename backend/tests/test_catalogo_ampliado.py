from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.catalog.definitions import INMUNOSEROLOGIA, MOCO_FECAL_CAMPOS, PARASITOLOGIA
from app.reports.pdf import renderizar_html_informe
from app.reports.presentation import estudios_para_informe
from app.services.serologia_service import presentar_serologia
from tests.base import IntegrationTestCase
from tests.test_pdf_report import documento_aprobado


class PresentacionCamposTests(unittest.TestCase):
    def test_omite_vacios_y_estudios_sin_datos_conservando_cero(self):
        parametros = [{"codigo": f"VACIO_{i}", "nombre": f"Vacío {i}", "valor": v} for i, v in enumerate((None, "", " ", "-", "--", "—"))]
        parametros += [{"codigo": "CERO", "nombre": "Cero capturado", "valor": 0},
                       {"codigo": "DERIVADO", "nombre": "Derivado vacío", "valor": None, "es_calculado": True,
                        "calculable": False, "codigo_motivo_no_calculable": "FALTA_ENTRADA"}]
        estudios = [{"codigo": "PRUEBA", "nombre": "Con resultado", "secciones": [{"parametros": parametros}]},
                    {"codigo": "VACIO", "nombre": "Estudio vacío", "secciones": [{"parametros": [{"valor": None}]}]}]
        original = deepcopy(estudios)
        salida = estudios_para_informe(estudios)
        self.assertEqual([p["codigo"] for p in salida[0]["secciones"][0]["parametros"]], ["CERO"])
        self.assertEqual(len(salida), 1)
        self.assertEqual(estudios, original)

    def test_los_tres_negativos_solo_imprimen_negativo(self):
        documento = documento_aprobado(False)
        secciones = []
        for codigo in ("PCR_DILUCION", "FR_DILUCION", "ASTO_DILUCION"):
            raw = json.dumps({"reactividad": "Negativo", "reactivo": "TECO" if codigo == "PCR_DILUCION" else "Estándar"})
            presentacion = presentar_serologia(raw, INMUNOSEROLOGIA.captura[codigo])
            self.assertEqual((presentacion["resultado"], presentacion["unidad"], presentacion["referencia"]), ("Negativo", "", ""))
            secciones.append({"grupo": codigo, "columnas": {"unidad": True, "referencia": True}, "parametros": [
                {"codigo": codigo, "nombre": codigo, "valor": raw, "unidad": "UI/mL", "referencia": {"texto": "Referencia no imprimir"},
                 "serologia": presentacion, "captura_serologia": INMUNOSEROLOGIA.captura[codigo]}]})
        documento["estudios"] = [{"codigo": "INMUNOSEROLOGIA", "nombre": "Inmunoserología", "secciones": secciones}]
        for aprobado in (False, True):
            documento["aprobado"] = aprobado
            html = renderizar_html_informe(documento)
            self.assertEqual(html.count('class="numeric">Negativo<'), 3)
            for excluido in ("TECO", "UI/mL", "Referencia no imprimir", ">Unidad<", ">V. Ref.<", "&lt;200"):
                self.assertNotIn(excluido, html)


class CatalogoAmpliadoTests(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.bio = self.crear_usuario_test(usuario="bio_catalogo_nuevo", rol="BIOQUIMICO", ci="90001111")
        token = self.client.post("/api/auth/login", json={"usuario": self.bio.usuario, "password": "ClaveSegura123!"}).json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}", "X-LIS-Client": "web"}
        self.paciente = self.crear_paciente_test(ci="FICTICIO-CATALOGO-01", sexo="F")

    def crear(self, estudios):
        respuesta = self.client.post("/api/ordenes", headers=self.headers, json={"id_paciente": self.paciente.id_paciente,
            "edad_anios": 30, "estudios": estudios})
        self.assertEqual(respuesta.status_code, 201, respuesta.text)
        return respuesta.json()["orden"]["id"]

    def test_migracion_pancreatico_conserva_resultados_overrides_y_snapshot(self):
        id_orden = self.crear([{"codigo": "PERFIL_PANCREATICO"}])
        guardado = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.headers, json={
            "valores": {"AMILASA_SERICA": "10", "LIPASA_SERICA": "125"},
            "rangos_override": {"LIPASA_SERICA": {"limite_superior": "130", "texto": "Hasta 130 UA/dL"}},
        })
        self.assertEqual(guardado.status_code, 200, guardado.text)
        publicada = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.headers)
        self.assertEqual(publicada.status_code, 201, publicada.text)
        folio = publicada.json()["folio"]
        original = self.client.get(f"/api/informes/{folio}", headers=self.headers).json()

        borrador = self.crear([{"codigo": "PERFIL_PANCREATICO"}])
        self.client.put(f"/api/ordenes/{borrador}/resultados", headers=self.headers, json={
            "valores": {"LIPASA_SERICA": "125"},
            "rangos_override": {"LIPASA_SERICA": {"limite_superior": "130", "texto": "Hasta 130 UA/dL"}},
        })
        ruta = Path(__file__).parents[1] / "alembic/versions/0009_presentacion_perfil_pancreatico.py"
        spec = importlib.util.spec_from_file_location("migracion_pancreatico", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        self.db.execute(text("""
            UPDATE laboratorio.parametros SET orden_visualizacion = 3 - orden_visualizacion
            WHERE codigo IN ('AMILASA_SERICA', 'LIPASA_SERICA')
        """))
        self.db.commit()
        try:
            for _ in range(2):
                with Operations.context(MigrationContext.configure(self.db.connection())):
                    modulo.upgrade()
                self.db.commit()
            captura = self.client.get(f"/api/ordenes/{borrador}/captura", headers=self.headers).json()
            parametros = [p for seccion in captura["estudios"][0]["secciones"] for p in seccion["parametros"]]
            self.assertEqual([p["codigo"] for p in parametros], ["AMILASA_SERICA", "LIPASA_SERICA"])
            self.assertEqual(parametros[0]["referencia"]["texto"], "10-150 UI/L")
            self.assertEqual(parametros[1]["valor"], "125")
            self.assertEqual(parametros[1]["referencia"]["texto"], "Hasta 130 UA/dL")
            self.assertTrue(parametros[1]["referencia"]["modificada"])
            self.assertEqual(parametros[1]["bandera"], "NORMAL")
            calculada = self.client.post(f"/api/ordenes/{borrador}/calcular", headers=self.headers,
                json={"valores": {"LIPASA_SERICA": "120.01"}, "rangos_override": {"LIPASA_SERICA": {"reestablecer": True}}})
            self.assertEqual(calculada.status_code, 200, calculada.text)
            lipasa = calculada.json()["estudios"][0]["secciones"][0]["parametros"][1]
            self.assertEqual(lipasa["referencia"]["texto"], "Hasta 120 UA/dL")
            self.assertEqual(lipasa["bandera"], "ALTO")
            actual = self.client.get(f"/api/informes/{folio}", headers=self.headers).json()
            self.assertEqual(actual["snapshot_json"], original["snapshot_json"])
            self.assertEqual(actual["snapshot_sha256"], original["snapshot_sha256"])
        finally:
            self.db.rollback()
            with Operations.context(MigrationContext.configure(self.db.connection())):
                modulo.upgrade()
            self.db.commit()

    def test_catalogo_parasitologia_independiente_y_vdrl_con_tipo_anterior(self):
        catalogo = self.client.get("/api/catalogo/estudios", headers=self.headers).json()
        self.assertEqual(len(catalogo), 13)
        inmuno = next(e for e in catalogo if e["codigo"] == "INMUNOSEROLOGIA")
        grupos = {g["codigo"]: g for g in inmuno["grupos"]}
        self.assertIn("PARASITOLOGIA", grupos)
        self.assertEqual({p["codigo"] for p in grupos["PARASITOLOGIA"]["parametros"]}, {
            "H_PYLORI_SUERO", "H_PYLORI_HECES_INMUNO", "SANGRE_OCULTA_HECES_INMUNO",
        })
        parasitologia = next(e for e in catalogo if e["codigo"] == "PARASITOLOGIA")
        self.assertFalse(parasitologia["seleccion_parcial"])
        self.assertIsNone(parasitologia["grupos"])
        self.assertEqual(
            {parametro.codigo for parametro in PARASITOLOGIA.parametros},
            {"H_PYLORI_HECES", "SANGRE_OCULTA_HECES", "MOCO_FECAL",
             "COPROPARASITOLOGICO_SIMPLE", "COPROPARASITOLOGICO_SERIADO"} | {codigo for codigo, _ in MOCO_FECAL_CAMPOS},
        )
        id_orden = self.crear([
            {"codigo": "INMUNOSEROLOGIA", "grupos": ["VDRL"]},
            {"codigo": "PARASITOLOGIA"},
        ])
        self.db.execute(text("UPDATE laboratorio.parametros SET tipo_campo='TEXTO_LIBRE', opciones=NULL WHERE codigo='VDRL_DILUCION'"))
        self.db.commit()
        try:
            captura = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.headers).json()
            estudios = {estudio["codigo"]: estudio for estudio in captura["estudios"]}
            self.assertEqual(set(estudios), {"INMUNOSEROLOGIA", "PARASITOLOGIA"})
            parametros = {p["codigo"]: p for e in estudios.values() for s in e["secciones"] for p in s["parametros"]}
            self.assertEqual(parametros["VDRL_DILUCION"]["tipo_campo"], "SELECCION")
            self.assertEqual(parametros["VDRL_DILUCION"]["opciones"], ["Negativo", "Positivo"])
            self.assertTrue(all(p["opciones"] == ["Negativo", "Positivo"] for p in parametros.values() if p["tipo_campo"] == "SELECCION"))
            self.assertTrue(all(p["valor"] is None for p in parametros.values()))
            respuesta = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.headers,
                json={"valores": {"VDRL_DILUCION": "Negativo", "MOCO_FECAL": "Positivo", "COPROPARASITOLOGICO_SIMPLE": "--"}})
            self.assertEqual(respuesta.status_code, 200, respuesta.text)
        finally:
            self.db.execute(text("UPDATE laboratorio.parametros SET tipo_campo='SELECCION', opciones='[\"Negativo\",\"Positivo\"]'::jsonb WHERE codigo='VDRL_DILUCION'"))
            self.db.commit()

    def test_subestudios_inmuno_muestran_muestra_metodo_y_opciones_cualitativas(self):
        id_orden = self.crear([
            {"codigo": "INMUNOSEROLOGIA", "grupos": ["PARASITOLOGIA"]},
            {"codigo": "PARASITOLOGIA"},
        ])
        captura = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.headers).json()
        estudios = {estudio["codigo"]: estudio for estudio in captura["estudios"]}
        inmuno = estudios["INMUNOSEROLOGIA"]
        parasito = estudios["PARASITOLOGIA"]
        parametros_inmuno = {
            parametro["codigo"]: parametro
            for seccion in inmuno["secciones"]
            for parametro in seccion["parametros"]
        }
        self.assertEqual(set(parametros_inmuno), {
            "H_PYLORI_SUERO", "H_PYLORI_HECES_INMUNO", "SANGRE_OCULTA_HECES_INMUNO",
        })
        esperados = {
            "H_PYLORI_SUERO": ("HELICOBACTER PYLORI", ["Negativo", "Positivo"], "Suero"),
            "H_PYLORI_HECES_INMUNO": ("HELICOBACTER PYLORI", ["No reactivo", "Reactivo"], "Heces"),
            "SANGRE_OCULTA_HECES_INMUNO": ("Sangre oculta en heces", ["No reactivo", "Reactivo"], "Heces"),
        }
        self.assertFalse(inmuno["secciones"][0]["columnas"]["unidad"])
        self.assertFalse(inmuno["secciones"][0]["columnas"]["referencia"])
        self.assertFalse(inmuno["secciones"][0]["columnas"]["bandera"])
        self.assertTrue(inmuno["secciones"][0]["columnas"]["muestra"])
        self.assertTrue(inmuno["secciones"][0]["columnas"]["metodo"])
        for codigo, parametro in parametros_inmuno.items():
            with self.subTest(codigo=codigo):
                nombre, opciones, muestra = esperados[codigo]
                self.assertEqual(parametro["nombre"], nombre)
                self.assertEqual(parametro["opciones"], opciones)
                self.assertEqual(parametro["muestra"], muestra)
                self.assertEqual(parametro["metodo"], "Inmunocromatografico")
                self.assertIsNone(parametro["unidad"])
                self.assertIsNone(parametro["referencia"])
                self.assertIsNone(parametro["bandera"])

        respuesta = self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            headers=self.headers,
            json={"valores": {
                "H_PYLORI_SUERO": "Positivo",
                "H_PYLORI_HECES_INMUNO": "Reactivo",
                "SANGRE_OCULTA_HECES_INMUNO": "No reactivo",
            }},
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.text)

        seccion_cualitativa = next(s for s in parasito["secciones"] if s["formato"] == "SELECCION_SIMPLE")
        self.assertEqual({p["codigo"] for p in seccion_cualitativa["parametros"]},
                         {"H_PYLORI_HECES", "SANGRE_OCULTA_HECES"})

    def test_migracion_0016_mueve_suero_y_conserva_las_pruebas_de_heces(self):
        id_orden = self.crear([
            {"codigo": "INMUNOSEROLOGIA", "grupos": ["VDRL"]},
            {"codigo": "PARASITOLOGIA"},
        ])
        respuesta = self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            headers=self.headers,
            json={"valores": {
                "VDRL_DILUCION": "Negativo",
                "H_PYLORI_HECES": "Positivo",
                "SANGRE_OCULTA_HECES": "Negativo",
            }},
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        self.db.commit()

        versiones = dict(self.db.execute(text("""
            SELECT e.codigo, ev.id_estudio_version
            FROM laboratorio.estudio_versiones ev
            JOIN laboratorio.estudios e USING (id_estudio)
            WHERE ev.activa AND e.codigo IN ('INMUNOSEROLOGIA', 'PARASITOLOGIA')
        """)).all())
        version_parasito = versiones["PARASITOLOGIA"]
        parametro_suero = self.db.execute(text("""
            SELECT id_parametro
            FROM laboratorio.parametros
            WHERE id_estudio_version = :version AND codigo = 'H_PYLORI_SUERO'
        """), {"version": version_parasito}).scalar_one_or_none()
        if parametro_suero is None:
            parametro_suero = self.db.execute(text("""
                INSERT INTO laboratorio.parametros (
                    id_estudio_version, codigo, nombre, tipo_campo, opciones, orden_visualizacion
                )
                VALUES (:version, 'H_PYLORI_SUERO', 'Helicobacter pylori (suero)',
                        'SELECCION', '["Negativo","Positivo"]'::jsonb, 999)
                RETURNING id_parametro
            """), {"version": version_parasito}).scalar_one()

        orden_estudio_parasito = self.db.execute(text("""
            SELECT oe.id_orden_estudio
            FROM laboratorio.orden_estudios oe
            JOIN laboratorio.estudios e USING (id_estudio)
            WHERE oe.id_orden = :orden AND e.codigo = 'PARASITOLOGIA'
        """), {"orden": id_orden}).scalar_one()
        self.db.execute(text("""
            INSERT INTO laboratorio.resultados_borrador
                (id_orden_estudio, id_parametro, valor_texto, actualizado_por)
            VALUES (:orden_estudio, :parametro, 'Positivo', :usuario)
        """), {
            "orden_estudio": orden_estudio_parasito,
            "parametro": parametro_suero,
            "usuario": self.bio.id_usuario,
        })
        self.db.commit()

        ruta = Path(__file__).parents[1] / "alembic/versions/0016_parasitologia_en_inmunoserologia.py"
        spec = importlib.util.spec_from_file_location("migracion_parasitologia_inmunoserologia", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        try:
            with Operations.context(MigrationContext.configure(self.db.connection())):
                modulo.upgrade()

            resultados = {
                (codigo_estudio, codigo_parametro): valor
                for codigo_estudio, codigo_parametro, valor in self.db.execute(text("""
                    SELECT e.codigo, p.codigo, r.valor_texto
                    FROM laboratorio.resultados_borrador r
                    JOIN laboratorio.orden_estudios oe USING (id_orden_estudio)
                    JOIN laboratorio.estudios e USING (id_estudio)
                    JOIN laboratorio.parametros p USING (id_parametro)
                    JOIN laboratorio.ordenes o USING (id_orden)
                    WHERE o.id_orden = :orden AND r.id_edicion IS NULL
                """), {"orden": id_orden}).all()
            }
            self.assertEqual(resultados[("INMUNOSEROLOGIA", "H_PYLORI_SUERO")], "Positivo")
            self.assertEqual(resultados[("PARASITOLOGIA", "H_PYLORI_HECES")], "Positivo")
            self.assertEqual(resultados[("PARASITOLOGIA", "SANGRE_OCULTA_HECES")], "Negativo")
            self.assertEqual(resultados[("INMUNOSEROLOGIA", "VDRL_DILUCION")], "Negativo")
            grupos = self.db.execute(text("""
                SELECT g.grupo
                FROM laboratorio.orden_estudio_grupos g
                JOIN laboratorio.orden_estudios oe USING (id_orden_estudio)
                JOIN laboratorio.estudios e USING (id_estudio)
                WHERE oe.id_orden = :orden AND e.codigo = 'INMUNOSEROLOGIA'
            """), {"orden": id_orden}).scalars().all()
            self.assertIn("PARASITOLOGIA", grupos)
        finally:
            self.db.rollback()

    def test_migracion_0017_reordena_ldl_y_vldl_sin_alterar_resultados(self):
        id_orden = self.crear([{"codigo": "PERFIL_LIPIDICO"}])
        respuesta = self.client.put(
            f"/api/ordenes/{id_orden}/resultados",
            headers=self.headers,
            json={"valores": {
                "COLESTEROL": "164.5",
                "TRIGLICERIDOS": "102.4",
                "HDL": "40",
            }},
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        self.db.commit()

        version_anterior = self.db.execute(text("""
            SELECT oe.id_estudio_version
            FROM laboratorio.orden_estudios oe
            JOIN laboratorio.estudios e USING (id_estudio)
            WHERE oe.id_orden = :orden AND e.codigo = 'PERFIL_LIPIDICO'
        """), {"orden": id_orden}).scalar_one()

        def resultados_guardados():
            return {
                codigo: (id_resultado, valor)
                for id_resultado, codigo, valor in self.db.execute(text("""
                    SELECT r.id_resultado, p.codigo, r.valor_numerico
                    FROM laboratorio.resultados_borrador r
                    JOIN laboratorio.orden_estudios oe USING (id_orden_estudio)
                    JOIN laboratorio.parametros p USING (id_parametro)
                    WHERE oe.id_orden = :orden AND r.id_edicion IS NULL
                """), {"orden": id_orden}).all()
            }

        resultados_antes = resultados_guardados()
        ruta = Path(__file__).parents[1] / "alembic/versions/0017_orden_ldl_vldl_perfil_lipidico.py"
        spec = importlib.util.spec_from_file_location("migracion_orden_ldl_vldl", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        try:
            with Operations.context(MigrationContext.configure(self.db.connection())):
                modulo.upgrade()

            version_nueva = self.db.execute(text("""
                SELECT oe.id_estudio_version
                FROM laboratorio.orden_estudios oe
                JOIN laboratorio.estudios e USING (id_estudio)
                WHERE oe.id_orden = :orden AND e.codigo = 'PERFIL_LIPIDICO'
            """), {"orden": id_orden}).scalar_one()
            orden_parametros = self.db.execute(text("""
                SELECT codigo
                FROM laboratorio.parametros
                WHERE id_estudio_version = :version
                ORDER BY orden_visualizacion
            """), {"version": version_nueva}).scalars().all()
            self.assertEqual(orden_parametros, ["COLESTEROL", "TRIGLICERIDOS", "HDL", "LDL", "VLDL"])
            self.assertNotEqual(version_anterior, version_nueva)
            self.assertEqual(resultados_guardados(), resultados_antes)
            versiones_resultados = self.db.execute(text("""
                SELECT DISTINCT p.id_estudio_version
                FROM laboratorio.resultados_borrador r
                JOIN laboratorio.orden_estudios oe USING (id_orden_estudio)
                JOIN laboratorio.parametros p USING (id_parametro)
                WHERE oe.id_orden = :orden AND r.id_edicion IS NULL
            """), {"orden": id_orden}).scalars().all()
            self.assertEqual(set(versiones_resultados), {version_nueva})
            self.assertFalse(self.db.execute(text("""
                SELECT activa
                FROM laboratorio.estudio_versiones
                WHERE id_estudio_version = :version
            """), {"version": version_anterior}).scalar_one())
        finally:
            self.db.rollback()

    def test_migracion_0019_actualiza_serologia_y_mapea_resultados_borrador(self):
        id_orden = self.crear([{"codigo": "INMUNOSEROLOGIA", "grupos": ["PARASITOLOGIA"]}])
        datos = self.db.execute(text("""
            SELECT oe.id_orden_estudio, oe.id_estudio_version, p.codigo, p.id_parametro
            FROM laboratorio.orden_estudios oe
            JOIN laboratorio.estudios e USING (id_estudio)
            JOIN laboratorio.parametros p ON p.id_estudio_version = oe.id_estudio_version
            WHERE oe.id_orden = :orden AND e.codigo = 'INMUNOSEROLOGIA'
              AND p.codigo IN ('H_PYLORI_SUERO', 'H_PYLORI_HECES_INMUNO', 'SANGRE_OCULTA_HECES_INMUNO')
        """), {"orden": id_orden}).all()
        self.assertEqual(len(datos), 3)
        id_orden_estudio = datos[0].id_orden_estudio
        version_anterior = datos[0].id_estudio_version
        valores_anteriores = {
            "H_PYLORI_SUERO": "Positivo",
            "H_PYLORI_HECES_INMUNO": "Negativo",
            "SANGRE_OCULTA_HECES_INMUNO": "Positivo",
        }
        for _, _, codigo, id_parametro in datos:
            self.db.execute(text("""
                INSERT INTO laboratorio.resultados_borrador
                    (id_orden_estudio, id_parametro, valor_texto, actualizado_por)
                VALUES (:orden_estudio, :parametro, :valor, :usuario)
            """), {
                "orden_estudio": id_orden_estudio,
                "parametro": id_parametro,
                "valor": valores_anteriores[codigo],
                "usuario": self.bio.id_usuario,
            })
        self.db.commit()

        ruta = Path(__file__).parents[1] / "alembic/versions/0019_serologia_muestra_metodo.py"
        spec = importlib.util.spec_from_file_location("migracion_serologia_muestra_metodo", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        try:
            with Operations.context(MigrationContext.configure(self.db.connection())):
                modulo.upgrade()

            version_nueva = self.db.execute(text("""
                SELECT oe.id_estudio_version
                FROM laboratorio.orden_estudios oe
                WHERE oe.id_orden_estudio = :orden_estudio
            """), {"orden_estudio": id_orden_estudio}).scalar_one()
            self.assertNotEqual(version_nueva, version_anterior)
            parametros = {
                codigo: (nombre, muestra, metodo, opciones)
                for codigo, nombre, muestra, metodo, opciones in self.db.execute(text("""
                    SELECT codigo, nombre, muestra, metodo, opciones
                    FROM laboratorio.parametros
                    WHERE id_estudio_version = :version
                      AND codigo IN ('H_PYLORI_SUERO', 'H_PYLORI_HECES_INMUNO', 'SANGRE_OCULTA_HECES_INMUNO')
                """), {"version": version_nueva}).all()
            }
            self.assertEqual(parametros, {
                "H_PYLORI_SUERO": ("HELICOBACTER PYLORI", "Suero", "Inmunocromatografico", ["Negativo", "Positivo"]),
                "H_PYLORI_HECES_INMUNO": ("HELICOBACTER PYLORI", "Heces", "Inmunocromatografico", ["No reactivo", "Reactivo"]),
                "SANGRE_OCULTA_HECES_INMUNO": ("Sangre oculta en heces", "Heces", "Inmunocromatografico", ["No reactivo", "Reactivo"]),
            })
            resultados = {
                codigo: valor
                for codigo, valor in self.db.execute(text("""
                    SELECT p.codigo, r.valor_texto
                    FROM laboratorio.resultados_borrador r
                    JOIN laboratorio.parametros p USING (id_parametro)
                    WHERE r.id_orden_estudio = :orden_estudio AND r.id_edicion IS NULL
                """), {"orden_estudio": id_orden_estudio}).all()
            }
            self.assertEqual(resultados, {
                "H_PYLORI_SUERO": "Positivo",
                "H_PYLORI_HECES_INMUNO": "No reactivo",
                "SANGRE_OCULTA_HECES_INMUNO": "Reactivo",
            })
            self.assertFalse(self.db.execute(text("""
                SELECT activa FROM laboratorio.estudio_versiones WHERE id_estudio_version = :version
            """), {"version": version_anterior}).scalar_one())
        finally:
            self.db.rollback()

    def test_migracion_0020_agrega_chagas_y_sensibilidad_personalizada_de_asto(self):
        id_orden = self.crear([{"codigo": "INMUNOSEROLOGIA", "grupos": ["PARASITOLOGIA", "ASTO"]}])
        ruta = Path(__file__).parents[1] / "alembic/versions/0020_inmunoserologia_chagas_asto.py"
        spec = importlib.util.spec_from_file_location("migracion_inmunoserologia_chagas_asto", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        try:
            with Operations.context(MigrationContext.configure(self.db.connection())):
                modulo.upgrade()

            version = self.db.execute(text("""
                SELECT oe.id_estudio_version, ev.configuracion_json
                FROM laboratorio.orden_estudios oe
                JOIN laboratorio.estudio_versiones ev USING (id_estudio_version)
                WHERE oe.id_orden = :orden
            """), {"orden": id_orden}).one()
            parametros = {
                codigo: (nombre, grupo, opciones)
                for codigo, nombre, grupo, opciones in self.db.execute(text("""
                    SELECT codigo, nombre, grupo, opciones
                    FROM laboratorio.parametros
                    WHERE id_estudio_version = :version
                """), {"version": version.id_estudio_version}).all()
            }
            self.assertEqual(parametros["SANGRE_OCULTA_HECES_INMUNO"][0], "SANGRE OCULTA EN HECES")
            self.assertEqual(parametros["CHAGAS"], ("CHAGAS", "CHAGAS", ["Negativo", "Positivo"]))
            config_asto = version.configuracion_json["captura"]["ASTO_DILUCION"]
            self.assertTrue(config_asto["personalizable"])
            self.assertEqual(config_asto["reactivos"][0]["sensibilidad"], "200")
            self.assertIn("UI/mL", config_asto["unidades"])

            grupos = {grupo for _, grupo, _ in parametros.values() if grupo}
            self.assertIn("PARASITOLOGIA", grupos)
            self.assertIn("CHAGAS", grupos)
        finally:
            self.db.rollback()

    def test_rangos_banderas_y_edicion_en_perfiles_y_quimica(self):
        id_orden = self.crear([{"codigo": c} for c in ("PERFIL_CARDIACO", "PERFIL_PANCREATICO", "QUIMICA_SANGUINEA")])
        casos = {
            "CPK": [("24.99", "BAJO"), ("25", "NORMAL"), ("192", "NORMAL"), ("192.01", "ALTO")],
            "CK_MB": [("0", "NORMAL"), ("24", "NORMAL"), ("24.01", "ALTO")],
            "LDH_QUIMICA": [("199.99", "BAJO"), ("200", "NORMAL"), ("400", "NORMAL"), ("400.01", "ALTO")],
            "LDH_CARDIACO": [("199.99", "BAJO"), ("200", "NORMAL"), ("400", "NORMAL"), ("400.01", "ALTO")],
            "LIPASA_SERICA": [("120", "NORMAL"), ("120.01", "ALTO")],
            "AMILASA_SERICA": [("9.99", "BAJO"), ("10", "NORMAL"), ("150", "NORMAL"), ("150.01", "ALTO")],
            "GLICEMIA_POST_PRANDIAL": [("69.99", "BAJO"), ("70", "NORMAL"), ("110", "NORMAL"), ("110.01", "ALTO")],
            "ALCOHOLEMIA": [("0", "NORMAL"), ("100", "NORMAL"), ("100.01", "ALTO")],
        }
        for codigo, valores in casos.items():
            for valor, bandera in valores:
                with self.subTest(codigo=codigo, valor=valor):
                    respuesta = self.client.post(f"/api/ordenes/{id_orden}/calcular", headers=self.headers, json={"valores": {codigo: valor}})
                    self.assertEqual(respuesta.status_code, 200, respuesta.text)
                    parametros = {p["codigo"]: p for e in respuesta.json()["estudios"] for s in e["secciones"] for p in s["parametros"]}
                    self.assertEqual(parametros[codigo]["bandera"], bandera)
        editada = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.headers, json={"valores": {"CK_MB": "25"},
            "rangos_override": {"CK_MB": {"limite_inferior": "0", "limite_superior": "30", "texto": "0-30 UI/L"}}})
        self.assertEqual(editada.status_code, 200, editada.text)
        parametros = {p["codigo"]: p for e in editada.json()["estudios"] for s in e["secciones"] for p in s["parametros"]}
        self.assertEqual(parametros["CK_MB"]["bandera"], "NORMAL")
        self.assertTrue(parametros["CK_MB"]["referencia"]["modificada"])
        self.assertEqual(parametros["LIPASA_SERICA"]["unidad"], "UA/dL")
        self.assertEqual(parametros["TROPONINA_CARDIACA"]["opciones"], ["Negativo", "Positivo"])
        self.assertEqual(parametros["GLICEMIA"]["referencia"], parametros["GLICEMIA_POST_PRANDIAL"]["referencia"])

    def test_troponina_se_captura_sin_unidad_referencia_ni_bandera(self):
        id_orden = self.crear([{"codigo": "PERFIL_CARDIACO"}])
        captura = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.headers).json()
        estudio = next(e for e in captura["estudios"] if e["codigo"] == "PERFIL_CARDIACO")
        seccion = next(s for s in estudio["secciones"] if s["grupo"] == "TROPONINA")
        troponina = seccion["parametros"][0]

        self.assertEqual(troponina["codigo"], "TROPONINA_CARDIACA")
        self.assertEqual(troponina["tipo_campo"], "SELECCION")
        self.assertEqual(troponina["opciones"], ["Negativo", "Positivo"])
        self.assertIsNone(troponina["unidad"])
        self.assertIsNone(troponina["referencia"])
        self.assertIsNone(troponina["bandera"])

    def test_publica_solo_campos_usados_y_no_informe_vacio(self):
        id_orden = self.crear([{"codigo": c} for c in ("EGO", "QUIMICA_SANGUINEA", "PERFIL_CARDIACO", "PERFIL_PANCREATICO")])
        inicial = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.headers).json()
        self.assertTrue(all(p["valor"] is None for e in inicial["estudios"] for s in e["secciones"] for p in s["parametros"]))
        self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.headers, json={"valores": {}, "observaciones_orden": "Datos ficticios de verificación."})
        self.assertEqual(self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.headers).status_code, 400)
        guardado = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.headers,
            json={"valores": {"ALCOHOLEMIA": "0", "CPK": "25.2", "NITRITOS": "--", "LIPASA_SERICA": ""}})
        self.assertTrue(guardado.json()["completitud"]["completo"], guardado.text)
        publicada = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=self.headers)
        self.assertEqual(publicada.status_code, 201, publicada.text)
        detalle = self.client.get(f"/api/informes/{publicada.json()['folio']}", headers=self.headers).json()
        for estudios in (detalle["snapshot_json"]["estudios"], detalle["estudios_informe"]):
            codigos = {p["codigo"] for e in estudios for s in e["secciones"] for p in s["parametros"]}
            self.assertEqual(codigos, {"ALCOHOLEMIA", "CPK"})
            self.assertEqual({e["codigo"] for e in estudios}, {"QUIMICA_SANGUINEA", "PERFIL_CARDIACO"})

    def test_migracion_separa_parasitologia_anterior_sin_perder_resultados(self):
        id_orden = self.crear([
            {"codigo": "INMUNOSEROLOGIA", "grupos": ["VDRL", "PARASITOLOGIA"]},
            {"codigo": "PARASITOLOGIA"},
        ])
        respuesta = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=self.headers, json={
            "valores": {"VDRL_DILUCION": "Negativo", "H_PYLORI_SUERO": "Positivo"},
        })
        self.assertEqual(respuesta.status_code, 200)
        orden_estudios = dict(self.db.execute(text("""
            SELECT e.codigo, oe.id_orden_estudio
            FROM laboratorio.orden_estudios oe
            JOIN laboratorio.estudios e USING (id_estudio)
            WHERE oe.id_orden = :orden
        """), {"orden": id_orden}).all())
        inmuno_oe = orden_estudios["INMUNOSEROLOGIA"]
        parasi_oe = orden_estudios["PARASITOLOGIA"]
        versiones = dict(self.db.execute(text("""
            SELECT e.codigo, ev.id_estudio_version
            FROM laboratorio.estudio_versiones ev
            JOIN laboratorio.estudios e USING (id_estudio)
            WHERE ev.activa = TRUE AND e.codigo IN ('INMUNOSEROLOGIA', 'PARASITOLOGIA')
        """)).all())
        inmuno_version = versiones["INMUNOSEROLOGIA"]
        parasi_version = versiones["PARASITOLOGIA"]

        # Simular una orden histórica: los campos estaban en Inmunoserología, dentro
        # del grupo PARASITOLOGIA, aunque hoy el catálogo los define por separado.
        self.db.execute(text("""
            INSERT INTO laboratorio.parametros
              (id_estudio_version, codigo, nombre, grupo, tipo_campo, unidad_medida, decimales,
               formula_expresion, opciones, valor_defecto, requiere_confirmacion, metodo, muestra,
               obligatorio, orden_visualizacion)
            SELECT :inmuno_version, codigo, nombre, 'PARASITOLOGIA', tipo_campo, unidad_medida, decimales,
                   formula_expresion, opciones, valor_defecto, requiere_confirmacion, metodo, muestra,
                   obligatorio, orden_visualizacion + 100
            FROM laboratorio.parametros WHERE id_estudio_version = :parasi_version
        """), {"inmuno_version": inmuno_version, "parasi_version": parasi_version})
        moco_parametro = self.db.execute(text("""
            SELECT id_parametro FROM laboratorio.parametros
            WHERE id_estudio_version = :inmuno_version AND codigo = 'MOCO_FECAL_ASPECTO'
        """), {"inmuno_version": inmuno_version}).scalar_one()
        self.db.execute(text("""
            INSERT INTO laboratorio.resultados_borrador
                (id_orden_estudio, id_parametro, valor_texto, actualizado_por)
            VALUES (:orden_estudio, :parametro, 'Moco ficticio', :usuario)
        """), {
            "orden_estudio": inmuno_oe,
            "parametro": moco_parametro,
            "usuario": self.bio.id_usuario,
        })
        self.db.execute(text("DELETE FROM laboratorio.orden_estudios WHERE id_orden_estudio = :id"), {"id": parasi_oe})
        self.db.execute(text("""
            INSERT INTO laboratorio.orden_estudio_grupos (id_orden_estudio, grupo)
            VALUES (:id, 'PARASITOLOGIA')
            ON CONFLICT (id_orden_estudio, grupo) DO NOTHING
        """), {"id": inmuno_oe})
        self.db.execute(text("""
            INSERT INTO laboratorio.orden_estudio_grupos (id_orden_estudio, grupo)
            VALUES (:id, 'H_PYLORI_SUERO')
        """), {"id": inmuno_oe})
        self.db.execute(text("""
            UPDATE laboratorio.estudio_versiones
            SET configuracion_json = configuracion_json - 'revision_catalogo'
            WHERE id_estudio = (
                SELECT id_estudio FROM laboratorio.estudios WHERE codigo = 'INMUNOSEROLOGIA'
            )
        """))
        self.db.commit()
        ruta = Path(__file__).parents[1] / "alembic/versions/0010_curva_y_parasitologia.py"
        spec = importlib.util.spec_from_file_location("migracion_parasitologia_independiente", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        with Operations.context(MigrationContext.configure(self.db.connection())):
            modulo.upgrade()
        self.db.commit()
        activa = self.db.execute(text("""
            SELECT ev.id_estudio_version, ev.configuracion_json->>'revision_catalogo'
            FROM laboratorio.estudio_versiones ev
            JOIN laboratorio.estudios e USING (id_estudio)
            WHERE e.codigo = 'INMUNOSEROLOGIA' AND ev.activa
        """)).one()
        self.assertNotEqual(activa.id_estudio_version, inmuno_version)
        self.assertEqual(activa[1], "0010_curva_parasitologia")
        self.assertFalse(self.db.execute(text("""
            SELECT activa FROM laboratorio.estudio_versiones WHERE id_estudio_version = :version
        """), {"version": inmuno_version}).scalar_one())
        captura = self.client.get(f"/api/ordenes/{id_orden}/captura", headers=self.headers).json()
        estudios = {estudio["codigo"]: estudio for estudio in captura["estudios"]}
        self.assertEqual(set(estudios), {"INMUNOSEROLOGIA", "PARASITOLOGIA"})
        self.assertEqual(set(estudios["INMUNOSEROLOGIA"]["grupos_seleccionados"]), {"PARASITOLOGIA", "VDRL"})
        parametros = {
            p["codigo"]: p
            for estudio in estudios.values()
            for seccion in estudio["secciones"]
            for p in seccion["parametros"]
        }
        self.assertEqual(parametros["H_PYLORI_SUERO"]["valor"], "Positivo")
        self.assertEqual(parametros["VDRL_DILUCION"]["valor"], "Negativo")
        self.assertEqual(parametros["MOCO_FECAL_ASPECTO"]["valor"], "Moco ficticio")
