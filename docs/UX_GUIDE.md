# Guía de UX — LIS Laboratorio Clínico

> **Esta guía manda sobre cualquier skill de diseño.** Los usuarios son bioquímicos acostumbrados al Excel; quieren **rapidez, pocos clics y fidelidad a su hoja**. Diseño minimalista y funcional, no "llamativo".
> Ubicación: `docs/UX_GUIDE.md`. Referenciada desde `AGENTS.md`.

## 1. Principios (en orden de prioridad)

1. **Fidelidad al Excel.** Disposición de hoja: filas `Parámetro · Resultado · Unidad · Valores de referencia · Bandera`, estudios agrupados como en las plantillas `HC-QMC-SEROL-EGO` y `HC-QMC-SERO-PROT`, mismo orden de campos que `definitions.py`.
2. **Una tarea = una pantalla.** Crear una orden no debe requerir bajar de página ni pasar por más de una confirmación.
3. **Menos clics.** Teclado primero: `Tab`/`Enter` avanzan al siguiente campo (como en Excel), `Esc` cierra diálogos, foco inicial en el primer campo útil.
4. **Densidad útil.** Se aprovecha el ancho completo de la pantalla. Sin tarjetas decorativas ni rellenos grandes.
5. **Lo importante, a la vista:** paciente, hora de inicio, estado (completo/faltan N) y banderas siempre visibles.
6. **Sin ruido.** Cero texto de desarrollo ("Fase 3", "Bloque 5", "Próximamente"), cero emojis, cero animaciones decorativas. Lo que no existe aún, **no se muestra**.

## 2. Pantallas objetivo

Resolución de referencia: **1366×768** (laptop del laboratorio) y 1920×1080. Todo el flujo principal debe funcionar sin scroll de página en 1366×768, salvo listas largas.

| Pantalla | Estructura |
|---|---|
| **Estructura general** | Menú lateral izquierdo **desplegable** (iconos + texto; colapsado = solo iconos). Barra superior mínima: nombre de la pantalla + estado de sesión. Pie del menú: usuario, rol, "Clave", "Salir" |
| **Inicio** | Fila superior de **acciones rápidas** (botones grandes): *Nueva orden*, *Buscar paciente*, *Mis pendientes (N)*; ADMIN: *Usuarios*. **Debajo, panel horizontal "Recientes"**: tabla de los últimos 15 trabajos (paciente, estudios, estado, hora, botón *Continuar*). Llena la pantalla; no queda vacía |
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
* La vista previa usa **fuente ≥ 14 px**, formato de informe (membrete, datos del paciente, tabla por estudio) y se actualiza al instante.

## 4. Color y banderas (a los bioquímicos les gustó: se conserva)

| Estado | Color de fondo | Texto/icono (obligatorio) |
|---|---|---|
| ALTO | rojo claro `#FEE2E2` | `▲ Alto` |
| BAJO | azul claro `#DBEAFE` | `▼ Bajo` |
| NORMAL | verde muy claro `#DCFCE7` | `Normal` |
| Sin confirmar | ámbar `#FEF3C7` | `Sin confirmar` |
| Error de validación | rojo `#FECACA` + borde | icono + mensaje |

Nunca se comunica algo **solo con color**. Contraste de texto ≥ 4.5:1.

## 5. Tokens de diseño (CSS variables, un solo archivo)

* Tipografía: sistema (`system-ui`), base **14 px**, tablas 13–14 px, títulos 16–18 px.
* Espaciado en múltiplos de 4 px; relleno de celda 4–6 px; radio de borde 4 px.
* Paleta neutra (grises) + **un** color de acento (azul). Sin degradados ni sombras grandes.
* Foco visible en todo elemento interactivo (contorno de 2 px).
* Transiciones ≤ 150 ms y solo funcionales (abrir/cerrar panel).

## 6. Microcopy

Español claro y corto. Botones con verbo: *Continuar*, *Empezar a calcular*, *Guardar ahora*, *Descartar borrador*. Errores: qué pasó + qué hacer. Estados de guardado visibles: "Guardando…", "Guardado a las 14:32", "Error — reintentar".

## 7. Prohibido

Emojis como iconos · texto de desarrollo visible · tarjetas con más de 16 px de relleno · carruseles/animaciones decorativas · pantallas intermedias que no aporten datos · formularios más largos que la pantalla · modales dentro de modales · `localStorage`/`sessionStorage`.

## 8. Qué NO usar

La carpeta `.agents/skills/` **no se usa** en este proyecto (estilos genéricos y contradictorios). Si algo no está en esta guía, se elige la opción más sobria y se registra en `docs/SUPUESTOS.md`.
