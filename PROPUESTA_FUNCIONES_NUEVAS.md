# Propuesta de diseño — Funciones nuevas solicitadas

> Estado: **propuesta para decidir**, no es un prompt aún. Faltan decisiones tuyas (§6). Ninguna de estas funciones entra en las Fases 3.5 y 3.6.

## 1. Estudio instantáneo (informe preliminar urgente)

**Lo que entendí:** los bioquímicos a veces deben entregar resultados al médico **ya**, antes de terminar y publicar el informe oficial. Hoy una orden pendiente no se imprime ni la ven los demás, y eso se mantiene. El estudio instantáneo es la **excepción controlada**.

**Flujo propuesto**
1. Botón **Estudio instantáneo** (en Inicio y en el menú): misma pantalla de Nueva orden (paciente existente o nuevo + estudios), con la confirmación y hora de inicio.
2. Captura normal; se permite imprimir **aunque falten campos** (los vacíos salen como "—").
3. Al imprimir: **justificativo de urgencia obligatorio** y registro de quién, cuándo y qué valores se imprimieron.
4. El papel lleva una marca clara: **"INFORME PRELIMINAR — NO VÁLIDO COMO INFORME OFICIAL — pendiente de validación"**, fecha/hora y bioquímico. Sin folio.
5. La orden sigue siendo un **pendiente** privado, ahora con **plazo de publicación** (por defecto 3 días, **configurable por el ADMIN**).
6. Recordatorios por **notificaciones** dentro del sistema (campana + aviso en Inicio), escalonados, hasta que publique o descarte.

**Riesgo que conviene cubrir (importante):** el médico puede actuar con un valor preliminar que luego cambie al validar. Propongo guardar una **huella del preliminar impreso** y, al publicar el oficial, **detectar si algún valor cambió** y avisar al bioquímico ("este valor difiere de lo entregado al médico") con registro. Así no se pierde esa trazabilidad.

**Datos nuevos (migración Alembic, sin tocar el esquema base):** columna `ordenes.limite_publicacion`; tabla `impresiones_preliminares` (orden, usuario, justificativo, fecha, huella de valores); tabla `notificaciones`; clave de configuración `instantaneo_plazo_horas`.

## 2. Temporizador y notificaciones

| Momento | Notificación |
|---|---|
| Al imprimir el preliminar | Aviso de plazo ("tienes hasta el 17/10 14:30") |
| 24 h antes | Recordatorio |
| 2 h antes | Recordatorio urgente |
| Vencido | Banner persistente + lista de **vencidos** visible para el ADMIN |

**Qué pasa al vencer** es decisión tuya (§6, Q2). Mi recomendación: **no borrar ni publicar automáticamente** (publicar algo sin revisar es peligroso); en su lugar, **bloquear nuevos estudios instantáneos** de ese bioquímico hasta que regularice, y avisar al ADMIN.

## 3. Rol VISITANTE (consulta de otras áreas)

* Tercer rol `VISITANTE`, creado por el ADMIN. Solo **consulta**: busca por CI/nombre, folio, fecha o estudio y **ve en pantalla** los informes oficiales **vigentes**.
* **No** ve pendientes, preliminares, papelera ni versiones anteriores. **No** descarga, **no** imprime (solo imprimen los bioquímicos, tanto el oficial como el preliminar).
* El servidor **no expone ningún endpoint de PDF** para este rol (la restricción se aplica en el backend, no solo ocultando botones).
* Cada consulta queda auditada (quién vio qué informe y cuándo). Límite de consultas por hora para evitar extracción masiva.
* **Depende de las Fases 4 y 5** (necesita informes oficiales y plantilla de visualización).

## 4. Anti-captura de pantalla — lo que sí y lo que no es posible

**Hay que decirlo con claridad al laboratorio:** una aplicación web **no puede impedir** capturas ni grabaciones de pantalla, ni que alguien fotografíe el monitor con un teléfono. WhatsApp lo logra con una función exclusiva de las **apps nativas** de Android/iOS; los navegadores no la tienen. Cualquier "bloqueo" web es solo un obstáculo.

**Lo que sí se puede hacer (y propongo construir):**

| Medida | Efecto real |
|---|---|
| **Marca de agua visible y repetida** sobre todo el informe con *usuario + fecha/hora + folio* | Disuade y **permite rastrear quién filtró** una captura. Es la medida más útil |
| Sin PDF, sin descarga y sin impresión para VISITANTE (backend) | Elimina la vía directa de copia |
| `@media print` oculto, texto no seleccionable, clic derecho desactivado | Obstáculo menor, fácil de evadir |
| Difuminar el informe al perder el foco de la ventana | Frena algunas herramientas de captura |
| Sesión corta, bloqueo por inactividad y auditoría de cada vista | Limita y deja evidencia |
| Límite de informes consultados por hora | Frena el raspado masivo |
| Acuerdo de confidencialidad firmado por los visitantes | Respaldo legal |

**Para bloqueo real** se necesitaría controlar los equipos (navegador en modo kiosco administrado por políticas, o una app nativa). Es otro proyecto y no lo garantiza del todo.

## 5. Hoja de ruta propuesta

| Fase | Contenido |
|---|---|
| 3.5 | Correcciones de seguridad y sesión dinámica |
| 3.6 | Rediseño de la interfaz |
| 4 | Publicar con folio, historial oficial |
| 5 | PDF oficial e impresión (solo bioquímicos) |
| 5B | **Estudio instantáneo**, preliminares, temporizador y notificaciones |
| 6 | Versiones V2/V3, papelera, reciclaje |
| 7 | Delegación, colaboración y concurrencia |
| 8 | **VISITANTE**, consulta, anti-captura, reportes |

## 6. Decisiones que necesito de ti

1. **Plazo por defecto** del instantáneo: ¿3 días (configurable)? ¿Y el ADMIN puede cambiarlo por usuario o es global?
2. **Al vencer el plazo:** (a) solo recordatorios, (b) bloquear nuevos instantáneos de ese usuario *(recomendado)*, (c) bloquear crear cualquier orden.
3. ¿El preliminar puede imprimirse con **campos vacíos** y con valores por defecto **sin confirmar**? *(Propongo: vacíos sí, sin confirmar no.)*
4. ¿Quién recibe las notificaciones: el autor y, además, un resumen de vencidos al ADMIN?
5. **VISITANTE:** ¿ve **todos** los informes oficiales o solo los de **su área** (por ejemplo, según `origen_solicitud`)? ¿Hay que registrar su área/servicio?
6. ¿Es aceptable que la marca de agua del visitante muestre **su nombre y hora**?
7. **Inicio vs toma de muestra:** hoy el "inicio del estudio" se guarda como hora de toma de muestra. ¿Deben ser campos distintos?
8. ¿Se imprime el preliminar con la leyenda "NO VÁLIDO COMO INFORME OFICIAL" tal como está redactada, o prefieren otra?
