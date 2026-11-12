# IMPLEMENTACIÓN DEFINITIVA: INFORMES CLÍNICOS Y CAPTURA DE RESULTADOS — LIS HOSPITAL METODISTA

## OBJETIVO

Corregir integralmente el sistema de generación, vista previa e impresión de informes clínicos del LIS, conservando la lógica existente y mejorando su presentación profesional.

El sistema utiliza FastAPI, React/TypeScript y PostgreSQL.

Se adjuntan capturas del módulo actual y una fotografía del informe físico utilizado por el Hospital Metodista. Deben utilizarse como referencias visuales.

**Antes de modificar código, inspecciona el repositorio y determina cómo funcionan actualmente la captura de resultados, el renderizado de informes, la autorización y la impresión. No presupongas nombres de funciones o archivos.**

## 1. MOTOR REAL DE DOCUMENTOS PDF

El problema actual es que la vista previa aparenta ser un documento HTML continuo que sobrepasa los límites de una hoja carta.

Implementar generación real de PDF multipágina.

Tecnologías preferidas:

- FastAPI: generación y entrega segura del documento.
- Jinja2: plantilla HTML del informe.
- WeasyPrint: conversión HTML/CSS a PDF con paginación.
- React-PDF y PDF.js: visualización en React.
- PyMuPDF y pytest: validación automatizada del PDF.

Comprobar compatibilidad con el entorno antes de instalar dependencias. Si WeasyPrint no resulta adecuado, justificar una alternativa como Playwright/Chromium. No incorporar motores redundantes.

Requisitos:

- Papel Letter: 215,9 × 279,4 mm.
- Márgenes de impresión seguros.
- Paginación física auténtica.
- Encabezado y pie institucional en cada página.
- Numeración Página X de Y.
- Repetición de encabezados de tabla al continuar en otra página.
- Evitar divisiones de filas y resultados.
- Evitar encabezados de estudio huérfanos al final de una página.
- Permitir que estudios extensos continúen en otra página.
- No ocultar contenido mediante overflow.
- No utilizar escalado global para comprimir arbitrariamente los informes.
- No imprimir secciones vacías.
- No permitir que firmas, notas o pies se superpongan al contenido.

## 2. VISTA PREVIA PROFESIONAL

Reemplazar la representación HTML actual por un visor del PDF generado.

Mantener las funcionalidades existentes de vista previa dentro de Captura de resultados y en pantalla completa.

Incorporar:

- Zoom porcentual.
- Ajustar ancho.
- Ajustar página.
- Navegación entre páginas.
- Contador de páginas.
- Impresión.
- Descarga autorizada.
- Indicador de carga.
- Manejo de errores.
- Fondo gris oscuro alrededor de las páginas.
- Separación visual entre hojas.

La vista previa, el PDF descargado y el documento impreso deben utilizar el mismo contenido paginado.

El zoom solo debe modificar la visualización, nunca la distribución física del documento.

Evitar generar PDF nuevo en cada pulsación de teclado. Utilizar actualización diferida o explícita y controlar peticiones obsoletas.

## 3. IDENTIDAD VISUAL Y MEMBRETE

Se han incorporado los siguientes recursos en:

frontend/public/branding/

- membrete-superior.svg
- membrete-inferior.svg
- marca-agua-no-aprobado.svg
- marca-agua-institucional.svg

Inspeccionar estos recursos e integrarlos en la plantilla.

Reservar posiciones para:

- logo-labmet.png
- logo-metodista.png

Estos dos logotipos deben provenir de archivos oficiales. No inventar ni redibujar logotipos institucionales.

Diseñar un encabezado con LABMET a la izquierda, Hospital Metodista en la zona central y decoración institucional roja.

Mantener el equilibrio entre encabezado y pie como en la fotografía original, pero con una presentación más limpia.

El pie debe admitir dirección, teléfonos y otros datos institucionales configurables, sin inventar información.

Usar tipografía legible, jerarquía visual clara, fondo blanco, rojo institucional y grises suaves.

El membrete no debe ocupar un espacio excesivo que reduzca innecesariamente la capacidad de las tablas.

Los recursos deben estar disponibles tanto para el frontend como para el generador PDF del backend, sin depender de URLs externas ni de rutas relativas frágiles.

### 3.1. INFORMACIÓN INSTITUCIONAL OBLIGATORIA

El membrete no debe ser únicamente decorativo. Debe incluir información institucional real y legible, siguiendo la fotografía del informe físico proporcionada.

**Encabezado:**

- Logotipo LABMET.
- Logotipo oficial del Hospital Metodista.
- Nombre: LABORATORIO CLÍNICO.
- Nombre: Hospital Metodista.
- Identificación institucional: Iglesia Evangélica Metodista en Bolivia.
- Título principal del documento: RESULTADOS.
- Subtítulo: ANÁLISIS DE LABORATORIO CLÍNICO.

**Pie de página:**

- Dirección: 14 de Septiembre N.º 5809, calle 12 de Obrajes.
- Teléfonos: 2 783371 - 2 783509 - 2 783510.
- Emergencias: 73258212.
- Numeración: Página X de Y.
- Información adicional de validación o identificación documental, si corresponde.

Estos datos se han transcrito de la fotografía institucional de referencia. Verificar su exactitud antes de utilizarlos en producción.

**Requisitos de presentación:**

1. Distribuir la información sin saturar el documento.
2. Incorporar iconos pequeños para ubicación, teléfonos y emergencias cuando mejoren la legibilidad.
3. Mantener el rojo institucional para los elementos principales.
4. Garantizar que los datos de contacto sean legibles al imprimir en papel carta.
5. Repetir el pie institucional en todas las páginas.
6. Evitar superposiciones con tablas, firmas y observaciones.
7. Mantener un diseño coherente entre informes aprobados y no aprobados.
8. No convertir los teléfonos ni la dirección en parte de una imagen: deben ser texto real, seleccionable e imprimible dentro del PDF.
9. Centralizar estos datos en una configuración institucional reutilizable, evitando escribirlos directamente en múltiples componentes.
10. Permitir actualizar posteriormente la dirección, teléfonos y otros datos sin modificar la estructura del informe.

**IMPORTANTE:** utilizar las imágenes SVG únicamente para elementos gráficos. La información institucional, los resultados clínicos y los datos del paciente deben renderizarse como texto real.

El diseño final debe respetar la identidad de la hoja física del Hospital Metodista, pero mejorar la distribución, alineación, tipografía y aprovechamiento del espacio.

## 4. REDISEÑO DE LAS TABLAS IMPRESAS

Actualmente las tablas tienen alineación y distribución mejorables.

Implementar tablas clínicas con celdas y bordes definidos, similares al formato físico del laboratorio, pero modernizadas.

Estructura estándar:

Parámetro | Resultado | Unidad | Valor de referencia | Bandera

Requisitos:

- Bordes horizontales y verticales finos.
- Cabeceras con fondo gris claro.
- Filas alternadas muy sutilmente.
- Resultados numéricos alineados correctamente.
- Unidades sin saltos innecesarios.
- Indicadores Alto, Bajo y Normal.
- Tipografía apta para impresión.
- No utilizar colores como único medio para identificar alteraciones.
- Mantener la información completa.
- Permitir observaciones largas.
- Mantener nombres de parámetros legibles.
- Utilizar anchuras de columnas adaptadas al tipo de estudio.

Evitar que resultados textuales largos se compriman en columnas estrechas. Utilizar ajustes de línea, filas de detalle o una disposición específica cuando sea necesario.

No todas las pruebas deben utilizar la misma distribución rígida.

## 5. HEMOGRAMA COMPLETO: TABLA ESPECIALIZADA

Este punto es prioritario.

La fotografía del informe físico muestra que los resultados relativos y absolutos del diferencial leucocitario aparecen juntos, horizontalmente.

Actualmente el sistema puede representar esos valores en una misma celda o como filas independientes, dificultando la lectura.

Implementar una presentación especializada para el hemograma.

Estructura recomendada:

Parámetro | Relativo | Absoluto | Unidad | Referencia | Bandera

Ejemplo de estructura:

Segmentados | 54 % | 2.700/mm³ | ... | ... | Bajo

Linfocitos | 45 % | 2.250/mm³ | ... | ... | Alto

El valor relativo y absoluto deben aparecer en la misma fila del parámetro, en columnas separadas y correctamente alineadas.

No duplicar parámetros ni crear filas artificiales para el recuento absoluto.

Diferenciar visualmente:

- Serie roja.
- Serie blanca.
- Fórmula leucocitaria.
- Plaquetas.
- Otros parámetros del hemograma.

Conservar los parámetros realmente configurados en el catálogo. No crear resultados ficticios.

Cuando el sistema almacene un parámetro compuesto, representar sus componentes mediante una estructura explícita sin alterar ni perder el valor original.

Las referencias deben corresponder al sexo y edad del paciente cuando sea clínicamente aplicable.

No copiar valores de referencia desde la fotografía sin validación del laboratorio.

Si no existe referencia válida para ese paciente, mostrar una indicación neutral y evitar generar una bandera clínica incorrecta.

Revisar la presentación de las unidades de recuentos celulares, valores relativos y absolutos, sin convertir o recalcular datos silenciosamente.

## 6. REDISEÑO DE CAPTURA DE RESULTADOS

Mejorar también la tabla editable del módulo Captura de resultados.

Actualmente los encabezados y campos de entrada no están alineados uniformemente.

Aplicar un sistema de cuadrícula consistente.

Columnas:

Parámetro | Resultado | Unidad | V. Ref. | Bandera

Implementar:

- Anchos de columna coherentes.
- Separadores verticales y horizontales.
- Campos centrados dentro de sus celdas.
- Valores numéricos alineados.
- Etiquetas legibles.
- Estados de validación visibles.
- Filas con altura consistente.
- Encabezados perfectamente alineados con los datos.
- Diseño adaptable sin superposición.
- Navegación por teclado conservada.
- Indicadores clínicos automáticos según las reglas existentes.

Para el diferencial leucocitario, si existen valores relativos y absolutos, utilizar subcolumnas apropiadas en lugar de concatenarlos en un campo.

No alterar la persistencia de datos ni la validación clínica sin analizar sus dependencias.

Conservar autoguardado, navegación entre estudios, observaciones y todas las funcionalidades actuales.

## 7. MARCA DE AGUA Y AUTORIZACIÓN

Implementar dos variantes del mismo informe.

### A. INFORME NO APROBADO

Aplicar en cada página:

NO APROBADO

Características:

- Texto diagonal centrado.
- Rojo institucional semitransparente.
- Tamaño grande.
- Visible tanto en pantalla como en impresión.
- No debe tapar completamente los resultados.
- Integrado en el PDF, no como superposición exclusiva del frontend.
- Mantener membrete y paginación normal.

La marca debe generarse a partir del estado real de autorización del backend.
Actualización importante del diseño institucional:

He proporcionado una nueva imagen del logotipo LABMET, mucho más fiel al original. Utiliza este recurso para el membrete y también para la marca de agua.

En todos los informes, colocar el logotipo LABMET ampliado y centrado detrás del contenido clínico, con una opacidad aproximada del 5–8 %, respetando la legibilidad de las tablas.

En los informes NO APROBADOS, mantener esa marca de agua institucional y añadir encima el texto diagonal «NO APROBADO», de gran tamaño y color rojo semitransparente.

Ambas marcas deben formar parte del PDF real, repetirse en todas las páginas y permanecer detrás del contenido clínico.

No aplicar opacidad al contenedor completo del informe, únicamente a las marcas de agua. No alterar el tamaño ni la paginación de las tablas.

### B. INFORME APROBADO

- No mostrar NO APROBADO.
- Permitir marca de agua institucional tenue.
- Mostrar datos de validación del bioquímico cuando correspondan.
- Incluir firma o sello únicamente cuando estén autorizados y disponibles.
- No simular firmas.

El backend debe verificar permisos y estados al generar o entregar el documento.

No permitir que un parámetro manipulable del navegador convierta un informe no aprobado en aprobado.

Evitar que URLs de documentos antiguos o archivos en caché permitan descargar versiones aprobadas indebidamente.

Conservar trazabilidad de emisión y validación.

## 8. OBSERVACIONES Y DATOS DEL PACIENTE

Presentar de forma compacta:

- Nombre completo.
- CI.
- Edad.
- Sexo.
- Número de orden.
- Fecha.
- Bioquímico responsable cuando corresponda.

Respetar los campos existentes y sus reglas de privacidad.

Las observaciones deben aparecer en el estudio correspondiente.

Las observaciones finales deben aparecer al terminar los resultados.

No duplicar información ni crear bloques vacíos.

## 9. PRUEBAS OBLIGATORIAS

Validar:

1. Un estudio corto.
2. Un hemograma completo.
3. Varios estudios combinados.
4. Resultados textuales largos.
5. Observaciones extensas.
6. Informes de varias páginas.
7. Estudios sin resultados.
8. Referencias diferenciadas por sexo y edad.
9. Informe aprobado.
10. Informe no aprobado.
11. Impresión en papel carta.
12. Vista previa normal y pantalla completa.
13. Filas de tablas próximas al final de una página.
14. Páginas con encabezado, pie y numeración correctos.

Verificar que el contenido no se recorte, superponga, desaparezca ni cambie entre vista previa y PDF.

Añadir pruebas para comprobar la presencia de marcas de agua y la cantidad de páginas cuando corresponda.

## 10. INTEGRIDAD Y FORMA DE TRABAJO

No eliminar ni sobrescribir cambios existentes del repositorio.

No modificar innecesariamente autenticación, órdenes, pacientes, catálogos o procesos de aprobación.

No ejecutar migraciones destructivas.

Primero:

1. Inspeccionar el código existente.
2. Identificar el origen del problema de paginación.
3. Determinar las dependencias necesarias.
4. Explicar brevemente la arquitectura propuesta.

Después implementar:

1. Motor PDF.
2. Plantilla y membrete.
3. Paginación.
4. Visor PDF.
5. Hemograma especializado.
6. Mejoras de captura.
7. Marcas de agua y autorización.
8. Pruebas y documentación.

Al finalizar, entregar:

- Archivos modificados.
- Dependencias instaladas.
- Comandos de ejecución.
- Pruebas ejecutadas.
- Resultado de la validación.
- Problemas pendientes.

**CRITERIO FINAL DE ACEPTACIÓN:** un informe clínico debe visualizarse como una secuencia de hojas carta reales, con membrete institucional, tablas correctamente alineadas, hemograma con valores relativos y absolutos en columnas separadas, paginación sin desbordamientos y marca de agua NO APROBADO cuando corresponda, sin alterar los datos ni la lógica clínica del LIS.
