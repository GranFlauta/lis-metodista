# PROMPT — FASE 2: Pacientes, Catálogo (lectura) y Órdenes en borrador

=== INICIO DEL PROMPT ===

# 1. ROL Y MODO DE TRABAJO

Eres un ingeniero senior (backend + frontend) en un **sistema clínico** (LIS). Un error puede afectar a pacientes. Por tanto:

* Haces **solo** lo que este prompt pide.
* **No inventas** reglas de negocio, endpoints, columnas, librerías ni valores. Lo que no esté en este prompt, en `docs/DECISIONES.md` o en `AGENTS.md` es **no decidido**.
* Ante un hueco: elige la opción **más segura y simple**, regístrala en `docs/SUPUESTOS.md` (continúa la numeración existente) y sigue. Solo te detienes a preguntar si el hueco **bloquea** el avance o afecta a seguridad/datos clínicos.
* Nunca digas "listo" sin haber **ejecutado** los tests y pegado su salida real.
* Sigue las **convenciones que ya usa el repositorio** (nombres de archivos, estructura, estilo de tests). Mira cómo quedó la Fase 1 y copia ese patrón; no introduzcas otro.

# 2. CONTEXTO

LIS on-premise (PostgreSQL 16 + FastAPI + React/Vite/TS; Podman/Docker Compose; Caddy HTTPS). Fases 0 y 1 están hechas: esquema, catálogo (9 estudios, 2 perfiles), motor de cálculo, autenticación con sesión por latido, usuarios (`ADMIN`, `BIOQUIMICO`).

**Esta fase construye:** pacientes, lectura del catálogo, y **órdenes en borrador** (con selección de perfil/estudios y detección de trabajo duplicado). **No** se capturan ni calculan resultados (eso es la Fase 3).

> Nota: el informe de evaluación de la Fase 1 describía la Fase 2 como "Pacientes, Órdenes y **Carga de Resultados**". Eso es incorrecto. La carga de resultados es la **Fase 3**. No la implementes.

# 3. PASO 0 — PUERTA DE ENTRADA (no negociable)

Esta fase **solo** puede comenzar si la **Fase 1.5** (`docs/PROMPT_FASE_1_5_CIERRE.md`) está terminada y aprobada. Antes de escribir código nuevo, ejecuta y pega la salida real de:

1. `git tag --list "fase-1-cerrada"` → debe existir. `git status` → limpio.
2. Desde `backend/`, con el entorno del proyecto y `TEST_DATABASE_URL` definida: `python -m unittest discover -s tests -v` → `Ran N tests`, `OK`, **sin ninguna línea `skipped`**. Anota `N`: es la línea base de regresión.
3. `git diff --stat fase-1-cerrada HEAD -- db/init backend/app/catalog` → vacío (y debe seguir vacío al terminar esta fase).
4. `grep -rn "datetime.now\|utcnow" backend/app --include=*.py` → solo `core/clock.py`; `grep -rn "HTTPException" backend/app --include=*.py` → sin resultados.
5. `podman compose config` (o `docker compose config`) → `db` **no** publica puertos en el compose base.

Si **cualquiera** falla: **detente** y repórtalo; no continúes.

**Primera respuesta obligatoria (sin código de la Fase 2):** resultado de los puntos 1–5 + resumen de 10 líneas de lo que vas a construir + archivos a crear/modificar + dudas **bloqueantes** (o "ninguna").

# 4. LECTURA OBLIGATORIA

Léelos completos: `AGENTS.md`, `docs/DECISIONES.md` (§3, §4, §6 matriz de permisos, §7), `docs/SUPUESTOS.md`, `db/init/001_schema.sql` (tablas `pacientes`, `ordenes`, `orden_estudios`, `orden_estudio_grupos`, `estudios`, `estudio_versiones`, `parametros`, `perfiles`, `perfil_estudios`, `borradores_descartados`, `log_seguridad`), `backend/app/catalog/definitions.py`, y el código de Fase 1, **en especial** `backend/app/api/deps.py` (dependencias de autorización y `registrar_evento_seguridad`, `obtener_ip_cliente`), `backend/app/core/errors.py` (clase `AppError` y subclases), `backend/app/core/database.py`, `backend/app/models/*.py`, `backend/app/schemas/*.py`, la clase base de tests de integración y `frontend/src/api/client.ts`.

# 5. PRIMER COMMIT: ACTUALIZAR DECISIONES

Añade **al final** de `docs/DECISIONES.md` exactamente este bloque (es la única edición permitida a ese archivo):

```markdown
## 11. Decisiones de Fase 2 (pacientes, órdenes, catálogo)

* **D2-01** La Fase 2 NO incluye captura de resultados ni cálculo (son Fase 3).
* **D2-02** Una orden se crea con su lista FINAL de estudios. En v1 los estudios de un borrador no se editan: para cambiarlos se descarta el borrador y se crea otro. (Revisar en Fase 3.)
* **D2-03** Crear paciente + Orden N°1 es una sola transacción (`POST /api/ordenes` con `paciente` anidado). Si falla la orden, no queda paciente.
* **D2-04** Detección de trabajo duplicado, a granularidad (estudio) o (estudio, grupo) en estudios de selección parcial (Inmunoserología). Solo contra borradores `INCOMPLETO`/`COMPLETO`, no bloqueados, de OTRO usuario. Solapamiento parcial → advertencia. Todos los estudios de la orden nueva ya presentes en UN mismo borrador ajeno → bloqueo 409 `ORDEN_DUPLICADA_EN_CURSO`. Delegación y urgencia llegan en la Fase 7; hasta entonces el bloqueo se resuelve esperando a que el otro autor publique o descarte.
* **D2-05** La advertencia/bloqueo revela solo nombre del autor y códigos de estudio; nunca ids de orden ni resultados.
* **D2-06** ADMIN: lee pacientes; lee órdenes ajenas con registro `ADMIN_VE_PRIVADO` en `log_seguridad`. No crea ni modifica nada.
* **D2-07** Una orden ajena para un BIOQUIMICO responde 404 (no 403) para no revelar su existencia.
* **D2-08** Edad: si el paciente tiene fecha de nacimiento, el servidor la calcula al crear la orden; si no, `edad_anios` es obligatoria.
* **D2-09** Etiqueta provisional de los grupos de Inmunoserología: código humanizado + nombres de sus parámetros, hasta que exista metadata de grupos.
* **D2-10** `numero_orden_paciente = MAX + 1` bajo bloqueo de la fila del paciente. Si se descarta la última orden, su número puede reutilizarse (son borradores privados; el folio sí es inviolable).
* **D2-11** PENDIENTE antes de producción: auditoría de ediciones de pacientes (el esquema actual no tiene tabla ni acción para ello).
```

# 6. ALCANCE

## 6.1 DENTRO
**Backend:** modelos (`Paciente`, `Orden`, `OrdenEstudio`, `OrdenEstudioGrupo`, `Estudio`, `EstudioVersion`, `Parametro` (solo lectura), `Perfil`, `PerfilEstudio`, `BorradorDescartado`); API de catálogo (lectura); API de pacientes; API de órdenes en borrador; detección de duplicados; auditoría `ADMIN_VE_PRIVADO`; tests.
**Frontend:** menú Pacientes y Órdenes; búsqueda y alta/edición de pacientes; asistente "Nuevo paciente + orden" y "Nueva orden"; lista y detalle de órdenes propias; descarte de borrador.

## 6.2 FUERA (no lo hagas)
Captura/cálculo de resultados, `resultados_borrador`, cambios de estado `INCOMPLETO↔COMPLETO`, publicación, folios, informes, PDF, delegación, urgencia, bloqueo por concurrencia (el flag `bloqueada` solo se **lee**), edición de los estudios de un borrador, notificaciones, reportes, auditoría de pacientes, **cualquier cambio de esquema** (`db/init/*.sql`) o del catálogo. Si crees que hace falta una columna o tabla: **detente y repórtalo**.

# 7. DECISIONES TÉCNICAS (no las cambies)

| Tema | Decisión |
|---|---|
| Autenticación | Reutiliza las dependencias de `app/api/deps.py` (existe `require_admin`; para "cualquier autenticado" y "solo BIOQUIMICO" **añade** dependencias equivalentes en ese mismo archivo, con el mismo patrón y la misma regla `DEBE_CAMBIAR_PASSWORD`) |
| Errores | Nuevas clases en `core/errors.py` siguiendo el patrón de `AppError` (`OrdenDuplicadaEnCursoError`, `ConflictoVersionError`, con `extra` para el `detalle`). **Prohibido** `HTTPException` |
| Estilo de código | **Imita el repositorio**: modelos con `Column` y la `Base` de `core/database.py`, sin `schema=` explícito (el `search_path` lo fija `connect_args`), consultas con `db.query`, esquemas Pydantic en `app/schemas/`. No migres lo existente. Regístralo en `SUPUESTOS.md` |
| Auditoría | Usa `registrar_evento_seguridad` y `obtener_ip_cliente` de `deps.py` para `ADMIN_VE_PRIVADO` |
| Reloj | Solo `clock.ahora()`. Fechas "de hoy" se calculan con él |
| Transacciones | Cada operación de escritura de este prompt es **una sola transacción** |
| Validación | Los modelos de entrada rechazan campos desconocidos (`extra="forbid"`) → 400 `VALIDACION` |
| Identificadores en API | Estudios y perfiles se referencian por `codigo`, no por id interno |
| Paginación | `limit` (1–100, defecto 25) y `offset` (≥ 0). Fuera de rango → 400. Respuesta `{items, total, limit, offset}` |
| Búsqueda | `ILIKE` parcial sobre los campos indicados. **No** se instala `unaccent` ni otra extensión |
| Dependencias | **Ninguna nueva** (si necesitas una, pídela antes) |
| Tests | `unittest`, ejecutados desde `backend/`. BD de prueba creada con `scripts/crear_bd_test.sh` (esquema real `001` + seed `002`). La clase base **falla** (no omite) si la BD no responde y **no** usa `create_all`. Extiende esa base con un helper que limpia, en orden de dependencias, `borradores_descartados`, `orden_estudio_grupos`, `orden_estudios`, `ordenes`, `pacientes` y usuarios de prueba, y con fábricas de pacientes/usuarios **ficticios** |
| Idioma | Mensajes y UI en español |

Códigos de error: se mantienen los de la Fase 1 y se añaden **dos**:

| HTTP | `codigo` | Cuándo |
|---|---|---|
| 409 | `ORDEN_DUPLICADA_EN_CURSO` | D2-04. Incluye `detalle: {autor: {nombres, apellido_paterno}, estudios: [codigos]}` |
| 409 | `CONFLICTO_VERSION` | `fila_version` desactualizada en `PATCH /api/ordenes/{id}` |

# 8. CONTRATO DE LA API

Prefijo `/api`. Todos requieren sesión válida. Permisos según la matriz de `DECISIONES.md` §6.

## 8.1 Catálogo (lectura) — cualquier usuario autenticado

* `GET /api/catalogo/estudios` → lista de estudios con `activo = TRUE`:
  `{codigo, nombre, categoria, seleccion_parcial, grupos}`. `grupos` solo si `seleccion_parcial`: `[{codigo, parametros: [{codigo, nombre}]}]` tomados de la **versión activa** del estudio, en orden de `orden_visualizacion`. Para los demás, `grupos: null`.
* `GET /api/catalogo/perfiles` → `[{codigo, nombre, estudios: [{codigo, grupos: [..] | null}]}]` ordenados por `perfil_estudios.orden_visualizacion`.

## 8.2 Pacientes

| Ruta | Quién | Reglas |
|---|---|---|
| `GET /api/pacientes?q=&limit=&offset=` | BIOQUIMICO, ADMIN | `q` busca en `ci`, `nombres`, `apellido_paterno`, `apellido_materno`. Orden: apellidos, nombres |
| `GET /api/pacientes/{id}` | BIOQUIMICO, ADMIN | 404 si no existe |
| `POST /api/pacientes` | BIOQUIMICO | 201 |
| `PATCH /api/pacientes/{id}` | BIOQUIMICO | 200; subconjunto de los campos editables |

**No existe `DELETE` de pacientes.**

Campos: `ci?`, `ci_complemento?`, `sin_ci` (bool), `nombres`, `apellido_paterno`, `apellido_materno?`, `fecha_nacimiento?`, `sexo` (`M`|`F`), `telefono?`.
Reglas:
* Normalización: `strip` y colapsar espacios múltiples en nombres/apellidos; `ci` y `ci_complemento` en **mayúsculas** y sin espacios; `ci_complemento` vacío → `NULL`.
* Exactamente una de: (`sin_ci = true` y `ci = NULL`) o (`sin_ci = false` y `ci` de 5–30 caracteres). Si no → 400 `VALIDACION`.
* `fecha_nacimiento`: no futura y no anterior a 130 años.
* Longitudes máximas según el esquema.
* CI duplicado (misma pareja `ci`+`ci_complemento`, tratando `NULL` como vacío) → 409 `CONFLICTO` con `paciente_existente_id` en el cuerpo. El mismo CI con distinto complemento **sí** es válido.
* `creado_por` = usuario actual.

JSON de paciente: `{id, ci, ci_complemento, sin_ci, nombres, apellido_paterno, apellido_materno, fecha_nacimiento, sexo, telefono, creado_en}`.

## 8.3 Órdenes (borrador)

### `POST /api/ordenes` — solo BIOQUIMICO — 201
```json
{
  "id_paciente": 12,                 // XOR con "paciente"
  "paciente": { ...campos de 8.2 },  // XOR con "id_paciente" (alta + orden en 1 transacción)
  "perfil": "HC-QMC-SEROL-EGO",      // opcional; solo se guarda como referencia
  "estudios": [                      // lista FINAL (la UI la preselecciona con el perfil y el usuario la ajusta)
    {"codigo": "HEMOGRAMA"},
    {"codigo": "INMUNOSEROLOGIA", "grupos": ["VIH", "PCR_SEMICUANT"]}
  ],
  "origen_solicitud": "...", "medico_solicitante": "...", "pieza": "...",
  "edad_anios": 33, "edad_meses": 4,
  "fecha_hora_toma_muestra": "2026-10-11T12:00:00-04:00"
}
```
Respuesta: `{"orden": <Orden>, "advertencias": [ {tipo:"SOLAPAMIENTO", autor:{nombres, apellido_paterno}, estudios:[codigos]} ]}`.

**Validaciones**
1. Exactamente uno de `id_paciente` / `paciente` (si no → 400).
2. `estudios`: ≥ 1; sin repetidos; cada `codigo` existe y está activo; usa la **versión activa** y guarda su `id_estudio_version` en `orden_estudios` (se congela).
3. `grupos`: obligatorio y no vacío **solo** si el estudio es `seleccion_parcial`; prohibido en los demás; cada grupo debe existir en los parámetros de la versión activa; sin repetidos. Se guardan en `orden_estudio_grupos`.
4. `perfil` (si viene) debe existir → se guarda `id_perfil`. No se exige que `estudios` coincida con el perfil.
5. **Edad (D2-08):** si el paciente tiene `fecha_nacimiento`, calcular `edad_anios`/`edad_meses` a la fecha de hoy (`clock`) e **ignorar** lo que envíe el cliente. Si no la tiene, `edad_anios` es obligatorio (0–130) y `edad_meses` opcional (0–11, defecto 0).
6. `fecha_hora_toma_muestra`: opcional, con zona horaria, no futura (tolerancia 5 min). `origen_solicitud` ≤ 100, `medico_solicitante` ≤ 150, `pieza` ≤ 100.
7. `estado_trabajo = 'INCOMPLETO'`, `id_usuario_autor` = usuario actual, `bloqueada = FALSE`.

**Algoritmo (una transacción)**
1. Si viene `id_paciente`: `SELECT … FROM pacientes WHERE id = :id FOR UPDATE` (serializa las altas de órdenes de ese paciente). Si viene `paciente`: insertarlo (si choca la unicidad de CI → 409 `CONFLICTO` con `paciente_existente_id`, y se revierte todo).
2. Validar estudios/grupos/perfil.
3. **Detección (D2-04):** construir el conjunto de ítems de la orden nueva: `"CODIGO"` para estudios normales y `"CODIGO:GRUPO"` para los de selección parcial. Para cada borrador del mismo paciente con `estado_trabajo IN ('INCOMPLETO','COMPLETO')`, `bloqueada = FALSE` y `id_usuario_autor <> usuario actual`, construir su conjunto de ítems igual.
   * Si el conjunto nuevo ⊆ el de **un** borrador ajeno → abortar con 409 `ORDEN_DUPLICADA_EN_CURSO` (no se crea nada, ni paciente).
   * Si no, por cada borrador ajeno con intersección no vacía → una advertencia `SOLAPAMIENTO` (con los códigos que se solapan).
4. `numero_orden_paciente = COALESCE(MAX(numero_orden_paciente), 0) + 1` de ese paciente.
5. Insertar `ordenes`, `orden_estudios`, `orden_estudio_grupos`; confirmar.

### `GET /api/ordenes?estado=&id_paciente=&q=&limit=&offset=`
* **BIOQUIMICO:** solo sus órdenes (`id_usuario_autor` = él). `estado` ∈ `INCOMPLETO|COMPLETO|PUBLICADA` (por defecto `INCOMPLETO` y `COMPLETO`). `q` busca en datos del paciente.
* **ADMIN:** todas las órdenes (más filtro `id_autor`). Si la respuesta incluye ≥ 1 orden, registrar **un** evento `ADMIN_VE_PRIVADO` en `log_seguridad` (`id_usuario` = admin, `id_objetivo` = NULL, `detalle` = `{"recurso":"ordenes","filtros":{...},"cantidad":n}`).
* Orden: más recientes primero. Elemento de lista: `{id, paciente:{id, ci, nombres, apellido_paterno, apellido_materno}, numero_orden_paciente, estado_trabajo, bloqueada, estudios:[codigos], fecha_solicitud, creado_en}`.

### `GET /api/ordenes/{id}`
* Autor o ADMIN. Cualquier otro BIOQUIMICO → **404** (D2-07).
* ADMIN sobre orden ajena → evento `ADMIN_VE_PRIVADO` (`id_objetivo` = autor, `detalle = {"recurso":"orden","id_orden":id}`).
* JSON completo `Orden`:
  `{id, paciente:{id, ci, ci_complemento, nombres, apellido_paterno, apellido_materno, sexo, fecha_nacimiento}, numero_orden_paciente, autor:{id, nombres, apellido_paterno}, perfil:{codigo, nombre}|null, origen_solicitud, medico_solicitante, pieza, edad_anios, edad_meses, fecha_solicitud, fecha_hora_toma_muestra, estado_trabajo, bloqueada, fila_version, estudios:[{codigo, nombre, grupos:[..]|null}], creado_en, actualizado_en}`.

### `PATCH /api/ordenes/{id}` — solo el autor
* Campos editables: `origen_solicitud`, `medico_solicitante`, `pieza`, `fecha_hora_toma_muestra`, `edad_anios`, `edad_meses` (esta regla de edad solo si el paciente no tiene fecha de nacimiento; si la tiene, enviar edad → 400).
* Requiere `fila_version` en el cuerpo; si no coincide → 409 `CONFLICTO_VERSION`. Si coincide, aplica y la incrementa en 1 (en la misma sentencia `UPDATE … WHERE fila_version = :v`).
* No se pueden editar estudios, paciente ni estado (campo desconocido → 400).
* Orden `PUBLICADA` o `bloqueada` → 409 `CONFLICTO`.

### `DELETE /api/ordenes/{id}` — solo el autor — 204 (descarte de borrador)
Una transacción: insertar en `borradores_descartados` (`id_orden`, `id_paciente`, `id_usuario`, `estado_trabajo`, `estaba_bloqueada`, `folio_causa = NULL`) y borrar la orden (cascada). Orden `PUBLICADA` → 409 `CONFLICTO`. Otro BIOQUIMICO → 404. ADMIN → 403 `PROHIBIDO`.

### Permisos resumidos
ADMIN: **solo lectura** (pacientes y órdenes, esta última auditada). Crear/editar/descartar → 403 `PROHIBIDO`. Sin token → 401. Con `debe_cambiar_password` → 403.

# 9. FRONTEND

Rutas: `/pacientes`, `/pacientes/nuevo`, `/pacientes/:id`, `/ordenes`, `/ordenes/nueva`, `/ordenes/:id`. Habilita en el menú **Pacientes** y **Órdenes** (las demás secciones siguen "Próximamente"). Para ADMIN se **ocultan** los botones de crear/editar/descartar.

* **Pacientes:** buscador (debounce 300 ms) + tabla paginada; formulario de alta/edición con la regla CI / "Sin CI"; ficha del paciente con sus órdenes y botón "Nueva orden".
* **Asistente de orden (una sola pantalla con secciones, o pasos):**
  1. Paciente: buscar existente **o** completar datos nuevos. Si el servidor responde 409 por CI duplicado, ofrecer **"Usar el paciente existente"**.
  2. Perfil (opcional): al elegirlo, **preselecciona** sus estudios; el usuario puede marcar/desmarcar. Lista los 9 estudios desde `GET /api/catalogo/estudios`.
  3. Para Inmunoserología: casillas por grupo (etiqueta provisional D2-09: código con guiones bajos → espacios, y debajo en texto pequeño los nombres de sus parámetros).
  4. Datos de la orden: origen, médico solicitante, pieza, toma de muestra; edad solo si el paciente no tiene fecha de nacimiento.
  5. Botón "Crear orden" deshabilitado sin ≥ 1 estudio.
* Tras crear: si hay `advertencias`, banner visible con autor y estudios solapados. Si el servidor responde `ORDEN_DUPLICADA_EN_CURSO`, mensaje claro: "Otro bioquímico (nombre) ya tiene un trabajo en curso para este paciente con estos estudios" — sin ofrecer saltarse el bloqueo.
* **Órdenes (Pendientes):** lista propia con filtros (estado, texto); detalle con datos y estudios; editar cabecera; **descartar** con diálogo de confirmación. Texto fijo "Captura de resultados: próximamente".
* Misma política de Fase 1: token solo en memoria, sin `localStorage`/`sessionStorage`, CSS propio, estados no dependientes solo del color, mensajes de error tomados del campo `mensaje`.

# 10. TESTS OBLIGATORIOS (`unittest`, PostgreSQL real, reloj simulado, sin `sleep`)

**Pacientes**
1. Alta con CI → 201; normaliza (mayúsculas, espacios).
2. `sin_ci=true` con `ci`, o `sin_ci=false` sin `ci` → 400.
3. CI duplicado → 409 con `paciente_existente_id`; mismo CI con otro complemento → 201; complemento `""` equivale a `NULL`.
4. Fecha de nacimiento futura o de hace > 130 años → 400.
5. ADMIN puede `GET`; `POST`/`PATCH` → 403. Sin token → 401. Con `debe_cambiar_password` → 403.
6. Búsqueda `q` por CI, apellido y nombre (parcial, sin distinguir mayúsculas); paginación y `total`; `limit=101` → 400.
7. `PATCH` edita campos y respeta unicidad de CI (409); campo desconocido → 400.
8. No existe `DELETE /api/pacientes/{id}`.

**Catálogo**
9. Devuelve exactamente los 9 estudios activos; solo Inmunoserología tiene `seleccion_parcial` y grupos (incluye `VIH` y `PCR_SEMICUANT`); los demás `grupos = null`.
10. Los 2 perfiles coinciden con `PERFILES` de `definitions.py` (mismos estudios, mismo orden, mismos grupos).
11. Exige autenticación; un estudio con `activo = FALSE` no aparece.

**Creación de órdenes**
12. Orden para paciente existente → 201, `INCOMPLETO`, autor correcto, `numero_orden_paciente` 1 y luego 2.
13. Alta de paciente + orden en una transacción; si la orden es inválida **no queda el paciente**.
14. `id_paciente` y `paciente` a la vez, o ninguno → 400.
15. Sin estudios, estudio repetido, código inexistente, estudio inactivo → 400.
16. `grupos` en estudio no parcial → 400; estudio parcial sin grupos → 400; grupo inexistente → 400.
17. Se guarda `id_estudio_version` activa y las filas de `orden_estudio_grupos`.
18. Edad calculada con fecha de nacimiento (reloj simulado) e ignorando la enviada; sin fecha de nacimiento y sin `edad_anios` → 400; `edad_meses` fuera de 0–11 → 400.
19. `perfil` inexistente → 400; `perfil` válido se guarda aunque `estudios` difiera.
20. ADMIN no puede crear → 403.
21. Dos creaciones **concurrentes** (hilos) para el mismo paciente → números 1 y 2, sin error 500 ni números repetidos.
22. Toma de muestra futura (> 5 min) → 400.

**Detección de duplicados (D2-04)**
23. Estudios disjuntos con borrador ajeno → 201, sin advertencias.
24. Solapamiento parcial → 201 con `advertencias` (autor + códigos, **sin** id de orden).
25. Nueva ⊆ borrador ajeno → 409 `ORDEN_DUPLICADA_EN_CURSO` con `detalle`; no se crea paciente ni orden.
26. No bloquea si el borrador es **propio**, está `bloqueada`, está `PUBLICADA`, o es de otro paciente.
27. Granularidad por grupo: `INMUNOSEROLOGIA:VIH` vs `INMUNOSEROLOGIA:PCR_SEMICUANT` son disjuntos (201); `VIH` vs `VIH` bloquea.
28. Nueva ⊄ ningún borrador individual (cubierta solo por la **unión** de dos borradores ajenos) → no bloquea (solo advertencias).

**Lectura y privacidad**
29. BIOQUIMICO lista solo sus órdenes; filtros `estado` e `id_paciente`.
30. `GET /api/ordenes/{id}` de orden ajena → 404 para BIOQUIMICO.
31. ADMIN lista todas y se registra **un** `ADMIN_VE_PRIVADO` por petición (con `cantidad`); `GET` de orden ajena registra `id_objetivo` = autor; una lista vacía **no** registra evento.
32. ADMIN no puede `PATCH` ni `DELETE` → 403.

**Edición y descarte**
33. `PATCH` con `fila_version` correcta la incrementa; incorrecta → 409 `CONFLICTO_VERSION`; dos `PATCH` simultáneos con la misma versión → uno gana y el otro recibe 409.
34. `PATCH` con `estudios`, `estado` o `id_paciente` → 400.
35. `DELETE` por el autor → 204, desaparecen orden y filas hijas, aparece fila en `borradores_descartados` con `estado_trabajo` y `estaba_bloqueada` correctos; otro BIOQUIMICO → 404; ADMIN → 403; orden `PUBLICADA` (forzada por SQL en el test) → 409.
36. A nivel de BD: insertar una orden sin estudios y confirmar la transacción **falla** (constraint trigger del esquema).

**Regresión**
37. **Regresión:** todos los tests existentes al iniciar la fase (la `N` anotada en el Paso 0) siguen pasando, y la ejecución final muestra `skipped=0`.

# 11. PROTOCOLO ANTI-ALUCINACIÓN

1. **Verifica antes de afirmar** cada API de librería en el entorno instalado (`python -c "import …"`, `pip show`, `npm ls`).
2. El **único** origen de nombres de tablas y columnas es `db/init/001_schema.sql`. Si falta algo, **detente y repórtalo**; no lo agregues.
3. Sin relleno: nada de `pass`, `TODO`, `NotImplementedError` ni funciones vacías dentro del alcance. Lo no hecho va a "No hecho".
4. Sin mocks de BD en tests de integración.
5. **Prohibido:** `eval`, `exec`, `pickle`, SQL concatenado con datos del usuario (usa parámetros/ORM), `print` de datos de pacientes, `except Exception: pass`, CORS `*`, `datetime.now()` fuera de `clock.py`, logs con datos clínicos o de pacientes.
6. No renombres ni reformatees archivos que no tocas; diffs mínimos.
7. Si un test falla, corrige el **código**. Si el test contradice este prompt, repórtalo.
8. **Datos ficticios** en todos los tests, fixtures y capturas. Nunca datos reales de pacientes.
9. Toda decisión no cubierta → una línea en `docs/SUPUESTOS.md` (`| # | Tema | Qué no estaba definido | Qué decidí | Impacto si está mal |`, continuando la numeración).

# 12. ORDEN DE TRABAJO (un commit por paso, mensajes en español, imperativo)

1. Paso 0 de reconciliación (§3) y primera respuesta (sin código nuevo).
2. Añadir §11 a `docs/DECISIONES.md` (§5).
3. Modelos + API de catálogo + tests 9–11.
4. Pacientes (servicio, endpoints) + tests 1–8.
5. Órdenes: creación, validaciones, numeración, detección de duplicados + tests 12–28.
6. Órdenes: lectura, auditoría admin, `PATCH`, `DELETE` + tests 29–36.
7. README (cómo crear la BD de test con **001 + 002**) + verificación de regresión (test 37).
8. Frontend: catálogo, pacientes.
9. Frontend: asistente de orden, lista/detalle de órdenes, descarte.
10. Verificación manual (§13) e informe final.

# 13. CRITERIOS DE ACEPTACIÓN

Marca solo lo que ejecutaste y pega la evidencia:

- [ ] Todos los tests (los previos + los nuevos) → `OK`, **sin ninguna omisión (`skipped`)**, salida pegada completa.
- [ ] Flujo manual como BIOQUIMICO: alta de paciente **+ orden** con el perfil `HC-QMC-SEROL-EGO` → quitar un estudio → crear → aparece en Órdenes con `numero_orden_paciente = 1`.
- [ ] Segunda orden del mismo paciente → número 2.
- [ ] Con **dos** usuarios BIOQUIMICO: A crea una orden con Hemograma + Química; B intenta Hemograma → **bloqueado**; B intenta Hemograma + Lipídico → **advertencia**; B intenta Lipídico → sin aviso.
- [ ] Orden con Inmunoserología solo `VIH` y otra solo `PCR_SEMICUANT` del mismo paciente por usuarios distintos → sin bloqueo.
- [ ] Como ADMIN: ve pacientes y órdenes, no ve botones de crear/editar/descartar, y `SELECT accion, count(*) FROM laboratorio.log_seguridad GROUP BY 1` muestra `ADMIN_VE_PRIVADO`.
- [ ] Descartar un borrador → desaparece y hay fila en `laboratorio.borradores_descartados`.
- [ ] Los comandos del §3 (puntos 3 y 4) vuelven a dar el resultado esperado al final; `git diff --stat fase-1-cerrada HEAD -- db/init backend/app/catalog` vacío.
- [ ] `.env` no versionado; sin datos reales en el repositorio.

# 14. INFORME FINAL (formato obligatorio)

```
## Puerta de entrada (§3)
(salida de los 5 puntos)
## Hecho
(lista, referenciando el nº de test o criterio que lo prueba)
## No hecho / parcial
(con motivo)
## Supuestos
(entradas nuevas de docs/SUPUESTOS.md)
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
