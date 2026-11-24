# Contexto rápido del LIS

**Actualizado:** 24/11/2026. Úsalo como índice de entrada; no sustituye las reglas completas.

## Ruta de lectura para continuar el proyecto

1. [`AGENTS.md`](../AGENTS.md): reglas obligatorias de desarrollo y seguridad.
2. [`docs/DECISIONES.md`](./DECISIONES.md): reglas clínicas, catálogo, informes y permisos. Es la fuente de decisión del dominio.
3. [`docs/UX_GUIDE.md`](./UX_GUIDE.md): leer antes de modificar cualquier pantalla del frontend.
4. [`REDISENO_FRONTEND.md`](../REDISENO_FRONTEND.md): registro del rediseño visual reciente.
5. Abre sólo los módulos relevantes indicados abajo y sus pruebas. No es necesario leer todo el repositorio de golpe.

`docs/SUPUESTOS.md` conserva decisiones tomadas cuando faltaban requisitos. Los documentos `docs/historial/` y los prompts de fases son antecedentes, no un estado actual del sistema.

## Qué es el sistema

LIS local para el laboratorio: PostgreSQL, FastAPI/SQLAlchemy/Alembic, React/TypeScript/Vite y Caddy. La app tiene autenticación y roles, pacientes, órdenes en borrador, captura y cálculo clínico, catálogo, informes con folio y PDF, perfiles y estadísticas. Para el estado de cada función, verifica el código y `docs/DECISIONES.md`; los números y fases del README antiguo no son una referencia fiable.

## Mapa de código

### Backend

- Catálogo y fuente única de fórmulas/rangos: [`backend/app/catalog/definitions.py`](../backend/app/catalog/definitions.py).
- Evaluación de captura, validación y resultados: [`backend/app/services/evaluacion_service.py`](../backend/app/services/evaluacion_service.py).
- Cálculo seguro con `Decimal`: [`backend/app/calculation/engine.py`](../backend/app/calculation/engine.py).
- Inmunoserología: [`backend/app/services/serologia_service.py`](../backend/app/services/serologia_service.py).
- Unidades editables de Coagulación: `backend/app/services/coagulacion_service.py`; pruebas en `backend/tests/test_coagulacion.py`. Grupo sanguíneo sin unidad y compatibilidad de borradores anteriores: `backend/app/services/grupo_sanguineo_service.py` y `backend/tests/test_grupo_sanguineo.py`.
- Curva y coproparasitológicos: `backend/app/services/curva_service.py` y `backend/app/services/coproparasitologia_service.py`.
- Endpoints: `backend/app/api/`; esquemas: `backend/app/schemas/`.
- Versionado del esquema y catálogos: `backend/alembic/versions/`. No editar una migración histórica para incorporar cambios nuevos; agregar una posterior.
- Pruebas: `backend/tests/`. Las de integración necesitan una base de pruebas separada cuyo nombre termine en `_test`.

### Frontend

- Rutas: [`frontend/src/App.tsx`](../frontend/src/App.tsx); estructura y menú: [`frontend/src/components/Layout.tsx`](../frontend/src/components/Layout.tsx).
- Estilos y temas: [`frontend/src/index.css`](../frontend/src/index.css).
- Creación de órdenes y selección de subestudios: [`frontend/src/features/ordenes/NuevaOrdenPage.tsx`](../frontend/src/features/ordenes/NuevaOrdenPage.tsx), [`frontend/src/components/EstudiosPerfil.tsx`](../frontend/src/components/EstudiosPerfil.tsx).
- Captura: [`frontend/src/features/ordenes/CapturaResultadosPage.tsx`](../frontend/src/features/ordenes/CapturaResultadosPage.tsx), [`frontend/src/features/ordenes/SeccionInmunoserologia.tsx`](../frontend/src/features/ordenes/SeccionInmunoserologia.tsx), [`frontend/src/features/ordenes/CurvaToleranciaCaptura.tsx`](../frontend/src/features/ordenes/CurvaToleranciaCaptura.tsx).
- Grupo sanguíneo usa `frontend/src/features/ordenes/SeccionGrupoSanguineo.tsx`: Parámetro, Captura y Resultado al final, sin Unidad. Coagulación conserva sus columnas y permite editar las seis unidades, con sus valores iniciales del catálogo e INR vacío.
- Vista previa e informes oficiales: `frontend/src/components/VistaPreviaInforme.tsx` y `frontend/src/features/informes/InformeDetallePage.tsx`.

### Dónde editar el diseño de cada estudio

La **base compartida** es [`CapturaResultadosPage.tsx`](../frontend/src/features/ordenes/CapturaResultadosPage.tsx), dentro de `frontend/src/features/ordenes/`. Busca `renderizarFilaParametro` para las celdas y controles, `renderizarSeccion` para encabezados y columnas, y `renderizarFilaDiferencial` para el diferencial del hemograma. Los nombres y el orden de parámetros llegan del catálogo backend.

| Estudio | Archivo o bloque de captura |
|---|---|
| Hemograma | Base compartida; diferencial en `renderizarFilaDiferencial`. |
| Coagulograma y Grupo Sanguíneo | Coagulación en la base; Grupo sanguíneo en [`SeccionGrupoSanguineo.tsx`](../frontend/src/features/ordenes/SeccionGrupoSanguineo.tsx). |
| Química Sanguínea | Base compartida. |
| Electrolitos | Base compartida. |
| Perfil Lipídico | Base compartida, incluidos los resultados calculados. |
| Hepatograma / Perfil Hepático | Base compartida. |
| Proteinograma | Base compartida. |
| EGO | Base compartida; rama `esEgoQuimico` para la tabla de dos columnas. |
| Inmunoserología | [`SeccionInmunoserologia.tsx`](../frontend/src/features/ordenes/SeccionInmunoserologia.tsx), incluidas las capturas particulares de PCR, FR y ASTO. |
| Perfil Cardíaco | Base compartida; `SELECCION_SIMPLE` para Troponina y tabla numérica para el resto. |
| Perfil Pancreático | Base compartida. |
| Parasitología | Base para selecciones, Moco fecal y Coproparasitológico simple; [`MuestrasSeriadas.tsx`](../frontend/src/components/MuestrasSeriadas.tsx) para el seriado. |
| Curva de tolerancia | [`CurvaToleranciaCaptura.tsx`](../frontend/src/features/ordenes/CurvaToleranciaCaptura.tsx), tabla y gráfica. |

Los estilos de todas estas capturas están en [`frontend/src/index.css`](../frontend/src/index.css). Busca `.lis-captura-tabla`, `.lis-sheet-*`, `.lis-serologia-*`, `.lis-grupo-sanguineo-*`, `.lis-curva-*`, `.lis-lista-texto` y `.lis-muestras-seriadas`. Hay reglas posteriores que sobrescriben las primeras: revisa también el final del archivo.

Los controles compartidos están en [`EntradaResultadoNumerico.tsx`](../frontend/src/components/EntradaResultadoNumerico.tsx) y [`EntradaResultadoTexto.tsx`](../frontend/src/components/EntradaResultadoTexto.tsx). La selección de estudios se dibuja en `NuevaOrdenPage.tsx`, `EstudiosPerfil.tsx` y, para subestudios de Inmunoserología durante captura, `ModalCapturaHelpers.tsx`.

El diseño del documento de la derecha y del PDF se edita en la **plantilla backend común** indicada abajo; `VistaPreviaInforme.tsx` controla su visor. Valores de referencia, unidades, fórmulas, nombres y orden clínico se editan en `definitions.py`, con seed, migración y pruebas cuando corresponda.

### Informes HTML/PDF

- [`backend/app/reports/templates/informe.html`](../backend/app/reports/templates/informe.html) es la plantilla Jinja real que genera el contenido de la vista previa y del PDF oficial.
- [`backend/app/reports/pdf.py`](../backend/app/reports/pdf.py) prepara los datos y renderiza/pagina esa plantilla; [`backend/app/reports/presentation.py`](../backend/app/reports/presentation.py) define qué resultados y columnas se muestran.
- Los membretes, logos y marcas de agua usados por esa plantilla están en `backend/app/reports/assets/`.
- [`frontend/index.html`](../frontend/index.html) sólo es la carcasa de Vite que monta React; no contiene las pantallas ni la plantilla de informe.
- [`RECURSOS/demo.html`](../RECURSOS/demo.html) es una demostración aislada del indicador LABMET, no una pantalla conectada a la aplicación.
- El archivo raíz [`REDISEÑO DE ESTUDIOS`](../REDISEÑO%20DE%20ESTUDIOS) contiene una lista de opciones de EGO; no es una guía general de diseño. No se encontraron otros prototipos HTML activos en el árbol actual.

## Cambios recientes y estado pendiente

- `docs/DECISIONES.md` y `docs/UX_GUIDE.md` contienen las reglas recientes de Inmunoserología: grupo visible SEROLOGIA, muestra/método, CHAGAS, y captura personalizable para ASTO/PCR.
- `REDISENO_FRONTEND.md` documenta el rediseño de frontend e informes. Los cambios de catálogo también están respaldados por `definitions.py`, el seed generado y migraciones Alembic.
- Último estado reportado: la base activa estaba en Alembic `0019`; las migraciones `0020_inmunoserologia_chagas_asto.py`, `0021_unidades_coagulacion.py` y `0022_referencias_hepatograma.py` están creadas pero **pendientes de autorización/aplicación**. Verifica la base antes de continuar; no apliques migraciones automáticamente.
- La unidad editable corresponde únicamente a Coagulación. Grupo sanguíneo queda sin Unidad. Reglas en `DECISIONES.md` D3-12/D3-13 y presentación en `UX_GUIDE.md` §3. La migración `0021` se prueba únicamente sobre PostgreSQL temporal. La revisión anterior detectó un fallo previo de validación de EGO, detallado en `REDISENO_FRONTEND.md`.
- GOT/AST y GPT/ALT del Hepatograma / Perfil Hepático usan `VR: Hasta 40` UI/L, con 40 incluido. Catálogo y seed actualizados; `0022` sincroniza sólo las referencias genéricas del catálogo y conserva las personalizadas y los informes publicados. Regla en `DECISIONES.md` D3-14.

## Reglas que no se deben romper

- Nada de `eval`/`exec` para fórmulas; usar el motor de cálculo existente.
- Resultados clínicos con `Decimal`; vacío es `None`/`NULL`, no cero.
- No duplicar fórmulas ni rangos en el frontend.
- Un informe publicado y sus eventos son inmutables; las migraciones versionan el catálogo y preservan los borradores/publicaciones según corresponda.
- Permisos y visibilidad se validan en backend; no registrar contraseñas ni datos reales de pacientes.
- Antes de desplegar o migrar una base activa, confirmar el alcance con el usuario.
