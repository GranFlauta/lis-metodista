# PROMPT — FASE 3.6: Rediseño de la interfaz (fiel al Excel, pocos clics)

> **Requisito previo:** Fase 3.5 cerrada (tag `fase-3-5-cerrada`).
> **Cómo usarlo:** pégalo completo, en la raíz del repositorio. Sin recortar.

=== INICIO DEL PROMPT ===

# 1. ROL Y REGLAS

Eres un ingeniero senior de frontend con criterio de producto, en un **sistema clínico**. Los usuarios son **bioquímicos acostumbrados a Excel**: piden rapidez, pocos clics, fidelidad a su hoja y diseño **minimalista**.

* **Lee `docs/UX_GUIDE.md` completa antes de empezar. Es la autoridad de diseño.** No uses skills de diseño externos.
* No cambies reglas de negocio ni el esquema (`db/init/*.sql`, `backend/app/catalog/**`). Los únicos cambios de backend permitidos son los de §5, sin migraciones.
* No inventes. Lo no definido → `docs/SUPUESTOS.md`, con la opción más sobria.
* Evidencia real en cada punto. Sin evidencia = no hecho.
* Todo lo que funciona hoy **debe seguir funcionando**: duplicados (409/advertencias), valores por defecto, banderas, autoguardado, solo lectura de ADMIN, token en memoria.

# 2. PUERTA DE ENTRADA

Pega: `git tag --list` (debe existir `fase-3-5-cerrada`), `git status` limpio, y la salida de la suite completa (`Ran N tests`, `OK`, sin `skipped`). Anota `N`.
**Primera respuesta obligatoria (sin código):** resumen de 10 líneas, lista de archivos a crear/modificar y dudas **bloqueantes** (o "ninguna").

# 3. DECISIONES (añádelas como §14 de `docs/DECISIONES.md`; única edición permitida)

```markdown
## 14. Decisiones de Fase 3.6 (interfaz)

* **D36-01** La interfaz sigue `docs/UX_GUIDE.md`. Lo que no existe aún no se muestra (sin "Próximamente").
* **D36-02** La orden se crea al pulsar **Empezar a calcular** en la ventana de confirmación (no antes), para no dejar borradores vacíos.
* **D36-03** "Fecha y hora de inicio" se guarda en `ordenes.fecha_hora_toma_muestra`, editable y precargada con la hora actual. (PENDIENTE de confirmar con el laboratorio si "inicio del estudio" y "toma de muestra" deben ser campos distintos.)
* **D36-04** El menú pasa a barra lateral izquierda desplegable. "Pendientes" es una entrada propia con contador.
* **D36-05** La vista previa de la captura es una representación en pantalla; el PDF oficial es de la Fase 5.
* **D36-06** FUERA de esta fase: Estudio instantáneo, rol VISITANTE, notificaciones/temporizadores e impresión (ver `PROPUESTA_FUNCIONES_NUEVAS.md`).
```

# 4. ALCANCE

**Dentro:** estructura general (menú lateral), Inicio, Nueva orden en una pantalla, ventana de confirmación, Captura densa con vista previa grande, Pacientes (búsqueda/gestión), Órdenes/Pendientes, limpieza de textos y emojis, los 3 cambios de backend de §5.
**Fuera:** impresión, PDF, publicar, folios, Estudio instantáneo, VISITANTE, notificaciones, anti-captura, cualquier regla de negocio nueva.
**Dependencias nuevas:** ninguna (iconos como SVG en línea; CSS propio con variables).

# 5. CAMBIOS DE BACKEND (mínimos, con tests)

**B1 — `GET /api/pacientes`** añade filtros opcionales `sexo` (`M|F`), `creado_desde`, `creado_hasta` (fechas) y `con_pendientes` (bool). Cada elemento añade `pendientes: int` = órdenes del **usuario actual** en `INCOMPLETO`/`COMPLETO` para ese paciente; para ADMIN = de **todos** los autores, y si devuelve algún `pendientes > 0` se registra **un** `ADMIN_VE_PRIVADO` (`detalle={"recurso":"pacientes_pendientes"}`). Valores inválidos → 400 `VALIDACION`.
**B2 — `GET /api/ordenes`** añade a cada elemento: `fecha_hora_toma_muestra`, `edad_anios`, `autor: {nombres, apellido_paterno}` y `estudios_detalle: [{codigo, nombre}]`. Se **conserva** `estudios` (códigos) para no romper lo existente.
**B3 — `GET /api/ordenes/resumen`** → `{"incompletas": n, "completas": n, "pendientes": n}` del usuario actual; ADMIN = totales de todos (solo conteos, sin auditoría). Requiere sesión.

**Tests (PostgreSQL real, datos ficticios):**
1. Filtro `sexo` y rango de fechas de creación.
2. `con_pendientes=true` devuelve solo pacientes con pendientes **propios**.
3. `pendientes` cuenta solo `INCOMPLETO`/`COMPLETO` (no `PUBLICADA`) y solo las propias.
4. ADMIN: `pendientes` de todos y un solo `ADMIN_VE_PRIVADO`; sin pendientes no audita.
5. Filtros inválidos → 400.
6. Lista de órdenes: nuevos campos presentes y `estudios` intacto.
7. `resumen` correcto para BIOQUIMICO y ADMIN; sin token → 401.
8. Regresión: `N` + nuevos, `OK`, `skipped=0`.

# 6. FRONTEND — ESPECIFICACIÓN

## 6.1 Estructura general
* **Menú lateral izquierdo desplegable:** expandido (≥ 1280 px) con iconos + texto; colapsado = solo iconos con *tooltip*. Estado en memoria de React (no `localStorage`).
* Entradas (BIOQUIMICO): **Inicio · Nueva orden** (destacada) **· Pacientes · Pendientes (contador de B3)**. ADMIN: Inicio · Pacientes · Órdenes · Administración (Usuarios, Configuración de sesión).
* Pie del menú: nombre, rol, *Clave*, *Salir*.
* **No se muestran** entradas de módulos inexistentes ni textos "Próximamente"/"Fase"/"Bloque". Sin emojis.
* Barra superior mínima con el título de la pantalla actual y, si aplica, el aviso de sesión (Fase 3.5).

## 6.2 Inicio
1. Fila de **acciones rápidas** (botones grandes): *Nueva orden*, *Buscar paciente*, *Mis pendientes (N)*; ADMIN: *Usuarios*.
2. Debajo, **panel horizontal "Recientes"** a todo el ancho: últimos **15** trabajos (`GET /api/ordenes?limit=15`; ADMIN ve de todos): paciente, estudios, estado, hora de inicio, autor (solo ADMIN), botón **Continuar** (abre la captura). Si está vacío: mensaje corto "Aún no hay trabajos hoy" con el botón *Nueva orden*.
3. Sin tarjetas de bienvenida ni texto de estado del sistema.

## 6.3 Nueva orden (una sola pantalla)
Ruta `/ordenes/nueva`. **Sin scroll de página en 1366×768.** Tres zonas en fila:
1. **Paciente:** un **buscador único** (CI o nombre, *debounce* 300 ms) con resultados desplegables; al elegir uno se muestra su resumen compacto (CI, nombre, edad, sexo) con opción *Cambiar*. Si no existe: enlace **"Crear paciente nuevo"** que despliega **en la misma zona** un formulario compacto (CI/Sin CI, complemento, nombres, apellidos, sexo, fecha de nacimiento **o** edad). Mantén las reglas de la Fase 2 (CI vs. "Sin CI", 409 con *Usar el paciente existente*).
2. **Estudios:** botones de **perfil** (los 2 de `GET /api/catalogo/perfiles`) que preseleccionan; los 9 estudios como **interruptores** compactos en cuadrícula; Inmunoserología despliega **en línea** sus grupos como casillas (etiqueta: código humanizado + parámetros en texto pequeño). Contador "N estudios seleccionados".
3. **Datos de la orden:** origen, médico solicitante, pieza (campos cortos), y debajo el **resumen** + botón **Continuar** (deshabilitado sin paciente y sin ≥ 1 estudio).
* **Recorrido objetivo:** paciente existente = buscar → clic en resultado → clic en perfil → **Continuar** → **Empezar a calcular** (**4 clics** más escritura). Paciente nuevo = rellenar con `Tab` → perfil → Continuar → Empezar (**3 clics**).

## 6.4 Ventana de confirmación (modal)
Al pulsar **Continuar** se abre una ventana con: **CI, nombre completo, edad (años), estudios a realizar (lista) y fecha y hora de inicio** (campo editable precargado con ahora; D36-03). Botones: *Volver* y **Empezar a calcular**.
* *Empezar a calcular* ejecuta `POST /api/ordenes` (con `fecha_hora_toma_muestra` = la hora indicada) y navega **directo** a la captura. Foco inicial en este botón; `Enter` lo activa, `Esc` cierra.
* Maneja en esta ventana: error de validación, `ORDEN_DUPLICADA_EN_CURSO` (tarjeta de bloqueo con el autor y los estudios, sin opción de saltarla) y CI duplicado. Las **advertencias** (solapamiento) se muestran como banner superior de la captura.

## 6.5 Captura (fiel al Excel)
Ruta `/ordenes/:id/captura`, **ancho completo** (sin `max-width` de 1280 px).
* **Barra fija superior:** paciente, CI, edad, **hora de inicio**, indicador *Completo / Faltan N*, "Guardado a las hh:mm", botones *Guardar ahora* y *Confirmar valores por defecto*.
* **Izquierda (≈ 55 %) — hoja de captura:** cada estudio es un bloque con encabezado (`Hemograma  9/12`) y filas de 28–32 px con columnas **Parámetro · Resultado · Unidad · V. Ref. · Bandera**. En pantallas anchas los bloques se acomodan en **columnas** (mínimo 420 px) como en la hoja de Excel.
* **Fidelidad al Excel:** en el grupo `DIFERENCIAL` del Hemograma, **una fila por leucocito con dos celdas** (`%` editable y `mm3` calculado), empareja por prefijo `*_PCT` / `*_ABS`. Numéricos alineados a la derecha. Calculados en gris, solo lectura.
* **Teclado:** `Enter` y `Tab` pasan al siguiente campo editable (como Excel); `Shift+Tab` al anterior; `Enter` **nunca** envía formularios.
* **Derecha (≈ 45 %) — vista previa grande:** hoja con membrete (nombre del laboratorio de `GET /api/configuracion/laboratorio`), bloque del paciente, y una tabla por estudio con **fuente ≥ 14 px**, banderas con color **e** icono/texto, "No calculable — motivo". Altura = alto de la ventana menos la barra fija, con **scroll propio**; botón **pantalla completa** de la vista previa. Texto discreto "Vista previa — no es el informe oficial".
* **Banderas:** colores y textos de `UX_GUIDE.md §4` (se conservan los colores que ya les gustaron).
* Conserva: vista previa en vivo con *debounce* 400 ms, autoguardado 1500 ms, validaciones ERROR/ADVERTENCIA por estudio, lista de pendientes clicable, y **solo lectura para ADMIN**.
* **Objetivo medible:** en 1366×768, Hemograma + Química + Electrolitos muestran **≥ 20 filas de parámetros sin scroll** en la hoja.

## 6.6 Pacientes (buscar y gestionar)
* Buscador principal grande con *debounce*, y **filtros** en una fila: sexo, creado desde/hasta, casilla **"Solo con pendientes"**.
* Tabla densa: CI, nombre completo, edad, sexo, teléfono, **etiqueta "Pendiente (n)"** (clic → abre esa orden o la lista filtrada). Acciones por fila: **Nueva orden** (abre `/ordenes/nueva` con el paciente ya elegido) y **Editar**.
* "Nuevo paciente" queda como botón **secundario** (la creación habitual ocurre dentro de Nueva orden). ADMIN: solo lectura (sin acciones de escritura).
* La ficha del paciente se mantiene, con su historial de órdenes.

## 6.7 Órdenes / Pendientes
* Tabla densa con filtros rápidos tipo pestaña: **Todas · Incompletas · Completas · Publicadas**, buscador y paginación.
* **Acción principal de la fila: Continuar captura.** El detalle de la orden queda como acción secundaria (cabecera editable, descarte con confirmación, como hoy).
* Columnas: paciente, estudios, estado (con texto), hora de inicio, creado, autor (solo ADMIN).

## 6.8 Limpieza general
Elimina todos los textos de desarrollo y emojis (`HomePage`, `Layout`, etc.); unifica estilos con **variables CSS** (tokens de `UX_GUIDE.md §5`) y reduce `index.css`; foco visible; `aria-live` en el estado de guardado; mensajes en español.

# 7. PROTOCOLO

* Sin `localStorage`/`sessionStorage`; token en memoria; sin `HTTPException`/`datetime.now()` en el backend; sin dependencias nuevas.
* Diffs mínimos fuera de lo que se rediseña. No reformatees archivos que no tocas.
* Cada decisión no cubierta → `docs/SUPUESTOS.md`.

# 8. ORDEN DE TRABAJO (un commit por paso)

1. Puerta de entrada + respuesta inicial.  2. Bloque §14 de DECISIONES.  3. Backend B1–B3 + tests.  4. Tokens CSS, estructura general y menú lateral, limpieza.  5. Inicio.  6. Nueva orden + modal de confirmación.  7. Captura (hoja + vista previa grande + teclado).  8. Pacientes.  9. Órdenes/Pendientes.  10. Verificación manual, medición de clics y tag `fase-3-6-cerrada` **solo** si todo está demostrado.

# 9. CRITERIOS DE ACEPTACIÓN (evidencia de cada uno)

- [ ] Suite completa `OK`, `skipped=0` (`N` + 8 nuevos o más); `npm run build` limpio.
- [ ] `grep -rniE "Próximamente|Bloque [0-9]|Fase [0-9]" frontend/src` → vacío. `grep -rn "localStorage\|sessionStorage" frontend/src` → vacío. Sin emojis en `frontend/src` (muestra el comando usado).
- [ ] **Capturas de pantalla** (1366×768) de: Inicio con Recientes, Nueva orden completa **sin scroll**, ventana de confirmación, Captura con Hemograma+Química+Electrolitos (≥ 20 filas visibles y vista previa grande), Pacientes con etiqueta "Pendiente (n)", Pendientes. Adjúntalas en `docs/capturas/`.
- [ ] Tabla de **conteo de clics** de los 2 recorridos de §6.3 (paciente existente: 4; nuevo: 3), medidos de verdad.
- [ ] Flujo completo manual: Nueva orden → confirmación → captura con `Enter` entre campos → autoguardado → orden `COMPLETO` visible en Recientes y en Pendientes.
- [ ] ADMIN: ve todo en solo lectura, sin botones de escritura; `ADMIN_VE_PRIVADO` registrado.
- [ ] Duplicados: B con los estudios de A → tarjeta de bloqueo; con solapamiento parcial → banner en la captura.
- [ ] Tag `fase-3-6-cerrada`.

# 10. INFORME FINAL (formato fijo)

```
## Puerta de entrada
## Hecho (con evidencia)
## No hecho / parcial
## Supuestos nuevos
## Desviaciones del prompt
## Salida completa de los tests
## Capturas y conteo de clics
```

=== FIN DEL PROMPT ===
