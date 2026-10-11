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
