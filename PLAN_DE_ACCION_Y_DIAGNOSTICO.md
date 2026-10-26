# LIS Laboratorio Clínico — Diagnóstico Integral y Plan de Acción Arquitectónico

> **Fecha de diagnóstico y actualización:** 26 de Octubre de 2026  
> **Objetivo:** Radiografía exhaustiva del estado del sistema y hoja de ruta metodológica por fases para implementar:
> 1. Saneamiento de inconsistencias, corrección de scripts y eliminación de parches volátiles.
> 2. Formato canónico de números (miles y decimales clínicos: ej. `1.092.324` y `14,5`).
> 3. Adición y eliminación dinámica de estudios en la orden (con casillas rosa de subestudios para Inmunoserología y auto-cancelación de orden si se eliminan todos los estudios).
> 4. Rangos de referencia editables en tiempo real por orden sin alterar el catálogo maestro, con botón de **"Reestablecer valores de referencia"**.
> 5. Observaciones por estudio (opcionales) y observaciones finales del informe (obligatorias para el documento final).
> 6. Conversión escalable de campos de texto a selección/cálculo (Caso PCR Semicuantitativa con corte TECO/MONLAB y dilución inversa).
> 7. Rol `VISITANTE` (auditor/lector de informes) con blindaje de interfaz contra descarga, copia y captura.

---

## 1. Diagnóstico del Estado Actual del Proyecto

### 1.1 Estado Global y Capas
| Capa | Estado Actual | Diagnóstico de Madurez |
|---|---|---|
| **Base de Datos** | Esquema `001_schema.sql` + Migración `0002_config_sesion.py` + Migración `0003_overrides_observaciones_visitante.py`. | **Sólida y versionada con Alembic.** Se amplió para soportar observaciones (`ordenes`, `orden_estudios`), overrides de rangos (`resultados_borrador`) y el rol `VISITANTE`. |
| **Backend (FastAPI)** | Fases 1, 2, 3 y correcciones 3.5 implementadas. 119 tests con `unittest`. | **Robusto en lógica clínica central.** Motor determinista sin `eval`, bloqueo optimista/pesimista `FOR UPDATE`, sesión por latidos y reloj desacoplado. |
| **Frontend (React + Vite)** | Transición entre la entrega de Fase 3 y la propuesta visual Metodista. | **Inestable por parches recientes.** Se detectaron 2.200 líneas duplicadas en memoria que deben reemplazarse por endpoints oficiales transaccionales. |

---

### 1.2 Hallazgos, Inconsistencias y Errores (Severidad)

#### A. ERRORES FATALES / GRAVES
1. **Script de Terminal `scripts/crear_admin.py` (CORREGIDO ✅)**:
   - **Problema previo:** Importaba `hash_password` en lugar de `get_password_hash`, provocando `ImportError` al ejecutarse.
   - **Estado:** Corregido y probado exitosamente con `scripts/crear_admin.py --help`.
2. **Parche Volátil en Memoria: `catalogoEstudiosPlantillas.ts` (2.200 líneas) y `ordenesMemoria.ts`**:
   - **Problema:** Para simular la adición de estudios en la pantalla de captura sin tocar el backend, se implementó un `Map<number, EstudioCatalogo[]>` en memoria de JavaScript y se duplicó todo el catálogo en TypeScript.
   - **Consecuencia destructiva:** Los estudios agregados de esta forma **no existen en la base de datos** (`laboratorio.orden_estudios`). Al recargar la página (F5) o cambiar de pestaña, los datos se pierden. Además, el backend rechaza persistir resultados de estudios que no forman parte de la orden original. Viola la regla 4 de `AGENTS.md` (*"Fórmulas y rangos viven solo en definitions.py"*).
   - **Solución oficial:** Crear los endpoints en backend para agregar, modificar grupos y eliminar estudios de la orden en borrador.

#### B. ERRORES MEDIOS
3. **Ausencia de Separador de Miles en Resultados Clínicos (CORREGIDO ✅)**:
   - Se creó el módulo `frontend/src/utils/formatoNumerico.ts` con la función canónica `formatearResultadoClinico`.
   - Si `separador_decimal === ','`: miles con `.` y decimales con `,` (`1092324` $\rightarrow$ `1.092.324`, `14.5` $\rightarrow$ `14,5`).
   - Se integró en `CapturaResultadosPage.tsx`.
4. **Rigidez de Rangos de Referencia en BD (RESUELTO EN ESQUEMA ✅)**:
   - Se generó la migración Alembic `0003_overrides_observaciones_visitante.py` agregando `ref_inferior_override`, `ref_superior_override`, `ref_texto_override`, `ref_modificada` a `resultados_borrador`.
5. **Observaciones Clínicas Faltantes (RESUELTO EN ESQUEMA ✅)**:
   - Se agregaron las columnas `observaciones` a `laboratorio.ordenes` y `laboratorio.orden_estudios` en la migración `0003`.

---

## 2. Respuestas Técnicas y Especificaciones Nuevas

### 2.1 Adición y Eliminación Dinámica de Estudios en la Orden
* **Añadir Estudio al Vuelo:**
  - Endpoint oficial: `POST /api/ordenes/{id}/estudios`.
  - Si es **Inmunoserología**, la interfaz despliega el selector de subestudios (casillas rosa de chips: `VIH`, `PCR_SEMICUANT`, `WIDAL`, etc.).
  - Si el bioquímico desea cambiar subestudios después, un botón contextual al lado de Inmunoserología reabre el selector para marcar/desmarcar subestudios.
  - El backend inserta en `laboratorio.orden_estudios` y `orden_estudio_grupos`, garantizando persistencia ante F5.
* **Eliminar Estudio de la Orden:**
  - Endpoint oficial: `DELETE /api/ordenes/{id}/estudios/{id_estudio}`.
  - Elimina en cascada los resultados en borrador de ese estudio.
  - **Regla de Negocio Crítica:** Si se elimina el último estudio de la orden, la orden se auto-cancela y se descarta en `borradores_descartados`, emitiendo el mensaje de advertencia:
    > *"La orden no tiene estudios a realizar. Ha sido cancelada y descartada de forma irreversible; debe crear una nueva orden."*

### 2.2 Rangos de Referencia Editables y Botón "Reestablecer"
* En la captura, la columna "V. Ref." permite modificar los límites inferior/superior o texto de referencia solo para esa orden.
* El backend evalúa la bandera (`BAJO`, `NORMAL`, `ALTO`) frente a este nuevo rango y lo marca como `ref_modificada = TRUE`.
* **Botón "Reestablecer valores de referencia":** Limpia el override en `resultados_borrador` (`ref_modificada = FALSE`), restaurando inmediatamente los valores del catálogo maestro según el sexo y edad del paciente.

### 2.3 Observaciones por Estudio y Observaciones Finales
* **Por estudio:** Campo de texto opcional en la cabecera/pie del estudio activo (persiste en `orden_estudios.observaciones`).
* **Finales del informe:** Campo de texto obligatorio en la orden para publicar el informe oficial (persiste en `ordenes.observaciones`).

### 2.4 PCR Semicuantitativa (Cálculo con Selección y Dilución Inversa)
* Sub-parámetros en el grupo `PCR_SEMICUANT`:
  1. `PCR_CUALITATIVO`: Selección entre `Negativo` y `Positivo`.
  2. `PCR_REACTIVO`: Selección entre `TECO (0.8 mg/dL)`, `MONLAB (6 mg/L)` o `Personalizado`.
  3. `PCR_VALOR_CORTE`: Valor numérico (0.8, 6, o ingresado manualmente).
  4. `PCR_DILUCION`: Selección (`1/2, 1/4, 1/8, 1/16, 1/32, 1/64`) o manual.
  5. `PCR_TITULO`: Calculado automáticamente como:
     $$\text{Resultado} = \text{Punto de Corte} \times \text{Inversa de Dilución}$$
     Ejemplo: $\text{MONLAB } 6 \times 16 = 96\text{ mg/L}$.
* Versionamiento a V2 de `INMUNOSEROLOGIA` para mantener intactos los estudios históricos V1.

---

## 3. Hoja de Ruta Metodológica por Fases

```
[Fase 3.7: Saneamiento y Formato] ──► [Fase 3.8: Estudios y Rangos Dinámicos] ──► [Fase 3.9: Catálogo V2 (PCR)]
        (COMPLETADA HOY)                                                                     │
[Fase 5: Rol Visitante y Blindaje] ◄── [Fase 4: Publicación, Folios e Informes] ◄───────────┘
```

### FASE 3.7: Saneamiento de Parches, Scripts y Formato Numérico (COMPLETADA HOY)
- [x] Corregir `scripts/crear_admin.py` (sustituir `hash_password` por `get_password_hash`).
- [x] Crear `frontend/src/utils/formatoNumerico.ts` para miles (`.`) y decimales (`,`).
- [x] Conectar formateador canónico en `CapturaResultadosPage.tsx` y vista previa.
- [x] Migración Alembic `0003_overrides_observaciones_visitante.py` creada.
- [x] Modelos ORM actualizados en `order.py` y `result.py`.

### FASE 3.8: Gestión Dinámica de Estudios, Rangos Editables y Observaciones (COMPLETADA)
1. **Backend - Endpoints de Gestión de Estudios:**
   - [x] `POST /api/ordenes/{id}/estudios`: Añadir estudio a orden en borrador y persistir en `orden_estudios`.
   - [x] `DELETE /api/ordenes/{id}/estudios/{id_estudio}`: Eliminar estudio; si queda vacía, descartar la orden irreversiblemente (`borradores_descartados`).
   - [x] `PUT /api/ordenes/{id}/estudios/{id_estudio}/grupos`: Modificar subestudios de Inmunoserología.
2. **Backend - Overrides de Rangos y Observaciones:**
   - [x] Soportar `rangos_override` en `/calcular` y `/resultados` con recálculo dinámico de banderas (respetando límites modificados).
   - [x] Soportar guardado y serialización de `observaciones` por estudio (`orden_estudios.observaciones`) y observaciones de la orden (`ordenes.observaciones`).
3. **Frontend:**
   - [x] Modal de subestudios para Inmunoserología con casillas rosas (`ModalSeleccionarInmunosero`).
   - [x] Botón contextual `[ ⚙️ Subestudios ]` para editar subestudios de Inmunoserología.
   - [x] Botón `[ 🗑️ Eliminar estudio ]` con alerta de auto-cancelación si se eliminan todos.
   - [x] Edición de rangos de referencia in-situ con botón `✏️` y botón `↺ Reestablecer`.
   - [x] Cajas de texto de observaciones por estudio y observaciones finales de la orden.
   - [x] Integración en vista previa en vivo (panel derecho).

### FASE 3.9: Caso PCR Semicuantitativa (COMPLETADA)
- [x] Componente interactivo `ModalCalculadorPcr`:
  - Selector de Reactividad (Negativo / Positivo).
  - Selector de Marca de Reactivo (MONLAB 6 mg/L, TECO 0.8 mg/dL, Personalizado).
  - Selector de Dilución (1/2, 1/4, 1/8, 1/16, 1/32, 1/64) con cálculo automático de Título (Factor inverso × Sensibilidad).
  - Aplicación directa al campo `PCR_DILUCION`.
- [x] Catálogo SQL regenerado en `db/init/002_seed_catalogo.sql` mediante `scripts/generar_seed_sql.py`.

---

### FASE 4: Papelera Lógica, Versionado con Justificación, Publicación Oficial y Filtros (EN PROGRESO — Núcleo Clínico y Papelera Completados ✅)
1. **Gestión de Papelera y Versionado (Soft-Delete Auditado):**
   - [x] Papelera lógica oficial para informes con folio (`POST /api/informes/{folio}/papelera` y `POST /api/informes/{folio}/restaurar`).
   - [x] Nada se elimina físicamente de la base de datos sin dejar rastro (inmutabilidad estricta garantizada por triggers PostgreSQL `trg_proteger_informe` y `trg_eventos_append_only`).
   - [x] Vista de "Papelera y Reciclaje" (`/papelera`) con visualización del motivo de descarte auditado y restauración controlada.
   - [x] Versionado oficial V1 $\rightarrow$ V2 $\rightarrow$ V3 (`POST /api/informes/{folio}/versiones`) con desplazamiento atómico y tope estricto de 3 versiones (D-71).
2. **Publicación Oficial y Folios (Inmutabilidad del Informe):**
   - [x] `POST /api/ordenes/{id}/publicar` con validación de obligatoriedad del campo "Observaciones finales del informe".
   - [x] Generación de folio correlativo inmutable (`2026-000001`) mediante secuencia atómica de PostgreSQL `siguiente_folio()`.
   - [x] Congelamiento en `snapshot_json` con hash criptográfico SHA-256.
   - [x] Vista del informe oficial (`/informes/:folio`) con membrete del Hospital Metodista, ficha médica, banderas y diseño de impresión física `@media print`.
   - [x] Botón interactivo "Publicar Informe" en la barra de captura de resultados.
3. **Filtros de Búsqueda y Consulta por Módulo:**
   - [x] Buscador rápido por folio, CI y nombres en el módulo de Informes Oficiales (`/informes`) y Papelera (`/papelera`).
4. **Módulo de Estadísticas, Gráficos y Reportes:**
   - [ ] Métricas de estudios más solicitados, tiempos de atención y volumen diario/mensual.

### FASE 5: Rol VISITANTE y Blindaje de Visualización
1. Activar rol `VISITANTE` en dependencias de FastAPI (solo lectura).
2. Bloqueo 403 estricto a descarga de PDFs.
3. Blindaje de UI: bloqueo de `@media print`, desactivación de clic derecho, blur al desenfoque y marca de agua dinámica (Usuario + CI + IP + Fecha/Hora).
