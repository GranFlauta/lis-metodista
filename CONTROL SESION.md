# TAREA 01 — Corregir definitivamente las sesiones del LIS

**Proyecto:** LIS Hospital Metodista  
**Prioridad:** Alta  
**Alcance:** Exclusivamente autenticación, sesiones, heartbeat e inactividad.

## Objetivo

Implementar dos políticas de sesión controladas mediante una variable de entorno:

```env
MODO_PRODUCCION=false
SESSION_IDLE_TIMEOUT_MINUTES=60
```

### MODO_PRODUCCION=true

- Mantener la sesión mientras exista actividad real del usuario.
- Cerrar sesión tras 60 minutos consecutivos de inactividad.
- Si ocurre una interacción válida en el minuto 59:59, reiniciar el contador a 60 minutos.
- No cerrar sesión simplemente porque expire un access token: renovarlo de forma segura mientras la sesión siga vigente.
- Un heartbeat automático no cuenta como actividad humana.
- El backend debe verificar la inactividad usando su propio reloj y el último registro válido de actividad.
- Cuando expire la sesión, invalidarla en el servidor y redirigir al login.
- El contador visual del frontend debe reflejar el tiempo restante real informado por el backend.

### MODO_PRODUCCION=false

- Mantener la sesión durante el uso del sistema sin aplicar el límite de 60 minutos.
- Permitir la renovación segura de access tokens.
- Al cerrar completamente la aplicación y abrirla de nuevo, exigir autenticación.
- Utilizar almacenamiento de sesión del navegador, evitando persistir tokens de autenticación en localStorage.
- Documentar que el navegador no garantiza detectar su cierre ni revocar inmediatamente la sesión del servidor.
- Mantener un límite absoluto de seguridad configurable para las sesiones de desarrollo.
- No permitir que este modo desactive controles de acceso, validación de roles, cookies seguras, protección de contraseñas ni restricciones HTTP.

## Archivos que debes inspeccionar

- `backend/app/core/config.py`
- `backend/app/api/auth.py`
- `backend/app/api/deps.py`
- `frontend/src/features/auth/AuthProvider.tsx`
- `frontend/src/api/client.ts`
- Pruebas existentes de sesiones y autenticación.

## Correcciones obligatorias

1. Eliminar la lógica que detecta `pytest` o `unittest` para decidir si el sistema está en modo demo.
2. Eliminar el comportamiento que activa automáticamente el modo demo en ejecuciones normales.
3. No utilizar `es_modo_demo()` para omitir controles de seguridad.
4. Centralizar la evaluación de sesiones en una política reutilizable.
5. Separar claramente:
   - Duración del access token.
   - Renovación mediante refresh token.
   - Tiempo de inactividad.
   - Heartbeat.
   - Límite absoluto de sesión.
6. El heartbeat debe comprobar el estado de la sesión, pero no prolongarla automáticamente por el simple hecho de ejecutarse.
7. Registrar actividad humana mediante un mecanismo autenticado, con validación en el servidor, frecuencia limitada y sin confiar en timestamps enviados por el navegador.
8. No considerar actividad las peticiones automáticas de polling, heartbeat o refresh.
9. Eliminar los valores fijos de `86400` del frontend cuando sustituyan el tiempo real de inactividad.
10. Mantener Argon2id, la autenticación actual, los permisos existentes y el mecanismo seguro de cookies. No guardar refresh tokens en JavaScript.
11. El cierre de sesión manual debe revocar la sesión del servidor y eliminar las credenciales del navegador.
12. Evitar carreras entre refresh, heartbeat y cierre de sesión que puedan provocar expulsiones injustificadas.

## Pruebas obligatorias

- Login correcto.
- Login incorrecto.
- Refresh válido.
- Refresh expirado.
- Heartbeat sin actividad humana.
- Actividad legítima que reinicia el plazo.
- Sesión activa después de varias horas de trabajo continuo.
- Expiración después de 60 minutos sin actividad.
- Actividad en el segundo 3599 y comprobación de reinicio del plazo.
- Logout y rechazo de tokens anteriores.
- Modo desarrollo sin expulsiones por inactividad.
- Apertura de una sesión nueva del navegador tras cerrar la anterior.
- Pruebas ejecutadas en ambos modos, sin detectar artificialmente pytest para cambiar el comportamiento.

Usar un reloj simulado para probar los tiempos sin esperar una hora real.

## Restricciones

- No modificar pacientes, órdenes, resultados, informes ni reglas clínicas.
- No alterar el esquema de base de datos salvo que sea estrictamente necesario; justificar cualquier migración.
- No eliminar cookies de seguridad indiscriminadamente.
- No cambiar los roles ni los permisos.
- No introducir dependencias innecesarias.
- No reemplazar el sistema completo de autenticación.

## Entregables

1. Archivos modificados.
2. Explicación breve de la causa raíz de las expulsiones inesperadas.
3. Tabla de comportamiento en ambos modos.
4. Pruebas automatizadas y resultados.
5. Variables de entorno definitivas.
6. Instrucciones para reconstruir los contenedores con Podman.
7. Confirmación de que las funciones clínicas existentes siguen funcionando.

**No declarar la tarea terminada hasta demostrar mediante pruebas que la sesión se mantiene con actividad y expira correctamente tras 60 minutos de inactividad.**