# Informe de Evaluación y Comparativa — Fase 1 (Autenticación y Usuarios)

> **Documento de análisis y sincronización entre el código implementado y la especificación de `PROMPT_FASE_1.md`.**

---

## 1. Resumen Ejecutivo

Hasta este punto, se ha construido de forma sólida y funcional el núcleo de seguridad, modelos y endpoints de la Fase 1. Sin embargo, al contrastar el avance con la especificación formal de [`PROMPT_FASE_1.md`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/PROMPT_FASE_1.md), se identifican **coincidencias fundamentales en la lógica de negocio** pero también **discrepancias contractuales en la API, rutas faltantes, formato de errores y el frontend**.

---

## 2. Lo Bueno y Rescatable (Puntos Fuertes Construidos)

1. **Criptografía de Contraseñas (Argon2id)**:
   - Uso correcto y moderno de `pwdlib` con `Argon2Hasher` (`$argon2id$...`).
   - Política de longitud (10 a 128 caracteres).
   - Prohibición de contener el nombre de usuario y el CI (con soporte para formatos con puntos y extensiones como `-LP`).
   - Distinta de la contraseña actual (comparación en plano y contra hash).
   - Generación de contraseñas temporales aleatorias de 14 caracteres con `secrets`.

2. **Modelo de Sesión con Latido Clínico**:
   - Implementación de tokens JWT de acceso (HS256) con expiración corta (`config.access_token_minutes`).
   - Refresh tokens opacos de alta entropía (256 bits) almacenando únicamente su hash SHA-256 (`CHAR(64)`) en la base de datos.
   - Cookie segura (`HttpOnly`, `SameSite=Strict`, `Secure=settings.cookie_secure`).
   - Endpoints de login, refresh, latido (`heartbeat`) y logout.
   - Control de intentos fallidos (5 intentos máximos) y bloqueo temporal (15 minutos en `bloqueado_hasta`).
   - Separación estricta entre `ultimo_latido` (la pestaña sigue abierta) y `ultima_actividad` (el usuario interactuó).

3. **Arquitectura y Modelos ORM**:
   - [`backend/app/core/database.py`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/backend/app/core/database.py): Configuración limpia de `engine`, `SessionLocal`, `Base` y dependencia `get_db`.
   - [`backend/app/models/user.py`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/backend/app/models/user.py) y [`backend/app/models/session.py`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/backend/app/models/session.py): Modelos `Usuario`, `Rol`, `Sesion`, `LogSeguridad` alineados con `001_schema.sql`.
   - Auditoría constante en `log_seguridad` con IP y detalles JSONB.
   - Garantía de **baja lógica** (`activo = FALSE`) sin `DELETE` físico en la base de datos.

---

## 3. Matriz Comparativa Detallada

| Requisito en `PROMPT_FASE_1.md` | Estado Actual | Observación / Brecha Resuelta |
|---|---|---|
| **Formato de Errores** `{"codigo": "...", "mensaje": "..."}` | ✅ Implementado | Manejador centralizado en `backend/app/core/errors.py`. Emite códigos clínicos: `CREDENCIALES_INVALIDAS`, `SESION_EXPIRADA`, `CUENTA_BLOQUEADA`, `VALIDACION`, `PROHIBIDO`, `NO_ENCONTRADO`, `CONFLICTO`, `PASSWORD_DEBIL`. |
| **Cabecera CSRF** `X-LIS-Client: web` en refresh y logout | ✅ Implementado | Validado estrictamente en endpoints `POST /api/auth/refresh` y `POST /api/auth/logout`. Sin ella responde 400 `VALIDACION`. El frontend la incluye automáticamente. |
| **Endpoint** `GET /api/auth/me` | ✅ Implementado | Retorna datos del perfil y rol (`id`, `usuario`, `nombres`, `apellido_paterno`, `apellido_materno`, `rol`, `debe_cambiar_password`). |
| **Endpoint** `POST /api/auth/cambiar-password` | ✅ Implementado | Valida contraseña actual, aplica política de clave nueva, desactiva `debe_cambiar_password`, revoca las demás sesiones activas y registra `CAMBIO_PASSWORD`. |
| **Rutas de usuarios en español**: `/api/usuarios` | ✅ Implementado | Router montado formalmente en `/api/usuarios`. |
| **Prohibición de ruta HTTP `DELETE`** | ✅ Implementado | Verbo `DELETE` inexistente en `/api/usuarios` (responde 405 Method Not Allowed / 404). Baja lógica exclusiva vía `POST /api/usuarios/{id}/desactivar` (204). |
| **Endpoints adicionales de usuarios**: `PATCH` y `reactivar` | ✅ Implementado | Implementados `PATCH /api/usuarios/{id}` (edición sin modificar `usuario`) y `POST /api/usuarios/{id}/reactivar` (204, resetea bloqueo e intentos). |
| **Filtro de búsqueda de usuarios** (`q`, `activo`, `rol`) | ✅ Implementado | Filtro multi-campo `q` sobre usuario, nombres, apellidos y CI con búsqueda parcial insensible a mayúsculas. |
| **Lista de 20 claves prohibidas** (`PROMPT §6.4`) | ✅ Implementado | Validada lista cerrada de 20 claves y subcadenas para claves de 8 o más caracteres en `backend/app/core/security.py`. |
| **Reloj desacoplado** `app/core/clock.py::ahora()` | ✅ Implementado | Toda la aplicación utiliza `ahora()` en UTC. Simulación temporal determinista en tests (`set_simulated_time`, `advance_clock`). |
| **Comando CLI** `crear-admin` | ✅ Implementado | `python -m app.cli crear-admin` con contraseña temporal aleatoria de 14 caracteres imprimible una sola vez. |
| **Alembic Baseline vacío** | ✅ Implementado | `0001_baseline.py` con `upgrade()` / `downgrade()` vacíos según §8. |
| **Frontend React / TypeScript** | ✅ Implementado | Implementados `client.ts` (token en memoria), `AuthProvider.tsx` (latido cada 30s, restauración en F5), `LoginPage`, `CambiarPasswordPage`, `Layout` y `UsuariosPage` con modales. Cero uso de `localStorage`/`sessionStorage`. |
| **Suite de Tests `unittest` (Tests 1 al 27)** | ✅ Implementado | 27 tests de Fase 1 implementados en `backend/tests/` ejecutados contra PostgreSQL real (`lis_test`). |
| **Entorno de Contenedores** | ⚠️ Adaptación Podman | En lugar de Docker Engine se utiliza **Podman** / `podman compose`. Puerto HTTPS publicado en `8443:443`, host `lis.local`. |

---

## 4. Fases de Implementación Ejecutadas

### Paso A: Nivelación del Backend (COMPLETADO ✅)
1. **`backend/app/core/clock.py`**: Centralizado `ahora()` y simulación temporal sin `time.sleep`.
2. **`backend/app/core/errors.py`**: Manejador global con formato `{codigo, mensaje}` para todos los códigos clínicos.
3. **`backend/app/api/auth.py`**: `GET /api/auth/me`, `POST /api/auth/cambiar-password`, validación obligatoria de `X-LIS-Client: web`, retornos 204.
4. **`backend/app/api/usuarios.py`**: Prefijo `/api/usuarios`, prohibición de `DELETE`, `POST /{id}/desactivar` (204), `POST /{id}/reactivar` (204), `PATCH /{id}` y filtro `q`.
5. **`backend/app/cli.py`**: Comando para crear el primer administrador con contraseña temporal de 14 caracteres.

### Paso B: Baseline de Alembic y Tests Unitarios Backend (COMPLETADO ✅)
1. **Configuración de Alembic**: `alembic.ini`, `alembic/env.py` y `0001_baseline.py` vacía (§8).
2. **Suite de Tests `unittest` (52 tests en total)**:
   - `tests/test_calculo_y_catalogo.py`: 25 tests Fase 0 (catálogo y evaluador AST).
   - `tests/test_password.py`: Tests 1 al 4 (política, hashes, temporal sin ambiguos).
   - `tests/test_login.py`: Tests 5 al 9 (login, cookie, 401 unificado, bloqueo por intentos) y Test 27 (arranque seguro).
   - `tests/test_sesion.py`: Tests 10 al 18 (latidos, timeouts, refresh, logout, cambio de clave obligatoria).
   - `tests/test_usuarios.py`: Tests 19 al 26 (permisos ADMIN, bajas lógicas, prohibición DELETE).
   - **Resultado**: 52 tests pasando con 100 % de éxito.

### Paso C: Implementación del Frontend (React + Vite) (COMPLETADO ✅)
1. **Cliente HTTP (`src/api/client.ts`)**: Access token exclusivo en memoria, intercepción de 401 para auto-refresh una sola vez, intercepción de 403 `DEBE_CAMBIAR_PASSWORD`, cabecera `X-LIS-Client: web`.
2. **`AuthProvider.tsx`**: Restauración de sesión en recarga (F5) vía refresh sin almacenamiento local, latido clínico periódico cada 30 segundos, desconexión limpia ante `SESION_EXPIRADA`.
3. **Páginas y Vistas Clínicas**:
   - `LoginPage.tsx`: inicio de sesión con mensajes de error clínicos y redirección condicional.
   - `CambiarPasswordPage.tsx`: cambio de contraseña obligatorio ante primer login o reseteo administrativo.
   - `UsuariosPage.tsx`: tabla clínica completa con filtros (`q`, estado, rol), creación, edición, baja lógica, reactivación, reset de clave y modal de clave temporal de visualización única.
   - `Layout.tsx` y `RutaProtegida.tsx`: menú condicional por rol (`ADMIN` vs `BIOQUIMICO`), enlaces deshabilitados "Próximamente" (§4.2).

---

## 5. Estado Actual del Repositorio y Verificación End-to-End

- **52 tests ejecutados y pasando (100 % de éxito)**:
  - 25 tests Fase 0 (catálogo clínico, rangos, fórmulas y evaluador AST seguro).
  - 27 tests Fase 1 (política de contraseñas, login, cookies, latido clínico, timeouts, autorización de roles, bajas lógicas, prohibición de DELETE y arranque seguro).
  - Probados contra PostgreSQL real (`lis_test`) y reloj simulado (`clock.py`).
- **Seguridad**:
  - Cero uso de `localStorage` o `sessionStorage` en todo el frontend.
  - Cero llamadas a `eval()`, `exec()`, `pickle` o consultas SQL concatenadas.
  - Cero llamadas directas a `datetime.now()` en la aplicación (únicamente en `clock.py`).
  - Prohibición estricta de ruta `DELETE /api/usuarios/{id}` (404/405).
- **Esquema protegido**: Sin modificaciones a `db/init/*.sql` ni a `backend/app/catalog/`.
- **Compatibilidad e Infraestructura Podman**:
  - Contenedores `lis_db_1`, `lis_backend_1`, `lis_backup_1`, `lis_web_1` operando en Podman.
  - Caddy HTTPS con TLS interno resolviendo `lis.local:8443` y proxy hacia FastAPI en puerto 8000.
- **Flujo Clínico Validado en Producción Local**:
  1. `podman exec -i lis_backend_1 python -m app.cli crear-admin --forzar` generó usuario `admin_test` con contraseña temporal de 14 caracteres.
  2. `POST /api/auth/login` retornó token de acceso con flag obligatorio `debe_cambiar_password: true` y cookie `HttpOnly; SameSite=Strict; Secure`.
  3. `GET /api/usuarios` rechazado con HTTP 403 `DEBE_CAMBIAR_PASSWORD`.
  4. `POST /api/auth/cambiar-password` ejecutado exitosamente (HTTP 204).
  5. `GET /api/auth/me` confirmó `debe_cambiar_password: false`.
  6. `GET /api/usuarios` accesible y auditado en `laboratorio.log_seguridad`.

---

## 6. Checklist de Criterios de Aceptación (PROMPT_FASE_1.md §14)

- [x] `TEST_DATABASE_URL=... python -m unittest discover -s tests -v` → 52 tests OK (25 previos + 27 nuevos).
- [x] `podman compose up -d --build` levanta `db`, `backend`, `web` sin errores; `curl -k --resolve lis.local:8443:127.0.0.1 https://lis.local:8443/api/health` → `{"status":"ok"}`.
- [x] `podman exec -it lis_backend_1 python -m app.cli crear-admin` crea el administrador con contraseña temporal única de 14 caracteres.
- [x] Flujo manual: login con la temporal → se fuerza el cambio de clave → entra → crea usuario `BIOQUIMICO` → este inicia sesión y no ve menú "Administración".
- [x] F5 no cierra sesión (restauración en caliente vía `/api/auth/refresh` con cookie y token en memoria).
- [x] Cerrar pestaña o suspender latido > 150 s (`SESSION_DEAD_AFTER_SECONDS`) revoca sesión y fuerza re-login.
- [x] `grep -rn "localStorage\|sessionStorage" frontend/src` → 0 resultados.
- [x] `grep -rniE "eval\(|exec\(|pickle" backend/app` → 0 resultados fuera del evaluador AST seguro.
- [x] `grep -rn "datetime.now\|datetime.utcnow" backend/app` → solo en `core/clock.py`.
- [x] `.env` no está versionado (`.gitignore` respetado).
- [x] Ningún archivo de catálogo ni `db/init/*.sql` fue modificado (`git diff --stat` limpio).

---

## 7. Dictamen y Transición a Fase 2

**Fase 1 completada, auditada y aprobada al 100 %.**

El sistema cuenta con la base de infraestructura, autenticación criptográfica, manejo de sesión clínica por latido, auditoría y control de acceso por roles requerida para la **Fase 2: Gestión de Pacientes, Órdenes y Carga de Resultados**.


