# Rediseño visual y corrección de informes

Actualizado: 24 de noviembre de 2026.

## Actualización 24 de noviembre — Referencias de Hepatograma y mapa de diseño

- GOT/AST y GPT/ALT usan `VR: Hasta 40` UI/L, con 40 incluido, por solicitud del laboratorio. Se actualizan `definitions.py` y el seed generado; las demás referencias del Hepatograma conservan sus valores.
- La migración `0022_referencias_hepatograma.py` sincroniza las referencias genéricas del catálogo. Conserva resultados capturados, referencias personalizadas por orden y snapshots publicados; queda pendiente de autorización/aplicación en la base activa.
- `docs/CONTEXTO_PROYECTO.md`, apartado «Dónde editar el diseño de cada estudio», contiene el mapa de los 13 estudios, sus componentes específicos y los archivos compartidos de estilos y PDF.
- Verificación: las cinco pruebas nuevas de límites, captura, referencias personalizadas y migración pasan. La revisión ampliada obtiene 50/51: el fallo restante es una expectativa anterior del nombre de Sangre oculta en minúsculas, mientras el catálogo ya utiliza `SANGRE OCULTA EN HECES`. Se reproduce usando la copia del catálogo previa al cambio de Hepatograma. El seed generado sólo cambia las dos referencias solicitadas; enlaces locales del mapa y `git diff --check` correctos.

## Actualización 24 de noviembre — Coagulación y Grupo sanguíneo

- La directriz corregida asigna Unidad editable sólo a **Coagulación**. Las seis filas permiten escritura, partiendo de las unidades de su catálogo (`min`, `seg`, `%`) e INR vacío. El resto de la tabla conserva sus columnas, referencias y banderas. Las unidades se guardan y se reflejan en vista previa y nuevos informes sin convertir resultados ni rangos.
- Grupo y Factor RH usan **Parámetro · Captura · Resultado**, con un selector único y Resultado al final, en solo lectura. Se elimina Unidad de esa sección de captura y de los nuevos informes, junto con V. Ref. y Bandera. Los borradores con el JSON anterior conservan su selección y omiten la unidad; los informes publicados mantienen su presentación y snapshots históricos.
- La migración `0021_unidades_coagulacion.py` añade `unidad_override` nullable a `resultados_borrador`, separada del valor numérico Decimal. No cambia el catálogo. `NULL` usa la unidad del catálogo, incluido INR sin unidad; texto vacío mantiene el borrado explícito. Una unidad sola no cuenta como resultado. La migración se prueba en PostgreSQL temporal y queda pendiente en la base activa.
- El flujo existente de autoguardado, cálculo y vista previa incorpora `unidades_override`, con validación de alcance y permisos en backend. Guardar y publicar esperan también las ediciones de unidades pendientes.
- Verificación de la directriz corregida: compilación del frontend y `git diff --check` correctos; 20 pruebas de Grupo sanguíneo/Coagulación y 46 regresiones de cálculo, almacenamiento, concurrencia, permisos, serología e informes aprobadas. Navegador con API real y datos ficticios en 1366×768 y 1920×1080: seis unidades iniciales correctas, edición y borrado conservados al recargar, una unidad sola no completa resultados, Grupo sanguíneo sin Unidad, Enter, temas claro/oscuro y ADMIN en solo lectura, sin errores de JavaScript.
- La revisión anterior de resultados, evaluación e informes detectó un fallo previo de EGO: `test_06_validaciones_cualitativas` espera rechazar texto ajeno a las opciones de NITRITOS, aunque el normalizador existente permite texto libre en la química de EGO. Se reprodujo con el soporte de Grupo sanguíneo desactivado; no se altera esa regla fuera del alcance solicitado.

## Actualización 24 de noviembre — Inmunoserología

- El selector de órdenes presenta el grupo interno `PARASITOLOGIA` como **SEROLOGIA** y mantiene disponible el subestudio **CHAGAS**.
- ASTO ofrece el reactivo estándar de 200 UI/mL o una sensibilidad propia en el mismo control; el icono de ajustes permite volver al estándar. PCR permite sensibilidad propia sin eliminar ni alterar el factor de dilución.
- La vista previa y el PDF oficial comparten la plantilla Jinja `backend/app/reports/templates/informe.html`. Para nuevos informes, SEROLOGIA imprime Muestra y Método; los snapshots históricos sin esas columnas conservan su presentación.
- El catálogo se actualiza en `backend/app/catalog/definitions.py`, su seed se genera con `scripts/generar_seed_sql.py` y la migración `0020_inmunoserologia_chagas_asto.py` queda pendiente de autorización/aplicación a la base activa.
- Verificación de esta actualización: build del frontend y `git diff --check` correctos. Las pruebas backend no se ejecutaron en esa sesión.

## Alcance y paleta

Se conservan los flujos clínicos, los formularios, las pestañas de estudios y la distribución de captura y vista previa. Por la última instrucción se añaden las rutas propias de Catálogo y Estadísticas de desempeño al menú lateral. La propuesta HTML aporta sólo referencias visuales, no catálogo, cálculos ni permisos.

La corrección de paleta utiliza **blanco y negro puros con grises neutros**. El rojo/vino se reserva para botones, vectores y jerarquía. Se retiran los tintes cálidos de fondos, entradas y tablas. Los tokens se centralizan en `frontend/src/index.css`. En oscuro, campos y marcos son más claros que los paneles; en claro, las entradas son blancas con bordes oscuros. Bajo recupera el azul, Normal y guardado el verde, y pendientes/sin confirmar el ámbar. Las banderas mantienen sus etiquetas e iconos. Los subestudios de Inmunoserología recuperan el rosa, adaptado al tema.

| Elemento | Claro | Oscuro |
| --- | --- | --- |
| Acento | `#982333` | `#f1a0ad` |
| Acción principal | `#982333` | `#a12a3c` |
| Página y menú | `#ffffff` | `#000000` |
| Panel | `#ffffff` | `#111111` |
| Entrada | `#ffffff` | `#303030` |
| Texto de entrada | `#000000` | `#ffffff` |
| Borde de entrada | `#444444` | `#b5b5b5` |
| Cuadrícula | `#555555` | `#919191` |
| Bajo | azul `#1e40af` | azul `#93c5fd` |
| Normal / guardado | verde `#166534` | verde `#86efac` |

El tema continúa compartido entre pantallas y en memoria. No se utiliza `localStorage` ni `sessionStorage`.

El menú lateral sigue el modo de la página; «Nueva orden» no tiene un relleno rojo permanente. La selección se distingue con una línea lateral y el icono. Inicio saluda con **BIENVENIDO, LIC. Nombre y apellidos del usuario**, tanto para ADMIN como para BIOQUIMICO. Menú, acceso, Inicio y favicon utilizan el logo original de LABMET, estático y sin filtros. El documento oficial conserva los logos y membretes de su plantilla.

## Catálogo y perfiles rápidos

Catálogo sale de Pacientes y tiene una sección propia en `/catalogo`. Se reutilizan sus consultas, editor, perfiles predefinidos y permisos personales; no se reestructura el contenido clínico que el laboratorio revisará posteriormente. Cada perfil personalizado guardado muestra los nombres de sus estudios y sus grupos. El listado de Nueva orden también muestra los estudios de ambos tipos de perfil y su detalle, sin cambiar cómo se aplica la selección.

## Estadísticas de desempeño

La ruta `/estadisticas` consulta `GET /api/estadisticas`. Incluye filtros de período (7/30/90 días o fechas propias), responsable para ADMIN, tiempo de respuesta, métrica y orden de barras. Presenta conteos, mediana de respuesta, barras de estudios o responsables, gráfico circular de estados y actividad por día/semana con detalle tabular accesible. Las superficies permanecen neutras y los gráficos y leyendas se adaptan a ambos temas.

No hay cifras de demostración en la pantalla: las consultas agregan los datos de PostgreSQL. Los conjuntos vacíos se muestran sin inventar tiempos. El período agrupa órdenes por creación en hora boliviana; cada orden y su primera publicación se cuentan una vez. Las reediciones y reimpresiones no duplican entregas. Se cuentan los estudios con parámetros del snapshot V1; la toma de muestra, o creación como respaldo, inicia el intervalo hasta esa primera entrega. Intervalos inválidos quedan fuera de la mediana.

BIOQUIMICO ve sólo su actividad como autor original. ADMIN puede consultar el conjunto o un responsable, con auditoría de consulta. La respuesta es agregada y no contiene pacientes, resultados ni snapshots. No se modifican el esquema, los datos clínicos ni las tablas protegidas. Reglas y pruebas en `docs/DECISIONES.md` §19 y `backend/tests/test_estadisticas_api.py`.

## Limpieza de recursos

Se eliminan las copias sin referencias de `LOGO SVG.svg` de la raíz y de `frontend/public`, `frontend/src/assets/logo-metodista.svg` y los SVG duplicados de `frontend/public/branding`. También se retira el SVG de trazo generado para el indicador anterior. LABMET se sirve desde un único recurso activo del frontend, copiado del original utilizado por los informes.

Se conservan:

- `frontend/public/logo-labmet.png`, usado por la interfaz y el favicon.
- `backend/app/reports/assets/logo-metodista.svg` y `logo-labmet.png`, usados por los informes.
- Los membretes y las marcas de agua de `backend/app/reports/assets`, utilizados por la plantilla de vista previa y PDF.

El build regenera `frontend/dist` sin las copias eliminadas. Se retiran además los componentes y formateadores exclusivos del antiguo informe HTML del navegador y sus estilos de simulación.

## Causa y corrección de la doble visualización

El detalle oficial conservaba un segundo documento HTML y lo ocultaba únicamente después de recibir la URL del PDF. Durante la descarga, o si ésta fallaba, esa plantilla antigua quedaba visible. No era otro motor LaTeX: era contenido residual de React.

`InformeDetallePage.tsx` utiliza ahora exclusivamente el documento del servidor:

1. Obtiene los metadatos y fija la versión exacta que se va a consultar.
2. Muestra texto de carga mientras obtiene el documento.
3. Muestra el PDF vigente o un error con Reintentar, sin dibujar tablas alternativas.
4. Cancela solicitudes anteriores y libera las URLs temporales cuando cambia el folio, la versión o la pantalla.

Imprimir y Descargar se habilitan sólo para el documento vigente cargado. Las versiones desplazadas, papelera y reciclaje se consultan como imágenes de la misma plantilla mediante `GET /api/informes/{folio}/vista-previa`, autenticado. Ese recurso no habilita el endpoint PDF ni registra una emisión de impresión. El endpoint `/pdf` mantiene su validación backend y su evento de emisión.

## Fecha, horas y responsable

La plantilla común de vista previa y PDF imprime:

- **Fecha:** `día/mes/año`, correspondiente a la publicación oficial; en borrador se utiliza el inicio disponible.
- **Hora de toma de muestra:** la hora de inicio almacenada en `fecha_hora_toma_muestra`, con la creación de la orden como respaldo.
- **Hora de entrega de resultado:** la hora en que se publica la versión consultada. En borradores aparece «Pendiente de publicación».

Las horas se presentan en `America/La_Paz`, en formato de 24 horas. Los datos que carecen de hora no se convierten artificialmente en medianoche.

El responsable conserva la autoría original y aparece como **LIC. Nombre del bioquímico**. No se imprime la matrícula, aunque exista en su usuario. El hash del snapshot, los timestamps completos y el número de versión dejan de aparecer en el cuerpo impreso; permanecen disponibles internamente para integridad y trazabilidad. El folio permanece visible.

Los nuevos snapshots incluyen la fecha de creación de la orden para congelar el respaldo de la toma. Los snapshots ya publicados no se actualizan ni se eliminan.

## Firma y partición de estudios

La firma y el nombre del responsable se sitúan en el pie repetido de todas las páginas Carta. La zona inferior reserva 48 mm para firma y membrete; no depende de cuánto espacio quede después de una tabla.

Cada estudio evita fragmentarse si puede caber completo en una hoja. Puede compartir la página anterior sólo si cabe íntegro antes de la firma; de lo contrario empieza en otra. Un estudio que por sí solo excede una hoja empieza en una hoja nueva después del anterior y continúa respetando filas, encabezados y zona de firma.

Para los estudios de varias páginas se comprueba la distribución real que genera el motor. Sólo esos casos se vuelven a maquetar: el primer estudio empieza debajo de los datos del paciente, evitando una portada vacía, y los siguientes empiezan en una hoja nueva. No se estima el salto mediante un número fijo de parámetros.

El logo del Hospital Metodista ocupa el centro del encabezado. LABMET permanece centrado en su espacio. Ambos conservan su proporción, sin filtros de brillo, neón ni deformación.

## Causas y corrección de la publicación

Se encontraron tres bloqueos:

1. Frontend y backend exigían observaciones finales, incluso con resultados válidos.
2. Los borradores de versiones de catálogo anteriores sin `seleccion_campos` seguían exigiendo campos no utilizados y defectos virtuales.
3. El guardado capturaba errores sin comunicar su fracaso al flujo de publicación.

Ahora las observaciones son opcionales. Todos los borradores se evalúan por campos utilizados: se requiere al menos un resultado, sin entradas utilizadas incompletas, confirmaciones pendientes ni errores clínicos. Los campos vacíos y los estudios sin uso no bloquean ni se publican. Un cero explícito continúa siendo un resultado; no se inventan negativos ni valores por defecto. Una serología positiva incompleta sigue bloqueando la publicación.

La interfaz espera un guardado satisfactorio antes de llamar a Publicar. Si falla o quedan cambios pendientes, detiene la publicación y permite reintentar. El servidor vuelve a validar y conserva la transacción existente de folio, snapshot y evento. No se modifican fórmulas ni rangos.

## Cargas

Se elimina el indicador flotante con logo y toda su instrumentación. Se retiran el trazo, el llenado, el neón y las animaciones del logo. Los logos de acceso, inicio y menú son estáticos. Las pantallas de espera muestran texto de estado, sin un logo de carga de sustitución.

## Verificación

- Resultado final del backend: **210 de 212 pruebas aprobadas**. Los dos fallos restantes son los de sesión descritos abajo y se reproducen con el código previo. Las **15 pruebas de PDF**, las de publicación y captura y las **8 nuevas pruebas de estadísticas** pasan.
- Compilación TypeScript y producción con `npm run build`.
- Pruebas numéricas existentes con `npm run test:numeros`.
- Pruebas de PDF: fecha y horas locales, ausencia de hash/versión/matrícula, prefijo LIC., firma repetida, reserva del pie, centrado del logo y partición de estudios cortos, largos y mayores de una página.
- Pruebas de publicación, captura, catálogo y evaluación sobre un PostgreSQL efímero `lis_redesign_test`, con esquema y migraciones completos, sin acceder a la base clínica.
- Estadísticas: alcance por rol, filtro por responsable, fechas inclusivas de Bolivia, ceros reales frente a tiempos ausentes, límites de respuesta, ausencia de duplicados por versión y publicación parcial mediante la API real. Este último caso verifica el formato efectivo `estudios[].secciones[].parametros[]` del snapshot, sin alterar su almacenamiento.
- Comprobación en navegador con la API real de esa base temporal: publicación con un campo de dos estudios y sin observaciones; bloqueo ante un guardado fallido; carga del PDF sin HTML residual; recuperación del visor; consulta de versiones sin imprimir.
- Comprobación del diseño con ADMIN y BIOQUIMICO: bienvenida con nombre completo y LIC., identidad y favicon LABMET, menú acorde al tema, guardado real de perfiles con sus estudios/grupos y selección rosa de Inmunoserología. Banderas Normal/Bajo y guardado verificados con los colores computados del navegador. Estadísticas con datos reales de prueba, filtros de respuesta/responsable, orden de barras y tamaños de 390, 1366 y 1920 px, sin errores de JavaScript.

Las capturas y documentos usados para revisar el diseño contienen exclusivamente datos ficticios y se generan temporalmente fuera del repositorio. Las reglas actualizadas se documentan en `docs/DECISIONES.md` §§18–19 y `docs/UX_GUIDE.md`.

### Diagnóstico de las pruebas de sesión preexistentes

La revisión ampliada identifica dos fallos ajenos a estos cambios, reproducidos también con una copia del código previo tomada del índice de Git:

- **Revocación por inactividad — falso negativo de la prueba.** `test_10_sesion_expira_por_60_minutos_sin_actividad` carga una instancia ORM de `Sesion` antes de llamar a la API. La API usa otra sesión SQLAlchemy y sí guarda `revocada_en` y el evento `SESION_EXPIRADA`. La segunda consulta de la prueba reutiliza la instancia que estaba en su mapa de identidad y conserva el valor anterior `None`. Se confirmó con un `SELECT` en otra conexión: la revocación está guardada; al ejecutar `self.db.refresh(sesion)`, el mismo objeto ya muestra el valor correcto. La corrección corresponde a la lectura de la prueba, no a prolongar ni modificar la sesión clínica.
- **Token renovado — dos relojes distintos.** `test_t5_02d_access_expirado_se_renueva_mientras_sesion_vigente` adelanta dos minutos el reloj de `app.core.clock`. `create_access_token` usa ese reloj para `iat` y `exp`. `decode_access_token` comprueba `exp` con el reloj de la aplicación, pero deja la comprobación de `iat` a PyJWT 2.15.1, que usa `datetime.now(timezone.utc)`. La hora de emisión queda unos 120 segundos en el futuro para el verificador. PyJWT lanza `ImmatureSignatureError`; la API traduce ese rechazo a 401 `SESION_EXPIRADA`, aunque el refresh haya devuelto 200 y la sesión siga vigente en PostgreSQL.

Contrapruebas realizadas en la base efímera con usuarios ficticios:

| Comprobación | Resultado |
| --- | --- |
| Expiración por inactividad | HTTP 401 y revocación persistida en PostgreSQL |
| Segunda consulta ORM antes de refrescar | Misma instancia y `revocada_en = None` en su caché |
| Misma instancia después de `refresh` | Revocación real visible |
| Refresh y consulta con reloj normal | 200 → 200 |
| Refresh y consulta con el reloj de aplicación adelantado | 200 → 401; causa interna `ImmatureSignatureError` |
| Misma consulta al sincronizar el reloj del verificador en la contraprueba | 200; sesión sin revocar |
| Firma manipulada y emisión futura con relojes sincronizados | Ambas rechazadas |

La corrección del segundo caso debe hacer coherente el reloj de emisión y validación temporal, conservando los controles de firma, vencimiento y emisión futura. No corresponde desactivar la firma ni ampliar artificialmente la duración de las sesiones. Este diagnóstico reproduce y explica las causas; no modifica el código de autenticación ni las dos pruebas originales.
