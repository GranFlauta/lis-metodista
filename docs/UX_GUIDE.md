# Guía de UX — LIS Laboratorio Clínico

> **Esta guía manda sobre cualquier skill de diseño.** Los usuarios son bioquímicos acostumbrados al Excel; quieren **rapidez, pocos clics y fidelidad a su hoja**. Diseño minimalista y funcional, no "llamativo".
> Ubicación: `docs/UX_GUIDE.md`. Referenciada desde `AGENTS.md`.

## 1. Principios (en orden de prioridad)

1. **Fidelidad al Excel.** Disposición de hoja: filas `Parámetro · Resultado · Unidad · Valores de referencia · Bandera`, estudios agrupados como en las plantillas `HC-QMC-SEROL-EGO` y `HC-QMC-SERO-PROT`, mismo orden de campos que `definitions.py`.
2. **Una tarea = una pantalla.** Crear una orden no debe requerir bajar de página ni pasar por más de una confirmación.
3. **Menos clics.** Teclado primero: `Tab`/`Enter` avanzan al siguiente campo (como en Excel), `Esc` cierra diálogos, foco inicial en el primer campo útil.
4. **Densidad útil.** Se aprovecha el ancho completo de la pantalla. Sin tarjetas decorativas ni rellenos grandes.
5. **Lo importante, a la vista:** paciente, hora de inicio, estado (completo/faltan N) y banderas siempre visibles.
6. **Sin ruido.** Cero texto de desarrollo ("Fase 3", "Bloque 5", "Próximamente"), cero emojis. Sólo se permiten las animaciones LABMET y de selección descritas en §9, solicitadas por el usuario. Lo que no existe aún, **no se muestra**.

## 2. Pantallas objetivo

Resolución de referencia: **1366×768** (laptop del laboratorio) y 1920×1080. Todo el flujo principal debe funcionar sin scroll de página en 1366×768, salvo listas largas.

| Pantalla | Estructura |
|---|---|
| **Estructura general** | Menú lateral izquierdo **desplegable** (iconos + texto; colapsado = solo iconos). Barra superior mínima: nombre de la pantalla + estado de sesión. Pie del menú: usuario, rol, "Clave", "Salir" |
| **Inicio** | Fila superior de **cuatro acciones rápidas del mismo tamaño**: *NUEVA ORDEN*, *BUSCAR PACIENTE*, *MIS PENDIENTES (N)* e *INFORMES*; ADMIN: *BUSCAR PACIENTE*, *ÓRDENES*, *USUARIOS* e *INFORMES*. **Debajo, panel horizontal "RECIENTES"**: tabla de los últimos 15 trabajos (paciente, estudios, estado, hora, botón *Continuar*). Llena la pantalla; no queda vacía |
| **Nueva orden** | **Una sola pantalla**, 3 zonas lado a lado: **Paciente** (buscador único; si no existe, formulario compacto en línea) · **Estudios** (botones de perfil + estudios como interruptores; Inmunoserología despliega sus grupos en línea) · **Datos de la orden** (origen, médico, pieza) + resumen y botón **Continuar** |
| **Confirmación** | Ventana modal con: **CI, nombre completo, edad, estudios a realizar, fecha y hora de inicio** (editable, precargada con ahora). Botones: *Volver* / **Empezar a calcular** → va **directo** a la captura |
| **Captura** | Barra superior fija con paciente, CI, edad, hora de inicio, estado y *Guardar*. Izquierda (≈55 %): hoja de captura densa. Derecha (≈45 %): **vista previa grande** del informe, con su propio scroll y botón de pantalla completa |
| **Pacientes** | Pensada para **buscar y gestionar**, no para crear: buscador + filtros, tabla con etiqueta **Pendiente (n)**, acciones *Editar* y *Nueva orden*. Crear paciente suelto es secundario |
| **Órdenes / Pendientes** | Tabla densa con filtros rápidos (Todas · Incompletas · Completas · Publicadas). La acción principal de la fila es **Continuar captura** |

## 3. Hoja de captura (fiel al Excel)

* Cada estudio es un bloque con encabezado (`Hemograma  9/12`) y filas de **28–32 px** de alto. En pantallas anchas los bloques se disponen en **columnas** (auto-ajuste, mínimo 420 px) como la hoja de Excel.
* Columnas: Parámetro (texto) · Resultado (campo, **alineado a la derecha** si es numérico) · Unidad · V. Ref. · Bandera.
* Calculados: fondo gris claro, solo lectura, con el valor o "No calculable".
* Valores por defecto: insignia "Sin confirmar" y botón único *Confirmar valores por defecto*.
* Los campos numéricos aceptan `.` o `,` decimal y agrupan miles/millones al escribir; el valor enviado al backend conserva el decimal y no incluye agrupación.
* La vista previa se actualiza automáticamente tras una pausa breve al escribir. Muestra páginas Carta de la plantilla oficial, con membrete y contenido a partir de 38 mm del borde superior. Su única acción es **Pantalla completa** (cerrar con `Esc`); impresión y descarga pertenecen al informe oficial vigente.
* Vacíos y valores por defecto sin confirmar no ocupan filas en el informe; cero capturado y «No calculable» por regla conservan su fila.
* En inmunoserología: **Prueba · Captura · Unidad (si corresponde) · V. Ref. (solo cálculos) · Resultado**. Reactividad, reactivo y dilución pertenecen a Captura; Resultado contiene únicamente el resultado final. No se muestran banderas. En el grupo de captura titulado **SEROLOGIA**, los tres análisis cualitativos muestran **Muestra · Método** entre Prueba y Captura. Las selecciones cualitativas no tienen Unidad ni V. Ref.; el informe elimina también la columna Captura y conserva Prueba, Resultado, Muestra y Método para SEROLOGIA. **CHAGAS** es otro subestudio seleccionable. Para PCR, FR y ASTO, al elegir sensibilidad propia, el campo numérico reemplaza el selector de reactivo en el mismo control y un icono de ajustes permite volver al reactivo estándar; PCR conserva su factor de dilución 1/n independiente.
* En **Grupo sanguíneo**, dentro de Coagulograma y Grupo Sanguíneo, la captura usa **Parámetro · Captura · Resultado**, siguiendo la tabla cualitativa de Inmunoserología. Grupo y Factor RH tienen un único selector en Captura con sus opciones del catálogo; Resultado aparece al final, en solo lectura. No se muestran Unidad, V. Ref. ni Bandera en esta sección. La vista previa y los nuevos informes muestran sólo Parámetro y Resultado; los informes publicados conservan su presentación histórica.
* En **Coagulación**, la columna Unidad es un campo de texto editable en las seis filas, incluido INR. Se muestran inicialmente las unidades del catálogo (`min`, `seg`, `%`) y el campo de INR vacío. Las ediciones y el borrado explícito de una unidad se conservan al reabrir el borrador y se reflejan en la vista previa y el informe. El resto de columnas mantiene su orden y comportamiento.
* Una selección `--` significa campo sin usar. Los campos sin usar permanecen disponibles en captura, pero no aparecen en el informe ni bloquean por sí solos su publicación. No se precargan resultados negativos del catálogo. PCR, FR y ASTO negativos imprimen sólo «Negativo»; sus reactivos y referencias no se imprimen.
* Parasitología es un estudio independiente con Helicobacter pylori (heces), Sangre oculta en heces, Moco fecal y Coproparasitológicos simple y seriado. Las selecciones cualitativas se presentan como Parámetro · Resultado, sin Unidad, V. Ref. ni Bandera. Inmunoserología también ofrece los subestudios cualitativos de H. pylori en suero y heces y Sangre oculta en heces. Los perfiles Cardíaco y Pancreático son independientes; sus campos numéricos utilizan el mismo editor de referencias y banderas que Química. En Perfil Cardíaco, Troponina se presenta separada con solo Parámetro y Resultado; CPK, CK-MB y LDH conservan sus columnas numéricas.
* Moco fecal se captura como lista de diez filas con dos celdas por fila: nombre del campo y texto libre, sin límite de caracteres. Las entradas multilínea crecen hasta 96 px y ofrecen desplazamiento para textos extensos, conservando la densidad de la hoja. Se reutiliza la captura y su guardado; los nombres, orden y formato proceden del catálogo backend. Vista previa e informe muestran las mismas dos columnas, omitiendo filas vacías.
* Curva de tolerancia presenta una tabla única de cinco tomas (hora, glucosa medida y unidad fija) y una gráfica SVG amplia con eje temporal continuo, horas reales marcadas y cuadrícula vertical en cada toma; el eje Y se muestra de 0 a 200 mg/dL en intervalos visuales de 20. Arrastrar un punto actualiza la hora/glucosa de su fila con la precisión configurada; «Restablecer» vuelve a los valores de la captura justo antes del primer arrastre. El detalle del punto se muestra al enfocarlo con teclado sin desplazar la gráfica; al pasar el cursor se usa el tooltip del punto. La tabla y el informe usan esos mismos campos y valores; la línea institucional mantiene color y grosor en impresión. Valores fuera de la escala se indican en el borde sin alterarse. Una toma sin hora o glucosa interrumpe el trazo; fechas por fila sólo aparecen si no hay fecha del estudio o si se debe aclarar un cruce de medianoche.

* Coproparasitológico simple muestra sólo el resultado de texto libre bajo el título del subestudio, sin repetir el nombre del campo ni Unidad, V. Ref. ni Bandera. Seriado utiliza Muestra · Fecha · Hora · Turno · Resultado. Las tres primeras filas permanecen; «+ Añadir muestra» incorpora la siguiente y un icono de eliminar quita sólo esas filas añadidas. El turno se elige entre MAÑANA, TARDE y NOCHE. El resultado ofrece en gris «No se observan formas parasitarias» y una marca de verificación para aceptarlo sin escribir; también admite texto propio. La sugerencia no se guarda automáticamente. Una fila iniciada necesita fecha y resultado para publicar; hora y turno son opcionales. Las vacías se omiten. La vista previa y el PDF muestran fecha y hora en la misma columna y el turno sólo si alguna muestra lo tiene.

## 4. Color y banderas (a los bioquímicos les gustó: se conserva)

| Estado | Color de fondo | Texto/icono (obligatorio) |
|---|---|---|
| ALTO | rojo claro `#FEE2E2` | `▲ Alto` |
| BAJO | azul claro `#DBEAFE` | `▼ Bajo` |
| NORMAL | verde claro `#DCFCE7` | `Normal` |
| Sin confirmar | ámbar claro `#FEF3C7` | `Sin confirmar` |
| Error de validación | rojo `#FECACA` + borde | icono + mensaje |

Nunca se comunica algo **solo con color**. Contraste de texto ≥ 4.5:1.

## 5. Tokens de diseño (CSS variables, un solo archivo)

* Tipografía: sistema (`system-ui`), base **14 px**, tablas 13–14 px, títulos 16–18 px.
* Espaciado en múltiplos de 4 px; relleno de celda 4–6 px; radio de borde 4 px.
* Página y menú lateral blancos en claro (`#FFFFFF`) y negros en oscuro (`#000000`); paneles, entradas y tablas usan grises neutros, sin tintes marrones, crema ni rosados. El rojo/vino se reserva para botones, iconos, viñetas y acentos de jerarquía. En oscuro, entradas y marcos son más claros que el fondo.
* Se conservan los colores semánticos: Bajo azul, Normal y guardado correcto verdes, pendientes ámbar, errores y Alto rojos. Cada uno tiene tokens de texto y fondo para ambos modos. Inmunoserología conserva el rosa claro en borde y check de las selecciones de subestudios, sin rellenar de rosa la tarjeta. Sin degradados ni sombras grandes.
* Foco visible en todo elemento interactivo (contorno de 2 px).
* Listados de pacientes, órdenes, informes, papelera, usuarios, catálogo, perfiles y trazabilidad: tablas con divisiones horizontales y verticales y contenido centrado. Los campos numéricos clínicos conservan su alineación de entrada a la derecha.
* Nombres de secciones, menú y acciones rápidas de Inicio en mayúsculas mediante presentación CSS; se conserva el texto de los datos y nombres propios.
* Transiciones de interacción ≤ 150 ms. La selección de estudios se amplía al pasar el cursor o enfocar por teclado, sin desplazar celdas ni cambiar la selección. Los SVG LABMET conservan sus ciclos originales.

## 6. Microcopy

Español claro y corto. Botones con verbo: *Continuar*, *Empezar a calcular*, *Guardar ahora*, *Descartar borrador*. Errores: qué pasó + qué hacer. Estados de guardado visibles: "Guardando…", "Guardado a las 14:32", "Error — reintentar".

## 7. Prohibido

Emojis como iconos · texto de desarrollo visible · tarjetas con más de 16 px de relleno · carruseles/animaciones ajenas a §9 · pantallas intermedias que no aporten datos · formularios más largos que la pantalla · modales dentro de modales · `localStorage`/`sessionStorage`.

## 8. Qué NO usar

La carpeta `.agents/skills/` **no se usa** en este proyecto (estilos genéricos y contradictorios). Si algo no está en esta guía, se elige la opción más sobria y se registra en `docs/SUPUESTOS.md`.

## 9. Informe oficial y cargas

* La firma del responsable con prefijo **LIC.**, sin matrícula, permanece al pie de todas las páginas. Los estudios caben completos antes de la zona de firma o empiezan en otra hoja, según `docs/DECISIONES.md` §18.
* Fecha, hora de toma y hora de entrega se presentan por separado. No se imprimen hashes ni versiones en el documento.
* Mientras se descarga el documento se muestra el indicador LABMET junto al texto de carga. No se monta una versión HTML anterior como respaldo visual.
* Por solicitud del usuario (21/11/2026), login, Inicio, menú y cargas usan los SVG animados proporcionados en `RECURSOS`, copiados a `frontend/public/branding/`. El frontend funciona sin esa carpeta de origen. No se recrea la marca en otro componente ni con efectos CSS que simulen el recurso.
* Login presenta el recurso LABMET grande y centrado sobre un fondo sólido que sigue el tema; el panel semitransparente queda arriba a la izquierda, sin franja roja, e incluye el saludo institucional y el escudo SVG del Hospital Metodista. Los campos mantienen contraste y énfasis visible al enfocarlos. En pantallas pequeñas el recurso se ajusta al viewport. Inicio y menú conservan su proporción y usan el SVG metálico en claro y el de cristal en oscuro, según el tema activo, incluido el cambio manual.
* La carga usa el SVG rojo original en ambos temas, en el espacio de la tarea. La creación de orden incluye un indicador compacto. `prefers-reduced-motion` desactiva las animaciones internas de los SVG y la ampliación tipo dock de la selección de estudios y las pestañas de captura.
* La identidad del acceso, Inicio, menú y favicon es LABMET. El logo del Hospital Metodista se copia a `frontend/public/branding/` para el login; los membretes oficiales permanecen en sus recursos del backend.

## 10. Catálogo y desempeño

* Catálogo tiene su propia ruta y entrada de menú, independiente de Pacientes. Los estudios se agrupan en secciones desplegables y sus campos se consultan bajo demanda. Los perfiles rápidos guardados se presentan como tarjetas compactas (no filas de tabla) y muestran sus estudios y grupos al desplegar; los perfiles predefinidos también muestran su contenido bajo demanda.
* Estadísticas de desempeño presenta filtros de período de inicio, responsable (ADMIN) y tiempo de respuesta, indicadores, barras de volumen, gráfico circular de estados y actividad por día o semana. Los colores responden al tema. Las cantidades y leyendas acompañan a todos los gráficos; se ofrece detalle tabular desplegable.
* Los gráficos usan agregados del backend, sin cifras ficticias ni estados decorativos. Una consulta vacía muestra ceros de conteo y tiempo «Sin datos». La definición del período y de primera entrega se muestra en pantalla. Los permisos y las reglas de conteo se describen en `DECISIONES.md` §19.
