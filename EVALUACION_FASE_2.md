# Informe de Evaluación y Avance — Fase 2 (Catálogo y Pacientes)

> **Documento de registro de avances, decisiones y resultados de la Fase 2 del Sistema LIS.**
> Estado al completarse el **Paso 4**: Modelos ORM base, Catálogo (lectura) y Módulo de Pacientes.

---

## 1. Resumen Ejecutivo

En este bloque de la **Fase 2**, se consolidaron las bases del dominio clínico y se implementaron por completo los módulos de **Catálogo de Estudios/Perfiles (lectura)** y **Gestión de Pacientes**, manteniendo estricta adherencia a [`db/init/001_schema.sql`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/db/init/001_schema.sql) y [`docs/DECISIONES.md`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/docs/DECISIONES.md):

* **Decisiones D2-01 a D2-11**: Registradas formalmente en `docs/DECISIONES.md` (§11).
* **Modelos ORM de SQLAlchemy**: Creados en `backend/app/models/` para Catálogo, Pacientes y Órdenes (`Estudio`, `EstudioVersion`, `Parametro`, `RangoReferencia`, `Perfil`, `PerfilEstudio`, `Paciente`, `Orden`, `OrdenEstudio`, `OrdenEstudioGrupo`, `BorradorDescartado`), sin `schema=` explícito, utilizando `search_path=laboratorio,public` configurado en `connect_args`.
* **Catálogo Clínico (Paso 3)**: Endpoints `GET /api/catalogo/estudios` y `GET /api/catalogo/perfiles` bajo autenticación con sesión viva, exponiendo los 9 estudios activos (con grupos y parámetros para Inmunoserología) y los 2 perfiles preconfigurados.
* **Módulo de Pacientes (Paso 4)**: CRUD de pacientes con exclusión explícita de `DELETE` físico, validaciones estrictas de CI vs `sin_ci`, normalización de textos, restricción de fechas de nacimiento y manejo de duplicados (HTTP 409 con `paciente_existente_id`).
* **Suite de Pruebas**: Se implementaron y validaron los **Tests 9 al 11** (Catálogo) y **Tests 1 al 8** (Pacientes), alcanzando **67 pruebas unitarias y de integración pasando al 100%** contra PostgreSQL real (`lis_test`), sin ninguna prueba omitida (`skipped`).

---

## 2. Decisiones de Fase 2 Incorporadas (docs/DECISIONES.md)

Se agregaron oficialmente las decisiones clínicas y de arquitectura:
- **D2-01**: Fase 2 no incluye captura ni cálculo de resultados (reservados a Fase 3).
- **D2-02**: Las órdenes se crean con lista final de estudios (inmutables en borrador v1).
- **D2-03**: Alta de paciente y Orden N° 1 en una sola transacción atómica.
- **D2-04**: Algoritmo de detección de trabajo duplicado por estudio/grupo.
- **D2-05**: Privacidad en advertencias de duplicidad (revela autor y estudios, no ids ni resultados).
- **D2-06**: Permisos de ADMIN (solo lectura, auditado con `ADMIN_VE_PRIVADO`).
- **D2-07**: Órdenes ajenas responden 404 a bioquímicos para evitar enumeración.
- **D2-08**: Cálculo automático de edad con fecha de nacimiento y reloj del sistema.
- **D2-09**: Rotulado provisional de grupos de Inmunoserología.
- **D2-10**: Numeración secuencial de órdenes por paciente (`MAX + 1`).
- **D2-11**: Pendiente antes de producción: auditoría de ediciones de pacientes.

---

## 3. Matriz de Requisitos y Cumplimiento

| Componente | Requisito / Regla | Estado | Evidencia / Test |
|---|---|---|---|
| **Catálogo** | 9 estudios activos; solo Inmunoserología con `seleccion_parcial=True` y grupos | ✅ Aprobado | Test 9 (`test_09_estudios_activos_y_seleccion_parcial`) |
| **Catálogo** | 2 perfiles coincidentes en orden, estudios y grupos con `definitions.py` | ✅ Aprobado | Test 10 (`test_10_perfiles_coinciden_con_definiciones`) |
| **Catálogo** | Exige autenticación; oculta estudios con `activo = FALSE` | ✅ Aprobado | Test 11 (`test_11_autenticacion_y_estudio_inactivo_oculto`) |
| **Pacientes** | Alta de paciente con CI; normalización de mayúsculas y espacios colapsados | ✅ Aprobado | Test 1 (`test_01_alta_con_ci_normaliza_datos`) |
| **Pacientes** | Regla excluyente: `(sin_ci=True y ci=NULL)` o `(sin_ci=False y ci 5-30 chars)` | ✅ Aprobado | Test 2 (`test_02_regla_excluyente_ci_vs_sin_ci`) |
| **Pacientes** | CI duplicado responde 409 `CONFLICTO` con `paciente_existente_id`; complemento `""` equivale a `NULL` | ✅ Aprobado | Test 3 (`test_03_ci_duplicado_y_complemento`) |
| **Pacientes** | Fecha de nacimiento no futura y no anterior a 130 años contra `clock.ahora()` | ✅ Aprobado | Test 4 (`test_04_fecha_nacimiento_limites`) |
| **Pacientes** | ADMIN puede `GET`; `POST`/`PATCH` dan 403 `PROHIBIDO`; sin token 401; flag cambio clave 403 | ✅ Aprobado | Test 5 (`test_05_permisos_y_estados_autenticacion`) |
| **Pacientes** | Búsqueda `q` multi-campo insensible a mayúsculas; paginación `{items, total, limit, offset}`; `limit > 100` da 400 | ✅ Aprobado | Test 6 (`test_06_busqueda_paginacion_y_limites`) |
| **Pacientes** | `PATCH` edita campos permitidos, respeta unicidad de CI y rechaza campos desconocidos con 400 | ✅ Aprobado | Test 7 (`test_07_patch_edicion_unicidad_y_campo_desconocido`) |
| **Pacientes** | Inexistencia de endpoint `DELETE` físico (responde 404 o 405) | ✅ Aprobado | Test 8 (`test_08_no_existe_delete_pacientes`) |

---

## 4. Estado de la Suite de Pruebas

Ejecutada contra PostgreSQL 16 real en el contenedor `lis_db_1` (`TEST_DATABASE_URL` sobre base de datos `lis_test` recreada con `001_schema.sql` y `002_seed_catalogo.sql`):

* **Línea base previa (Fase 1 / 1.5)**: 56 pruebas aprobadas.
* **Nuevas pruebas de Catálogo (Tests 9 al 11)**: +3 pruebas aprobadas.
* **Nuevas pruebas de Pacientes (Tests 1 al 8)**: +8 pruebas aprobadas.
* **Total ejecutado**: **67 tests**.
* **Resultado**: `OK` (0 fallos, 0 errores, 0 omisiones / `skipped`).

---

## 5. Próximos Pasos (Paso 5 de la Fase 2)

1. Implementar la creación de órdenes en borrador (`POST /api/ordenes`).
2. Implementar soporte para creación atómica de paciente + Orden N° 1 (D2-03).
3. Implementar algoritmo de detección de duplicados (D2-04: advertencias de solapamiento y 409 `ORDEN_DUPLICADA_EN_CURSO`).
4. Numeración correlativa por paciente (`numero_orden_paciente = MAX + 1`) con bloqueo de fila del paciente.
5. Implementar y aprobar los tests 12 al 28 de órdenes.
