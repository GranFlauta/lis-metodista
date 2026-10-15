# Auditoría de código — Fases 1 a 3 (LIS)

**Alcance:** reconstruí los 158 archivos del volcado (`CODE_COMPLETO_HASTA_FASE_3.docx`) y revisé el código, no solo los informes.
**Límites de esta auditoría (lo que NO pude hacer):** no hay PostgreSQL ni las dependencias en mi entorno, así que **no ejecuté los 119 tests** ni la aplicación, y no vi la interfaz renderizada. Lo que sí hice: compilar todo el backend, ejecutar los 25 tests que no necesitan BD (pasan), comparar esquema/catálogo/motor contra mis originales, y leer el código de seguridad, cálculo, órdenes, resultados, tests y frontend.

## 1. Veredicto

| Fase | Veredicto | Motivo |
|---|---|---|
| **1** (auth, sesión, usuarios) | **Aprobada con 3 correcciones obligatorias** | El `auth.py` real **sí** cumple lo exigido (el que se pegó antes era un archivo viejo). Pero hay 3 incumplimientos de seguridad (ver §3) |
| **2** (pacientes, órdenes) | **Aprobada** | Bloqueos `FOR UPDATE`, detección de duplicados, privacidad 404 y descarte con registro |
| **3** (captura y cálculo) | **Aprobada en backend; rechazada en usabilidad** | Lógica clínica correcta y bien probada; la interfaz no sirve para el trabajo diario (§5) |

El esquema (`001_schema.sql`) y el catálogo (`definitions.py`) son **idénticos** a los que entregué. El motor solo tiene el cambio autorizado (`codigo_motivo`). Eso es lo más importante: la base clínica no se tocó.

## 2. Lo que está bien (verificado en el código)

* `auth.py`: 6 endpoints, `X-LIS-Client`, cookie con `path` propio, errores `{codigo, mensaje}`, verificación ficticia en login, sin `HTTPException` ni `datetime.now` fuera de `clock.py`.
* `security.py`: hash ficticio generado al importar, excepciones acotadas.
* `deps.py`: `require_auth` implementa los 5 pasos; existen `require_admin` y `require_bioquimico`.
* Resultados: `SELECT … FOR UPDATE` en `PUT` y `confirmar-defectos`; el orden de cálculo es topológico; nunca se guarda un 0 inventado; LDL no calculable no bloquea; regla ERROR sí bloquea.
* Auditoría `ADMIN_VE_PRIVADO` en lecturas ajenas del admin.
* Tests: 119 definidos (25+3+11+6+25+8+8+16+9+8), con unas 5 aserciones por test, contra PostgreSQL real y sin `SkipTest`.
* Documentación de supuestos y decisiones al día (§11 y §12).

## 3. Hallazgos que hay que corregir

| # | Sev. | Hallazgo | Evidencia | Riesgo |
|---|---|---|---|---|
| A1 | **ALTA** | **CORS abierto con credenciales.** `allow_origin_regex=r"^https?://.*"` + `allow_credentials=True` + `allow_methods/headers=["*"]` | `backend/app/main.py:12-20` | Viola la regla "no CORS `*`" de los prompts. Cualquier sitio web puede llamar a la API con las cookies del navegador del usuario |
| A2 | **ALTA** | **El sistema estuvo expuesto a internet vía ngrok.** Cabecera `ngrok-skip-browser-warning` en el cliente, `allowedHosts: true` en Vite, el backend sirve el frontend y `/docs` (Swagger) está público | `client.ts:51`, `vite.config.ts`, `main.py` (SPA fallback, `docs_url="/docs"`) | Contradice la decisión D-04 (on-premise, sin depender de internet). Un LIS con datos de pacientes no debe quedar accesible desde internet |
| A3 | **ALTA** | **Los tests pueden borrar la base de datos real.** `setUp` hace `DELETE` de usuarios, pacientes, órdenes, folios e informes (con `session_replication_role='replica'`). No hay ninguna guarda de que la BD sea `lis_test`; además la URL por defecto trae una contraseña escrita | `tests/base.py` | Si alguien apunta `TEST_DATABASE_URL` a la BD real, **se pierden todos los datos** |
| A4 | MEDIA | **Confianza total en cabeceras de proxy**: `ProxyHeadersMiddleware(trusted_hosts="*")` **y** `--forwarded-allow-ips=*` (dos mecanismos). Con el backend expuesto (A2), cualquiera falsifica su IP en `log_seguridad` | `main.py:21`, `Dockerfile` | Auditoría con IP falsificable |
| A5 | MEDIA | **Sesión no configurable y latido "ciego".** Intervalo fijo de 30 s en el frontend; la inactividad solo se renueva con llamadas a la API. Un usuario que lee o escribe sin disparar peticiones es expulsado a los 30 min "esté pulsando o no" | `AuthProvider.tsx:66`, `config.py` | Es la queja que reportaste. Hay que detectar actividad real del usuario y hacer los tiempos editables por el admin |
| A6 | MEDIA | **Los skills de diseño no se leen.** `.cursorignore` contiene `.agents/skills/` y `skills-lock.json` → Cursor los **ignora** a propósito. Además `AGENTS.md` no los menciona, hay 28 (incluye `write-swift`, `animate-expo`, `mobile-native`, estilos contradictorios: brutalista, Apple, "gpt-taste") y `impeccable/SKILL.md` contiene literalmente `404: Not Found` | `.cursorignore`, `.agents/skills/` | Explica por qué "no funcionaron": nunca estuvieron al alcance del agente, y aun estándolo se contradicen |
| A7 | BAJA | `except Exception` silencioso al convertir un valor por defecto numérico | `evaluacion_service.py:447` | Oculta errores; debe acotarse a `ValueError` |
| A8 | BAJA | Textos internos visibles al usuario final: "Disponible en Bloque 5", "Disponible en Fase 3", "Próximamente" | `HomePage.tsx`, `Layout.tsx` | Aspecto de producto sin terminar |
| A9 | BAJA | `.env.example` perdió `ACCESS_TOKEN_MINUTES`, `MAX_LOGIN_ATTEMPTS`, `LOCKOUT_MINUTES`, `COOKIE_SECURE`; README sigue diciendo "Fase 1" y "52 tests"; los prompts e informes están en la raíz del repo | raíz del repo | Documentación desactualizada |

## 4. Calidad de los tests

Buena en el backend: aserciones abundantes y casos reales del Excel. Dos riesgos: (1) A3; (2) no hay ningún test de frontend, y la única validación de la interfaz es `npm run build` más pruebas manuales no verificables. Los informes de evaluación son listas de casillas; los criterios de aceptación manuales deberían respaldarse con capturas o grabaciones.

## 5. Diagnóstico de usabilidad (lo que dijiste, confirmado en el código)

| Queja | Causa en el código |
|---|---|
| Demasiadas pantallas y scroll | `NuevaOrdenPage.tsx` (37 KB) es un formulario vertical de 3 secciones con envío al final; luego otro paso hacia la captura |
| Preview pequeño y espacio desperdiciado | `.lis-captura-grid { grid-template-columns: 1fr 420px }` con `max-width: 1280px`, tabla a `0.85rem`, tarjetas con mucho relleno |
| No fiel al Excel | Formulario en tarjetas, no en la disposición densa de hoja con filas Parámetro/Resultado/Unidad/V.Ref |
| Menú | Barra superior horizontal; sin entrada "Pendientes"; las pendientes solo se alcanzan por "Órdenes" |
| Inicio vacío | Tarjetas de bienvenida con texto de desarrollo; sin "recientes" |

## 6. Plan de corrección

1. **Fase 3.5 — Correcciones** (`PROMPT_FASE_3_5_CORRECCIONES.md`): A1–A9 + sesión dinámica con actividad real.
2. **Fase 3.6 — Rediseño de interfaz** (`PROMPT_FASE_3_6_UX.md`, guiado por `UX_GUIDE.md`): una sola pantalla de nueva orden, ventana de confirmación con hora de inicio, menú lateral, inicio con "Recientes", captura fiel al Excel con vista previa grande, módulo de pacientes orientado a búsqueda.
3. **Fase 4 en adelante**, incluyendo las funciones nuevas que pediste (`PROPUESTA_FUNCIONES_NUEVAS.md`): requieren decisiones tuyas y dependen de publicar/PDF.
