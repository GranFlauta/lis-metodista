# PROMPT — FASE 1: Autenticación, sesión por latido y gestión de usuarios

**Cómo usarlo:** abre la carpeta `lis/` en Cursor / Claude Code / VS Code + IA y pega **todo lo que está debajo de la línea `=== INICIO DEL PROMPT ===`**. No lo resumas ni le quites secciones.

=== INICIO DEL PROMPT ===

# 1. ROL Y MODO DE TRABAJO

Eres un ingeniero senior de backend y frontend trabajando en un **sistema clínico** (LIS de laboratorio). Un error aquí puede afectar a pacientes, así que:

* Haces **solo** lo que este prompt pide. Nada más, nada menos.
* **No inventas** reglas de negocio, endpoints, columnas, librerías ni valores. Si algo no está en este prompt, en `docs/DECISIONES.md` o en `AGENTS.md`, lo tratas como **no decidido**.
* Ante un hueco: elige la opción **más segura y más simple**, regístrala en `docs/SUPUESTOS.md` (formato en §12) y sigue. Solo detente a preguntar si el hueco **bloquea** el avance o afecta a seguridad.
* Prefieres código aburrido y explícito a código ingenioso.
* Nunca digas "listo" sin haber **ejecutado** los tests y pegado su salida real.

# 2. CONTEXTO (5 líneas)

LIS on-premise: PostgreSQL 16 + FastAPI + React/Vite/TypeScript, Docker Compose, HTTPS interno con Caddy. El esquema de BD y el catálogo ya existen (Fase 0). Dos roles: `ADMIN` y `BIOQUIMICO`. Los usuarios **nunca se borran** (baja lógica). La sesión se mantiene con **latidos** porque el navegador no puede avisar de forma fiable cuando se cierra la pestaña o se apaga el PC.

# 3. LECTURA OBLIGATORIA (antes de escribir una línea)

Léelos **completos y en este orden**:

1. `AGENTS.md`
2. `docs/DECISIONES.md` (especialmente §1, §4 y **§6 Sesión y seguridad**, incluida la matriz de permisos)
3. `db/init/001_schema.sql` (tablas `roles`, `usuarios`, `sesiones`, `log_seguridad`)
4. `backend/app/core/config.py`, `backend/app/main.py`, `backend/requirements.txt`
5. `.env.example`, `docker-compose.yml`, `frontend/Caddyfile`

Tu **primera respuesta** debe ser *solo* esto (sin código todavía):
* Resumen en 10 líneas de lo que vas a construir.
* Lista de archivos que **crearás** y que **modificarás**.
* Lista de dependencias nuevas (solo las permitidas en §5).
* Dudas **bloqueantes** (si no hay, escribe "ninguna").
Espera mi "adelante" solo si declaras dudas bloqueantes; si no las hay, continúa.

# 4. ALCANCE

## 4.1 DENTRO de la Fase 1
**Backend**
1. Conexión a BD (SQLAlchemy 2.0 síncrono + psycopg 3) y modelos de: `roles`, `usuarios`, `sesiones`, `log_seguridad`.
2. Hash y verificación de contraseñas (Argon2id), política de claves, contraseña temporal.
3. Login, refresh, heartbeat, logout, `me`, cambio de contraseña.
4. Bloqueo por intentos fallidos.
5. Dependencias de autorización (`require_auth`, `require_role`) con la regla de "debe cambiar contraseña".
6. CRUD de usuarios solo para `ADMIN` (con baja lógica) y reset de contraseña.
7. Registro de eventos en `log_seguridad`.
8. Comando CLI para crear el **primer** administrador.
9. Configuración de Alembic con migración baseline **vacía** (ver §8).
10. Tests (ver §10).

**Frontend**
11. Cliente HTTP, manejo de sesión (token en memoria, refresh al cargar, latido), rutas protegidas.
12. Pantallas: Login, Cambio de contraseña obligatorio, Layout con menú por rol y botón salir, Administración de usuarios.
13. Idioma de la interfaz: **español**.

## 4.2 FUERA de la Fase 1 (NO lo hagas, aunque parezca fácil)
Pacientes, órdenes, catálogo en API, cálculo en API, folios, informes, PDF, delegación, concurrencia, notificaciones, reportes, subida de firma (`firma_imagen`), evento `ADMIN_VE_PRIVADO`, recuperación de contraseña por correo, doble factor, internacionalización, modo oscuro, librerías de componentes UI. Las secciones futuras del menú pueden existir **solo como enlaces deshabilitados** con el texto "Próximamente".

# 5. DECISIONES TÉCNICAS YA TOMADAS (no las cambies)

| Tema | Decisión |
|---|---|
| ORM | SQLAlchemy 2.0 estilo moderno (`Mapped[...]`, `mapped_column`), **síncrono**. Tablas con `schema="laboratorio"` |
| Driver | `psycopg` 3 (URL `postgresql+psycopg://`) |
| Hash | `argon2-cffi`, `PasswordHasher()` con parámetros por defecto; usar `check_needs_rehash` al login |
| JWT | `PyJWT`, HS256, secreto = `JWT_SECRET`. Claims: `sub` (id_usuario, string), `sid` (id_sesion), `rol`, `iat`, `exp`, `typ="access"` |
| Access token | 10 min (`ACCESS_TOKEN_MINUTES`). Se guarda **solo en memoria** del frontend (nunca `localStorage`/`sessionStorage`) |
| Refresh token | Cadena aleatoria opaca de 256 bits (`secrets.token_urlsafe(32)`). En BD solo su **SHA-256** (`sesiones.refresh_hash`). **Sin rotación** en v1 |
| Cookie refresh | `httpOnly`, `Secure` (según `COOKIE_SECURE`), `SameSite=Strict`, `Path=/api/auth`, sin `Max-Age` (cookie de sesión) |
| CSRF | `SameSite=Strict` + los endpoints `refresh` y `logout` exigen la cabecera `X-LIS-Client: web`; sin ella → 400 `VALIDACION` |
| Sesión viva | `revocada_en IS NULL` **y** `ahora < expira_en` **y** `ahora - ultimo_latido <= SESSION_DEAD_AFTER_SECONDS` **y** `ahora - ultima_actividad <= IDLE_TIMEOUT_MINUTES` |
| Latido | `POST /api/auth/heartbeat` cada `HEARTBEAT_INTERVAL_SECONDS` (30 s) desde el frontend. Actualiza **solo** `ultimo_latido` |
| Actividad | Cualquier otra petición autenticada actualiza `ultima_actividad` (el latido **no**) |
| Bloqueo | `MAX_LOGIN_ATTEMPTS` (5) fallos seguidos → `bloqueado_hasta = ahora + LOCKOUT_MINUTES` (15). Un login correcto pone `intentos_fallidos = 0` |
| Reloj | Todo el código usa `app/core/clock.py::ahora()` (UTC, `timezone.utc`) para poder simularlo en tests. **Prohibido** llamar a `datetime.now()` fuera de ese módulo |
| Contraseña | mín. 10 y máx. 128 caracteres; no estar en la lista de prohibidas (§6.4); no contener el `usuario` ni el `ci` (sin distinguir mayúsculas); distinta de la actual. **Sin** reglas de composición |
| Pass temporal | 14 caracteres con `secrets`, alfabeto sin caracteres ambiguos (`0 O 1 l I`) |
| Roles | Solo `ADMIN` y `BIOQUIMICO` (ya insertados por el esquema) |
| Errores | JSON `{"codigo": "...", "mensaje": "..."}`. Mensajes en español, sin detalles internos |
| Tests | `unittest` (como el resto del proyecto). **No** introducir pytest |
| Dependencias nuevas permitidas | Backend: ninguna salvo `httpx` en un nuevo `backend/requirements-dev.txt` (para `TestClient`). Frontend: solo `react-router-dom`. **Cualquier otra → pídela antes** |

# 6. CONTRATO DE LA API (exacto)

Prefijo `/api`. JSON UTF-8. Fechas ISO-8601 UTC.

## 6.1 Códigos de error

| HTTP | `codigo` | Cuándo |
|---|---|---|
| 400 | `VALIDACION` | Datos mal formados o cabecera `X-LIS-Client` ausente |
| 401 | `CREDENCIALES_INVALIDAS` | Usuario inexistente, clave incorrecta **o usuario inactivo** (mismo mensaje en los tres casos: "Usuario o contraseña incorrectos") |
| 401 | `SESION_EXPIRADA` | Token inválido/expirado o sesión no viva |
| 403 | `DEBE_CAMBIAR_PASSWORD` | El usuario tiene `debe_cambiar_password = TRUE` y llama a cualquier endpoint **salvo** `me`, `cambiar-password`, `logout`, `heartbeat` |
| 403 | `PROHIBIDO` | Rol insuficiente o regla de negocio (p. ej. desactivarse a sí mismo) |
| 404 | `NO_ENCONTRADO` | Recurso inexistente |
| 409 | `CONFLICTO` | `usuario`, `ci` o `correo` duplicado |
| 422 | `PASSWORD_DEBIL` | La clave incumple la política (el `mensaje` dice qué regla) |
| 423 | `CUENTA_BLOQUEADA` | Usuario existente y bloqueado; incluir `minutos_restantes` (entero, redondeo hacia arriba) |

Todo error de validación de FastAPI/Pydantic (422 por defecto) debe **convertirse** al formato `{"codigo":"VALIDACION", "mensaje": ...}` con HTTP 400, **excepto** `PASSWORD_DEBIL`.

## 6.2 Endpoints de autenticación

| Método y ruta | Auth | Cuerpo | Respuesta |
|---|---|---|---|
| `POST /api/auth/login` | no | `{usuario, password}` | 200 `{access_token, token_type:"bearer", expires_in, debe_cambiar_password, usuario:{id, usuario, nombres, apellido_paterno, apellido_materno, rol}}` + cookie refresh |
| `POST /api/auth/refresh` | cookie | — (+ cabecera `X-LIS-Client`) | 200 mismo formato que login (nuevo access; la cookie **no cambia**). Si la sesión no está viva → 401 `SESION_EXPIRADA` y se borra la cookie |
| `POST /api/auth/heartbeat` | Bearer | — | 204 |
| `POST /api/auth/logout` | cookie | — (+ cabecera) | 204; revoca la sesión y borra la cookie. Idempotente (sin sesión → 204) |
| `GET /api/auth/me` | Bearer | — | 200 `{id, usuario, nombres, apellido_paterno, apellido_materno, rol, debe_cambiar_password}` |
| `POST /api/auth/cambiar-password` | Bearer | `{password_actual, password_nueva}` | 204; pone `debe_cambiar_password = FALSE`; **revoca las demás sesiones** del usuario y mantiene la actual |

**Login, algoritmo exacto**
1. Normalizar `usuario` a minúsculas y sin espacios en los extremos.
2. Buscar usuario. Si **no existe**: ejecutar igualmente una verificación Argon2 contra un hash ficticio (para igualar tiempos) y responder 401 `CREDENCIALES_INVALIDAS`.
3. Si existe y `bloqueado_hasta > ahora` → 423 `CUENTA_BLOQUEADA` (sin verificar la clave).
4. Si `activo = FALSE` → 401 `CREDENCIALES_INVALIDAS`.
5. Verificar clave. Si falla: `intentos_fallidos += 1`; si llega a `MAX_LOGIN_ATTEMPTS` → `bloqueado_hasta = ahora + LOCKOUT_MINUTES` y `intentos_fallidos = 0`; evento `LOGIN_FALLIDO`; 401.
6. Si es correcta: `intentos_fallidos = 0`, `bloqueado_hasta = NULL`, `ultimo_login = ahora`, rehash si corresponde, crear fila en `sesiones` (`expira_en = ahora + ABSOLUTE_SESSION_HOURS`), evento `LOGIN_OK`, emitir tokens.

**Dependencia `require_auth` (se aplica a todo endpoint protegido)**
1. Decodificar el Bearer; error → 401 `SESION_EXPIRADA`.
2. Cargar la sesión por `sid`; si no está viva (regla de §5): si no estaba ya revocada, ponerle `revocada_en = ahora` y registrar `SESION_EXPIRADA`; responder 401 `SESION_EXPIRADA`.
3. Cargar el usuario; si `activo = FALSE` → 401 `SESION_EXPIRADA`.
4. Si la ruta **no** es el heartbeat: `ultima_actividad = ahora`.
5. Si `debe_cambiar_password` y la ruta no está en la lista blanca de §6.1 → 403 `DEBE_CAMBIAR_PASSWORD`.

## 6.3 Endpoints de usuarios (solo `ADMIN`)

| Método y ruta | Cuerpo | Respuesta / reglas |
|---|---|---|
| `GET /api/usuarios?activo=&rol=&q=` | — | 200 lista (sin `hash_password`, sin `firma_imagen`). `q` busca en usuario, nombres, apellidos y CI (insensible a mayúsculas) |
| `POST /api/usuarios` | `{usuario, ci, nombres, apellido_paterno, apellido_materno?, correo?, matricula_profesional?, rol}` | 201 con el usuario **y** `password_temporal` (**única vez** que se muestra). Crea con `debe_cambiar_password = TRUE`. Evento `USUARIO_CREADO` |
| `GET /api/usuarios/{id}` | — | 200 / 404 |
| `PATCH /api/usuarios/{id}` | cualquier subconjunto de `{nombres, apellido_paterno, apellido_materno, correo, matricula_profesional, rol, ci}` | 200. Evento `USUARIO_EDITADO` con `detalle` = campos cambiados (**sin** valores sensibles). **No** se puede cambiar `usuario` (login) |
| `POST /api/usuarios/{id}/desactivar` | — | 204. Pone `activo = FALSE` y **revoca todas sus sesiones**. Evento `USUARIO_DESACTIVADO` |
| `POST /api/usuarios/{id}/reactivar` | — | 204. Pone `activo = TRUE`, `intentos_fallidos = 0`, `bloqueado_hasta = NULL`. Evento `USUARIO_EDITADO` con `detalle={"activo": true}` |
| `POST /api/usuarios/{id}/reset-password` | — | 200 `{password_temporal}` (única vez). `debe_cambiar_password = TRUE`, revoca sus sesiones, limpia bloqueo. Evento `RESET_PASSWORD_ADMIN` |

Reglas de negocio:
* Un admin **no puede** desactivarse a sí mismo ni cambiarse su propio rol → 403 `PROHIBIDO`.
* **Nunca** debe quedar el sistema sin al menos un `ADMIN` activo → 403 `PROHIBIDO`.
* **No existe `DELETE` de usuarios.** Si lo implementas, la fase se rechaza.
* `usuario`: regex `^[a-z0-9._-]{3,40}$` (se guarda en minúsculas). `ci`: 5–30 caracteres sin espacios en los extremos. `correo`: opcional, validación simple (`texto@dominio.tld`), sin dependencias extra.
* `password_temporal` **jamás** se guarda en claro, se loguea ni vuelve a aparecer en ninguna otra respuesta.

## 6.4 Claves prohibidas (lista cerrada, comparar en minúsculas)
`12345`, `123456`, `1234567`, `12345678`, `123456789`, `1234567890`, `0123456789`, `password`, `contraseña`, `contrasena`, `qwerty`, `qwertyuiop`, `abcdef`, `abcd1234`, `admin`, `admin123`, `administrador`, `lis123`, `laboratorio`, `urgenlab`, `bioquimico`.
(Aplica también si la clave **contiene** alguna de las de ≥ 8 caracteres.)

## 6.5 Eventos en `log_seguridad`
Solo estos valores de `accion` (el esquema los exige con `CHECK`): `LOGIN_OK`, `LOGIN_FALLIDO`, `LOGOUT`, `SESION_EXPIRADA`, `CAMBIO_PASSWORD`, `RESET_PASSWORD_ADMIN`, `USUARIO_CREADO`, `USUARIO_EDITADO`, `USUARIO_DESACTIVADO`.
Guardar `ip` (`request.client.host`) y, en `LOGIN_FALLIDO` sobre un usuario inexistente, `detalle={"usuario_intentado": "<texto>"}` (**nunca** la contraseña). Para `id_usuario`/`id_objetivo`: `id_usuario` = quien actúa (NULL si es un login fallido de un usuario inexistente), `id_objetivo` = sobre quién.

# 7. ESTRUCTURA DE ARCHIVOS ESPERADA

```
backend/
  alembic.ini
  alembic/env.py
  alembic/versions/0001_baseline.py        # vacía a propósito (ver §8)
  requirements-dev.txt                     # httpx
  app/
    core/clock.py  core/db.py  core/security.py  core/errors.py  core/config.py (ya existe: solo validar)
    models/{rol,usuario,sesion,log_seguridad}.py
    schemas/{auth,usuario}.py
    services/{auth_service,usuario_service,log_service}.py
    api/{deps,auth,usuarios}.py
    cli.py                                  # python -m app.cli crear-admin
    main.py                                 # registrar routers y manejadores de error
  tests/
    base.py                                 # utilidades de BD de prueba y reloj simulado
    test_password.py  test_login.py  test_sesion.py  test_usuarios.py
frontend/src/
  api/client.ts  api/auth.ts  api/usuarios.ts
  features/auth/{AuthProvider.tsx,LoginPage.tsx,CambiarPasswordPage.tsx,RutaProtegida.tsx}
  features/admin/UsuariosPage.tsx
  components/Layout.tsx
  App.tsx  main.tsx
docs/SUPUESTOS.md
```
No crees archivos fuera de esta lista salvo que lo justifiques en `SUPUESTOS.md`.

# 8. CAMBIOS PERMITIDOS EN LO YA EXISTENTE

* `db/init/001_schema.sql`, `002_seed_catalogo.sql` y `backend/app/catalog/**`: **NO se tocan.** (La columna `sesiones.ultima_actividad` ya fue añadida; verifícalo con `grep`.)
* `backend/app/core/config.py`: solo añadir validación de arranque: si `JWT_SECRET` tiene < 32 caracteres o empieza por `CAMBIAR`, la app **no arranca** (excepción clara).
* `backend/app/main.py`: registrar routers, manejadores de error y `/api/health` (se conserva).
* `backend/Dockerfile`: añadir `--proxy-headers --forwarded-allow-ips='*'` al comando de uvicorn (el backend solo es accesible desde la red interna de Compose).
* `docs/DECISIONES.md`: **no editar**. Si algo contradice, repórtalo en el informe final.
* Alembic: crear la configuración y **una** revisión `0001_baseline` con `upgrade()`/`downgrade()` vacíos y un comentario: *"El esquema base lo crea db/init/*.sql. Desde el primer despliegue con datos reales, db/init/001 queda CONGELADO y todo cambio va en migraciones."* No ejecutar `alembic upgrade` en el arranque del contenedor.

# 9. FRONTEND — REQUISITOS FUNCIONALES

* **Token en memoria** (variable del `AuthProvider`/módulo), nunca en storage.
* Al cargar la app: intentar `POST /api/auth/refresh`. Si responde 200 → sesión restaurada (así el **F5 no cierra sesión**). Si 401 → pantalla de login.
* **Latido**: mientras haya sesión, `POST /api/auth/heartbeat` cada 30 s. Si recibe 401 `SESION_EXPIRADA` → limpiar estado y volver al login con el mensaje "Tu sesión expiró por inactividad o cierre de la aplicación".
* Cliente HTTP: añade `Authorization: Bearer`; ante 401 `SESION_EXPIRADA` en una petición normal intenta **un** refresh y reintenta **una** vez; si falla, cierra sesión. Ante 403 `DEBE_CAMBIAR_PASSWORD` redirige a `/cambiar-password`.
* **Prohibido** `beforeunload`/`pagehide` para hacer logout (rompería el F5 y no es fiable). El cierre de pestaña lo resuelve el servidor por falta de latidos.
* Rutas: `/login`, `/cambiar-password`, `/` (inicio vacío con saludo), `/admin/usuarios` (solo `ADMIN`; si no, redirigir a `/`). Un `BIOQUIMICO` no ve el menú "Administración".
* **Administración de usuarios**: tabla (usuario, nombre completo, CI, rol, estado), filtro por texto/estado/rol, formulario crear/editar, botones desactivar/reactivar y reset de contraseña con confirmación. Al crear o resetear, mostrar un **diálogo modal** con la contraseña temporal, botón "Copiar" y el aviso "Se muestra una sola vez". Al cerrarlo, el valor se **elimina** del estado.
* Formularios con mensajes de error en español tomados del campo `mensaje` de la API.
* Estilos: CSS simple propio. **Sin** librerías de componentes. Contraste y foco visibles; los estados (activo/inactivo) no deben depender solo del color: incluir texto.

# 10. TESTS OBLIGATORIOS (`unittest`)

Los tests de integración usan una BD PostgreSQL de prueba (`TEST_DATABASE_URL`, p. ej. `lis_test`) creada aplicando `db/init/001_schema.sql` (sin el seed del catálogo) y reiniciada entre clases de test. Documenta en el README cómo levantarla con `docker compose up -d db`. Usa el reloj simulado de `clock.py`; **no** uses `time.sleep`.

**Contraseñas (unitarios, sin BD)**
1. Hash y verificación correctos; dos hashes de la misma clave difieren.
2. Rechaza: < 10 caracteres, > 128, en la lista prohibida, que contenga el usuario, que contenga el CI, igual a la actual.
3. Acepta una clave larga y no prohibida.
4. La temporal tiene 14 caracteres y ninguno de `0 O 1 l I`.

**Login y bloqueo**
5. Login correcto devuelve token, cookie `httpOnly`+`SameSite=Strict`+`Path=/api/auth` y crea sesión.
6. Usuario inexistente, clave incorrecta y usuario inactivo → **mismo** 401 y mismo mensaje.
7. 5 fallos seguidos → el 6.º intento (aunque la clave sea correcta) da 423 con `minutos_restantes`; pasado `LOCKOUT_MINUTES` (reloj simulado) vuelve a funcionar.
8. Login correcto reinicia `intentos_fallidos`.
9. Se registran `LOGIN_OK` y `LOGIN_FALLIDO` con IP; la contraseña no aparece en ningún registro.

**Sesión**
10. Sesión muere con `SESSION_DEAD_AFTER_SECONDS` sin latido (401 `SESION_EXPIRADA`) y queda revocada con evento `SESION_EXPIRADA`.
11. Con latidos pero sin actividad durante `IDLE_TIMEOUT_MINUTES` → muere (el latido **no** cuenta como actividad).
12. Una petición normal renueva `ultima_actividad`; el latido **no**.
13. Muere al superar `ABSOLUTE_SESSION_HOURS` aunque haya latidos y actividad.
14. `refresh` sin cabecera `X-LIS-Client` → 400; con sesión muerta → 401 y limpia la cookie; con sesión viva → 200 y la cookie no cambia.
15. `logout` revoca la sesión; usar el access token después → 401; logout repetido → 204.
16. Con `debe_cambiar_password = TRUE`, cualquier endpoint fuera de la lista blanca → 403 `DEBE_CAMBIAR_PASSWORD`.
17. `cambiar-password` correcto: baja el flag, revoca **otras** sesiones, conserva la actual, registra `CAMBIO_PASSWORD`; con clave actual incorrecta → rechazado.
18. Un token cuyo usuario fue desactivado deja de funcionar de inmediato.

**Usuarios**
19. Un `BIOQUIMICO` recibe 403 `PROHIBIDO` en **todos** los endpoints `/api/usuarios`; sin token → 401.
20. Crear usuario: devuelve `password_temporal` una vez; en BD solo hay hash Argon2id; `GET` posterior no la devuelve; `debe_cambiar_password = TRUE`.
21. Duplicados de `usuario`, `ci`, `correo` → 409 `CONFLICTO`.
22. Desactivar revoca sus sesiones; reactivar limpia bloqueo.
23. Un admin no puede desactivarse ni cambiarse el rol; no se puede dejar el sistema sin admin activo.
24. No existe ruta `DELETE /api/usuarios/{id}` (responde 405/404).
25. Reset de contraseña: nueva temporal, flag activo, sesiones revocadas, evento registrado.
26. Ninguna respuesta de la API contiene `hash_password` ni `refresh_hash`.

**Arranque**
27. La app no arranca con `JWT_SECRET` corto o que empiece por `CAMBIAR`.

Además deben **seguir pasando** los 25 tests existentes (`cd backend && python -m unittest discover -s tests -v`).

# 11. PROTOCOLO ANTI-ALUCINACIÓN

1. **Verifica antes de afirmar.** Antes de usar una API de una librería (SQLAlchemy, FastAPI, argon2-cffi, PyJWT, psycopg, react-router) comprueba en el entorno instalado que existe: `python -c "import ..."`, `pip show`, `npm ls`. Si no puedes verificarlo, dilo.
2. **Prohibido inventar** nombres de columnas: el único origen es `db/init/001_schema.sql`. Si necesitas una columna que no existe, **detente y repórtalo** (no la agregues).
3. Si el tipo `CITEXT` no existe en tu versión de SQLAlchemy (`from sqlalchemy.dialects.postgresql import CITEXT`), usa `String` y normaliza a minúsculas en código; anótalo en `SUPUESTOS.md`.
4. **Sin código de relleno**: nada de `pass`, `TODO`, `NotImplementedError` ni funciones vacías dentro del alcance. Lo que no se hace va a "No hecho" en el informe.
5. **Sin mocks de la BD** en tests de integración: se prueba contra PostgreSQL real.
6. **Prohibido** `eval`, `exec`, `pickle`, SQL concatenado con texto del usuario, `print` de datos sensibles, `except Exception: pass`, desactivar verificación TLS, `CORS *`.
7. No hay CORS: front y API comparten origen (Caddy / proxy de Vite). No lo añadas.
8. No renombres ni reformatees archivos que no tocas. Diffs mínimos.
9. Si un test falla, **corrige el código**, no el test (salvo que el test contradiga este prompt: entonces repórtalo).
10. Cada decisión que no esté en este prompt → una línea en `docs/SUPUESTOS.md`.

# 12. FORMATO DE `docs/SUPUESTOS.md`

```
| # | Tema | Qué no estaba definido | Qué decidí (la opción más segura/simple) | Impacto si está mal |
```

# 13. ORDEN DE TRABAJO (un commit por paso, mensaje en español, imperativo)

1. Plan y verificación de librerías (solo respuesta, sin código).
2. `clock.py`, `config` (validación de arranque), `db.py`, modelos. → commit.
3. `security.py` (hash, política, temporal, tokens) + `test_password.py`. → commit.
4. Servicios de auth + endpoints `login/refresh/heartbeat/logout/me/cambiar-password` + `deps.py` + manejador de errores + tests 5–18, 27. → commit.
5. Usuarios (servicio + endpoints) + `cli.py crear-admin` + tests 19–26. → commit.
6. Alembic baseline + `Dockerfile` + README (cómo correr tests de integración). → commit.
7. Frontend: cliente, `AuthProvider`, login, cambio de clave, rutas protegidas. → commit.
8. Frontend: administración de usuarios. → commit.
9. Verificación end-to-end manual (§14) y informe final.

`python -m app.cli crear-admin`: pide por consola `usuario`, `ci`, nombres y apellidos; **genera** una contraseña temporal, la imprime **una sola vez**, crea el usuario con rol `ADMIN` y `debe_cambiar_password = TRUE`. Se niega a ejecutarse si ya existe un `ADMIN` activo (a menos que se pase `--forzar`). No lee contraseñas por argumento de línea de comandos.

# 14. CRITERIOS DE ACEPTACIÓN (definición de "terminado")

Marca cada punto **solo** si lo ejecutaste:

- [ ] `cd backend && python -m unittest discover -s tests -v` → todos OK (25 previos + los nuevos). Pega la salida.
- [ ] `docker compose up -d --build` levanta `db`, `backend`, `web` sin errores; `curl -k https://localhost/api/health` → `{"status":"ok"}`.
- [ ] `docker compose exec backend python -m app.cli crear-admin` crea el primer admin.
- [ ] Flujo manual: login con la temporal → se fuerza el cambio de clave → entra → crea un usuario `BIOQUIMICO` → este inicia sesión y **no** ve "Administración".
- [ ] **F5 no cierra sesión.**
- [ ] Cerrar la pestaña (o detener el latido) y esperar `SESSION_DEAD_AFTER_SECONDS` → al volver, pide login.
- [ ] `grep -rn "localStorage\|sessionStorage" frontend/src` → sin resultados.
- [ ] `grep -rniE "eval\(|exec\(|pickle" backend/app` → sin resultados.
- [ ] `grep -rn "datetime.now\|datetime.utcnow" backend/app` → solo en `core/clock.py`.
- [ ] `git status` limpio; `.env` no está versionado.
- [ ] Ningún archivo de catálogo ni `db/init/*.sql` fue modificado (`git diff --stat`).

# 15. INFORME FINAL (formato obligatorio)

```
## Hecho
(lista, referenciando el nº de test o criterio que lo prueba)
## No hecho / parcial
(con motivo)
## Supuestos
(copia de docs/SUPUESTOS.md)
## Desviaciones del prompt
(si no hubo: "ninguna")
## Contradicciones o huecos detectados en la documentación
(si no hubo: "ninguno")
## Salida de los tests
(pegar tal cual)
## Cómo probarlo
(comandos exactos)
```

=== FIN DEL PROMPT ===
