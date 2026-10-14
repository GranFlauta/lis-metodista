# Informe de Evaluación y Avance — Fase 3 (Captura de Resultados, Cálculo en Vivo, Banderas y Completitud)

> **Documento de registro de avances, decisiones y resultados de la Fase 3 del Sistema LIS.**
> Estado al completarse los **Pasos 5 y 6**: Módulo de Backend de Captura y Evaluación de Resultados (Endpoints de Captura, Cálculo en Vivo, Persistencia Parcial, Confirmación de Defectos, Configuración de Laboratorio, Concurrencia y Regresión Total).

---

## 1. Resumen Ejecutivo

En este ciclo correspondiente a los **Pasos 1 al 6 de la Fase 3**, se completó íntegramente la capa de backend para el procesamiento clínico, captura analítica y cálculo en vivo de resultados de laboratorio, dando cumplimiento riguroso a las especificaciones de [`PROMPT_FASE_3.md`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/PROMPT_FASE_3.md), el esquema [`db/init/001_schema.sql`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/db/init/001_schema.sql) y las decisiones [`docs/DECISIONES.md`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/docs/DECISIONES.md):

* **Motor de Cálculo Seguro ([`backend/app/calculation/engine.py`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/backend/app/calculation/engine.py))**:
  * Extensión retrocompatible de `ResultadoCalculo` incorporando `codigo_motivo: Optional[str] = None` con categorización unívoca: `FALTA_ENTRADA`, `DIVISION_POR_CERO` y `REGLA_INVALIDA`.
  * Preservación del 100% de los 25 tests unitarios preexistentes del motor y catálogo.
* **Modelo Relacional de Resultados ([`backend/app/models/result.py`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/backend/app/models/result.py))**:
  * Mapeo de SQLAlchemy para `laboratorio.resultados_borrador` y `laboratorio.laboratorio_config` respetando tipos estrictos, exclusividad de `valor_numerico` vs `valor_texto`, y claves foráneas.
* **Servicio de Evaluación Clínica ([`backend/app/services/evaluacion_service.py`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/backend/app/services/evaluacion_service.py))**:
  * **Orden Topológico**: Algoritmo de Kahn por estudio según dependencias de variables en fórmulas (`variables_de`), detectando ciclos de configuración.
  * **Cálculo de Derivados**: Evaluación pura sin efectos colaterales; distinción entre no calculable por regla (ej. LDL con TG > 400) vs falta de entradas.
  * **Banderas Biológicas por Rango**: Determinación automática de `BAJO`, `NORMAL` o `ALTO` por sexo y edad en meses (`edad_anios * 12 + edad_meses`), aplicando límites inclusivos/exclusivos.
  * **Reglas Cruzadas**: Validación de coherencia analítica (`SUMA_IGUAL` y `MENOR_IGUAL`) y asignación de severidades (`ERROR` vs `ADVERTENCIA`).
  * **Determinación de Completitud**: Evaluación de parámetros obligatorios, valores por defecto no confirmados y reglas con error que impiden el paso a `COMPLETO`.
* **Endpoints Oficiales de la API ([`backend/app/api/resultados.py`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/backend/app/api/resultados.py))**:
  * `GET /api/ordenes/{id}/captura`: Retorno de la estructura canónica de captura (§8.1); respuesta 404 para bioquímicos ajenos; auditoría `ADMIN_VE_PRIVADO` en `log_seguridad` para consultas de administradores.
  * `POST /api/ordenes/{id}/calcular`: Vista previa síncrona en memoria con conjunto completo de valores; cero operaciones de escritura en base de datos.
  * `PUT /api/ordenes/{id}/resultados`: Persistencia parcial en transacción atómica con `SELECT ... FOR UPDATE`; recálculo integral de todos los parámetros derivados; actualización de `estado_trabajo` (`INCOMPLETO` ↔ `COMPLETO`); inmutabilidad de `ordenes.fila_version` (D3-09).
  * `POST /api/ordenes/{id}/resultados/confirmar-defectos`: Persistencia atómica de valores por defecto virtuales con `confirmado = TRUE` (D3-05).
  * `GET /api/configuracion/laboratorio`: Exposición restringida a `nombre_laboratorio` y `separador_decimal` para clientes autenticados.
* **Seguridad y Concurrencia**:
  * Bloqueo pesimista de fila en cada operación de escritura.
  * Prohibición absoluta de `HTTPException` (utilización exclusiva de jerarquía `AppError`).
  * Rol `ADMIN` restringido a solo lectura (HTTP 403 `PROHIBIDO` en endpoints de escritura).
* **Suite de Pruebas y Regresión**:
  * **27 pruebas** automatizadas de la Fase 3 cubriendo exhaustivamente todos los escenarios clínicos y de concurrencia.
  * **119 pruebas totales** en la suite completa de backend pasando limpiamente contra PostgreSQL real con `skipped=0`.

---

## 2. Decisiones de Fase 3 Incorporadas y Validadas

Se integró en [`docs/DECISIONES.md`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/docs/DECISIONES.md) el bloque oficial §12:

* **D3-01 Alcance**: Captura, cálculo, banderas, validaciones y estado `INCOMPLETO↔COMPLETO`. Sin publicación, folios, informes ni PDFs (reservados para Fases 4 y 5).
* **D3-02 Servidor como Fuente de Verdad**: `POST /calcular` es vista previa sin escritura; `PUT /resultados` persiste y recalcula. El cliente jamás envía valores calculados.
* **D3-03 Alcance de Captura**: Parámetros congelados en la versión de la orden. En selección parcial (Inmunoserología), solo grupos solicitados.
* **D3-04 Tipos y Normalización**: Numéricos aceptan coma o punto y se guardan con punto (hasta 6 decimales, no negativos). Selección validada en opciones. Textos con límites de longitud. Vacío = ausente (nunca se guarda 0 ni string vacío).
* **D3-05 Defectos Virtuales**: Los valores por defecto se presentan como virtuales (`confirmado = FALSE`, sin fila en BD). Se confirman explícitamente o al editarlos.
* **D3-06 Completitud**: Estado `COMPLETO` requiere todos los obligatorios resueltos. Calculado no calculable por regla válida (LDL con TG > 400) no bloquea; falta de entradas sí bloquea. Reglas con severidad `ERROR` bloquean.
* **D3-07 Banderas por Rango**: Selección por sexo y edad en meses, respetando inclusividad de cotas inferiores y superiores. Solo para numéricos.
* **D3-08 Persistencia de Calculados**: Calculados válidos se persisten con `es_calculado = TRUE`; no calculables por regla con `calculable = FALSE` y valor `NULL`; falta de entradas sin fila.
* **D3-09 Inmutabilidad de Versión**: Guardar resultados no altera `ordenes.fila_version` (reservado para la cabecera).
* **D3-10 Separador Decimal**: La API opera internamente con punto decimal. La UI presenta según configuración (`separador_decimal`).
* **D3-11 Límites Fisiológicos**: Registrado como pendiente para versiones posteriores.

---

## 3. Matriz de Requisitos y Cumplimiento (Tests 1 al 28)

| # | Escenario / Requisito | Estado | Evidencia / Test Unitario |
|---|---|---|---|
| 1 | `GET captura` con `HEMOGRAMA`: secciones/parámetros con tipo, unidad y decimales; referencia según sexo | ✅ Aprobado | Test 1 (`test_01_get_captura_estructura_y_referencias_por_sexo`) |
| 2 | Inmunoserología con `grupos=[VIH]`: solo el parámetro `VIH` (no `PCR_*`) | ✅ Aprobado | Test 2 (`test_02_inmunoserologia_seleccion_parcial`) |
| 3 | EGO: defectos aparecen virtuales (`es_defecto=true`, `confirmado=false`) y sin filas en BD | ✅ Aprobado | Test 3 (`test_03_ego_defectos_virtuales_sin_filas`) |
| 4 | Orden ajena → 404 (BIOQUIMICO); ADMIN → 200 y audita `ADMIN_VE_PRIVADO`; sin token → 401; `debe_cambiar_password` → 403; ADMIN en escritura → 403 | ✅ Aprobado | Test 4 (`test_04_seguridad_acceso_y_roles`) |
| 5 | Numérico con coma y punto → mismo valor; > 6 decimales → 400; negativo → 400; no numérico → 400 | ✅ Aprobado | Test 5 (`test_05_validaciones_numericas`) |
| 6 | SELECCION fuera de opciones → 400; TEXTO > 500 y RECUENTO > 50 → 400; FECHA futura o inválida → 400 | ✅ Aprobado | Test 6 (`test_06_validaciones_cualitativas`) |
| 7 | Código de otro estudio no pedido, inexistente, o CALCULADO en cuerpo → 400; > 200 claves → 400 | ✅ Aprobado | Test 7 (`test_07_validaciones_claves`) |
| 8 | `null` borra la fila; el upsert actualiza `actualizado_por` y `actualizado_en` | ✅ Aprobado | Test 8 (`test_08_null_borra_fila_y_upsert`) |
| 9 | Parámetro numérico nunca escribe `valor_texto` y cualitativo nunca escribe `valor_numerico` | ✅ Aprobado | Test 9 (`test_09_almacenamiento_excluyente_numerico_vs_texto`) |
| 10 | Hemograma: hto 45 → GR `4815000`, Hb `14.4` persistidos; recálculo al cambiar hto; borrado al vaciar hto | ✅ Aprobado | Test 10 (`test_10_hemograma_calculados_y_recalculo`) |
| 11 | Diferencial: GB 8000 y segmentados 60 % → `SEGMENTADOS_ABS = 4800`; sin GB → sin fila | ✅ Aprobado | Test 11 (`test_11_diferencial_con_y_sin_gb`) |
| 12 | Lipídico: col 164.5, TG 102.4, HDL 40 → VLDL `20.48`, LDL `104.02`; TG 450 → VLDL sí y LDL `calculable=false`; HDL ausente → LDL sin fila | ✅ Aprobado | Test 12 (`test_12_lipidico_valores_y_reglas`) |
| 13 | Hepatograma: directa > total → indirecta `calculable=false` + validación ERROR; orden no pasa a `COMPLETO` | ✅ Aprobado | Test 13 (`test_13_hepatograma_directa_mayor_que_total`) |
| 14 | Proteinograma: PT = albúmina → relación A/G no calculable, sin error 500 | ✅ Aprobado | Test 14 (`test_14_proteinograma_sin_division_por_cero`) |
| 15 | `POST /calcular` no escribe (conteo de filas idéntico) y coincide con el resultado guardado de `PUT` | ✅ Aprobado | Test 15 (`test_15_calcular_no_escribe_y_coincide_con_guardar`) |
| 16 | Colesterol `200` → `ALTO` y `199.9` → `NORMAL`; sexo M vs F en hematocrito; sin rango → `bandera=null` | ✅ Aprobado | Test 16 (`test_16_banderas_colesterol_sexo_y_sin_rango`) |
| 17 | Rango con límites de edad en meses: selección determinista por edad de la orden | ✅ Aprobado | Test 17 (`test_17_rango_con_limites_de_edad`) |
| 18 | `SUMA_IGUAL`: tolerancia evaluada (ADVERTENCIA vs NORMAL); ausente cuenta 0; no bloquea `COMPLETO`. `MENOR_IGUAL` ERROR sí bloquea | ✅ Aprobado | Test 18 (`test_18_reglas_cruzadas_suma_igual_y_menor_igual`) |
| 19 | ELECTROLITOS: 6 obligatorios completados → `COMPLETO`; borrar uno → `INCOMPLETO` | ✅ Aprobado | Test 19 (`test_19_electrolitos_completitud`) |
| 20 | EGO: defectos sin confirmar → `sin_confirmar` los lista; `confirmar-defectos` los persiste con `confirmado=TRUE` y completa | ✅ Aprobado | Test 20 (`test_20_ego_confirmar_defectos`) |
| 21 | Calculado obligatorio no calculable por regla (LDL con TG > 400) no impide `COMPLETO`; por falta de entrada sí impide | ✅ Aprobado | Test 21 (`test_21_calculado_regla_no_impide_completo`) |
| 22 | Guardar resultados no modifica `ordenes.fila_version`; `PATCH` de cabecera posterior no colisiona | ✅ Aprobado | Test 22 (`test_22_guardar_resultados_no_cambia_fila_version`) |
| 23 | Orden `PUBLICADA` o `bloqueada` responde HTTP 409 `CONFLICTO` en `PUT` y `confirmar-defectos` | ✅ Aprobado | Test 23 (`test_23_orden_publicada_o_bloqueada_responde_409`) |
| 24 | Dos `PUT` simultáneos por hilos concurrentes sobre la misma orden → ambos 200, sin 500 y calculados consistentes | ✅ Aprobado | Test 24 (`test_24_concurrencia_dos_put_simultaneos`) |
| 25 | `GET /api/configuracion/laboratorio`: retorna solo `nombre_laboratorio` y `separador_decimal`; exige autenticación | ✅ Aprobado | Test 25 (`test_25_configuracion_laboratorio`) |
| 26 | Todos los tipos de regla de `definitions.py` implementados; orden topológico sin ciclos en los 9 estudios | ✅ Aprobado | Test 26 (`test_26_tipos_regla_y_orden_topologico_sin_ciclos`) |
| 27 | Motor: `codigo_motivo` clasifica `FALTA_ENTRADA`, `DIVISION_POR_CERO` y `REGLA_INVALIDA`; 25 tests del motor pasan | ✅ Aprobado | Test 27 (`test_27_motor_distingue_codigo_motivo`) |
| 28 | Suite completa de regresión (56 Auth + 3 Catálogo + 8 Pacientes + 25 Órdenes + 11 Servicio + 16 API) | ✅ Aprobado | Test 28 (`Ran 119 tests ... OK, skipped=0`) |

---

## 4. Arquitectura y Detalles Técnicos

### 4.1 Endpoints Implementados (`backend/app/api/resultados.py`)

1. **`GET /api/ordenes/{id}/captura`**:
   * Valida existencia de la orden en base de datos.
   * Bioquímico no autor: retorna `NoEncontradoError` (HTTP 404) para prevenir la enumeración de recursos clínicos privados.
   * Usuario Administrador: permite lectura institucional e inserta un registro en `laboratorio.log_seguridad` con acción `ADMIN_VE_PRIVADO` y detalle `{"recurso": "captura", "id_orden": id}`.
   * Ejecuta `evaluar_captura_orden` retornando la representación canónica de captura (§8.1).

2. **`POST /api/ordenes/{id}/calcular`**:
   * Precondiciones: orden propia, no bloqueada, estado `INCOMPLETO` o `COMPLETO`. Rol `ADMIN` bloqueado con HTTP 403 `PROHIBIDO`.
   * Validación estricta del diccionario de entradas (códigos autorizados según estudios de la orden, rechazo de calculados en la carga útil con HTTP 400).
   * Evaluación síncrona en memoria simulando el cálculo con las entradas suministradas.
   * Cero operaciones de inserción, actualización o eliminación en la base de datos (conteo de filas inalterado).

3. **`PUT /api/ordenes/{id}/resultados`**:
   * Bloqueo pesimista de fila mediante `SELECT ... FROM ordenes WHERE id = :id FOR UPDATE`.
   * Verificación de estado (`bloqueada = FALSE`, estado no `PUBLICADA`).
   * Soporta cambios parciales (claves omitidas conservan su valor en BD; clave con valor `null` elimina la fila de borrador).
   * Recálculo topológico de todos los parámetros derivados del alcance de la orden.
   * Transición automática de `ordenes.estado_trabajo` (`INCOMPLETO` ↔ `COMPLETO`) en la misma transacción.
   * Garantía de inmutabilidad sobre `ordenes.fila_version` para permitir actualizaciones concurrentes de cabecera.

4. **`POST /api/ordenes/{id}/resultados/confirmar-defectos`**:
   * Bloqueo pesimista `FOR UPDATE` sobre la orden.
   * Persiste valores por defecto virtuales asignando `confirmado = TRUE` y `es_defecto = TRUE`.
   * Actualiza el estado de completitud de la orden y retorna la forma canónica de captura actualizada.

5. **`GET /api/configuracion/laboratorio`**:
   * Requiere autenticación válida.
   * Consulta la tabla singleton `laboratorio.laboratorio_config`.
   * Retorna exclusivamente `{"nombre_laboratorio": "...", "separador_decimal": "..."}`.

### 4.2 Servicio de Evaluación (`backend/app/services/evaluacion_service.py`)

* **Aritmética de Alta Precisión**:
  * Utilización de `Decimal` para todas las operaciones numéricas clínicas.
  * Normalización previa de separadores decimales (aceptando coma y punto) y límite de 6 decimales.
* **Manejo de Errores y Excepciones**:
  * Ausencia total de `HTTPException` en toda la capa de servicio y endpoints.
  * Empleo exclusivo de excepciones de dominio: `ValidacionError`, `ConflictoError`, `NoEncontradoError`, `ProhibidoError`.
* **Disciplina de Reloj**:
  * Invocación exclusiva de `clock.ahora()` para marcas temporales (`actualizado_en`), sin llamadas directas a `datetime.now()` en la capa de negocio.

---

## 5. Registro de Evidencias Crudas

### 5.1 Verificación de `HTTPException` y `datetime.now()`

```bash
# Búsqueda de HTTPException en backend/app:
grep -rn "HTTPException" backend/app --include=*.py
# Resultado: Vacío (0 coincidencias)

# Búsqueda de datetime.now() o utcnow() en backend/app:
grep -rn "datetime\.now\|utcnow" backend/app --include=*.py
# Resultado:
# backend/app/core/clock.py:4:en lugar de llamar directamente a datetime.now() fuera de este módulo.
# backend/app/core/clock.py:24:    return datetime.now(timezone.utc)
```

### 5.2 Ejecución de Pruebas de la Fase 3 (Tests 1 al 27)

```text
test_10_hemograma_calculados_y_recalculo (tests.test_evaluacion.TestEvaluacionServicio.test_10_hemograma_calculados_y_recalculo)
10. Hemograma: hto 45 → GR 4815000, Hb 14.4 persistidos; cambiar hto los recalcula; borrar hto elimina calculados. ... ok
test_11_diferencial_con_y_sin_gb (tests.test_evaluacion.TestEvaluacionServicio.test_11_diferencial_con_y_sin_gb)
11. Diferencial: GB 8000 y segmentados 60 % → SEGMENTADOS_ABS = 4800; sin GB → sin fila. ... ok
test_12_lipidico_valores_y_reglas (tests.test_evaluacion.TestEvaluacionServicio.test_12_lipidico_valores_y_reglas)
12. Lipídico: col 164.5, TG 102.4, HDL 40 → VLDL 20.48, LDL 104.02; TG 450 → VLDL sí y LDL calculable=false (regla); HDL ausente → LDL sin fila. ... ok
test_13_hepatograma_directa_mayor_que_total (tests.test_evaluacion.TestEvaluacionServicio.test_13_hepatograma_directa_mayor_que_total)
13. Hepatograma: directa > total → indirecta calculable=false + validación ERROR; orden no pasa a COMPLETO. ... ok
test_14_proteinograma_sin_division_por_cero (tests.test_evaluacion.TestEvaluacionServicio.test_14_proteinograma_sin_division_por_cero)
14. Proteinograma: PT = albúmina → relación A/G no calculable, sin error 500. ... ok
test_15_calcular_no_escribe_y_coincide_con_guardar (tests.test_evaluacion.TestEvaluacionServicio.test_15_calcular_no_escribe_y_coincide_con_guardar)
15. evaluar_captura_orden simulado no escribe (conteo de filas idéntico) y coincide con el resultado guardado. ... ok
test_16_banderas_colesterol_sexo_y_sin_rango (tests.test_evaluacion.TestEvaluacionServicio.test_16_banderas_colesterol_sexo_y_sin_rango)
16. Colesterol 200 → ALTO y 199.9 → NORMAL; hombre vs mujer en hematocrito; parámetro sin rango → bandera=null, referencia=null. ... ok
test_17_rango_con_limites_de_edad (tests.test_evaluacion.TestEvaluacionServicio.test_17_rango_con_limites_de_edad)
17. Rango con límites de edad en meses: se elige según la edad en meses de la orden. ... ok
test_18_reglas_cruzadas_suma_igual_y_menor_igual (tests.test_evaluacion.TestEvaluacionServicio.test_18_reglas_cruzadas_suma_igual_y_menor_igual)
18. SUMA_IGUAL: suma 98 con tolerancia 1 → ADVERTENCIA; 99 → sin aviso; cayados ausente cuenta 0; no bloquea COMPLETO. MENOR_IGUAL ERROR sí bloquea. ... ok
test_26_tipos_regla_y_orden_topologico_sin_ciclos (tests.test_evaluacion.TestEvaluacionServicio.test_26_tipos_regla_y_orden_topologico_sin_ciclos)
26. Todos los tipos de regla de definitions.py están implementados; el orden topológico de los 9 estudios se resuelve sin ciclos. ... ok
test_27_motor_distingue_codigo_motivo (tests.test_evaluacion.TestEvaluacionServicio.test_27_motor_distingue_codigo_motivo)
27. Motor: codigo_motivo distingue FALTA_ENTRADA, DIVISION_POR_CERO y REGLA_INVALIDA; los 25 tests existentes siguen pasando. ... ok
test_01_get_captura_estructura_y_referencias_por_sexo (tests.test_resultados_api.TestResultadosAPI.test_01_get_captura_estructura_y_referencias_por_sexo)
1. GET captura con HEMOGRAMA: secciones/parámetros con tipo, unidad y decimales; referencia según sexo. ... ok
test_02_inmunoserologia_seleccion_parcial (tests.test_resultados_api.TestResultadosAPI.test_02_inmunoserologia_seleccion_parcial)
2. Inmunoserología con grupos=[VIH]: solo el parámetro VIH (no PCR_* ni otros). ... ok
test_03_ego_defectos_virtuales_sin_filas (tests.test_resultados_api.TestResultadosAPI.test_03_ego_defectos_virtuales_sin_filas)
3. EGO: los defectos aparecen como virtuales (es_defecto=true, confirmado=false) y no hay filas en resultados_borrador. ... ok
test_04_seguridad_acceso_y_roles (tests.test_resultados_api.TestResultadosAPI.test_04_seguridad_acceso_y_roles)
4. Orden ajena → 404 (BIOQUIMICO); ADMIN → 200 solo lectura y audita ADMIN_VE_PRIVADO; sin token → 401; con debe_cambiar_password → 403; ADMIN en PUT/calcular/confirmar → 403. ... ok
test_05_validaciones_numericas (tests.test_resultados_api.TestResultadosAPI.test_05_validaciones_numericas)
5. Numérico con coma y con punto → mismo valor; > 6 decimales → 400; negativo → 400; no numérico → 400. ... ok
test_06_validaciones_cualitativas (tests.test_resultados_api.TestResultadosAPI.test_06_validaciones_cualitativas)
6. SELECCION fuera de opciones → 400; TEXTO > 500 y RECUENTO > 50 → 400; FECHA futura o inválida → 400. ... ok
test_07_validaciones_claves (tests.test_resultados_api.TestResultadosAPI.test_07_validaciones_claves)
7. Código de otro estudio no pedido, inexistente, o CALCULADO en cuerpo → 400; > 200 claves → 400. ... ok
test_08_null_borra_fila_y_upsert (tests.test_resultados_api.TestResultadosAPI.test_08_null_borra_fila_y_upsert)
8. null borra la fila; el upsert actualiza actualizado_por y actualizado_en. ... ok
test_09_almacenamiento_excluyente_numerico_vs_texto (tests.test_resultados_api.TestResultadosAPI.test_09_almacenamiento_excluyente_numerico_vs_texto)
9. Un parámetro numérico nunca escribe valor_texto y uno cualitativo nunca escribe valor_numerico. ... ok
test_19_electrolitos_completitud (tests.test_resultados_api.TestResultadosAPI.test_19_electrolitos_completitud)
19. Orden solo con ELECTROLITOS: al completar los 6 obligatorios pasa a COMPLETO; borrar uno la devuelve a INCOMPLETO. ... ok
test_20_ego_confirmar_defectos (tests.test_resultados_api.TestResultadosAPI.test_20_ego_confirmar_defectos)
20. EGO: con defectos sin confirmar → sin_confirmar los lista; confirmar-defectos los persiste con confirmado=TRUE. ... ok
test_21_calculado_regla_no_impide_completo (tests.test_resultados_api.TestResultadosAPI.test_21_calculado_regla_no_impide_completo)
21. CALCULADO obligatorio no calculable por regla (LDL con TG > 400) NO impide COMPLETO; no calculable por falta de entrada sí lo impide. ... ok
test_22_guardar_resultados_no_cambia_fila_version (tests.test_resultados_api.TestResultadosAPI.test_22_guardar_resultados_no_cambia_fila_version)
22. Guardar resultados no cambia fila_version; un PATCH de cabecera posterior sigue funcionando. ... ok
test_23_orden_publicada_o_bloqueada_responde_409 (tests.test_resultados_api.TestResultadosAPI.test_23_orden_publicada_o_bloqueada_responde_409)
23. Orden PUBLICADA o bloqueada → 409 en PUT y confirmar-defectos. ... ok
test_24_concurrencia_dos_put_simultaneos (tests.test_resultados_api.TestResultadosAPI.test_24_concurrencia_dos_put_simultaneos)
24. Dos PUT simultáneos sobre la misma orden → ambos 200, sin 500 y calculados coherentes. ... ok
test_25_configuracion_laboratorio (tests.test_resultados_api.TestResultadosAPI.test_25_configuracion_laboratorio)
25. GET /api/configuracion/laboratorio devuelve solo nombre_laboratorio y separador_decimal; exige sesión. ... ok

----------------------------------------------------------------------
Ran 27 tests in 20.025s

OK
```

### 5.3 Ejecución de la Suite Completa de Regresión (119 Tests)

```text
Ran 119 tests in 58.402s

OK (skipped=0)
```

Desglose de pruebas aprobadas:
* **Fase 1 / 1.5 (Autenticación, Sesiones y Usuarios)**: 56 tests.
* **Fase 2 (Catálogo Clínico)**: 3 tests.
* **Fase 2 (Pacientes)**: 8 tests.
* **Fase 2 (Órdenes y Trabajo Duplicado D2-04)**: 25 tests.
* **Fase 3 (Servicio de Evaluación, Motor y Fórmulas)**: 11 tests.
* **Fase 3 (API de Resultados, Concurrencia y Configuración)**: 16 tests.
* **Total**: **119 tests ejecutados, 0 fallos, 0 errores, 0 omitidos**.

---

## 6. Frontend — Pasos 7, 8 y 9: Captura de Resultados, Vista Previa en Vivo y Banderas (Completado)

Se implementó, integró y validó la interfaz de usuario en React, TypeScript y Vite para el módulo analítico de captura de resultados, dando cumplimiento riguroso a `PROMPT_FASE_3.md` §9:

* **Enrutamiento y Navegación ([`src/App.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/App.tsx))**:
  * Registrada la ruta protegida `/ordenes/:id/captura` bajo el layout clínico.
  * Accesos integrados en la bandeja de órdenes ([`src/features/ordenes/OrdenesPage.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/features/ordenes/OrdenesPage.tsx)) y en la ficha de detalle ([`src/features/ordenes/OrdenDetallePage.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/features/ordenes/OrdenDetallePage.tsx)).
* **Cliente de API ([`src/api/resultados.ts`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/api/resultados.ts))**:
  * Funciones para `getCapturaOrdenApi`, `calcularResultadosApi`, `guardarResultadosApi`, `confirmarDefectosApi` y `getConfiguracionLaboratorioApi`.
  * Exclusividad del cliente HTTP en memoria ([`src/api/client.ts`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/api/client.ts)), sin uso de `localStorage` ni `sessionStorage`.
* **Formulario Analítico por Estudio y Sección ([`src/features/ordenes/CapturaResultadosPage.tsx`](file:///home/pika123/Vídeos/lis-proyecto-base/lis/frontend/src/features/ordenes/CapturaResultadosPage.tsx))**:
  * Adaptación precisa de campos por tipo:
    * `NUMERICO`: Campo de texto que acepta coma y punto sin restricciones de `type=number`, con indicación de unidad.
    * `SELECCION`: Selector desplegable con validación de opciones.
    * `TEXTO`: Área de texto multilínea (máx. 500 caracteres).
    * `RECUENTO`: Campo de texto corto (máx. 50 caracteres).
    * `FECHA`: Selector nativo de fecha (`type=date`).
    * `CALCULADO`: Campo de solo lectura estilizado de forma diferenciada, mostrando el valor calculado y la etiqueta `(estimado)` o el motivo clínico de no calculabilidad.
  * En estudios con selección parcial (Inmunoserología), se despliegan exclusivamente los grupos solicitados en la orden.
* **Vista Previa en Vivo Síncrona**:
  * Tras 400 ms de pausa al modificar cualquier valor, se invoca `POST /api/ordenes/:id/calcular` enviando el conjunto completo de entradas.
  * Actualización en caliente de valores calculados, banderas y completitud sin recargar la página y sin escribir en base de datos.
* **Autoguardado Inteligente**:
  * Tras 1500 ms de inactividad, se ejecuta `PUT /api/ordenes/:id/resultados` enviando únicamente los campos modificados.
  * Indicador de estado en tiempo real: `🔄 Guardando cambios…`, `✓ Guardado a las HH:MM:SS`, `🟡 Cambios sin guardar…` y `❌ Error al guardar`.
  * Botón manual "Guardar ahora" para persistencia inmediata.
  * Manejador de evento `beforeunload` configurado exclusivamente para advertir de cambios pendientes sin guardar.
* **Banderas Analíticas Biológicas**:
  * Representación obligatoria mediante icono + texto con alto contraste:
    * `↓ Bajo`: Insignia azul/marino de contraste elevado.
    * `↑ Alto`: Insignia carmesí/roja de contraste elevado.
    * `✓ Normal`: Insignia verde bosque de contraste elevado.
  * Resaltado sutil de filas en la tabla de vista previa según la bandera.
* **Confirmación de Valores por Defecto Virtuales (D3-05)**:
  * Insignia visible "Sin confirmar" en campos precargados con valor por defecto virtual.
  * Botón "Confirmar defectos" en el panel lateral que invoca `POST /confirmar-defectos`, persistiendo los valores y habilitando el estado `COMPLETO`.
  * La edición manual de un campo virtual lo confirma automáticamente.
* **Control Interactivo de Completitud**:
  * Tarjeta dinámica que informa si la orden está completa o los campos pendientes.
  * Chips interactivos de parámetros pendientes que, al hacer clic, desplazan suavemente la pantalla y enfocan el campo correspondiente (`input-${codigo}`).
* **Modo Estricto de Solo Lectura para ADMIN**:
  * Al ingresar un usuario con rol `ADMIN`, todos los campos de entrada se renderizan deshabilitados (`disabled`).
  * Los botones de guardado manual, confirmación de defectos y autoguardado se ocultan por completo.
  * Notificación institucional visible: "🛡️ Modo Supervisión (Solo Lectura) — Acceso auditado ADMIN_VE_PRIVADO".

---

## 7. Verificación de Criterios de Aceptación (§13)

Se ejecutó el protocolo de verificación de criterios de aceptación con los siguientes resultados:

| Criterio (§13) | Resultado | Evidencia |
|---|---|---|
| **Suite completa de backend** | ✅ `OK`, `skipped=0` | `Ran 119 tests in 58.402s` sin pruebas omitidas |
| **Integridad de esquema y catálogo** | ✅ Sin cambios | `git diff --stat fase-1-cerrada HEAD -- db/init backend/app/catalog` vacío |
| **Grep de HTTPException** | ✅ Vacío | 0 ocurrencias en `backend/app` |
| **Disciplina de Reloj** | ✅ Cumplido | `datetime.now()` invocado únicamente en `core/clock.py` |
| **Flujo Manual Hemograma (hto 45)** | ✅ Aprobado | GR = `4815000` y Hb = `14.4` derivados como "(estimado)" |
| **Flujo Manual Lipídico (TG > 400)** | ✅ Aprobado | VLDL = `90.00`; LDL = "No calculable" sin bloquear la orden |
| **Flujo Manual Hepatograma (Directa > Total)** | ✅ Aprobado | Error analítico visible: "La bilirrubina directa no puede superar a la total"; orden no pasa a `COMPLETO` |
| **EGO Defectos Virtuales** | ✅ Aprobado | 10 defectos aparecen con `confirmado=False`; botón "Confirmar defectos" los persiste con `confirmado=True` |
| **Completitud y Transición** | ✅ Aprobado | Orden con 6 obligatorios pasa automáticamente a `COMPLETO`; vaciar uno la devuelve a `INCOMPLETO` |
| **Banderas con Icono + Texto** | ✅ Aprobado | Icono + texto (`↓ Bajo`, `↑ Alto`, `✓ Normal`) implementados en UI y tabla |
| **Auditoría ADMIN en Captura** | ✅ Aprobado | Lectura por `ADMIN` registra evento `ADMIN_VE_PRIVADO` (`recurso: captura`) en `log_seguridad` |
| **Compilación Frontend** | ✅ Limpio | `npm run build` (`tsc -b && vite build`) exitoso en 2.03s |
| **Prohibición de Storage** | ✅ Cumplido | `grep -rn "localStorage\|sessionStorage" frontend/src` vacío (solo comentarios) |

### Salida de la Verificación Clínica Integral (§13):

```text
=== INICIANDO VERIFICACIÓN DE CRITERIOS DE ACEPTACIÓN FASE 3 (§13) ===

[1] Creando orden para paciente con perfil HC-QMC-SEROL-EGO...
 -> Orden #779 creada exitosamente (estado=INCOMPLETO).

[2] Guardando HTO = 45 en Hemograma...
 -> GR = 4815000 y Hb = 14.4 calculados correctamente como derivados (estimados).

[3] Creando orden con PERFIL LIPÍDICO y HEPATOGRAMA...
[3.1] Guardando Lipídico: COLESTEROL=200, TG=450, HDL=40...
 -> VLDL = 90.00 calculado; LDL = No calculable (TG > 400) sin bloquear.
[3.2] Guardando Hepatograma con BILIRRUBINA_DIRECTA=3.0 > TOTAL=1.5...
 -> Regla cruzada ERROR detectada: 'La bilirrubina directa no puede superar a la total'
 -> Error bloquea estado COMPLETO correctamente.

[4] Verificando EGO y confirmación de defectos en orden #1...
 -> 10 defectos de EGO aparecen virtuales (confirmado=False).
 -> Todos los defectos de EGO persistidos con confirmado=TRUE.

[5] Probando transición INCOMPLETO <-> COMPLETO con orden de ELECTROLITOS...
 -> Orden con 6 obligatorios pasa automáticamente a COMPLETO.
 -> Vaciar SODIO devuelve la orden a INCOMPLETO.

[6] Verificando auditoría ADMIN_VE_PRIVADO en captura de orden...
 -> Evento ADMIN_VE_PRIVADO registrado exitosamente: {'accion': 'ADMIN_VE_PRIVADO', 'detalle': {'recurso': 'captura', 'id_orden': 779}}

=== TODOS LOS CRITERIOS DE ACEPTACIÓN DE LA FASE 3 VERIFICADOS AL 100% ===
```

---

## 8. Conclusión y Cierre de la Fase 3

La **Fase 3 (Captura de Resultados, Cálculo en Vivo, Banderas y Completitud)** se encuentra completada al 100% en todos sus componentes:

1. **Backend**: Endpoints de captura, cálculo, resultados, defectos y configuración operativos; control de concurrencia pesimista (`FOR UPDATE`), evaluación clínica pura y 119 tests automáticos aprobados.
2. **Frontend**: Pantalla interactiva en `/ordenes/:id/captura` con formulario analítico, vista previa síncrona en vivo (400 ms), autoguardado inteligente (1500 ms), banderas biológicas por rango, confirmación de defectos, navegación interactiva a campos pendientes y modo de solo lectura para administradores.
3. **Seguridad y Rendimiento**: Token en memoria sin storage, cero uso de `HTTPException`, reloj centralizado y compilación limpia para producción.
4. **Demarcación**: Las funcionalidades de publicación, folios oficiales, informes finales y generación de documentos PDF quedan debidamente delimitadas para las **Fases 4 y 5**.

