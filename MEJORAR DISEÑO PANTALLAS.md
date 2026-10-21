### REFACTOR FRONTEND: Sistema de Pestañas / Paginador para Captura de Resultados (LIS)

#### 1. Contexto y Problema Actual
En la vista actual de **Captura de resultados**, cuando una orden contiene múltiples estudios (por ejemplo: Hemograma, Hepatograma, Orina, etc.), todos los formularios de captura se renderizan verticalmente en una sola pantalla (scroll infinito). Esto satura la interfaz y dificulta el llenado para el bioquímico y borrar la palabra "URGEN LAB" del todo y reemplazarlo por "METODISTA" en la interfaz, en el texto o en el pdf

#### 2. Requerimiento Principal
Reestructurar la pantalla de captura para que funcione con **modo enfocado (un solo formulario de estudio activo a la vez)**, conservando intacto el panel derecho del informe previo en tiempo real.

1. **Diseño de Layout:**
   - **Columna Izquierda (Área de Trabajo):** Muestra **únicamente el formulario del estudio seleccionado actualmente**, ocupando todo el alto/ancho disponible de dicha sección.
   - **Columna Derecha (Vista Previa en Tiempo Real):** Se mantiene exactamente como está, actualizando los valores conforme se completan los campos del formulario activo.
   - **Barra de Navegación / Paginador Inferior:** Barra fija al pie de la columna izquierda con botones `[ < Anterior ]`, `[ Siguiente > ]` y pestañas/chips numerados con nombre.

---

#### 3. Comportamiento y Diseño de la Barra Inferior (Tabs / Paginador)

La barra inferior debe listar el catálogo total de estudios disponibles en el sistema (ej. los 14 estudios), organizados y diferenciados por su estado en la orden del paciente:

##### A. Ordenamiento de las pestañas:
1. **Primeros puestos:** Se posicionan los estudios que **ya forman parte de la orden actual** (asignados inicialmente).
2. **Puestos finales:** Se colocan los estudios que **no están incluidos** en la orden de este paciente.

##### B. Estados visuales y estilos de cada pestaña:
- **Estudio Asignado y Activo (En visualización):** Botón resaltado en color primario sólido (ej. Azul `#0284c7` o `#2563eb`), texto blanco con el índice y nombre: `1. Hemograma`.
- **Estudio Asignado pero Inactivo:** Color distintivo suave (ej. azul claro/pastel con borde o badge de estado), indicando que pertenece a la orden del paciente: `2. Hepatograma`.
- **Estudio No Asignado (Fuera de la orden):** Estilo atenuado/fantasma (fondo blanco/gris claro con borde sutil y texto gris): `7. Urocultivo`.

##### C. Dinámica de Selección y Acción "Añadir a la orden":
- Si el usuario hace clic en una pestaña de un **estudio ya asignado**:
  - Cambia inmediatamente la vista del formulario activo a ese estudio.
- Si el usuario hace clic en una pestaña de un **estudio NO asignado**:
  - Se muestra una vista previa o un banner/botón contextual visible: **`[ + Añadir estudio a esta orden ]`**.
  - Al pulsar "Añadir", el estudio pasa a formar parte de la orden actual en memoria/estado:
    - Se habilita inmediatamente su formulario de captura.
    - La pestaña cambia su estilo al color de "estudio asignado".
    - El estudio se incorpora automáticamente a la vista previa del informe de la derecha.
    - Se reorganiza como el último de la lista de estudios asignados.
    - El nuevo estudio asignado instantaneamente se mantiene y guarda en memoria para el paciente inclsuo guardandose en la pantalla de Detalle de orden en estudios solicitados   

---

#### 4. Navegación por Teclado y Botones
- `[ Siguiente ]`: Valida/guarda en el estado local el estudio actual y pasa al siguiente estudio asignado de la orden.
- `[ Anterior ]`: Regresa al estudio asignado previo.
- Si la cantidad de pestañas excede el ancho disponible, la barra debe contar con scroll horizontal fluido (`overflow-x: auto` sin romper el layout) o paginado con elipsis (`1 ... 4 5 6 ... 14`).

#### 5. Restricciones Técnicas
- **No alterar el backend:** Todos los cálculos locales, estados reactivos del formulario y la sincronización con el visor de PDF/HTML en tiempo real de la derecha deben mantenerse operativos.
- Mantener las validaciones existentes por cada estudio (alertas de sumatorias de diferenciales, rangos fuera de referencia, etc.).

#### 6. Redundnacia de botones con las misma acciones 
- **No alterar el backend:** En pantallas como Detalles de orden y Captura de resultados existe un boton guardar y otro confirmar, los cuales tienen la misma accion, seria bueno tener un solo boton para esta accion, al igual que los botones de "Capturar resutlados" como "Ingresar a Captura de resultados" (este esta en la cabecera final con un mensaje en color verde indicando lo que ingresara y obtendra es innecesario el mensaje como ese boton casi al final), tambien en la misma pantalla de detalle de orden en las primera cabecera hay informacion redundadnte que puede acoplarse en una soloa cabecera visualmente mas ordenada englobando datos del paciente, de la orden y muestra ,tampoco tiene sentido un boton de ficha completa que redirije a la misma infromacion pero mas resumida sobre todos con todas las ordenes sobre ese paciente existente, eso deberia poder verse en la seccion de Pacientes con filtrado para seleccionar x paciente y ver todas sus rodendes.

#### 7. Redireccionamiento y recientes
- **Logica de navegacion:** En la pantalla de nueva orden debajo del buscador para buscar paciente existente debera mostrar una lista con scroll sde todos los pacientes existentes sin romper la ventana o alargar la cabecera y en la ultima cabecera añadir la lista de receintes de todas las ordenes existentes tanto los publicados como los pendientes con filtro de bsucado por tiempo, fecha o ambos, y que al presionar en una de ellas te envie al detalle de esa orden con el informe completo o el de vista previa centrado y conservarse la opcion del boton para publicar e impirmir el informe si es pendiente boton para ir a la captura de datos, y un boton para volver al inicio para repetir los pasos de nueva orden sin perder la sesion actual

#### 8. Pantalla de inicio 
- **Logica de navegacion:** En esta pantalla que es la primera que debe mostrar al usuario al ingresar con sus credenciales mostrar botones (sin funcion todabia) que muestren el menu en horizonal con (ordenes coolaborativos, restaurados, historial clinico, imprimir y papelera) todos con una etiqueta debajo en tono difuso como (proximamente)

#### 9. Llenado de campos en formularios o con caracteres
- **Llenado de datos personales:** En este apartado al ingresar nombre, apellido o cualquier otro campo de escritura el sistema debe automaticamente el primer caracter de x palabra ponero en minuscual ya sea despues de un punto o con tab para que al escribir nombre salga de esta forma automatica (Juan Perez Loaiza) o cuando se mencione a un doctor usando un punto (Dr. Perez Velazo) sin embargo el usuario debe poder eliminar la segunda ves el caracter de inicio para escribir en minuscual si asi lo quisiera no debe ser en mayuscual permanentemente cada primer caracter de una palabra ya que en el apartado de justificacion (cuando se cree y habilite ) donde seran parrafos de oraciones solamente el inicio sera en mayuscual o despues de un punto.
- Al inicio de sesion o login debe incluir un ojito para ver u oculatar la contraseña, no dee ser un emogi generico sino contar con colres y paletas combinadas del ojo como se explica en el siguiente paso a continuacion.

### Aplicación de estilos mas especificos del Hospital Metodista (Navbar e Informe LIS)

#### 1. Objetivo
Implementar la identidad corporativa oficial del **Hospital Metodista** según su Manual de Marca en dos puntos clave de la interfaz:
1. **Encabezado / Sidebar superior (Botón Home / Navegación del sistema)**.
2. **Encabezado oficial del Informe Clínico** (tanto en la vista previa en tiempo real como en la impresión/exportación a PDF).

---

#### 2. Paleta de Colores y Tipografías Oficiales
- **Color Primario (Rojo Metodista):** `#E51900` (RGB: 229, 25, 0).
- **Color Secundario / Fondo:** `#FFFFFF` (Blanco).
- **Tipografía Institucional Primaria:** `'Bernard MT Condensed', sans-serif` (o fallback condensed en CSS) para títulos formales de marca.
- **Tipografía Secundaria / Lectura:** `'Dubai', sans-serif` (o fuentes del sistema como `Segoe UI`, `Inter`, `Roboto`) para tablas y datos de pacientes.

---

#### 3. Implementación en la Barra Superior / Sidebar (Home / LIS)
- **Logotipo de la barra:**
  - Sustituir el recuadro genérico actual ("LIS Laboratorio Metodista") por la variante **Uso Reducido / Isotipo** del manual (el imagotipo ovalado con la cruz y el caduceo médico).
  - Asegurar que el fondo del imagotipo conserve su blanco y rojo oficial sin transparencias que deformen la cruz.
  - Al hacer clic en el isotipo o en el texto "Hospital Metodista", debe funcionar como acceso directo a la pantalla de Inicio / Órdenes pendientes (`/home` o `/`).
- **Acentos del Sistema:**
  - Ajustar los botones principales o badges de estado prioritarios para usar el tono de marca `#E51900` o integrarlo coherentemente con el diseño limpio del LIS.

---

#### 4. Cabecera del Informe de Laboratorio (Vista Previa y Documento Final)
En el contenedor del informe clínico (panel derecho de captura de resultados y plantilla de impresión):

- **Encabezado alineado:**
  - **Izquierda / Centro:** Colocar el **Imagotipo Completo** del Hospital Metodista (Isotipo + "HOSPITAL METODISTA" en Bernard MT Condensed + lema "Al servicio de tu salud").
  - **Subtítulo del Servicio:** Justo debajo, indicar claramente en tipografía clara: `LABORATORIO DE ANÁLISIS CLÍNICOS`.
  - Respetar los márgenes de seguridad (área de restricción del manual de marca) para que el logo no quede pegado a los bordes de la página ni a la tabla de datos del paciente.
- **Detalle de datos del paciente:**
  - Mantener la grilla de metadatos (Paciente, C.I., Edad/Sexo, Médico Solicitante, Fecha/Hora, Pieza/Cama) limpia con líneas divisoras sutiles (`#E5E7EB` o `#E51900` en bordes principales).
- **Compatibilidad con Impresión (`@media print`):**
  - Asegurar que la imagen del imagotipo esté en formato SVG o PNG de alta resolución (300 DPI) con fondo blanco sólido (`background: white`) para evitar que fondos oscuros o colores degradados afecten la impresión.

---

#### 5. Reglas de Marca a Cumplir (Restricciones):
- Prohibido estirar, distorsionar la relación de aspecto o rotar el logotipo.
- No aplicar degradados ni filtros CSS (`filter: hue-rotate` o sombras saturadas) sobre el escudo.
- Prohibido dejar el fondo del isotipo transparente sobre fondos con color; debe ubicarse sobre fondo blanco o con su contenedor limpio.

#### 6. Contexto y Objetivo
En el componente de la vista previa en tiempo real del informe de laboratorio (panel derecho de la pantalla de captura de resultados, y su vista de impresión), actualmente solo se muestra texto plano como título (`LABORATORIO CLINICO METODISTA / INFORME DE ANÁLISIS CLÍNICOS`).
Se requiere integrar el archivo oficial del logo (`LOGO SVG.svg` que ya se encuentra ubicado en la raíz del proyecto / carpeta pública) en la parte superior, completamente centrado y sobre fondo blanco limpio.

---

#### 7. Requerimientos de Diseño y Maquetación

1. **Ubicación del archivo:**
   - Usar el archivo `LOGO SVG.svg` (mover o referenciar desde `/public/LOGO SVG.svg` o importarlo directamente según la estructura del proyecto en React/Vite: `import hospitalLogo from '/LOGO SVG.svg'`).

2. **Estructura del Encabezado (`<header>` del Informe):**
   - **Contenedor superior:**
     - Fondo: estrictamente blanco (`background-color: #FFFFFF`).
     - Alineación: completamente centrado horizontalmente (`display: flex; flex-direction: column; align-items: center; justify-content: center;`).
     - Padding: margen interior adecuado para respetar el área de restricción del manual de marca (ej. `padding: 1rem 0;`).
   - **Renderizado del Logo SVG:**
     - Etiqueta: `<img src={hospitalLogo} alt="Hospital Metodista - Al servicio de tu salud" />`
     - Dimensiones recomendadas: altura controlada para no desplazar excesivamente el contenido clínico (ej. `max-height: 90px; width: auto; object-fit: contain; margin-bottom: 0.5rem;`).
     - Prohibido distorsionar el `aspect-ratio` o estirar la imagen.
   - **Subtítulo Institucional:**
     - Debajo del SVG, colocar centrado el subtítulo formal:
       ```html
       <h2 class="text-sm md:text-base font-bold tracking-wider text-gray-800 uppercase mt-1">
         Informe de Análisis Clínicos
       </h2>
       ```
     - Si existía el texto anterior `LABORATORIO CLINICO METODISTA`, se puede retirar o estilizar como subtítulo secundario fino, ya que el SVG ya contiene el imagotipo completo ("HOSPITAL METODISTA - Al servicio de tu salud").

3. **Separación con los Datos del Paciente:**
   - Añadir una línea divisoria sutil (`border-b border-gray-300` o un separador fino en rojo institucional `#E51900`) antes del bloque de metadatos del paciente (Nombre, C.I., Edad/Sexo, Médico, Fecha/Hora, Cama).

4. **Reglas para Impresión (`@media print`):**
   - Asegurarse de que el logo se imprima nítido en modo vector SVG sin bordes recortados:
     ```css
     @media print {
       header.report-header {
         background: #ffffff !important;
         page-break-inside: avoid;
       }
       header.report-header img {
         max-height: 85px !important;
         print-color-adjust: exact;
         -webkit-print-color-adjust: exact;
       }
     }
     ```

#### 8. Criterios de Aceptación
- El SVG se muestra nítido, sin pérdida de resolución ni fondo transparente que altere sus colores.
- El encabezado permanece centrado tanto en el panel derecho de vista previa como en la vista a pantalla completa o modal de impresión.
- No afecta la reactividad en tiempo real de los campos clínicos calculados.

