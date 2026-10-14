# LIS Laboratorio Clínico — Decisiones y reglas de negocio (v1)

> Este documento **manda** sobre el .docx original cuando haya contradicción.
> Si cambias una regla aquí, cambia también el código y los tests en el mismo commit.

## 1. Decisiones cerradas

| # | Decisión | Motivo |
|---|---|---|
| D-01 | **9 estudios** en v1: Hemograma, Coagulograma (+ grupo sanguíneo), Química, Electrolitos, Perfil Lipídico, Hepatograma, Proteinograma, EGO, Inmunoserología | Cubren el 100 % de los 2 perfiles |
| D-02 | **Hemograma manual** del Excel (GR y Hb estimados desde Hto). La imagen de referencia solo guía el estilo del PDF | El Excel es la regla operativa |
| D-03 | El informe impreso lleva **siempre al autor original (A)** como responsable, aunque B lo haya calculado/publicado. B queda en la trazabilidad colaborativa | Responsabilidad legal |
| D-04 | **On-premise** con Docker Compose: PostgreSQL + FastAPI + Caddy (HTTPS interno) + respaldo diario | Velocidad, datos médicos en el local, sin depender de internet |

Stack: **FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL 16** · **React + Vite + TypeScript**.

## 2. Qué quedó fuera del v1 (la arquitectura ya lo soporta)

Toxicológico, Coproparasitológico, Curva de tolerancia a la glucosa, Perfil cardíaco (CK-MB/CPK/LDH), Amilasa, Lipasa, hemograma de analizador (28 parámetros, otra `estudio_version`), informes parciales, rangos pediátricos, valores críticos, estadísticas, integración con equipos.
Agregarlos = insertar filas en el catálogo (`definitions.py` → regenerar seed), no tocar el esquema.

## 3. Modelo: orden ≠ informe

```
paciente 1─N orden (borrador PRIVADO, se borra físicamente si se descarta)
                │
                └── al publicar ──► informe (documento OFICIAL, inmutable)
                                      folio (nunca se reutiliza) + numero_version (1..3)
```

* **Orden**: trabajo en curso. Estados de trabajo: `INCOMPLETO` → `COMPLETO` → `PUBLICADA`.
  *Pendientes* = vista filtrada de órdenes propias en `INCOMPLETO` o `COMPLETO`. No es otro módulo.
* **Informe**: estados `VIGENTE`, `DESPLAZADO` (versión anterior), `PAPELERA`, `RECICLAJE`.
* **Bloqueo por concurrencia** es un flag (`ordenes.bloqueada`), **no** un estado: así se conserva el avance real del borrador.
* Un folio tiene como máximo **una versión no desplazada** (índice parcial) y como máximo **3 versiones** (`CHECK`).
* Folio formato `AAAA-NNNNNN` con contador sin huecos por año (`siguiente_folio()`), solo se genera al publicar. *Formato pendiente de confirmar (ver §10).*

### Qué cambió respecto al DDL del .docx

| Problema en el original | Corrección |
|---|---|
| Sección 7 decía clave compuesta folio+versión, pero el DDL versionaba **por estudio** | Tabla `informes` con `UNIQUE(folio, numero_version)` |
| Unicidad del folio solo `WHERE estado='OFICIAL'` | Tabla `folios` (PK global, inmutable) |
| `estado` mezclaba trabajo, publicación, papelera y bloqueo | Separados (`estado_trabajo`, `bloqueada`, `informes.estado`) |
| `BLOQUEADO_CONCURRENCIA` pisaba el estado previo | Flag independiente |
| `DELETE` en cascada fallaba (FKs sin `ON DELETE CASCADE`) | Cascadas definidas |
| El log colaborativo se borraba al publicar | `colaboracion_cambios` append-only, ligado al folio |
| `valor_a/valor_b` solo guardaba un cambio | Un registro por cambio (quién, cuándo, antes, después) |
| `delegaciones.activa` booleano | Estados SOLICITADA/ACEPTADA/RECHAZADA/REVOCADA/FINALIZADA |
| `auditoria.folio` nullable pese a ser "obligatorio" | `informe_eventos.folio NOT NULL` + append-only |
| `papelera_ordenes` duplicaba datos de `ordenes` | Eliminada; la papelera es un estado + evento |
| `pacientes.ci` y `fecha_nacimiento` NOT NULL | CI opcional (`sin_ci`), edad guardada en la orden |
| Sin hora de toma, médico solicitante, matrícula, firma | Añadidos |
| `obligatorio` siempre FALSE → ninguna orden llegaba a COMPLETO | Obligatorio por defecto TRUE |
| Sin decimales/rangos inclusivos/edad | `decimales`, `inferior_inclusivo`, `edad_*_meses` |
| Snapshot "inmutable" sin garantía | Triggers + SHA-256 |
| Sin registro de la justificación de urgencia | `informes.es_urgencia` + `justificativo` |

## 4. Reglas de flujo

**Crear paciente + Orden N°1** en una sola acción; no se guarda sin ≥ 1 estudio (servicio + constraint trigger). Orden N°2, 3… desde Órdenes.

**Pendientes** (INCOMPLETO/COMPLETO): edición libre, sin justificativo ni versionado, vista previa en vivo, sin folio y **sin impresión**.

**Publicar**: transacción única → valida completitud y confirmaciones → `siguiente_folio()` → inserta `informes` V1 con snapshot + hash → orden `PUBLICADA` → evento `PUBLICACION` → liga `colaboracion_cambios.folio`.

**Editar informe oficial** (V1→V2, V2→V3), solo el **firmante**:
1. Justificativo obligatorio → se crea `ediciones_informe` (una abierta por informe) con copia de valores.
2. Mientras no se publique, el informe vigente sigue siendo el visible.
3. "Guardar y subir V2/V3": en la misma transacción se pasa la versión anterior a `DESPLAZADO` **antes** de insertar la nueva (el índice parcial lo exige), se registra `EDICION_V2/V3`.
4. V4 no existe: la UI solo ofrece "Mover a papelera con justificativo" y crear un informe nuevo (`reemplaza_a_folio` deja el vínculo).

**Papelera**: solo el firmante, justificativo obligatorio. El folio se va con el informe y no se reasigna. Visible para todos.
**Restaurar** → `RECICLAJE`, conserva folio; se puede ver el PDF pero **la impresión queda bloqueada** (igual que en pendientes).

**Impresión**: solo `VIGENTE`. Cada impresión genera evento `IMPRESION` (reimpresión visible).

**Colores**: versiones → fondo rojo claro (original) / verde (oficial), colaboración → rojo (A) / azul (B). Como el rojo significa cosas distintas y rojo/verde es difícil para daltónicos, **siempre acompañar el color con un icono o tachado/subrayado**.

## 5. Cálculo (motor en `backend/app/calculation/engine.py`)

* Sin `eval`: se parsea con `ast` y lista blanca (`+ - * /`, comparaciones, `if/else`, `abs/min/max/no_calculable`).
* `Decimal` siempre; redondeo `ROUND_HALF_UP` según `parametros.decimales`.
* **Vacío = `NULL`, nunca 0.** Falta una entrada, división por cero o regla inválida → *"No calculable"* (el Excel mostraba `0`, `#DIV/0!` y un LDL calculado con HDL vacío).
* Diferencial: se captura en **%** (0-100). Absoluto = `pct / 100 × GB`.
* LDL (Friedewald) no se calcula con TG > 400 mg/dl.
* El **backend es la única fuente de verdad**; la vista previa llama a `/calcular` con debounce. No duplicar fórmulas en TypeScript.
* Valores por defecto (`requiere_confirmacion`): se muestran marcados "sin confirmar" y **bloquean la publicación** hasta que el bioquímico los confirme.
* GR y Hb del hemograma se rotulan **"(estimado)"** en el informe.

## 6. Sesión y seguridad

* "Cerrar sesión al cerrar pestaña/apagar PC" **no es detectable** por el navegador. Solución: access token en memoria + refresh en cookie `httpOnly`/`Secure`/`SameSite=Strict` + **latido cada 30 s**; sin latido durante 150 s la sesión muere en el servidor. Además timeout por inactividad (30 min) y tope absoluto (12 h). Un F5 **no** cierra sesión (se re-autentica con el refresh).
* Contraseñas **Argon2id**. Usuarios nuevos y resets del admin → `debe_cambiar_password = TRUE`. Bloqueo temporal tras N intentos. El admin nunca ve contraseñas.
* **Usuarios no se borran**: baja lógica (`activo = false`), porque firman informes.
* Toda regla de visibilidad se aplica **en el backend** (no solo ocultando botones) y con tests por rol.
* Cuando el admin mira pendientes/colaborativos ajenos → evento `ADMIN_VE_PRIVADO` en `log_seguridad`.
* HTTPS interno con Caddy (`tls internal`): instalar el certificado raíz en los PCs.

### Matriz de permisos

| Acción | Admin | Autor (A) | Colaborador (B) | Otro bioquímico |
|---|---|---|---|---|
| CRUD usuarios / reset de clave | ✔ | ✘ | ✘ | ✘ |
| Ver pacientes, historial oficial, papelera, versiones | ✔ (lectura) | ✔ | ✔ | ✔ |
| Crear paciente / orden | ✘ | ✔ | ✔ | ✔ |
| Ver pendientes y órdenes propias | ✔ (auditado) | ✔ | solo las delegadas aceptadas | ✘ |
| Editar / guardar borrador | ✘ | ✔ | ✔ si hay delegación aceptada | ✘ |
| Publicar | ✘ | ✔ | ✔ (sale firmado por A) | ✘ (solo vía urgencia) |
| Publicar por urgencia con justificativo | ✘ | ✔ | ✔ | ✔ |
| Nueva versión V2/V3, enviar a papelera, restaurar | ✘ | ✔ | ✘ | ✘ |
| Imprimir informe `VIGENTE` | *(pendiente)* | ✔ | ✔ | ✔ |
| Reportes de actividad (PDF) | ✔ | ✔ | ✔ | ✔ |

## 7. Concurrencia (propuesta del CTO sobre las secciones 2, 3, 5 y 6 del .docx)

Al crear una orden de B para un paciente que tiene borradores **ajenos** abiertos:

| Situación | Respuesta |
|---|---|
| Estudios de B disjuntos de los de A | Nada |
| Solapamiento parcial | Advertencia, deja continuar |
| **Todos los estudios de B ya están en el borrador de A** (B ⊆ A) | Bloquea: *pedir delegación* o *Urgencia + Justificativo* |

*(El original solo bloqueaba "exactamente iguales"; con B ⊆ A se cierra el hueco de "mismos estudios + uno extra".)*
La advertencia revela únicamente **nombre del autor y lista de estudios** (lo mínimo para pedir delegación).

**Publicación por urgencia** (cualquier bioquímico, justificativo obligatorio, sin pedir permisos): en **una transacción** → `SELECT … FOR UPDATE` de los borradores del paciente cuyos estudios ⊆ los del informe urgente → publica con folio y `es_urgencia` → marca esos borradores `bloqueada = TRUE`. Cualquier guardado posterior sobre un borrador bloqueado recibe **HTTP 409** y la UI lo muestra.

**Qué ve cada quien**: el colaborador (B) ve el trabajo en gris "No disponible", solo lectura. Al **autor (A)** se le exige decidir:
* **Conservar como informe nuevo** → `bloqueada = FALSE`; sigue su flujo normal y, al completarse y publicarse, recibe su propio folio. *(Así también funciona si el borrador estaba INCOMPLETO; en el original solo se contemplaba publicar.)*
* **Descartar** → `DELETE` físico en cascada + fila en `borradores_descartados` (sin contenido clínico).

Delegación: A solicita → B acepta/rechaza → A puede revocar; máx. 1 viva por orden (índice único parcial). Edición simultánea: bloqueo optimista con `fila_version` (409 si cambió).

## 8. Snapshot del informe (`informes.snapshot_json`)

Congela todo lo necesario para reimprimir idéntico aunque el catálogo cambie:
`paciente`, `orden` (edad al momento, médico, pieza, toma de muestra), `firmante` (nombre, matrícula), `publicador`, `estudios[]` → `parametros[]` con `{codigo, nombre, valor, unidad, decimales, rango_aplicado, referencia_texto, bandera, calculable, version_catalogo}`, y `aportes_colaborativos[]`. Se guarda `snapshot_sha256`; el trigger impide modificarlo.

## 9. Hoja de ruta

| Fase | Entrega |
|---|---|
| 0 | Repo, Docker Compose, BD con esquema + seed (**esto**) |
| 1 | Auth: login, sesión con latido, usuarios, cambio de clave, admin |
| 2 | Pacientes + órdenes + selección de perfil/estudios |
| 3 | Captura por estudio + cálculo + vista previa en vivo |
| 4 | Pendientes → publicar con folio |
| 5 | PDF oficial (misma plantilla HTML para preview y PDF; paginación y nº de página) |
| 6 | Versiones V2/V3, papelera, reciclaje |
| 7 | Delegación, colaborativos, concurrencia/urgencia |
| 8 | Búsquedas y filtros, reportes PDF, notificaciones |

## 10. Pendientes de validación (no son bloqueantes para arrancar)

**Clínicos — que los confirme el bioquímico responsable** (marcados `requiere_validacion` en la BD):
1. Ácido úrico: 2,5-7,0 (perfiles) vs 1,5-7,0 (hoja VN).
2. HbA1c 6,0-8,3 % (no es un rango de normalidad estándar).
3. Fósforo: 2,5-5,0 (la mayoría) vs 2,5-5,6 (HC-QMC).
4. GOT/AST: 37 (perfiles) vs 40 (HC-QMC) vs 39 (VN). GPT/ALT: 45 vs 40 vs 39.
5. Fosfatasa alcalina: 98-279 vs 25-90 (VN).
6. "Hepatitis A (Ag. superficie)": el Excel la rotula así; confirmar la denominación.
7. El diferencial del Excel no incluye basófilos y la imagen sí; confirmar si se agrega.

**De negocio:**
8. **Formato del folio** (`AAAA-NNNNNN` propuesto; la imagen muestra un "Código" tipo fecha `20230106`).
9. **Separador decimal**: el Excel usa coma, la imagen de referencia usa punto y lo declara en el pie. Hay que elegir uno (`laboratorio_config.separador_decimal`).
10. ¿Puede el Admin imprimir informes vigentes?
11. ¿Quién puede restaurar de la papelera? (propuesto: el firmante, con justificativo).
12. **Autor inactivo**: si A deja el laboratorio, nadie podría corregir sus informes. Falta definir un mecanismo de transferencia de autoría.
13. RUC, teléfono, horario y logo para el encabezado/pie del informe.
14. Usar siempre **datos ficticios** en desarrollo y pruebas (la imagen de referencia contiene los datos de una paciente real).

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

## 12. Decisiones de Fase 3 (captura y cálculo)

* **D3-01** Alcance: captura, cálculo, banderas, validaciones y estado `INCOMPLETO↔COMPLETO`. NO incluye publicar, folios, informes, PDF, ediciones de informes oficiales (`id_edicion` siempre NULL) ni delegación (solo el autor edita; B llega en la Fase 7).
* **D3-02** El backend es la única fuente de verdad del cálculo. `POST /calcular` es una vista previa sin escritura; `PUT /resultados` persiste y recalcula todo. El cliente NUNCA envía valores de parámetros calculados.
* **D3-03** Qué se captura: los parámetros de la versión de estudio congelada en la orden. En estudios de selección parcial, solo los parámetros cuyo `grupo` figura en `orden_estudio_grupos`.
* **D3-04** Valores: NUMERICO acepta coma o punto; se guarda con punto en `valor_numerico` tal cual lo digitó (sin redondear); máx. 6 decimales; no negativos. SELECCION debe estar en `opciones`. TEXTO ≤ 500 caracteres; RECUENTO ≤ 50; FECHA ISO no futura (se guarda como texto `AAAA-MM-DD`). Vacío = ausente: nunca se guarda 0 ni cadena vacía.
* **D3-05** Valores por defecto (`requiere_confirmacion`): se muestran como **virtuales** (no se guardan). Solo cuentan para completar cuando existe una fila `confirmado = TRUE`, creada al confirmarlos explícitamente o al editarlos a mano.
* **D3-06** Una orden es `COMPLETO` si todo parámetro `obligatorio` del alcance está resuelto: capturado y confirmado, o CALCULADO calculable, o CALCULADO no calculable por regla de validez/división por cero (p. ej. LDL con TG > 400 se informa "No calculable" y NO bloquea). CALCULADO sin entradas completas = pendiente. Una regla cruzada de severidad ERROR bloquea `COMPLETO`; ADVERTENCIA no.
* **D3-07** Banderas por rango: se elige el rango por sexo del paciente (o ambos) y, si el rango trae `edad_min/max_meses`, por la edad de la orden en meses. Respeta límites inclusivos/exclusivos. Solo para valores numéricos; los cualitativos no llevan bandera en v1.
* **D3-08** Los calculados se persisten (`es_calculado = TRUE`); si no son calculables por regla, fila con `calculable = FALSE` y valor NULL; si faltan entradas, sin fila.
* **D3-09** Guardar resultados NO modifica `ordenes.fila_version` (esa versión protege solo la cabecera). Dos pestañas del mismo autor = última escritura gana por parámetro; cada escritura bloquea la fila de la orden (`FOR UPDATE`).
* **D3-10** La API usa el punto decimal como formato canónico. La interfaz muestra según `laboratorio_config.separador_decimal` (hoy sembrado en coma). La decisión de negocio sobre el separador sigue pendiente (§10, punto 9).
* **D3-11** PENDIENTE: valores críticos y límites fisiológicos (p. ej. % > 100); permitir reemplazar GR/Hb estimados por valor medido (v1.1).

## 13. Decisiones de Fase 3.5 (correcciones)

* **D35-01** No hay CORS: frontend y API comparten origen (Caddy en producción, proxy de Vite en desarrollo). No se sirve el frontend desde el backend. `/docs` y `/openapi.json` están desactivados salvo `ENABLE_DOCS=true`.
* **D35-02** El tiempo de sesión lo configura el ADMIN en `laboratorio_config`: intervalo de latido (10–120 s), sesión muerta sin latido (≥ 3× el intervalo y ≤ 1800 s), inactividad (5–480 min) y tope absoluto (1–24 h). Los valores por defecto siguen siendo 30 s / 150 s / 30 min / 12 h. El tope absoluto se aplica a sesiones nuevas.
* **D35-03** La inactividad se mide con **actividad real del usuario** (ratón, teclado, toque, desplazamiento) que el navegador comunica en el latido (`actividad: true`). Un latido sin actividad NO renueva la inactividad.
* **D35-04** Los tests solo corren contra bases cuyo nombre termina en `_test`.
* **D35-05** Los cambios de esquema de esta fase se hacen con la migración Alembic `0002`. El contenedor del backend ejecuta `alembic upgrade head` al arrancar.
