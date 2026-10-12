# Informe de Evaluación y Avance — Fase 2 (Catálogo, Pacientes y Órdenes)

> **Documento de registro de avances, decisiones y resultados de la Fase 2 del Sistema LIS.**
> Estado al completarse los **Pasos 5 y 6**: Módulo completo de Órdenes en borrador (Creación, Detección de Duplicados D2-04, Lectura y Privacidad D2-06/D2-07, Edición Optimista D2-02 y Descarte de Borradores).

---

## 1. Resumen Ejecutivo

En este bloque de la **Fase 2**, se implementó en su totalidad la capa de backend para la gestión de **Órdenes de Laboratorio en borrador** (Pasos 5 y 6), manteniendo estricta adherencia a [`db/init/001_schema.sql`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/db/init/001_schema.sql), [`docs/DECISIONES.md`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/docs/DECISIONES.md) y [`PROMPT_FASE_2.md`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/PROMPT_FASE_2.md):

* **Creación de Órdenes (`POST /api/ordenes`)**:
  * Transacción atómica única para alta de paciente + Orden N° 1 (D2-03) o asociación a paciente existente con bloqueo de fila (`SELECT ... FOR UPDATE`).
  * Numeración correlativa por paciente (`numero_orden_paciente = COALESCE(MAX, 0) + 1`, D2-10).
  * Congelamiento de versión activa de cada estudio en `orden_estudios.id_estudio_version` y desglose de grupos en `orden_estudio_grupos`.
  * Cálculo determinista de edad mediante `clock.ahora()` cuando existe fecha de nacimiento (D2-08).
  * **Algoritmo D2-04 de detección de trabajo duplicado**:
    * Granularidad fina: código de estudio directo o `CODIGO:GRUPO` para estudios con selección parcial (Inmunoserología).
    * Bloqueo estricto con HTTP 409 `ORDEN_DUPLICADA_EN_CURSO` si los estudios de la nueva orden son un subconjunto de **un** borrador ajeno en curso (`INCOMPLETO`/`COMPLETO`, no bloqueado).
    * Advertencias informativas (`SOLAPAMIENTO`) revelando únicamente el autor y códigos si existe intersección no cubierta por completo por un único borrador (D2-05).
* **Lectura y Privacidad de Órdenes (`GET /api/ordenes`, `GET /api/ordenes/{id}`)**:
  * Los bioquímicos solo ven sus propias órdenes; acceso a órdenes ajenas responde HTTP 404 para evitar enumeración de recursos (D2-07).
  * Los administradores pueden consultar todas las órdenes y filtrar por autor, auditando accesos privados mediante el evento `ADMIN_VE_PRIVADO` en `log_seguridad` (D2-06). Las consultas vacías no generan registros espurios.
* **Edición de Cabecera (`PATCH /api/ordenes/{id}`)**:
  * Restricción exclusiva al autor; control de concurrencia optimista forzado en base de datos (`UPDATE ... WHERE fila_version = :v`, HTTP 409 `CONFLICTO_VERSION`).
  * Inmutabilidad de estudios, estado y paciente (HTTP 400 `VALIDACION`). Rechazo de edición en órdenes publicadas o bloqueadas (HTTP 409 `CONFLICTO`).
* **Descarte de Borradores (`DELETE /api/ordenes/{id}`)**:
  * Eliminación física en cascada y registro transaccional en `laboratorio.borradores_descartados` con `estaba_bloqueada` y `estado_trabajo` persistidos (HTTP 204). Bloqueo de descarte en órdenes publicadas (HTTP 409).
* **Suite de Pruebas**: Se implementaron y validaron los **Tests 12 al 36** (Órdenes) y el **Test 37** (Regresión global), alcanzando **92 pruebas unitarias y de integración pasando al 100%** contra PostgreSQL real (`lis_test`), sin ninguna prueba omitida (`skipped=0`).

---

## 2. Decisiones de Fase 2 Incorporadas y Validadas

* **D2-01**: Sin captura ni cálculo de resultados en esta fase (alcance estricto).
* **D2-02**: Estudios inmutables en borrador; edición de cabecera vía `PATCH` con control `fila_version`.
* **D2-03**: Alta de paciente y Orden N° 1 en una sola transacción atómica reversible ante errores de validación.
* **D2-04**: Detección granular de trabajo duplicado por estudio y estudio:grupo.
* **D2-05**: Privacidad en advertencias (solo autor y códigos solapados, sin ids de orden ni datos clínicos).
* **D2-06**: Permisos de ADMIN (solo lectura de órdenes auditada con `ADMIN_VE_PRIVADO`).
* **D2-07**: Respuesta HTTP 404 a bioquímicos sobre órdenes ajenas para evitar enumeración.
* **D2-08**: Cálculo de edad con fecha de nacimiento contra `clock.ahora()`.
* **D2-10**: Correlativo por paciente `MAX + 1` protegido por bloqueo optimista / pesimista.

---

## 3. Matriz de Requisitos y Cumplimiento (Pasos 1 al 6)

| # | Componente | Requisito / Regla | Estado | Evidencia / Test |
|---|---|---|---|---|
| 1 | **Pacientes** | Alta de paciente con CI; normalización de mayúsculas y espacios colapsados | ✅ Aprobado | Test 1 (`test_01_alta_con_ci_normaliza_datos`) |
| 2 | **Pacientes** | Regla excluyente: `(sin_ci=True y ci=NULL)` o `(sin_ci=False y ci 5-30 chars)` | ✅ Aprobado | Test 2 (`test_02_regla_excluyente_ci_vs_sin_ci`) |
| 3 | **Pacientes** | CI duplicado responde 409 `CONFLICTO` con `paciente_existente_id`; complemento `""` equivale a `NULL` | ✅ Aprobado | Test 3 (`test_03_ci_duplicado_y_complemento`) |
| 4 | **Pacientes** | Fecha de nacimiento no futura y no anterior a 130 años contra `clock.ahora()` | ✅ Aprobado | Test 4 (`test_04_fecha_nacimiento_limites`) |
| 5 | **Pacientes** | ADMIN puede `GET`; `POST`/`PATCH` dan 403 `PROHIBIDO`; sin token 401; flag cambio clave 403 | ✅ Aprobado | Test 5 (`test_05_permisos_y_estados_autenticacion`) |
| 6 | **Pacientes** | Búsqueda `q` multi-campo insensible a mayúsculas; paginación `{items, total, limit, offset}`; `limit > 100` da 400 | ✅ Aprobado | Test 6 (`test_06_busqueda_paginacion_y_limites`) |
| 7 | **Pacientes** | `PATCH` edita campos permitidos, respeta unicidad de CI y rechaza campos desconocidos con 400 | ✅ Aprobado | Test 7 (`test_07_patch_edicion_unicidad_y_campo_desconocido`) |
| 8 | **Pacientes** | Inexistencia de endpoint `DELETE` físico (responde 404 o 405) | ✅ Aprobado | Test 8 (`test_08_no_existe_delete_pacientes`) |
| 9 | **Catálogo** | 9 estudios activos; solo Inmunoserología con `seleccion_parcial=True` y grupos | ✅ Aprobado | Test 9 (`test_09_estudios_activos_y_seleccion_parcial`) |
| 10 | **Catálogo** | 2 perfiles coincidentes en orden, estudios y grupos con `definitions.py` | ✅ Aprobado | Test 10 (`test_10_perfiles_coinciden_con_definiciones`) |
| 11 | **Catálogo** | Exige autenticación; oculta estudios con `activo = FALSE` | ✅ Aprobado | Test 11 (`test_11_autenticacion_y_estudio_inactivo_oculto`) |
| 12 | **Órdenes** | Orden para paciente existente → 201, `INCOMPLETO`, autor correcto, `numero_orden_paciente` 1 y luego 2 | ✅ Aprobado | Test 12 (`test_12_orden_paciente_existente_numeracion_correlativa`) |
| 13 | **Órdenes** | Alta de paciente + orden atómica; si la orden falla, se revierte y no queda el paciente | ✅ Aprobado | Test 13 (`test_13_alta_paciente_mas_orden_atomica_revierte_si_falla`) |
| 14 | **Órdenes** | Exclusividad `id_paciente` vs `paciente` anidado (ambos o ninguno → 400) | ✅ Aprobado | Test 14 (`test_14_exclusividad_id_paciente_vs_objeto_paciente`) |
| 15 | **Órdenes** | Validación de estudios (sin estudios, repetidos, inexistentes, inactivos → 400) | ✅ Aprobado | Test 15 (`test_15_validaciones_de_estudios`) |
| 16 | **Órdenes** | Validación de grupos (grupos en estudio normal → 400; parcial sin grupos → 400; grupo inválido → 400) | ✅ Aprobado | Test 16 (`test_16_validaciones_de_grupos_en_estudios`) |
| 17 | **Órdenes** | Congelamiento de versión activa de estudios e inserción en `orden_estudio_grupos` | ✅ Aprobado | Test 17 (`test_17_persistencia_version_estudio_y_grupos`) |
| 18 | **Órdenes** | Cálculo de edad con fecha de nacimiento e ignorando enviada; sin fecha de nacimiento exige `edad_anios` | ✅ Aprobado | Test 18 (`test_18_calculo_edad_con_reloj_y_validaciones`) |
| 19 | **Órdenes** | Perfil inexistente → 400; perfil válido se guarda aunque estudios difieran | ✅ Aprobado | Test 19 (`test_19_perfil_existencia_y_discrepancia_permitida`) |
| 20 | **Órdenes** | ADMIN no puede crear órdenes → 403 `PROHIBIDO` | ✅ Aprobado | Test 20 (`test_20_admin_no_puede_crear_ordenes`) |
| 21 | **Órdenes** | Dos creaciones concurrentes para el mismo paciente asignan números 1 y 2 sin colisión 500 | ✅ Aprobado | Test 21 (`test_21_concurrencia_creacion_ordenes_mismo_paciente`) |
| 22 | **Órdenes** | Fecha y hora de toma de muestra futura (> 5 min) → 400 | ✅ Aprobado | Test 22 (`test_22_toma_de_muestra_no_futura`) |
| 23 | **D2-04** | Estudios disjuntos con borrador ajeno → 201 sin advertencias | ✅ Aprobado | Test 23 (`test_23_duplicados_estudios_disjuntos_sin_advertencias`) |
| 24 | **D2-04** | Solapamiento parcial con borrador ajeno → 201 con `advertencias` (`SOLAPAMIENTO`, autor, códigos) | ✅ Aprobado | Test 24 (`test_24_duplicados_solapamiento_parcial_genera_advertencia`) |
| 25 | **D2-04** | Nueva orden ⊆ borrador ajeno → 409 `ORDEN_DUPLICADA_EN_CURSO` (no crea paciente ni orden) | ✅ Aprobado | Test 25 (`test_25_duplicados_subconjunto_bloquea_con_409`) |
| 26 | **D2-04** | No bloquea si el borrador es propio, está `bloqueada`, está `PUBLICADA`, o es de otro paciente | ✅ Aprobado | Test 26 (`test_26_no_bloquea_si_es_propio_bloqueada_publicada_o_distinto_paciente`) |
| 27 | **D2-04** | Granularidad por grupo: `VIH` vs `PCR_SEMICUANT` son disjuntos (201); `VIH` vs `VIH` bloquea (409) | ✅ Aprobado | Test 27 (`test_27_granularidad_por_grupo`) |
| 28 | **D2-04** | Nueva ⊄ ningún borrador individual (cubierta solo por la unión de dos ajenos) → no bloquea (solo advertencias) | ✅ Aprobado | Test 28 (`test_28_cubierta_solo_por_union_no_bloquea`) |
| 29 | **Lectura** | BIOQUIMICO lista solo sus órdenes con filtros de `estado` e `id_paciente` | ✅ Aprobado | Test 29 (`test_29_bioquimico_lista_solo_sus_ordenes_y_filtros`) |
| 30 | **Lectura** | `GET /api/ordenes/{id}` de orden ajena para BIOQUIMICO responde 404 (D2-07) | ✅ Aprobado | Test 30 (`test_30_get_orden_ajena_responde_404_para_bioquimico`) |
| 31 | **Lectura** | ADMIN lista todas y registra un evento `ADMIN_VE_PRIVADO`; `GET` ajena registra `id_objetivo`; vacía no audita | ✅ Aprobado | Test 31 (`test_31_admin_lista_todas_y_audita_admin_ve_privado`) |
| 32 | **Lectura** | ADMIN no puede `PATCH` ni `DELETE` órdenes → 403 `PROHIBIDO` | ✅ Aprobado | Test 32 (`test_32_admin_no_puede_patch_ni_delete`) |
| 33 | **Edición** | `PATCH` con `fila_version` correcta incrementa versión; incorrecta → 409 `CONFLICTO_VERSION`; concurrencia optimista atómica | ✅ Aprobado | Test 33 (`test_33_patch_fila_version_y_concurrencia_optimista`) |
| 34 | **Edición** | `PATCH` con campos inmutables (`estudios`, `estado`, `id_paciente`) responde 400 | ✅ Aprobado | Test 34 (`test_34_patch_campos_prohibidos`) |
| 35 | **Descarte** | `DELETE` por autor → 204, borrado en cascada, registro en `borradores_descartados`; otro BIO → 404; ADMIN → 403; `PUBLICADA` → 409 | ✅ Aprobado | Test 35 (`test_35_delete_descarte_de_borrador_y_registro_historico`) |
| 36 | **Esquema BD** | Inserción de orden sin estudios a nivel BD dispara constraint trigger y revierte la transacción | ✅ Aprobado | Test 36 (`test_36_trigger_orden_requiere_estudios_a_nivel_bd`) |
| 37 | **Regresión** | Todos los 92 tests de la suite pasan satisfactoriamente con `skipped=0` | ✅ Aprobado | Test 37 (`Ran 92 tests ... OK, skipped=0`) |

---

## 4. Estado de la Suite de Pruebas

Ejecutada contra PostgreSQL 16 real en el contenedor `lis_db_1` (`TEST_DATABASE_URL` sobre base de datos `lis_test` recreada con `001_schema.sql` y `002_seed_catalogo.sql`):

* **Línea base previa (Fase 1 / 1.5)**: 56 pruebas aprobadas.
* **Catálogo Clínico (Tests 9 al 11)**: +3 pruebas aprobadas.
* **Módulo de Pacientes (Tests 1 al 8)**: +8 pruebas aprobadas.
* **Módulo de Órdenes y Concurrencia (Tests 12 al 36)**: +25 pruebas aprobadas.
* **Total ejecutado**: **92 tests**.
* **Resultado**: `OK` (0 fallos, 0 errores, 0 omisiones / `skipped=0`).
* **Tiempo total de ejecución**: ~38 segundos.

---

## 5. Frontend — Bloque 4: Catálogo y Pacientes (Completado)

Se implementó y compiló exitosamente (`tsc -b && vite build`) la interfaz de usuario para el módulo de Pacientes y Catálogo Clínico:

* **Navegación y Menú ([`src/components/Layout.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/components/Layout.tsx))**:
  * Habilitada la sección activa **Pacientes** (`/pacientes`) en la barra de navegación principal.
  * Secciones **Órdenes** e **Informes** conservadas como `Próximamente` con indicador deshabilitado accesible.
* **Cliente de API ([`src/api/pacientes.ts`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/api/pacientes.ts) y [`src/api/catalogo.ts`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/api/catalogo.ts))**:
  * Conectado mediante [`apiClient`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/api/client.ts) con almacenamiento de token JWT estrictamente en memoria (sin `localStorage` ni `sessionStorage`).
* **Vista Principal de Pacientes ([`src/features/pacientes/PacientesPage.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/features/pacientes/PacientesPage.tsx))**:
  * Buscador rápido con debounce de 300 ms consultando `q` (CI, nombres, apellidos).
  * Tabla paginada con selector de límite (10, 25, 50), botones Anterior/Siguiente y conteo total.
  * Ocultamiento estricto de botones de acción de escritura (alta/edición) para usuarios con rol `ADMIN`.
* **Formulario de Alta y Edición ([`src/features/pacientes/PacienteFormModal.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/features/pacientes/PacienteFormModal.tsx))**:
  * Control del campo "Sin CI": al marcarlo desactiva y limpia CI / complemento; al desmarcarlo exige longitud de 5 a 30 caracteres.
  * Normalización automática a mayúsculas para CI/complemento y colapso de espacios múltiples en nombres.
  * Manejo del error HTTP 409 `CONFLICTO` exponiendo banner destacado con acción para navegar a la ficha del paciente existente (`paciente_existente_id`).
* **Ficha Clínica del Paciente ([`src/features/pacientes/PacienteDetallePage.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/features/pacientes/PacienteDetallePage.tsx))**:
  * Resumen de datos demográficos y biológicos, cálculo de edad cumplida y enlace directo a edición.
  * Sección reservada de órdenes clínicas lista para enlazar en el Bloque 5.
* **Visor de Catálogo Clínico ([`src/features/pacientes/CatalogoModal.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/features/pacientes/CatalogoModal.tsx))**:
  * Modal interactivo que consulta `GET /api/catalogo/estudios` y `GET /api/catalogo/perfiles`, exponiendo los 9 estudios activos (con desglose de grupos para Inmunoserología) y los 2 perfiles preconfigurados.

---

## 6. Frontend — Bloque 5: Módulo de Órdenes y Cierre de Fase 2 (Completado)

Se implementó, integró y validó en su totalidad el módulo frontend de **Órdenes Clínicas**, completando el ciclo funcional de la Fase 2 con compilación limpia (`tsc -b && vite build`):

* **Navegación Institucional ([`src/components/Layout.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/components/Layout.tsx))**:
  * Habilitada la sección activa **Órdenes** (`/ordenes`) en la barra superior.
  * La sección **Informes** se mantiene visible y deshabilitada con el distintivo `Próximamente` (destinada a la Fase 3).
* **Enrutamiento Protegido ([`src/App.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/App.tsx))**:
  * Registradas las rutas `/ordenes` (Bandeja general), `/ordenes/nueva` (Asistente protegido exclusivo para `BIOQUIMICO`) y `/ordenes/:id` (Ficha de detalle).
* **Asistente de Creación de Órdenes ([`src/features/ordenes/NuevaOrdenPage.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/features/ordenes/NuevaOrdenPage.tsx))**:
  * **Sección 1 — Paciente**: Selección de paciente existente con buscador reactivo (debounce 300 ms) o alta rápida integrada en la misma transacción atómica (con soporte de regla CI vs Sin CI y normalización).
  * **Sección 2 — Catálogo y Estudios**: Preselección mediante perfiles clínicos (`HC-QMC-SEROL-EGO`, etc.) permitiendo al profesional marcar o desmarcar estudios libremente.
  * **Inmunoserología (D2-09)**: Casillas específicas por grupo con etiquetas provisionales (código humanizado transformando guiones bajos a espacios) y lista de parámetros en texto secundario.
  * **Sección 3 — Datos de la Orden**: Captura de origen de solicitud, médico, pieza/sala, toma de muestra y edad calculada automáticamente contra fecha de nacimiento (o manual si no dispone de fecha).
  * **Manejo Clínico de Duplicados (D2-04 / D2-05)**:
    * **Advertencia de Solapamiento**: Banner visible ante respuesta 201 con advertencias, informando el nombre del colega y los códigos concurrentes (sin exponer identificadores internos).
    * **Bloqueo Estricto 409 (`ORDEN_DUPLICADA_EN_CURSO`)**: Tarjeta de bloqueo institucional informando el nombre del colega responsable del trabajo en curso y los estudios que impiden la duplicación, sin alternativa de omisión por directiva D2-04.
* **Bandeja de Órdenes ([`src/features/ordenes/OrdenesPage.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/features/ordenes/OrdenesPage.tsx))**:
  * Lista de órdenes propias para bioquímicos y supervisión institucional para administradores.
  * Filtros por estado (`INCOMPLETO`, `COMPLETO`, `PUBLICADA`) y búsqueda por paciente con debounce de 300 ms.
  * Paginación dinámica y badges de estado y bloqueo concurrente.
  * Diálogo modal de confirmación antes de descartar borradores (`DELETE /api/ordenes/:id`).
* **Detalle y Edición de Orden ([`src/features/ordenes/OrdenDetallePage.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/features/ordenes/OrdenDetallePage.tsx))**:
  * Visualización completa de cabecera, paciente y determinaciones congeladas según la versión de catálogo.
  * Edición de cabecera (`PATCH /api/ordenes/:id`) enviando `fila_version` para control de concurrencia optimista, manejando elegantemente el error 409 `CONFLICTO_VERSION`.
  * Acción de descarte de borrador (código 204) con diálogo de confirmación y redirección.
  * Panel informativo reservando la captura de mediciones y cálculo de fórmulas para la Fase 3.
* **Control Estricto de Roles (§6, §9)**:
  * Si el usuario autenticado tiene el rol `ADMIN`, los botones de crear orden (`+ Nueva Orden`), editar cabecera (`✏️ Editar Cabecera`) y descartar borrador (`🗑️ Descartar`) se ocultan rigurosamente en toda la interfaz.
* **Vinculación en Ficha de Paciente ([`src/features/pacientes/PacienteDetallePage.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/features/pacientes/PacienteDetallePage.tsx))**:
  * Botón `+ Nueva Orden` vinculado con parámetro `?id_paciente=`, y tabla activa de historial de órdenes de dicho paciente.
* **Seguridad y Token en Memoria**:
  * Exclusividad del cliente HTTP en memoria (`src/api/client.ts`), sin persistencia de tokens en `localStorage` o `sessionStorage`.

---

## 7. Conclusión y Cierre de la Fase 2

La **Fase 2 (Catálogo, Pacientes y Órdenes)** ha sido completada en su totalidad tanto en la capa de Backend (Pasos 1 al 6) como en la capa de Frontend (Bloques 4 y 5):

1. **Backend**: 92 pruebas automatizadas pasando al 100% (`OK`, 0 errores, 0 fallos, `skipped=0`).
2. **Frontend**: Compilación exitosa en producción (`tsc -b && vite build` OK), interfaz clínica reactiva, soporte integral de directivas D2-01 a D2-10 y límites de rol estrictamente verificados.
3. **Límite Clínico Respetado**: Sin intrusión de captura de resultados o cálculo analítico, dejando la arquitectura en estado óptimo para el arranque de la **Fase 3**.

