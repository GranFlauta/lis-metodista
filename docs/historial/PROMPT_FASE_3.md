# PROMPT — FASE 3: Captura de resultados, cálculo en vivo, banderas y completitud

**Cómo usarlo:** pégalo completo en la IA/programador, en la raíz del repositorio. No lo resumas.

=== INICIO DEL PROMPT ===

# 1. ROL Y MODO DE TRABAJO

Eres un ingeniero senior (backend + frontend) en un **sistema clínico** (LIS). Un valor mal calculado o mal guardado puede llegar a un paciente.

* Haces **solo** lo que este prompt pide. No inventas reglas, endpoints, columnas, librerías ni valores clínicos.
* Un hueco no cubierto → opción **más segura y simple**, registrada en `docs/SUPUESTOS.md` (continúa la numeración). Solo preguntas si el hueco **bloquea** o afecta a seguridad/datos clínicos.
* Cada afirmación va con la **salida real** del comando que la prueba. Sin salida pegada = **no hecho**.
* Imita las convenciones del repositorio (clases `AppError` de `core/errors.py`, dependencias de `api/deps.py`, modelos con `Column`, `db.query`, esquemas en `app/schemas/`, tests con `unittest` sobre PostgreSQL real).

# 2. CONTEXTO

Hecho: esquema, catálogo (9 estudios, 2 perfiles), motor de cálculo seguro (`app/calculation/engine.py`), autenticación con sesión por latido, usuarios, pacientes, catálogo (lectura) y órdenes en borrador (Fase 2).

**Esta fase construye:** capturar los resultados de cada orden, calcular los parámetros derivados **en el servidor**, mostrar banderas (bajo/normal/alto), validar reglas cruzadas y marcar la orden como `COMPLETO` cuando corresponda.

> **Corrección:** el informe de Fase 2 dice que "Informes" es de la Fase 3. No lo es. **Publicar, folios, informes y PDF son Fases 4 y 5.** No los toques.

# 3. PASO 0 — PUERTA DE ENTRADA (no negociable; si algo falla, DETENTE y repórtalo)

Pega la salida real de cada punto:

1. **Contradicción de `auth.py` (bloqueante).** En dos entregas consecutivas se mostró un `backend/app/api/auth.py` que: tiene solo 4 endpoints (sin `/me` ni `/cambiar-password`), usa `HTTPException`, llama a `datetime.now(...)`, define modelos con `try/except ImportError` + `sys.modules`, usa cookie `path="/"` y no exige `X-LIS-Client`. Eso **contradice** a `deps.py` (cuya lista blanca incluye `/api/auth/me` y `/api/auth/cambiar-password`), a los tests (que llaman a `/api/auth/me`) y a los informes (56/92 tests OK). Ejecuta y pega:
   * `git show HEAD:backend/app/api/auth.py | grep -nE "HTTPException|datetime\.now|sys\.modules|path=|X-LIS-Client|@router"`
   * `grep -rn "HTTPException" backend/app --include=*.py` → debe estar vacío.
   * `grep -rn "datetime.now\|utcnow" backend/app --include=*.py` → solo `core/clock.py`.
   Esperado: **ningún** `HTTPException`/`datetime.now`/`sys.modules`; `path="/api/auth"`; `X-LIS-Client` en `refresh` y `logout`; **6** rutas (`login`, `refresh`, `heartbeat`, `logout`, `me`, `cambiar-password`). Si el repositorio contiene el archivo viejo: **stop**; corrige según `PROMPT_FASE_1.md` §6.2 y reporta.
2. **Tags:** `git tag --list` debe mostrar `fase-1-cerrada`. (El informe 1.5 decía "listo para ser marcado": si no existe, créalo tras confirmar el punto 1.) Tras el punto 5, crea `fase-2-cerrada`.
3. **Tests:** desde `backend/`, con `TEST_DATABASE_URL` real: `python -m unittest discover -s tests -v` → `Ran N tests`, `OK`, **sin `skipped`**, con `N ≥ 92`. Anota `N` (línea base).
4. `git diff --stat fase-1-cerrada HEAD -- db/init backend/app/catalog` → vacío. `podman compose config` (o `docker compose config`) → `db` sin puertos en el compose base.
5. **Evidencia de aceptación de Fase 2 que faltó** (criterios de `PROMPT_FASE_2.md` §13), cada uno con su resultado real: (a) alta de paciente + orden con perfil `HC-QMC-SEROL-EGO`, quitar un estudio, `numero_orden_paciente = 1`; segunda orden = 2; (b) dos usuarios BIOQUIMICO: A crea Hemograma+Química → B con Hemograma **bloqueado**; B con Hemograma+Lipídico **advertencia**; B con Lipídico **sin aviso**; (c) Inmunoserología `VIH` vs `PCR_SEMICUANT` entre usuarios distintos sin bloqueo; (d) ADMIN no ve botones de escritura y `SELECT accion, count(*) FROM laboratorio.log_seguridad GROUP BY 1` muestra `ADMIN_VE_PRIVADO`; (e) descartar un borrador deja fila en `laboratorio.borradores_descartados`.

**Primera respuesta obligatoria (sin código de Fase 3):** resultado de los puntos 1–5 + resumen de 10 líneas + archivos a crear/modificar + dudas **bloqueantes** (o "ninguna").

# 4. LECTURA OBLIGATORIA

`AGENTS.md`, `docs/DECISIONES.md` (§3, §4, §5, §6, §7, §11), `docs/SUPUESTOS.md`, `db/init/001_schema.sql` (tablas `resultados_borrador`, `orden_estudios`, `orden_estudio_grupos`, `parametros`, `rangos_referencia`, `estudio_versiones`, `ordenes`, `pacientes`, `laboratorio_config`), `backend/app/catalog/definitions.py`, `backend/app/calculation/engine.py`, `backend/app/api/deps.py`, `backend/app/core/errors.py`, el código y tests de Fase 2 (`api/ordenes*`, servicios, modelos) y `frontend/src/features/ordenes/*`, `frontend/src/api/client.ts`.

# 5. PRIMER COMMIT: DECISIONES

Añade **al final** de `docs/DECISIONES.md` (única edición permitida a ese archivo) este bloque:

```markdown
## 12. Decisiones de Fase 3 (captura y cálculo)

* **D3-01** Alcance: captura, cálculo, banderas, validaciones y estado `INCOMPLETO↔COMPLETO`. NO incluye publicar, folios, informes, PDF, ediciones de informes oficiales (`id_edicion` siempre NULL) ni delegación (solo el autor edita; B llega en la Fase 7).
* **D3-02** El backend es la única fuente de verdad del cálculo. `POST /calcular` es una vista previa sin escritura; `PUT /resultados` persiste y recalcula todo. El cliente NUNCA envía valores de parámetros calculados.
* **D3-03** Qué se captura: los parámetros de la versión de estudio congelada en la orden. En estudios de selección parcial, solo los parámetros cuyo `grupo` figura en `orden_estudio_grupos`.
* **D3-04** Valores: NUMERICO acepta coma o punto; se guarda con punto en `valor_numerico` tal cual lo digitó (sin redondear); máx. 6 decimales; no negativos. SELECCION debe estar en `opciones`. TEXTO ≤ 500 caracteres; RECUENTO ≤ 50; FECHA ISO no futura (se guarda como texto `AAAA-MM-DD`). Vacío = ausente: nunca se guarda 0 ni cadena vacía.
* **D3-05** Valores por defecto (`requiere_confirmacion`): se muestran como **virtuales** (no se guardan). Solo cuentan para completar cuando existe una fila `confirmado = TRUE`, creada al confirmarlos explícitamente o al editarlos a mano.
* **D3-06** Una orden es `COMPLETO` si todo parámetro `obligatorio` del alcance está resuelto: capturado y confirmado, o CALCULADO calculable, o CALCULADO no calculable por regla de validez/división por cero (p. ej. LDL con TG > 400 se informa "No calculable" y NO bloquea). CALCULADO sin entradas completas = pendiente. Una regla cruzada de severidad ERROR bloquea `COMPLETO`; ADVERTENCIA no.
* **D3-07** Banderas por rango: se elige el rango por sexo del paciente (o ambos) y, si el rango trae `edad_min/max_meses`, por la edad de la orden en meses. Respeta límites inclusivos/exclusivos. Solo para valores numéricos; los cualitativos no llevan bandera en v1.
* **D3-08** Los calculados se persisten (`es_calculado = TRUE`); si no son calculables por regla, fila con `calculable = FALSE` y valor NULL; si faltan entradas, sin fila.
* **D3-09** Guardar resultados NO modifica `ordenes.fila_version` (esa versión protege solo la cabecera). Dos pestañas del mismo autor = última escritura gana por parámetro; cada escritura bloquea la fila de la orden (`FOR UPDATE`).
* **D3-10** La API usa el punto decimal como formato canónico. La interfaz muestra según `laboratorio_config.separador_decimal` (hoy sembrado en coma). La decisión de negocio sobre el separador sigue pendiente (§10, punto 9).
* **D3-11** PENDIENTE: valores críticos y límites fisiológicos (p. ej. % > 100); permitir reemplazar GR/Hb estimados por valor medido (v1.1).
```

# 6. ALCANCE

## 6.1 DENTRO
**Backend:** modelo `ResultadoBorrador`; servicio de captura/evaluación; endpoints de §8; evaluación de reglas cruzadas; banderas; actualización de `estado_trabajo`; lectura de `laboratorio_config`; ajuste mínimo del motor (§7); tests.
**Frontend:** pantalla de captura por orden con vista previa en vivo, autoguardado, banderas, confirmación de valores por defecto e indicador de completitud.

## 6.2 FUERA (no lo hagas)
Publicar/folios/informes/PDF, `ediciones_informe`, delegación y colaboración (`colaboracion_cambios`), concurrencia entre usuarios, notificaciones, reportes, auditoría de resultados, valores críticos, límites fisiológicos, override de estimados, edición de estudios de la orden, **cualquier cambio en `db/init/*.sql` o en `backend/app/catalog/**`**. Si falta una columna o tabla: **detente y repórtalo**.

# 7. DECISIONES TÉCNICAS (no las cambies)

| Tema | Decisión |
|---|---|
| Motor de cálculo | Reutiliza `calculation/engine.py`. **Único cambio permitido:** añadir a `ResultadoCalculo` el campo `codigo_motivo: str \| None = None` con valores `FALTA_ENTRADA`, `DIVISION_POR_CERO`, `REGLA_INVALIDA` (compatible hacia atrás; los 25 tests existentes deben seguir pasando). No uses `eval` ni reimplementes fórmulas |
| Orden de cálculo | Orden topológico dentro de cada estudio usando `variables_de`; si hubiera un ciclo → error de configuración (test) |
| Aritmética | `Decimal` siempre; entrada normalizada con `a_decimal` (acepta coma) |
| Almacenamiento | NUMERICO/CALCULADO → `valor_numerico`; TEXTO, SELECCION, RECUENTO, FECHA → `valor_texto`. Nunca ambos |
| Transacciones | Cada escritura = una transacción con `SELECT … FOR UPDATE` sobre la fila de `ordenes` |
| Errores | Clases nuevas en `core/errors.py` siguiendo `AppError` solo si hacen falta; reutiliza `ValidacionError`, `ConflictoError`, `NoEncontradoError`, `ProhibidoError`. **Prohibido** `HTTPException` |
| Autorización | `deps.py` (`require_auth`, `require_bioquimico`, `require_admin`) |
| Dependencias | **Ninguna nueva** |
| Tests | `unittest`, PostgreSQL real con esquema `001` + seed `002` (`scripts/crear_bd_test.sh`), reloj simulado, sin `sleep`, **datos ficticios** |

# 8. CONTRATO DE LA API

Prefijo `/api`. Todos requieren sesión válida. Valores numéricos en JSON como **string con punto** (p. ej. `"14.4"`).

## 8.1 Forma común de respuesta ("captura")
```json
{
  "orden": {"id": 7, "estado_trabajo": "INCOMPLETO", "bloqueada": false,
            "paciente": {"id": 3, "sexo": "F"}, "edad_anios": 33, "edad_meses": 4},
  "estudios": [{
    "codigo": "HEMOGRAMA", "nombre": "Hemograma Completo",
    "grupos_seleccionados": null,
    "secciones": [{
      "grupo": null,
      "parametros": [{
        "codigo": "HEMATOCRITO", "nombre": "Hematocrito", "tipo_campo": "NUMERICO",
        "unidad": "%", "decimales": 1, "opciones": null, "obligatorio": true,
        "requiere_confirmacion": false, "metodo": null, "muestra": null,
        "valor": "45", "es_calculado": false,
        "calculable": true, "motivo_no_calculable": null,
        "confirmado": true, "es_defecto": false, "valor_defecto": null,
        "referencia": {"texto": "44 - 54 %", "inferior": "44", "superior": "54"},
        "bandera": "NORMAL"
      }]
    }],
    "validaciones": [{"severidad": "ADVERTENCIA", "mensaje": "El diferencial no suma 100 %", "parametros": ["SEGMENTADOS_PCT"]}]
  }],
  "completitud": {"completo": false, "pendientes": ["VES"], "sin_confirmar": [], "errores": []}
}
```
* `valor`: string o `null`. Para CALCULADO no calculable: `valor = null`, `calculable = false`, `motivo_no_calculable` en español legible (p. ej. "Falta el valor de HDL", "No válido con triglicéridos > 400").
* `es_defecto = true` y `confirmado = false` cuando se muestra un valor por defecto **virtual** (D3-05); en ese caso `valor` trae el defecto.
* `bandera ∈ {"BAJO","NORMAL","ALTO", null}`. `referencia = null` si no hay rango aplicable.
* `completitud.pendientes`: códigos obligatorios sin resolver. `sin_confirmar`: defectos sin confirmar. `errores`: mensajes de reglas ERROR.
* Orden de estudios, secciones y parámetros: `orden_estudios` por id, `grupo` por primera aparición y parámetros por `orden_visualizacion`.

## 8.2 Endpoints

| Ruta | Quién | Descripción |
|---|---|---|
| `GET /api/ordenes/{id}/captura` | autor; ADMIN (solo lectura) | Devuelve la forma común con los valores persistidos. Otro BIOQUIMICO → **404**. ADMIN sobre orden ajena → registra `ADMIN_VE_PRIVADO` (`detalle={"recurso":"captura","id_orden":id}`) |
| `POST /api/ordenes/{id}/calcular` | autor | Cuerpo `{"valores": {"CODIGO": valor\|null, ...}}` = **conjunto completo** de entradas actuales del formulario. **No escribe nada.** Devuelve la forma común evaluada con esos valores (los defectos no enviados aparecen virtuales) |
| `PUT /api/ordenes/{id}/resultados` | autor | Cuerpo `{"valores": {...}}` = **cambios parciales** (clave ausente = sin cambio; `null` = borrar). Valida, persiste, recalcula todos los calculados, actualiza `estado_trabajo` y devuelve la forma común |
| `POST /api/ordenes/{id}/resultados/confirmar-defectos` | autor | Cuerpo `{"parametros": ["COD",...]}` opcional (omitido = todos los pendientes). Persiste los valores por defecto con `confirmado = TRUE`; devuelve la forma común |
| `GET /api/configuracion/laboratorio` | cualquier autenticado | `{"nombre_laboratorio": "...", "separador_decimal": ","}` — **solo** esas dos claves de `laboratorio_config` |

## 8.3 Reglas
* **Precondiciones de escritura** (`PUT`, `confirmar-defectos`; `calcular` también): orden propia; `estado_trabajo ∈ {INCOMPLETO, COMPLETO}`; `bloqueada = FALSE`. Si no → 409 `CONFLICTO`. ADMIN → 403 `PROHIBIDO`. Otro BIOQUIMICO → 404.
* **Validación de claves:** cada código debe pertenecer al alcance de la orden (D3-03) → si no, 400 `VALIDACION`. Un código de tipo CALCULADO en el cuerpo → 400. Máximo 200 claves.
* **Validación de valores** (D3-04), error 400 `VALIDACION` indicando el código del parámetro. Mensajes en español.
* **Persistencia en `PUT`:** `resultados_borrador` con `id_edicion = NULL`, `actualizado_por` = usuario actual, `actualizado_en` = `ahora()`, `confirmado = TRUE` para valores digitados, `es_calculado = FALSE`. Valor `null` → borrar fila. Tras aplicar cambios, **recalcular todos los CALCULADO del alcance** (D3-08): eliminar sus filas previas y reinsertar según el resultado.
* **Cálculo:** entradas = valores persistidos (en `calcular`: los enviados). Clave del contexto = código en minúsculas; valor ausente = `None`. Redondeo por `decimales` del parámetro calculado.
* **Reglas cruzadas** (`estudio_versiones.configuracion_json.reglas`):
  * `SUMA_IGUAL`: se evalúa cuando todos los parámetros **obligatorios** listados tienen valor; los opcionales ausentes cuentan como 0 **solo** para esta suma. Falla si `|suma − valor| > tolerancia`.
  * `MENOR_IGUAL`: `parametros = [a, b]`, falla si `a > b`; se evalúa solo si ambos tienen valor.
  * Un tipo de regla desconocido → error de configuración (cubierto por test, no se ignora en silencio).
* **Completitud** (D3-06) y transición automática de `ordenes.estado_trabajo` en la misma transacción. No cambia `fila_version` (D3-09).
* **Banderas** (D3-07): rango por sexo del paciente (o `NULL`), y por edad en meses (`edad_anios*12 + edad_meses`) si el rango trae límites de edad. Normal si cumple inferior (≥ o > según `inferior_inclusivo`) y superior (≤ o < según `superior_inclusivo`); si no, `BAJO`/`ALTO`.

# 9. FRONTEND

Ruta `/ordenes/:id/captura` (enlazada desde el detalle de la orden con el botón "Capturar resultados" y desde la lista). Reutiliza `apiClient` y los patrones de Fase 1/2.

* **Disposición:** formulario por estudio (secciones por grupo) a la izquierda; panel **"Vista previa"** fijo a la derecha con la tabla *Parámetro · Resultado · Unidad · Referencia · Bandera*.
* **Entradas por tipo:** NUMERICO (texto que acepta coma/punto; no uses `type=number`), SELECCION (lista), TEXTO, RECUENTO (texto corto), FECHA (selector de fecha). Los CALCULADO son de **solo lectura** y muestran el valor o "No calculable — motivo". El estudio de selección parcial muestra solo los grupos pedidos.
* **Vista previa en vivo:** al cambiar un campo, tras 400 ms de pausa → `POST /calcular` con **todos** los valores; pinta calculados, banderas y completitud con la respuesta. No dupliques fórmulas en TypeScript.
* **Autoguardado:** tras 1500 ms sin cambios → `PUT /resultados` solo con los campos modificados; botón "Guardar ahora"; estado visible ("Guardando…", "Guardado a las hh:mm", "Error al guardar — reintentar"). Si falla, **conserva** lo digitado. Se permite `beforeunload` **únicamente** para avisar de cambios sin guardar (nunca para cerrar sesión).
* **Banderas:** nunca solo color: icono + texto ("↓ Bajo", "↑ Alto", "Normal"), con contraste suficiente.
* **Valores por defecto:** campo precargado con insignia "Sin confirmar" y botón **"Confirmar valores por defecto"** (llama a `confirmar-defectos`). Editar el campo a mano lo confirma.
* **Validaciones:** ERROR (rojo con icono) y ADVERTENCIA (ámbar con icono) en la parte superior de cada estudio.
* **Completitud:** indicador "Completo" / "Faltan N campos" con la lista de pendientes (clic → enfoca el campo) y "N valores sin confirmar".
* **Separador decimal:** formato de visualización según `GET /api/configuracion/laboratorio`; la API siempre recibe/envía punto (la entrada acepta ambos).
* **ADMIN:** misma pantalla en **solo lectura** (campos deshabilitados, sin botones de guardado/confirmación). Los botones de escritura no deben existir para ADMIN.
* Sin `localStorage`/`sessionStorage`. CSS propio. Mensajes en español tomados de `mensaje`.

# 10. TESTS OBLIGATORIOS (`unittest`, PostgreSQL real, datos ficticios)

**Estructura y acceso**
1. `GET captura` de una orden con `HEMOGRAMA`: secciones/parámetros con tipo, unidad y decimales correctos; referencia según sexo (hematocrito M `48 - 58`, F `44 - 54`).
2. Inmunoserología con `grupos=[VIH]`: solo el parámetro `VIH` (no `PCR_*`).
3. EGO: los defectos aparecen como virtuales (`es_defecto=true`, `confirmado=false`) y **no** hay filas en `resultados_borrador`.
4. Orden ajena → 404 (BIOQUIMICO); ADMIN → 200 solo lectura y se registra `ADMIN_VE_PRIVADO` con `recurso="captura"`; sin token → 401; con `debe_cambiar_password` → 403; ADMIN en `PUT`/`calcular`/`confirmar-defectos` → 403.

**Valores**
5. Numérico con coma y con punto → mismo `valor_numerico` exacto; más de 6 decimales → 400; negativo → 400; texto no numérico → 400.
6. SELECCION fuera de `opciones` → 400; TEXTO > 500 y RECUENTO > 50 → 400; FECHA futura o inválida → 400.
7. Código de otro estudio/grupo no pedido, código inexistente, o código CALCULADO en el cuerpo → 400. Más de 200 claves → 400.
8. `null` borra la fila; el upsert actualiza `actualizado_por` y `actualizado_en`.
9. Un parámetro numérico nunca escribe `valor_texto` y uno cualitativo nunca escribe `valor_numerico`.

**Cálculo** (con los valores del Excel)
10. Hemograma: hto 45 → GR `4815000`, Hb `14.4` persistidos como calculados; cambiar hto los recalcula; borrar hto elimina las filas calculadas.
11. Diferencial: GB 8000 y segmentados 60 % → `SEGMENTADOS_ABS = 4800`; sin GB → sin fila.
12. Lipídico: col 164.5, TG 102.4, HDL 40 → VLDL `20.48`, LDL `104.02`; TG 450 → VLDL sí y LDL con `calculable=false` (regla); HDL ausente → LDL **sin fila** (falta entrada). Nunca aparece un 0 inventado.
13. Hepatograma: directa > total → indirecta `calculable=false` + validación ERROR; la orden no pasa a COMPLETO.
14. Proteinograma: PT = albúmina → relación A/G no calculable, sin error 500.
15. `POST /calcular` **no escribe** (conteo de filas idéntico antes y después) y su resultado coincide con el de `PUT` para los mismos valores.

**Banderas y reglas**
16. Colesterol `200` → `ALTO` (superior exclusivo) y `199.9` → `NORMAL`; hombre vs mujer en hematocrito; parámetro sin rango → `bandera=null`, `referencia=null`.
17. Rango con límites de edad (fila insertada por el test): se elige según la edad en meses de la orden.
18. `SUMA_IGUAL`: suma 98 con tolerancia 1 → ADVERTENCIA; 99 → sin aviso; cayados ausente cuenta 0; **no** bloquea COMPLETO. `MENOR_IGUAL` ERROR **sí** bloquea.

**Estado y defectos**
19. Orden solo con `ELECTROLITOS`: al completar los 6 obligatorios pasa a `COMPLETO`; borrar uno la devuelve a `INCOMPLETO`.
20. EGO: con defectos sin confirmar → no completo y `sin_confirmar` los lista; `confirmar-defectos` los persiste con `confirmado=TRUE` y permite completar; editar un defecto a mano lo confirma.
21. CALCULADO obligatorio no calculable **por regla** (LDL con TG > 400) NO impide `COMPLETO`; no calculable **por falta de entrada** sí lo impide.
22. Guardar resultados **no** cambia `fila_version`; un `PATCH` de cabecera posterior sigue funcionando.
23. Orden `PUBLICADA` o `bloqueada` (forzadas por SQL en el test) → 409 en `PUT` y `confirmar-defectos`.
24. Dos `PUT` simultáneos (hilos) sobre los mismos parámetros → ambos 200, sin 500 ni bloqueos mutuos, y las filas calculadas coinciden con los **valores finales** guardados.

**Configuración, motor y catálogo**
25. `GET /api/configuracion/laboratorio` devuelve solo `nombre_laboratorio` y `separador_decimal`; exige sesión.
26. Todos los tipos de regla de `definitions.py` están implementados; el orden topológico de los 9 estudios se resuelve sin ciclos.
27. Motor: `codigo_motivo` distingue `FALTA_ENTRADA`, `DIVISION_POR_CERO` y `REGLA_INVALIDA`; los 25 tests del motor/catálogo siguen pasando.

**Regresión**
28. La suite completa (la `N` del Paso 0 + los nuevos) → `OK`, **`skipped=0`**.

# 11. PROTOCOLO ANTI-ALUCINACIÓN

1. **Verifica antes de afirmar** cada API de librería en el entorno instalado.
2. Nombres de tablas/columnas: **solo** de `db/init/001_schema.sql`. Si falta algo, detente y repórtalo.
3. **No inventes valores clínicos**: ni rangos, ni límites, ni reglas. Todo sale de `definitions.py` y la BD.
4. Sin relleno: nada de `pass`, `TODO`, `NotImplementedError` dentro del alcance. Lo no hecho va a "No hecho".
5. **Prohibido:** `eval`, `exec`, `pickle`, SQL concatenado con datos del usuario, `HTTPException`, `datetime.now()` fuera de `clock.py`, `float` para resultados clínicos, `except Exception: pass`, logs con datos de pacientes o resultados, convertir un valor vacío en `0`.
6. Si un test falla, corrige el **código**. Si el test contradice este prompt, repórtalo.
7. Datos **ficticios** en tests, fixtures y capturas.
8. Toda decisión no cubierta → `docs/SUPUESTOS.md` (`| # | Tema | Qué no estaba definido | Qué decidí | Impacto si está mal |`).
9. Diffs mínimos; no renombres ni reformatees lo que no tocas.

# 12. ORDEN DE TRABAJO (un commit por paso, mensajes en español, imperativo)

1. Paso 0 y primera respuesta.
2. Bloque §12 en `docs/DECISIONES.md`.
3. Motor: `codigo_motivo` + test 27.
4. Modelo, servicio de evaluación (orden topológico, calculados, banderas, reglas, completitud) + tests 10–18, 26.
5. Endpoints `captura`, `calcular`, `resultados`, `confirmar-defectos`, `configuracion` + tests 1–9, 15, 19–25.
6. Concurrencia y regresión + tests 24 y 28.
7. Frontend: pantalla de captura (formulario, vista previa, banderas).
8. Frontend: autoguardado, defectos, completitud, modo solo lectura ADMIN.
9. Verificación manual (§13), tag `fase-3-cerrada` **solo** si todo está demostrado, e informe final.

# 13. CRITERIOS DE ACEPTACIÓN (pega la evidencia de cada uno)

- [ ] Suite completa → `OK`, `skipped=0`, salida pegada.
- [ ] `git diff --stat fase-2-cerrada HEAD -- db/init backend/app/catalog` → vacío.
- [ ] Greps del Paso 0 (puntos 1 y 4) vuelven a dar el resultado esperado.
- [ ] Flujo manual (BIOQUIMICO): orden con `HC-QMC-SEROL-EGO`; capturar el Hemograma con hto 45 → GR y Hb aparecen solos como "(estimado)"; capturar Lipídico con TG 450 → LDL "No calculable" sin bloquear; Hepatograma con directa > total → ERROR visible y orden no completa.
- [ ] EGO: valores por defecto marcados "Sin confirmar"; completar sin confirmarlos no es posible; "Confirmar valores por defecto" lo permite.
- [ ] Llenar todos los obligatorios → la orden aparece `COMPLETO` en la lista; vaciar uno → vuelve a `INCOMPLETO`.
- [ ] Banderas con icono y texto (no solo color); la vista previa se actualiza sin recargar; el autoguardado persiste tras F5.
- [ ] ADMIN abre la captura de una orden ajena en solo lectura y `log_seguridad` registra `ADMIN_VE_PRIVADO`.
- [ ] `grep -rn "localStorage\|sessionStorage" frontend/src` → vacío (aparte de comentarios); `npm run build` limpio.
- [ ] `.env` no versionado; sin datos reales en el repositorio.

# 14. INFORME FINAL (formato obligatorio)

```
## Puerta de entrada (§3)
(salida de los 5 puntos)
## Hecho
(lista, cada ítem con el nº de test o criterio que lo prueba)
## No hecho / parcial
## Supuestos nuevos
## Desviaciones del prompt
(si no hubo: "ninguna")
## Contradicciones o huecos en la documentación
(si no hubo: "ninguno")
## Salida de los tests
(pegar tal cual: Ran N tests / OK / sin skipped)
## Evidencia de aceptación (§13)
## Cómo probarlo
```

=== FIN DEL PROMPT ===
