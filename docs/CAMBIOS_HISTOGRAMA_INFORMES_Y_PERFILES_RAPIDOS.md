# Cambios en hemograma, informes, tema oscuro y perfiles

**Fecha:** 12 de noviembre de 2026

## Hemograma e inmunoserología

- La captura muestra la suma porcentual del diferencial debajo de sus campos y comunica visualmente el resultado. Se conservó sin cambios la tolerancia vigente del backend: 99–101% para la regla `SUMA_IGUAL`.
- El informe presenta cada diferencial en una sola fila con valores relativo y absoluto, referencia clínica del parámetro según el paciente y separadores de tabla. También imprime la suma del diferencial.
- La etiqueta de Cayados es editable durante la captura, se guarda en la orden y se conserva en el informe oficial. El backend limita el texto a 80 caracteres.
- ASTO y FR usan captura Reactivo/No reactivo, dilución opcional y cálculo semicuantitativo. En los informes se presenta el resultado clínico resumido (por ejemplo, `Reactivo · 1/32 · 256 UI/mL`); sensibilidad, lote, vencimiento y controles quedan en el dato de auditoría persistido, pero no se imprimen como texto del resultado. La referencia clínica permanece en su columna.
- Se añadió Troponinas como selección Positivo/Negativo en Inmunoserología mediante la migración `0005_troponinas_inmunoserologia.py`.

## Informe y vista previa

- La vista previa y el informe vigente se generan como PDF real multipágina en papel Carta. La captura y el detalle oficial usan el visor PDF incorporado en el navegador, con navegación, zoom, impresión y descarga.
- El PDF incluye membrete, logotipos y marcas de agua de `frontend/public/branding/`; diferencia el borrador con la marca «NO APROBADO». El encabezado y pie se repiten en cada página con numeración real.
- Se corrigió la ruta base de recursos estáticos para que WeasyPrint encuentre PNG/SVG en todas las páginas. El encabezado y pie usan elementos paginados repetibles, con márgenes reservados para que no se monten sobre estudios ni tablas; el número de página ocupa una línea independiente.
- Se omiten parámetros vacíos, secciones sin resultados y observaciones sin contenido. Los informes oficiales se generan desde el snapshot vigente; las peticiones de impresión se registran en auditoría.
- WeasyPrint 70.0 genera el documento en backend. Las dependencias de sistema para Pango y fuentes se declaran en la imagen Docker y `WeasyPrint==70.0` junto con `Jinja2==3.1.6` en `backend/requirements.txt`.
- Los datos de contacto del pie se tomaron del documento de diseño del proyecto y requieren confirmación institucional antes de publicar documentos oficiales.

## Tema oscuro

- Se mejoró el contraste del texto, formularios, menús, tablas y estados hover/seleccionados del tema oscuro.
- Las hojas HTML antiguas del informe conservan superficie clara, y el PDF se renderiza de forma independiente; las reglas del tema oscuro no alteran su salida.

## Perfiles rápidos

- Se añadió CRUD de perfiles rápidos personales: nombre, selección de estudios y grupos. Se guardan por usuario y aparecen al crear una orden. Los perfiles preconfigurados del catálogo no se modifican ni eliminan.

## Verificación

- `npm run build`: correcto.
- `python -m compileall -q backend/app backend/alembic/versions`: correcto.
- `git diff --check`: correcto.
- `backend/tests/test_pdf_report.py`: pasó en el entorno virtual del backend; verifica marcas de agua, salida clínica resumida y paginación.
- No se aplicaron migraciones ni se ejecutó la suite integrada contra una base de datos.
