# CONTEXTO RÁPIDO DEL PROYECTO — LIS Laboratorio Clínico (UrgenLab / Metodista)

> **Instrucción para el Agente de IA:** Lee este archivo primero al iniciar una sesión para comprender la arquitectura, el estado actual y las reglas inquebrantables antes de abrir archivos individuales. Luego consulta `@AGENTS.md`, `@docs/DECISIONES.md` y `@docs/UX_GUIDE.md`.

## 1. ¿Qué es este sistema?
Sistema de Información de Laboratorio Clínico (LIS) **on-premise** (servidor local sin dependencia de internet) diseñado para bioquímicos acostumbrados a trabajar con plantillas de Excel de alta velocidad.
* **Stack:** PostgreSQL 16 + FastAPI (SQLAlchemy 2.0 síncrono, psycopg 3, Pydantic v2) + React 19 / Vite / TypeScript + Caddy (HTTPS interno).

## 2. Reglas Clínicas y Técnicas Inquebrantables
1. **Esquema y Catálogo Congelados:** Prohibido editar `db/init/001_schema.sql`, `db/init/002_seed_catalogo.sql` y `backend/app/catalog/definitions.py`. Todo cambio de BD desde ahora va por migraciones en `backend/alembic/versions/`.
2. **Cero `float` y cero `eval`:** Todo cálculo clínico usa `Decimal` y el motor AST seguro (`backend/app/calculation/engine.py`). Vacío es `None`/`NULL`, jamás `0`.
3. **Reloj Determinista:** Prohibido usar `datetime.now()` o `utcnow()`. Todo el backend debe importar y usar `ahora()` de `backend/app/core/clock.py`.
4. **Manejo de Errores:** Prohibido usar `HTTPException` de FastAPI. Todo error debe lanzar una subclase de `AppError` (`backend/app/core/errors.py`) que formatea `{"codigo": "...", "mensaje": "..."}`.
5. **Seguridad y Sesiones:**
   - Access token JWT guardado **exclusivamente en memoria de React** (`frontend/src/api/client.ts`). **Prohibido** usar `localStorage` o `sessionStorage`.
   - Refresh token en cookie `HttpOnly`, `SameSite=Strict`, `Path=/api/auth` + cabecera CSRF `X-LIS-Client: web`.
   - Roles: `BIOQUIMICO` (opera sus propias órdenes; las ajenas responden 404) y `ADMIN` (gestiona usuarios/configuración; ve órdenes/capturas en modo **solo lectura** auditando `ADMIN_VE_PRIVADO` en `log_seguridad`).
6. **Diseño y UX:** Manda `@docs/UX_GUIDE.md`. Interfaz densa fiel a Excel, resolución base 1366×768 sin scroll innecesario, navegación por teclado (`Enter`/`Tab`), cero emojis, cero textos de desarrollo ("Fase X", "Próximamente") y cero librerías UI externas o skills de `.agents/`.

## 3. Mapa de Módulos (Dónde vive cada cosa)
* **Configuración y Seguridad:** `backend/app/core/{config,database,clock,errors,security}.py` | `backend/app/api/{deps,auth,usuarios}.py`.
* **Catálogo y Motor:** `backend/app/catalog/definitions.py` (9 estudios, 2 perfiles) | `backend/app/calculation/engine.py` | `backend/app/api/catalogo.py`.
* **Pacientes y Órdenes (Borrador):** `backend/app/models/{patient,order}.py` | `backend/app/api/{pacientes,ordenes}.py` (incluye algoritmo D2-04 de detección de duplicados y solapamientos).
* **Captura y Evaluación en Vivo:** `backend/app/models/result.py` | `backend/app/services/evaluacion_service.py` (orden topológico Kahn, banderas por sexo/edad, reglas `SUMA_IGUAL` y `MENOR_IGUAL`, defectos virtuales de EGO) | `backend/app/api/resultados.py`.
* **Tests Backend:** `backend/tests/` (`unittest` contra PostgreSQL real `lis_test`; requiere que el nombre de la BD termine en `_test`).
* **Frontend SPA:** `frontend/src/api/` (cliente HTTP en memoria) | `frontend/src/features/{auth,admin,home,pacientes,ordenes}/` | `frontend/src/components/Layout.tsx`.

## 4. Estado de Fases
* **Fase 0, 1 y 1.5 (Completadas):** Esquema, catálogo, auth Argon2id, sesiones por latido, CRUD usuarios.
* **Fase 2 (Completada):** Pacientes, lectura de catálogo, órdenes en borrador, bloqueo de duplicados.
* **Fase 3 (Completada):** Captura de resultados, cálculo en vivo, banderas, reglas cruzadas, completitud.
* **Fase 3.5 (En curso):** Endurecimiento de seguridad (quitar CORS/ngrok), guarda de BD de test, sesión dinámica con actividad real del usuario, limpieza de `.agents/skills`.
* **Fase 3.6 (Siguiente):** Rediseño UX fiel a Excel según `docs/UX_GUIDE.md`.
* **Fases 4+ (Futuras):** Publicación con folio inmutable, PDF oficial, Estudio Instantáneo Preliminar y Rol Visitante.