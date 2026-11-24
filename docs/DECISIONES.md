# LIS Laboratorio Clínico — Decisiones y reglas de negocio (v1)

> Este documento **manda** sobre el .docx original cuando haya contradicción.
> Si cambias una regla aquí, cambia también el código y los tests en el mismo commit.

## 1. Decisiones cerradas

| # | Decisión | Motivo |
|---|---|---|
| D-01 | Catálogo vigente con 13 estudios: Hemograma, Coagulograma (+ grupo sanguíneo), Química, Electrolitos, Perfil Lipídico, Hepatograma, Proteinograma, EGO, Inmunoserología, Perfil Cardíaco, Perfil Pancreático, Parasitología y Curva de tolerancia | Catálogo ampliado por solicitud del laboratorio |
| D-02 | **Hemograma manual** del Excel (GR y Hb estimados desde Hto). La imagen de referencia solo guía el estilo del PDF | El Excel es la regla operativa |
| D-03 | El informe impreso lleva **siempre al autor original (A)** como responsable, aunque B lo haya calculado/publicado. B queda en la trazabilidad colaborativa | Responsabilidad legal |
| D-04 | **On-premise** con Docker Compose: PostgreSQL + FastAPI + Caddy (HTTPS interno) + respaldo diario | Velocidad, datos médicos en el local, sin depender de internet |

Stack: **FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL 16** · **React + Vite + TypeScript**.

## 2. Qué quedó fuera del v1 (la arquitectura ya lo soporta)

Toxicológico, LDH, hemograma de analizador (28 parámetros, otra `estudio_version`), rangos pediátricos, valores críticos e integración con equipos. Las estadísticas operativas se incorporan por solicitud posterior (§19). La Curva de tolerancia fue incorporada al catálogo como estudio independiente.

La Curva de tolerancia conserva únicamente las cinco mediciones capturadas. Cada punto requiere hora y glucosa válidas; los vacíos interrumpen la línea, y las horas anteriores requieren aclaración explícita de fecha. No se estiman valores ni se agregan umbrales o diagnósticos.
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

**Colores**: superficies de blanco, negro y grises neutros; rojo para acciones, iconos y jerarquía. Se conservan las banderas y estados semánticos: Bajo azul, Normal y guardado verdes, pendientes ámbar y Alto/error rojos. Versiones y colaboración se distinguen mediante etiquetas explícitas, iconos y, cuando corresponda, tachado/subrayado; nunca sólo mediante el color. La identidad de autor y colaborador no cambia.

## 5. Cálculo (motor en `backend/app/calculation/engine.py`)

* Sin `eval`: se parsea con `ast` y lista blanca (`+ - * /`, comparaciones, `if/else`, `abs/min/max/no_calculable`).
* `Decimal` siempre; redondeo `ROUND_HALF_UP` según `parametros.decimales`.
* **Vacío = `NULL`, nunca 0.** Falta una entrada, división por cero o regla inválida → *"No calculable"* (el Excel mostraba `0`, `#DIV/0!` y un LDL calculado con HDL vacío).
* Diferencial: se captura en **%** (0-100). Absoluto = `pct / 100 × GB`.
* LDL (Friedewald) no se calcula con TG > 400 mg/dl.
* El **backend es la única fuente de verdad**; la vista previa llama a `/calcular` con debounce. No duplicar fórmulas en TypeScript.
* En captura por campos utilizados, un campo sin usar permanece vacío. Los valores por defecto del catálogo no se convierten automáticamente en resultados. Un resultado utilizado que requiera confirmación debe confirmarse.
* GR y Hb del hemograma se rotulan **"(estimado)"** en el informe.

## 6. Sesión y seguridad

* La política de sesión se configura por entorno. `MODO_PRODUCCION=true` aplica expiración tras `SESSION_IDLE_TIMEOUT_MINUTES` sin actividad humana (60 min por defecto); los heartbeats y refresh automáticos no cuentan como actividad. `MODO_PRODUCCION=false` no aplica límite de inactividad, pero conserva `SESSION_ABSOLUTE_TIMEOUT_HOURS` (24 h por defecto). El access token vive en memoria; el refresh permanece en cookie `HttpOnly`, `SameSite=Strict` y `Secure` en producción. La vigencia del access token es independiente y se renueva mientras la sesión siga vigente.
* El navegador no garantiza detectar el cierre de una pestaña o aplicación ni revocar inmediatamente la sesión; una cookie de sesión puede restaurarse si el navegador restaura la sesión. No se persisten tokens en `localStorage` ni `sessionStorage`.
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
4. **Resuelto el 24/11/2026 por instrucción del laboratorio:** GOT/AST y GPT/ALT tienen referencia predeterminada **Hasta 40 UI/L**, inclusiva. Se retira `requiere_validacion` de estas dos referencias; ver D3-14.
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
* **D3-05** Los valores por defecto no se precargan como resultados ni se convierten en entradas utilizadas al abrir un borrador, incluido un catálogo anterior. Una entrada utilizada que requiera confirmación debe estar confirmada explícitamente o por su edición manual.
* **D3-06** En todos los borradores, incluidos los de catálogos anteriores sin `seleccion_campos`, una orden es `COMPLETO` al tener al menos un resultado utilizado y no contener entradas utilizadas incompletas, sin confirmar ni errores de validación. Vacíos y `--` se omiten, incluidos sus derivados por falta de entradas. Un positivo semicuantitativo iniciado sin los datos necesarios bloquea la publicación. Las observaciones finales son opcionales: no se exige inventar texto para publicar.
* **D3-07** Banderas por rango: se elige el rango por sexo del paciente (o ambos) y, si el rango trae `edad_min/max_meses`, por la edad de la orden en meses. Respeta límites inclusivos/exclusivos. Solo para valores numéricos; los cualitativos no llevan bandera en v1.
* **D3-08** Los calculados se persisten (`es_calculado = TRUE`); si no son calculables por regla, fila con `calculable = FALSE` y valor NULL; si faltan entradas, sin fila.
* **D3-09** Guardar resultados NO modifica `ordenes.fila_version` (esa versión protege solo la cabecera). Dos pestañas del mismo autor = última escritura gana por parámetro; cada escritura bloquea la fila de la orden (`FOR UPDATE`).
* **D3-10** La API usa el punto decimal como formato canónico. La interfaz muestra según `laboratorio_config.separador_decimal` (hoy sembrado en coma). La decisión de negocio sobre el separador sigue pendiente (§10, punto 9).
* **D3-11** PENDIENTE: valores críticos y límites fisiológicos (p. ej. % > 100); permitir reemplazar GR/Hb estimados por valor medido (v1.1).
* **D3-12** Grupo y Factor RH no tienen Unidad en captura, vista previa ni nuevos informes. Su selección se valida contra las opciones del catálogo y se guarda como texto simple. Los borradores de la captura anterior con selección y unidad en JSON siguen siendo legibles: se conserva la selección y se omite su antigua unidad. Los informes publicados conservan sus snapshots y su presentación histórica.
* **D3-13** Los seis parámetros numéricos de Coagulación tienen unidades editables de texto libre de hasta 30 caracteres. Inicialmente se muestran las unidades de su versión de catálogo (`min`, `seg`, `%`); INR continúa sin unidad predeterminada. La personalización se guarda por resultado en `resultados_borrador.unidad_override` mediante la migración `0021`, separada del valor numérico Decimal. `NULL` restablece la unidad del catálogo; texto vacío representa una unidad borrada explícitamente. Editar una unidad no convierte números ni modifica fórmulas, referencias o banderas. Una unidad sola no constituye resultado ni permite publicar un informe vacío. Guardado, cálculo y vista previa aceptan `unidades_override` sólo para Coagulación y validan alcance y permisos en backend; los resultados utilizados congelan su unidad en nuevos snapshots.
* **D3-14** GOT/AST y GPT/ALT del Hepatograma / Perfil Hepático usan **VR: Hasta 40 UI/L**, con límite superior inclusivo: 40 es Normal y cualquier valor mayor que 40 es Alto. La fuente es `definitions.py`; la migración `0022` sincroniza las referencias genéricas del catálogo en sus versiones existentes. Se conservan los resultados capturados, las referencias personalizadas por orden y los snapshots de informes publicados.

## 13. Decisiones de Fase 3.5 (correcciones)

* **D35-01** No hay CORS: frontend y API comparten origen (Caddy en producción, proxy de Vite en desarrollo). No se sirve el frontend desde el backend. `/docs` y `/openapi.json` están desactivados salvo `ENABLE_DOCS=true`.
* **D35-02** La política de sesión la configura el entorno del backend: `MODO_PRODUCCION`, `SESSION_IDLE_TIMEOUT_MINUTES` (60 por defecto) y `SESSION_ABSOLUTE_TIMEOUT_HOURS` (24 por defecto). El modo de desarrollo no desactiva el tope absoluto, cookies seguras en producción, autorización ni políticas de contraseña.
* **D35-03** La inactividad se mide con señales autenticadas de interacción real (ratón, teclado, toque o desplazamiento) que el navegador comunica en el latido (`actividad: true`). El backend no confía en timestamps del cliente; heartbeat automático, refresh y peticiones API no renuevan inactividad.
* **D35-04** Los tests solo corren contra bases cuyo nombre termina en `_test`.
* **D35-05** Los cambios de esquema de esta fase se hacen con la migración Alembic `0002`. El contenedor del backend ejecuta `alembic upgrade head` al arrancar.

## 14. Decisiones de Fase 3.6 (interfaz)

* **D36-01** La interfaz sigue `docs/UX_GUIDE.md`. Lo que no existe aún no se muestra (sin "Próximamente").
* **D36-02** La orden se crea al pulsar **Empezar a calcular** en la ventana de confirmación (no antes), para no dejar borradores vacíos.
* **D36-03** "Fecha y hora de inicio" se guarda en `ordenes.fecha_hora_toma_muestra`, editable y precargada con la hora actual. (PENDIENTE de confirmar con el laboratorio si "inicio del estudio" y "toma de muestra" deben ser campos distintos.)
* **D36-04** El menú pasa a barra lateral izquierda desplegable. "Pendientes" es una entrada propia con contador.
* **D36-05** La vista previa de la captura es una representación en pantalla; el PDF oficial es de la Fase 5.
* **D36-06** FUERA de esta fase: Estudio instantáneo, rol VISITANTE, notificaciones/temporizadores e impresión (ver `PROPUESTA_FUNCIONES_NUEVAS.md`).

## 15. Captura decimal y vista previa de pantalla

* **DC-01** Todo campo numérico acepta coma o punto decimal, incluidos Glóbulos Blancos, VES, Plaquetas, GOT/AST, GPT/ALT, Fosfatasa Alcalina y GGT. `decimales = 0` no permite quitar el separador ni redondear la entrada; se conserva la precisión capturada, hasta seis decimales (D3-04). Los miles se agrupan únicamente para mostrar; la API recibe texto canónico sin agrupación.
* **DC-02** La vista previa se actualiza automáticamente al cambiar resultados, referencias, observaciones, etiquetas o estudios. Es de pantalla y solo permite ampliar a pantalla completa. El backend entrega imágenes de las páginas, sin ofrecer un PDF preliminar descargable. Impresión y descarga de PDF permanecen reservadas al informe oficial `VIGENTE` y sus permisos.
* **DC-03** No se dibujan campos vacíos, defectos virtuales sin confirmar, derivados sin entradas ni estudios sin resultados. El cero capturado sí se muestra. Un derivado no calculable por regla o división por cero se muestra como «No calculable».
* **DC-04** Todas las páginas son Carta vertical (215,9 × 279,4 mm), con membrete SVG repetido. El contenido comienza a 38 mm del borde superior; la vista previa y el informe oficial usan la misma plantilla paginada. Los nuevos informes congelan el separador decimal en el snapshot para conservar su formato al reimprimir.

## 16. EGO e inmunoserología

* **DS-01** El final del microscópico de EGO se ordena: Cristales, Cilindros, Bacterias, Otros.
* **DS-02** Inmunoserología no presenta banderas. Las pruebas cualitativas llevan solo prueba y resultado en el informe, excepto las tres pruebas del grupo **SEROLOGIA**, que imprimen también Muestra y Método; las de entrada con unidad conservan Unidad; V. Ref. se reserva a PCR semicuantitativa, FR y ASTO. En captura, los controles tienen su columna **Captura** y el resultado final aparece al final.
* **DS-03** Los cuatro Widal usan Negativo/Positivo. Positivo habilita 1/20, 1/40, 1/80, 1/160, 1/320 u Otro (texto 1/n). Son títulos sin cálculo de concentración y sin «dilución» como unidad física. La serie fue confirmada por el usuario.
* **DS-04** PCR semicuantitativa usa MONLAB (6 mg/L), TECO (0,8 mg/dL) o sensibilidad propia; mantiene la dilución 1/n para el cálculo. FR usa Negativo/Positivo, dilución y sensibilidad de 8 UI/mL o propia; no solicita lote, vencimiento ni controles. ASTO conserva sensibilidad y cálculo, con sensibilidad estándar de 200 UI/mL o propia y etiquetas Negativo/Positivo. VDRL es una selección Negativo/Positivo.
* **DS-05** Las configuraciones, fórmulas y sensibilidades viven en `definitions.py`, se publican en la configuración del catálogo y se calculan con Decimal mediante el motor seguro. La captura estructurada se guarda en `valor_texto`; resultado, unidad y referencia se congelan en el snapshot. Un positivo con entrada incompleta no puede publicarse. Los textos de borradores anteriores siguen siendo legibles, sin reescribir informes publicados.

## 17. Campos utilizados y ampliación del catálogo

* **DA-01** Un informe incluye únicamente campos utilizados. Vacío, espacios, `-`, `--` o guiones de presentación no son resultados. No se dibujan sus filas ni secciones o estudios vacíos, tanto en pantalla como en PDF. El cero sí es un resultado. Se permite publicar una selección de campos de los estudios solicitados; nunca un informe sin resultados.
* **DA-02** PCR, FR y ASTO negativos se informan únicamente como «Negativo», sin sensibilidad, reactivo, unidad ni referencia en esa fila. VDRL ofrece `--`, Negativo y Positivo incluso al abrir un catálogo anterior.
* **DA-03** Parasitología es independiente de Inmunoserología y conserva Helicobacter pylori (heces) y Sangre oculta en heces como selecciones Negativo/Positivo, sin Unidad, V. Ref. ni Bandera. Helicobacter pylori (suero) pasa a Inmunoserología; los tres subestudios quedan disponibles bajo el grupo seleccionable `PARASITOLOGIA`, que en la interfaz se titula **SEROLOGIA**. H. pylori en heces y Sangre oculta en heces también permanecen en Parasitología. En Inmunoserología, H. pylori en suero y heces se titulan **HELICOBACTER PYLORI** y se distinguen por Muestra; suero conserva Negativo/Positivo y heces junto con Sangre oculta usan Reactivo/No reactivo. Los tres muestran Muestra y Método tanto en captura como en el informe; Sangre oculta se titula **SANGRE OCULTA EN HECES**. `CHAGAS` es un subestudio seleccionable Negativo/Positivo. La migración `0016` crea versiones nuevas y traslada resultados de suero en borradores a Inmunoserología; `0019` agrega Muestra y Método; `0020` incorpora CHAGAS y sensibilidad propia de ASTO. Las migraciones conservan catálogos históricos e informes publicados. Moco fecal es una sección de diez campos de texto libre, en este orden: Aspecto, Restos alimenticios, PH, Moco fecal, Flora bacteriana, Eritrocitos, Leucocitos, Polimorfonucleares, Mononucleares y Coproparasitología. Estos diez campos no tienen límite de caracteres, no se precargan y no agregan cálculos ni rangos. La migración `0012` amplía todas las versiones de Parasitología y conserva el código/id y el texto previo de MOCO_FECAL; no altera resultados ni snapshots. Los campos vacíos siguen omitiéndose del informe.
* **DA-04** Perfil Cardíaco incluye Troponina cualitativa (Negativo/Positivo, sin unidad, referencia ni bandera), CPK (25–192 UI/L), CK-MB (0–24 UI/L) y LDH (200–400 UI/L, inclusivo). En Perfil Pancreático, la fila UI/L se presenta como Lipasa sérica (10–150 UI/L, inclusivo) y la fila UA/dL como Amilasa sérica (hasta 120 UA/dL, inclusivo); se conservan las unidades y referencias de cada fila. Los numéricos tienen banderas y referencias editables por orden. La migración `0009` sincroniza el orden y las referencias del catálogo; conserva resultados, referencias personalizadas por orden e informes publicados.
* **DA-05** Química añade Glicemia post prandial (misma referencia que Glicemia), Alcoholemia (0–100 mg/dL, inclusivo) y LDH (200–400 UI/L, inclusivo). Los rangos provienen del catálogo y sus modificaciones se guardan por orden.

* **DA-06** Coproparasitológico simple es texto libre sin límite de caracteres. En captura e informe el título del subestudio basta: no se repite el nombre del campo junto al resultado. Seriado usa tres muestras iniciales, que no se eliminan, y permite añadir más, numeradas consecutivamente. Cada muestra admite fecha real, hora `HH:mm`, turno `MAÑANA`/`TARDE`/`NOCHE` y resultado de texto libre. Hora y turno son opcionales; una fila iniciada sigue exigiendo fecha y resultado para publicar. La frase «No se observan formas parasitarias» es una sugerencia gris: sólo se convierte en resultado al aceptarla explícitamente con un clic. Abrir la captura, añadir filas o elegir una fecha nunca inventa ese resultado. Una fila vacía no se informa; una fila iniciada se guarda parcialmente. Fecha y hora no pueden ser futuras y se validan en el backend. Las muestras se guardan estructuradas en valor_texto; el snapshot congela sus valores, incluida hora y turno cuando existen. La migración `0013` conserva IDs, resultados anteriores e informes publicados. El texto histórico de Seriado sigue visible sin inventar fechas y se reemplaza por muestras sólo por acción explícita del operador. Muestras guardadas antes de hora y turno se reabren con esos datos vacíos.

## 18. Presentación oficial y publicación (19/11/2026)

* **DI-01** El informe publicado se visualiza exclusivamente con el documento generado por la plantilla backend. Mientras carga el PDF se muestra un estado de espera, sin montar una plantilla HTML alternativa. La versión del documento se fija a la versión de los metadatos resueltos; los cambios de folio o versión cancelan las solicitudes anteriores.
* **DI-02** El hash del snapshot, el número de versión y los timestamps completos permanecen en el almacenamiento y la trazabilidad, pero no se imprimen en el cuerpo del informe. El folio permanece visible.
* **DI-03** Se imprimen **Fecha: día/mes/año**, **Hora de toma de muestra** y **Hora de entrega de resultado** en `America/La_Paz`. La fecha del informe oficial y la hora de entrega provienen de su publicación. La hora de toma usa `fecha_hora_toma_muestra`, con la creación de la orden como respaldo. Los nuevos snapshots congelan también `orden.creado_en`; para informes anteriores se consulta esa fecha de creación existente sin modificar el snapshot. En borradores, Fecha usa el inicio y la entrega dice «Pendiente de publicación»; una hora ausente nunca se inventa.
* **DI-04** El responsable sigue siendo el autor original. Se presenta con prefijo **LIC.**, sin imprimir matrícula, aunque esté registrada. La línea de firma y el nombre se repiten al pie de cada hoja, con una zona reservada de 48 mm para firma y membrete inferior. La firma conserva su posición aunque sobren espacios después de los resultados.
* **DI-05** Un estudio se mantiene completo si cabe en una página. Puede compartir la hoja anterior sólo si cabe íntegro en el espacio disponible antes de la firma. Si no cabe, empieza en otra hoja. Un estudio mayor que una hoja empieza en hoja nueva después del anterior y continúa con filas sin dividir y encabezados repetidos, respetando el área de firma.
* **DI-06** Versiones desplazadas, papelera y reciclaje se consultan como imágenes de la misma plantilla oficial mediante un endpoint autenticado, sin habilitar descarga PDF ni impresión ni registrar una emisión. `/pdf` mantiene la restricción a `VIGENTE` y su evento de emisión.
* **DI-07** La interfaz espera el guardado confirmado antes de publicar. Un error de persistencia o cambios todavía pendientes detienen la publicación y permiten reintentar. El backend vuelve a validar los resultados utilizados antes de reservar el folio en su transacción existente.

## 19. Estadísticas operativas y catálogo independiente

* **DE-01** `GET /api/estadisticas` devuelve únicamente agregados de actividad y metadatos mínimos de profesionales. BIOQUIMICO consulta sus órdenes como autor original; intentar filtrar otro autor recibe 403. ADMIN consulta el laboratorio y puede filtrar responsable, incluidos profesionales inactivos. La respuesta nunca incluye pacientes, resultados ni snapshots. La consulta administrativa de conjuntos no vacíos se registra como `ADMIN_VE_PRIVADO`, sin contenido clínico.
* **DE-02** El período incluye órdenes por `creado_en`, con fechas inclusivas en `America/La_Paz`, hasta 366 días. Por defecto, últimos 30 días. La serie diaria refleja la fecha de inicio y cuántas órdenes de cada día ya fueron publicadas, aunque la entrega fuera posterior al período; no se presenta como publicaciones efectuadas ese día. Los descartes físicos no forman parte de las órdenes existentes.
* **DE-03** Cada orden y su primera publicación V1 se cuentan una vez. Reediciones V2/V3, vistas previas y reimpresiones no incrementan entregas. Publicaciones después desplazadas, enviadas a papelera o recicladas conservan su primera entrega histórica. El volumen de estudios usa los estudios con parámetros del snapshot de esa primera publicación; no suma estudios solicitados sin resultados.
* **DE-04** Tiempo de respuesta = primera publicación menos toma de muestra, con creación de la orden como respaldo cuando falta la toma. Intervalos negativos o ausentes se excluyen de la mediana y se muestran como entregas «Sin hora válida»; no se convierten en cero. El cero real es válido. Se usa mediana discreta sobre valores NUMERIC y se transmite texto decimal en minutos, sin resultados clínicos ni fórmulas nuevas.
* **DE-05** El filtro de respuesta se aplica a todos los agregados del conjunto: todos, hasta 60 minutos inclusive, más de 60 hasta 240 inclusive, más de 240, o publicadas sin hora válida. Al seleccionar un intervalo quedan sólo órdenes publicadas con dicho intervalo. Los tramos organizan la visualización; no establecen metas clínicas ni criterios de calidad profesional.
* **DE-06** Catálogo pasa a `/catalogo`, sin modificar estudios, fórmulas ni estructura clínica. Perfiles rápidos conservan sus endpoints y permisos personales; sólo se amplía el detalle visible de los estudios y grupos guardados. `/estadisticas` añade un acceso propio para ambos roles.

