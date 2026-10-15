# PROMPT — FASE 3.5: Correcciones de seguridad, sesión dinámica y orden del repositorio

> **Cuándo aplicarlo:** **después** de la presentación. Algunas correcciones (quitar CORS abierto, el servidor de frontend dentro del backend y la compatibilidad con ngrok) **rompen** el modo de demostración por túnel. Para la presentación, usa **solo datos ficticios**.
> **Cómo usarlo:** pégalo completo en la IA/programador, en la raíz del repositorio. Sin recortar.

=== INICIO DEL PROMPT ===

# 1. ROL Y REGLAS

Eres un ingeniero senior en un **sistema clínico**. Esta fase **corrige** y **endurece**; no añade funcionalidades de negocio.

* Cada tarea termina con **evidencia real** (salida pegada). Sin salida = no hecho.
* No inventes: lo no definido va a `docs/SUPUESTOS.md` con la opción más segura.
* No toques `db/init/001_schema.sql`, `db/init/002_seed_catalogo.sql` ni `backend/app/catalog/**`. Los cambios de BD van **solo** en una migración Alembic (§T4).
* Imita las convenciones del repo (`AppError`, `deps.py`, `Column`, tests `unittest` sobre PostgreSQL real, `clock.ahora()`).
* Un commit por tarea, en español, imperativo.

# 2. PUERTA DE ENTRADA

Pega la salida real de:
1. `git status` limpio y `git tag --list` (si falta, crea `fase-3-cerrada` sobre el estado actual).
2. Desde `backend/`: `python -m unittest discover -s tests -v` → `Ran 119 tests`, `OK`, sin `skipped` (línea base).
3. `git diff --stat fase-1-cerrada HEAD -- db/init backend/app/catalog` → vacío o limitado al cambio autorizado del motor.

# 3. DECISIONES (añádelas al final de `docs/DECISIONES.md` como §13; única edición permitida)

```markdown
## 13. Decisiones de Fase 3.5 (correcciones)

* **D35-01** No hay CORS: frontend y API comparten origen (Caddy en producción, proxy de Vite en desarrollo). No se sirve el frontend desde el backend. `/docs` y `/openapi.json` están desactivados salvo `ENABLE_DOCS=true`.
* **D35-02** El tiempo de sesión lo configura el ADMIN en `laboratorio_config`: intervalo de latido (10–120 s), sesión muerta sin latido (≥ 3× el intervalo y ≤ 1800 s), inactividad (5–480 min) y tope absoluto (1–24 h). Los valores por defecto siguen siendo 30 s / 150 s / 30 min / 12 h. El tope absoluto se aplica a sesiones nuevas.
* **D35-03** La inactividad se mide con **actividad real del usuario** (ratón, teclado, toque, desplazamiento) que el navegador comunica en el latido (`actividad: true`). Un latido sin actividad NO renueva la inactividad.
* **D35-04** Los tests solo corren contra bases cuyo nombre termina en `_test`.
* **D35-05** Los cambios de esquema de esta fase se hacen con la migración Alembic `0002`. El contenedor del backend ejecuta `alembic upgrade head` al arrancar.
```

# 4. TAREAS

## T1 — Endurecer la superficie de red (hallazgos A1, A2, A4)
1. `backend/app/main.py`: **elimina** `CORSMiddleware` y `ProxyHeadersMiddleware` (queda un único mecanismo: los flags de uvicorn del `Dockerfile`, válidos porque el backend **no** publica puertos y solo lo alcanza Caddy). Elimina el servidor de frontend estático y el catch-all `/{full_path:path}`.
2. `docs_url`, `redoc_url`, `openapi_url` = `None` salvo variable `ENABLE_DOCS=true` (añádela a `config.py` y a `.env.example`, valor `false`).
3. `frontend/src/api/client.ts`: elimina la cabecera `ngrok-skip-browser-warning`. `frontend/vite.config.ts`: quita `allowedHosts: true` y `host: true` (deja el proxy `/api`).
4. `.env.example`: restituye `ACCESS_TOKEN_MINUTES=10`, `MAX_LOGIN_ATTEMPTS=5`, `LOCKOUT_MINUTES=15`, `COOKIE_SECURE=true`, `ENABLE_DOCS=false`.
5. **Tests nuevos:** (a) una petición `OPTIONS` con `Origin: https://evil.example` a `/api/auth/login` **no** devuelve `access-control-allow-origin`; (b) `GET /docs` y `GET /openapi.json` → 404 por defecto; (c) `GET /` no devuelve el frontend ni información del sistema.
**Evidencia:** `grep -rniE "ngrok|CORSMiddleware|ProxyHeadersMiddleware|allow_origin" backend frontend/src frontend/vite.config.ts` → vacío; salida de los 3 tests.

## T2 — Guarda contra borrado accidental en los tests (hallazgo A3)
En `tests/base.py`: antes de cualquier operación, **aborta** (excepción con mensaje claro) si el nombre de la base de `TEST_DATABASE_URL` no termina en `_test`. Elimina la contraseña por defecto de la URL: si `TEST_DATABASE_URL` no está definida, falla indicando cómo definirla.
**Test nuevo (unitario, sin BD):** una URL terminada en `/lis` es rechazada; una terminada en `/lis_test` es aceptada (extrae la validación a una función pura).
**Evidencia:** salida de ese test y de la suite completa.

## T3 — Limpieza menor (hallazgos A7, A9)
1. `evaluacion_service.py` (~línea 447): reemplaza `except Exception` por `except ValueError`.
2. Mueve `PROMPT_*.md`, `PROMT_*.md`, `EVALUACION_*.md` y `EVIDENCIAS.md` a `docs/historial/`. Actualiza `README.md` (estado real: Fase 3.5, número real de tests, comandos reales) y la tabla de `docs/DECISIONES.md §9`.
**Evidencia:** `grep -rn "except Exception" backend/app` → vacío; `git status`.

## T4 — Migración Alembic 0002 y arranque (soporta D35-02 y D35-05)
1. `backend/alembic/versions/0002_config_sesion.py`:
   * Amplía el `CHECK` de `log_seguridad.accion` (constraint `log_seguridad_accion_check`; **verifica su nombre real** en la BD antes de borrarlo) añadiendo `CONFIG_SESION_EDITADA`.
   * Inserta en `laboratorio_config` (con `ON CONFLICT DO NOTHING`): `sesion_intervalo_latido_seg=30`, `sesion_muerta_tras_seg=150`, `sesion_inactividad_min=30`, `sesion_tope_absoluto_horas=12`.
   * `downgrade()` revierte ambos cambios.
2. `backend/Dockerfile`: copia `alembic/` y `alembic.ini`; el comando de arranque ejecuta `alembic upgrade head` y luego `uvicorn` (mismos flags de proxy).
3. `scripts/crear_bd_test.sh`: tras aplicar `001` y `002`, ejecuta `alembic upgrade head` contra `lis_test`.
4. La base de pruebas (`tests/base.py`) debe comprobar que existen las 4 claves `sesion_*`.
**Evidencia:** `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` (salida de los tres) y `\d+ laboratorio.log_seguridad` mostrando el `CHECK` nuevo.

## T5 — Configuración de sesión dinámica (hallazgo A5)
**Backend**
1. Servicio `obtener_config_sesion(db)`: lee las 4 claves de `laboratorio_config` con **caché en memoria de 15 s** (invalidada al guardar); si falta una clave o es inválida, usa el valor de `settings`.
2. `require_auth` y `refresh` usan esa configuración en lugar de `settings.*` para latido, inactividad y muerte por falta de latido. `login` usa `sesion_tope_absoluto_horas` al crear la sesión.
3. `POST /api/auth/heartbeat` acepta cuerpo opcional `{"actividad": true|false}` (ausente = `false`). Siempre actualiza `ultimo_latido`; actualiza `ultima_actividad` **solo si** `actividad = true`. Responde **200** con `{"intervalo_latido_seg": N, "segundos_restantes_inactividad": M}`.
4. Las respuestas de `login` y `refresh` añaden `config_sesion: {intervalo_latido_seg, inactividad_min}`.
5. `GET /api/admin/configuracion/sesion` y `PUT /api/admin/configuracion/sesion` (solo ADMIN). El `PUT` recibe los 4 valores, valida los rangos de D35-02 (error 400 `VALIDACION` con el campo y el rango), guarda, invalida la caché y registra `CONFIG_SESION_EDITADA` con `detalle` = `{campo: {antes, despues}}`.
**Frontend**
6. `AuthProvider.tsx`: el intervalo de latido sale de `config_sesion` (defecto 30 s). Registra actividad con `pointerdown`, `keydown`, `wheel` y `touchstart` (más `mousemove` con *throttle* de 5 s); cada latido envía `{actividad}` y reinicia el indicador. Al volver la pestaña a primer plano (`visibilitychange`), envía un latido inmediato.
7. Aviso previo: cuando `segundos_restantes_inactividad < 120`, banner superior "Tu sesión expirará por inactividad en N min" con botón **Seguir conectado** (envía un latido con `actividad: true`). Si expira, vuelve al login con mensaje claro.
8. Pantalla `/admin/configuracion` (solo ADMIN, enlace dentro de Administración): 4 campos con unidades, rango y ayuda breve; guarda con confirmación y muestra los valores vigentes. Sin `localStorage`/`sessionStorage`.
**Tests nuevos (PostgreSQL real, reloj simulado):**
1. Latido con `actividad=false` durante 40 min **no** evita la expiración por inactividad; con `actividad=true` sí.
2. Latido sin cuerpo se comporta como `actividad=false`.
3. Cambiar `sesion_muerta_tras_seg` y `sesion_inactividad_min` por la API cambia el comportamiento de sesiones **ya abiertas** (tras ≤ 15 s de caché; el test invalida la caché).
4. El tope absoluto nuevo se aplica a sesiones creadas después del cambio, no a las existentes.
5. Rangos: intervalo 9 y 121 → 400; muerta < 3× intervalo → 400; inactividad 4 y 481 → 400; tope 0 y 25 → 400.
6. BIOQUIMICO → 403 en ambos endpoints; sin token → 401.
7. El `PUT` registra `CONFIG_SESION_EDITADA` con antes/después; clave ausente en BD → usa `settings`.
8. `login`/`refresh` devuelven `config_sesion`; el heartbeat devuelve `segundos_restantes_inactividad` coherente.
9. Los tests de sesión previos (10–13 y 14 de Fase 1) se **actualizan** al nuevo contrato del latido y siguen cubriendo lo mismo.

## T6 — Que los agentes lean las reglas de diseño (hallazgo A6)
1. Copia `UX_GUIDE.md` (adjunto) a `docs/UX_GUIDE.md`.
2. `.cursorignore`: elimina las líneas `.agents/skills/` y `skills-lock.json` (ya no se usarán esas rutas).
3. **Elimina** la carpeta `.agents/skills/` y `skills-lock.json` (28 skills genéricos y contradictorios, con un archivo roto que contiene "404: Not Found").
4. Crea `.cursor/rules/ux.mdc` con `alwaysApply: true` y este contenido: *"Antes de tocar `frontend/`, lee `docs/UX_GUIDE.md` y cúmplela. Prohibido usar skills de diseño externos."*
5. Añade al final de `AGENTS.md`: sección **"Interfaz"** con la misma instrucción y el enlace a `docs/UX_GUIDE.md`.
**Evidencia:** `cat .cursorignore`, `ls .agents 2>&1`, `cat .cursor/rules/ux.mdc`, `tail -8 AGENTS.md`.

# 5. PROHIBIDO
Cambiar el esquema base o el catálogo; añadir dependencias; `HTTPException`; `datetime.now()` fuera de `clock.py`; `except Exception`; CORS de cualquier tipo; marcar algo como hecho sin evidencia.

# 6. CRITERIOS DE ACEPTACIÓN

- [ ] Suite completa → `OK`, `skipped=0`, con los tests nuevos (T1: 3, T2: 1, T5: 9) y los previos; salida completa pegada.
- [ ] Greps de T1 y T3 vacíos; `git diff --stat fase-1-cerrada HEAD -- db/init backend/app/catalog` sin cambios fuera del motor.
- [ ] Prueba manual: iniciar sesión, **no tocar nada** pero mover el ratón y escribir en un campo durante 3 ciclos de latido → la sesión sigue; dejar la ventana sin interacción más de `inactividad − 2 min` → aparece el aviso; no pulsar → vuelve al login.
- [ ] Prueba manual como ADMIN: cambiar la inactividad a 5 min en `/admin/configuracion` y comprobar que se aplica.
- [ ] `npm run build` limpio; `grep -rn "localStorage\|sessionStorage" frontend/src` vacío.
- [ ] Tag `fase-3-5-cerrada` **solo** si todo lo anterior está demostrado.

# 7. INFORME FINAL (formato fijo)

```
## Puerta de entrada
## Evidencia por tarea (T1…T6)
## No hecho / parcial
## Supuestos nuevos
## Desviaciones del prompt
## Salida completa de los tests
```

=== FIN DEL PROMPT ===
