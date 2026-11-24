"""Agregados operativos con datos ficticios; permisos y límites temporales reales."""
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.models.catalog import Estudio, EstudioVersion
from app.models.order import Orden, OrdenEstudio
from app.models.patient import Paciente
from app.models.report import Folio, Informe
from app.services.informes_service import calcular_hash_snapshot
from tests.base import IntegrationTestCase

ZONA = ZoneInfo("America/La_Paz")


class TestEstadisticasAPI(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.bio = self.crear_usuario_test(usuario="bio_estadistica", rol="BIOQUIMICO")
        self.otro = self.crear_usuario_test(usuario="otro_estadistica", rol="BIOQUIMICO")
        self.admin = self.crear_usuario_test(usuario="admin_estadistica", rol="ADMIN")
        self.headers = {}
        for usuario in (self.bio, self.otro, self.admin):
            login = self.client.post("/api/auth/login", json={"usuario": usuario.usuario, "password": "ClaveSegura123!"})
            self.assertEqual(login.status_code, 200, login.text)
            self.headers[usuario.id_usuario] = {"Authorization": f"Bearer {login.json()['access_token']}"}
        self.paciente = Paciente(ci="ESTADISTICA-FICTICIA", nombres="Paciente ficticio",
            apellido_paterno="Prueba estadística", sexo="F", creado_por=self.bio.id_usuario)
        self.db.add(self.paciente)
        self.db.commit()
        self.secuencia = 0
        self.filtros = {"desde": "2026-11-10", "hasta": "2026-11-10"}

    def crear_orden(self, autor=None, minutos=None, inicio=None, toma=True):
        self.secuencia += 1
        autor = autor or self.bio
        inicio = inicio or datetime(2026, 11, 10, 8, tzinfo=ZONA)
        orden = Orden(id_paciente=self.paciente.id_paciente, numero_orden_paciente=self.secuencia,
            id_usuario_autor=autor.id_usuario, edad_anios=30, edad_meses=0, creado_en=inicio,
            fecha_hora_toma_muestra=inicio if toma else None,
            estado_trabajo="PUBLICADA" if minutos is not None else "INCOMPLETO")
        self.db.add(orden)
        self.db.flush()
        for codigo in ("ELECTROLITOS", "EGO"):
            estudio = self.db.query(Estudio).filter_by(codigo=codigo).one()
            version = self.db.query(EstudioVersion).filter_by(id_estudio=estudio.id_estudio, activa=True).one()
            self.db.add(OrdenEstudio(id_orden=orden.id_orden, id_estudio=estudio.id_estudio, id_estudio_version=version.id_estudio_version))
        informe = None
        if minutos is not None:
            folio = f"2026-{900000 + self.secuencia:06d}"
            self.db.add(Folio(folio=folio, anio=2026, correlativo=900000 + self.secuencia))
            self.db.flush()
            snapshot = {"estudios": [
                {"codigo": "ELECTROLITOS", "nombre": "Electrolitos", "secciones": [{"grupo": "GENERAL", "parametros": [{"codigo": "SODIO", "valor": "140"}]}]},
                {"codigo": "EGO", "nombre": "EGO", "secciones": [{"grupo": "GENERAL", "parametros": []}]},
            ]}
            informe = Informe(folio=folio, numero_version=1, id_orden=orden.id_orden,
                estado="VIGENTE", id_usuario_firmante=autor.id_usuario, id_usuario_publicador=autor.id_usuario,
                snapshot_json=snapshot, snapshot_sha256=calcular_hash_snapshot(snapshot), publicado_en=inicio + timedelta(minutes=minutos))
            self.db.add(informe)
        self.db.commit()
        return orden, informe

    def consultar(self, usuario=None, **filtros):
        return self.client.get("/api/estadisticas", params={**self.filtros, **filtros}, headers=self.headers[(usuario or self.bio).id_usuario])

    def test_vacio_no_inventa_tiempos(self):
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        datos = respuesta.json()
        self.assertEqual(datos["resumen"]["ordenes"], 0)
        self.assertIsNone(datos["resumen"]["respuesta_mediana_minutos"])
        self.assertEqual(datos["actividad"], [{"fecha": "2026-11-10", "iniciadas": 0, "publicadas": 0}])

    def test_bio_solo_propias_admin_filtra_responsable(self):
        self.crear_orden(minutos=60)
        self.crear_orden(autor=self.otro, minutos=120)
        self.crear_orden(autor=self.otro)
        propia = self.consultar().json()
        self.assertEqual(propia["alcance"], "propio")
        self.assertEqual(propia["resumen"]["ordenes"], 1)
        self.assertEqual([item["id"] for item in propia["profesionales"]], [self.bio.id_usuario])
        self.assertEqual(self.consultar(id_autor=self.otro.id_usuario).status_code, 403)
        todas = self.consultar(self.admin).json()
        self.assertEqual(todas["resumen"]["ordenes"], 3)
        self.assertEqual(todas["resumen"]["pendientes"], 1)
        self.assertEqual(todas["alcance"], "laboratorio")
        ajena = self.consultar(self.admin, id_autor=self.otro.id_usuario).json()
        self.assertEqual(ajena["resumen"]["ordenes"], 2)
        self.assertEqual(ajena["resumen"]["publicadas"], 1)
        self.assertNotIn("Paciente ficticio", str(todas))
        self.assertNotIn("snapshot", str(todas))

    def test_no_duplica_versiones_y_cuenta_solo_estudios_informados(self):
        orden, primera = self.crear_orden(minutos=90)
        primera.estado = "DESPLAZADO"
        self.db.flush()
        self.db.add(Informe(folio=primera.folio, numero_version=2, id_orden=orden.id_orden,
            estado="VIGENTE", id_usuario_firmante=self.bio.id_usuario, id_usuario_publicador=self.bio.id_usuario,
            snapshot_json=primera.snapshot_json, snapshot_sha256=primera.snapshot_sha256,
            justificativo="Reedición ficticia para verificar el conteo único.",
            publicado_en=primera.publicado_en + timedelta(hours=5)))
        self.db.commit()
        datos = self.consultar().json()
        self.assertEqual(datos["resumen"]["ordenes"], 1)
        self.assertEqual(datos["resumen"]["publicadas"], 1)
        self.assertEqual(datos["resumen"]["estudios_informados"], 1)
        self.assertEqual(datos["estudios"], [{"codigo": "ELECTROLITOS", "nombre": "Electrolitos", "cantidad": 1}])
        self.assertEqual(Decimal(datos["resumen"]["respuesta_mediana_minutos"]), Decimal("90"))

    def test_respuesta_limites_inclusivos_y_filtro_en_todos_los_agregados(self):
        for minutos in (0, 60, 61, 240, 241):
            self.crear_orden(minutos=minutos)
        self.crear_orden()
        for filtro, cantidad in (("hasta_60", 2), ("de_60_a_240", 2), ("mas_240", 1)):
            with self.subTest(filtro=filtro):
                datos = self.consultar(respuesta=filtro).json()
                self.assertEqual(datos["resumen"]["ordenes"], cantidad)
                self.assertEqual(datos["resumen"]["pendientes"], 0)
                self.assertEqual(sum(fila["cantidad"] for fila in datos["estados"]), cantidad)
                self.assertEqual(sum(fila["cantidad"] for fila in datos["estudios"]), cantidad)
                self.assertEqual(sum(fila["iniciadas"] for fila in datos["actividad"]), cantidad)
        self.assertEqual(self.consultar(respuesta="hasta_60").json()["resumen"]["respuesta_mediana_minutos"], "0.0")

    def test_tiempo_invalido_no_se_hace_cero_y_ausente_usa_creacion(self):
        self.crear_orden(minutos=-10)
        self.crear_orden(minutos=45, toma=False)
        datos = self.consultar().json()
        self.assertEqual(datos["resumen"]["publicadas_sin_hora"], 1)
        self.assertEqual(datos["resumen"]["respuestas_validas"], 1)
        self.assertEqual(datos["resumen"]["respuesta_mediana_minutos"], "45.0")
        sin_hora = self.consultar(respuesta="sin_hora").json()
        self.assertEqual(sin_hora["resumen"]["ordenes"], 1)
        self.assertIsNone(sin_hora["resumen"]["respuesta_mediana_minutos"])

    def test_fechas_inclusivas_en_bolivia_y_dias_sin_actividad(self):
        self.crear_orden(inicio=datetime(2026, 11, 10, 0, 0, tzinfo=ZONA))
        self.crear_orden(inicio=datetime(2026, 11, 10, 23, 59, 59, tzinfo=ZONA))
        self.crear_orden(inicio=datetime(2026, 11, 11, 0, 0, tzinfo=ZONA))
        self.assertEqual(self.consultar().json()["resumen"]["ordenes"], 2)
        actividad = self.consultar(hasta="2026-11-12").json()["actividad"]
        self.assertEqual([fila["iniciadas"] for fila in actividad], [2, 1, 0])

    def test_autenticacion_y_filtros_invalidos(self):
        self.assertEqual(self.client.get("/api/estadisticas").status_code, 401)
        for filtros in ({"desde": "2026-11-11"}, {"desde": "2025-01-01"}, {"desde": "fecha"}, {"respuesta": "inventada"}, {"id_autor": 0}):
            with self.subTest(filtros=filtros):
                self.assertEqual(self.consultar(**filtros).status_code, 400)

    def test_publicacion_real_usa_secciones_del_snapshot_y_omite_estudio_vacio(self):
        headers = self.headers[self.bio.id_usuario]
        creada = self.client.post("/api/ordenes", headers=headers, json={
            "id_paciente": self.paciente.id_paciente, "edad_anios": 30,
            "estudios": [{"codigo": "ELECTROLITOS"}, {"codigo": "EGO"}],
        })
        self.assertEqual(creada.status_code, 201, creada.text)
        id_orden = creada.json()["orden"]["id"]
        guardada = self.client.put(f"/api/ordenes/{id_orden}/resultados", headers=headers,
            json={"valores": {"SODIO": "140"}})
        self.assertEqual(guardada.status_code, 200, guardada.text)
        publicada = self.client.post(f"/api/ordenes/{id_orden}/publicar", headers=headers)
        self.assertEqual(publicada.status_code, 201, publicada.text)
        hoy = datetime.now(ZONA).date().isoformat()
        respuesta = self.consultar(desde=hoy, hasta=hoy)
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        datos = respuesta.json()
        self.assertEqual(datos["resumen"]["publicadas"], 1)
        self.assertEqual(datos["resumen"]["estudios_informados"], 1)
        self.assertEqual(datos["estudios"], [{"codigo": "ELECTROLITOS", "nombre": "Electrolitos", "cantidad": 1}])
