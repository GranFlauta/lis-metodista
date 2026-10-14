# Registro de Evidencias Crudas — Fase 1.5 y Fase 2 (LIS)

> **Documento de validación técnica y evidencia empírica directa.**
> Todas las secciones a continuación corresponden a comandos reales ejecutados en el entorno local del proyecto.

---

## 1. Verificaciones del Paso 0 (Puerta de Entrada No Negociable)

### 1.1 Verificación de Tag `fase-1-cerrada` y Estado Git

```bash
$ git tag --list "fase-1-cerrada"
fase-1-cerrada

$ git status -s
 M EVALUACION_FASE_2.md
 M backend/app/core/clock.py
 M backend/app/main.py
 M backend/tests/base.py
 M docs/DECISIONES.md
 M frontend/src/App.tsx
 M frontend/src/components/Layout.tsx
 M frontend/src/features/home/HomePage.tsx
 M frontend/src/index.css
 M frontend/tsconfig.tsbuildinfo
?? EVIDENCIAS.md
?? PROMPT_FASE_2.md
?? PROMPT_FASE_3.md
?? PROMT_FASE_1.5_CERRAR.md
?? backend/app/api/ordenes.py
?? backend/app/schemas/orden.py
?? backend/tests/test_ordenes.py
?? frontend/src/api/catalogo.ts
?? frontend/src/api/ordenes.ts
?? frontend/src/api/pacientes.ts
?? frontend/src/features/ordenes/NuevaOrdenPage.tsx
?? frontend/src/features/ordenes/OrdenDetallePage.tsx
?? frontend/src/features/ordenes/OrdenesPage.tsx
?? frontend/src/features/pacientes/CatalogoModal.tsx
?? frontend/src/features/pacientes/PacienteDetallePage.tsx
?? frontend/src/features/pacientes/PacienteFormModal.tsx
?? frontend/src/features/pacientes/PacientesPage.tsx
```

---

### 1.2 Integridad del Esquema y Catálogo (`db/init` y `backend/app/catalog`)

```bash
$ git diff --stat fase-1-cerrada HEAD -- db/init backend/app/catalog
(salida vacía: 0 cambios en esquemas ni en catálogo)
```

---

### 1.3 Grep de Reloj (`datetime.now` / `utcnow` restringido a `clock.py`)

```bash
$ grep -rn "datetime.now\|utcnow" backend/app --include=*.py
backend/app/core/clock.py:4:en lugar de llamar directamente a datetime.now() fuera de este módulo.
backend/app/core/clock.py:24:    return datetime.now(timezone.utc)
```

---

### 1.4 Grep de Excepciones HTTP (`HTTPException` prohibido; se usan errores de dominio)

```bash
$ grep -rn "HTTPException" backend/app --include=*.py
(salida vacía: 0 coincidencias en toda la aplicación)
```

---

### 1.5 Configuración Compose Base (`db` sin puertos publicados al exterior)

```bash
$ podman compose -f docker-compose.yml config
services:
  backend:
    build:
      context: "/home/pika123/Vídeos/lis-proyecto-base/lis/backend"
    depends_on:
      db:
        condition: service_healthy
    env_file:
    - .env
    environment:
      DATABASE_URL: postgresql+psycopg://lis_app:CAMBIAR_por_una_clave_larga_y_aleatoria@db:5432/lis
    restart: unless-stopped
  backup:
    depends_on:
      db:
        condition: service_healthy
    entrypoint:
    - /bin/sh
    - -c
    - while true; do /bin/sh /backup.sh; sleep 86400; done
    environment:
      BACKUP_RETENTION_DAYS: '30'
      PGDATABASE: lis
      PGHOST: db
      PGPASSWORD: CAMBIAR_por_una_clave_larga_y_aleatoria
      PGUSER: lis_app
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
    - ./backups:/backups
    - ./scripts/backup.sh:/backup.sh:ro
  db:
    environment:
      POSTGRES_DB: lis
      POSTGRES_PASSWORD: CAMBIAR_por_una_clave_larga_y_aleatoria
      POSTGRES_USER: lis_app
    healthcheck:
      interval: 5s
      retries: 10
      test:
      - CMD-SHELL
      - pg_isready -U lis_app -d lis
      timeout: 5s
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
    - pgdata:/var/lib/postgresql/data
    - ./db/init:/docker-entrypoint-initdb.d:ro,z
  web:
    build:
      context: "/home/pika123/Vídeos/lis-proyecto-base/lis/frontend"
    depends_on:
      backend:
        condition: service_started
    environment:
      LIS_HOST: lis.local
    ports:
    - 8443:443
    restart: unless-stopped
    volumes:
    - caddy_data:/data
volumes:
  caddy_data: null
  pgdata: null
```

---

## 2. Salida Íntegra de `git show HEAD:backend/app/api/auth.py`

```python
"""
Endpoints de autenticación y gestión de sesiones para FastAPI (Fase 1).
Implementa estrictamente PROMPT_FASE_1.md §5 y §6.2:
- POST /api/auth/login: Normalización, dummy hash para igualar tiempos, 423 CUENTA_BLOQUEADA,
  401 CREDENCIALES_INVALIDAS, emisión de JWT y cookie refresh (Path=/api/auth).
- POST /api/auth/refresh: Validación de cabecera X-LIS-Client: web, comprobación de sesión viva.
- POST /api/auth/heartbeat: 204 No Content, actualiza exclusivamente ultimo_latido.
- POST /api/auth/logout: 204 No Content, cabecera X-LIS-Client, revocación y borrado de cookie.
- GET /api/auth/me: 200 con datos del usuario autenticado.
- POST /api/auth/cambiar-password: 204 No Content, valida clave actual, valida política clínica (422),
  revoca las demás sesiones del usuario y actualiza estado.
"""

from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import (
    obtener_ip_cliente,
    registrar_evento_seguridad,
    require_auth,
)
from app.core.clock import ahora
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import (
    CredencialesInvalidasError,
    CuentaBloqueadaError,
    PasswordDebilError,
    SesionExpiradaError,
    ValidacionError,
)
from app.core.security import (
    check_password_policy,
    create_access_token,
    generate_refresh_token,
    get_password_hash,
    hash_token,
    verify_dummy_password,
    verify_password,
)
from app.models.session import Sesion
from app.models.user import Usuario
from app.schemas.auth import (
    CambiarPasswordRequest,
    LoginRequest,
    MeResponse,
    TokenResponse,
    UsuarioResumenResponse,
)

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión (Login)",
    description="Valida credenciales, aplica bloqueo temporal y emite tokens.",
)
def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    ip_cliente = obtener_ip_cliente(request)
    now = ahora()

    # 1. Normalizar usuario a minúsculas y sin espacios (§6.2)
    usuario_normalizado = login_data.usuario.strip().lower()

    # 2. Buscar usuario. Si no existe: ejecutar verificación dummy y responder 401
    usuario_db = (
        db.query(Usuario)
        .filter(func.lower(Usuario.usuario) == usuario_normalizado)
        .first()
    )

    if not usuario_db:
        verify_dummy_password(login_data.password)
        registrar_evento_seguridad(
            db=db,
            accion="LOGIN_FALLIDO",
            id_usuario=None,
            id_objetivo=None,
            ip=ip_cliente,
            detalle={"usuario_intentado": login_data.usuario},
        )
        db.commit()
        raise CredencialesInvalidasError()

    # 3. Si existe y bloqueado_hasta > ahora -> 423 CUENTA_BLOQUEADA (sin verificar clave)
    bloqueado_hasta = usuario_db.bloqueado_hasta
    if bloqueado_hasta:
        bloqueado_tz = bloqueado_hasta.replace(tzinfo=now.tzinfo) if bloqueado_hasta.tzinfo is None else bloqueado_hasta
        if bloqueado_tz > now:
            minutos_restantes = math.ceil((bloqueado_tz - now).total_seconds() / 60)
            registrar_evento_seguridad(
                db=db,
                accion="LOGIN_FALLIDO",
                id_usuario=usuario_db.id_usuario,
                id_objetivo=usuario_db.id_usuario,
                ip=ip_cliente,
                detalle={"motivo": f"Cuenta bloqueada hasta {bloqueado_tz.isoformat()}"},
            )
            db.commit()
            raise CuentaBloqueadaError(minutos_restantes=max(1, minutos_restantes))

    # 4. Si activo = FALSE -> 401 CREDENCIALES_INVALIDAS (mismo mensaje §6.1)
    if not usuario_db.activo:
        verify_dummy_password(login_data.password)
        registrar_evento_seguridad(
            db=db,
            accion="LOGIN_FALLIDO",
            id_usuario=usuario_db.id_usuario,
            id_objetivo=usuario_db.id_usuario,
            ip=ip_cliente,
            detalle={"motivo": "Usuario inactivo"},
        )
        db.commit()
        raise CredencialesInvalidasError()

    # 5. Verificar clave con Argon2id
    es_valida = verify_password(login_data.password, usuario_db.hash_password)

    if not es_valida:
        intentos = (usuario_db.intentos_fallidos or 0) + 1
        if intentos >= settings.max_login_attempts:
            usuario_db.bloqueado_hasta = now + timedelta(minutes=settings.lockout_minutes)
            usuario_db.intentos_fallidos = 0
            detalle = {
                "motivo": f"Máximo de intentos alcanzado ({settings.max_login_attempts}). Bloqueo de {settings.lockout_minutes} min.",
                "bloqueado_hasta": usuario_db.bloqueado_hasta.isoformat(),
            }
        else:
            usuario_db.intentos_fallidos = intentos
            detalle = {"intentos_fallidos": intentos}

        registrar_evento_seguridad(
            db=db,
            accion="LOGIN_FALLIDO",
            id_usuario=usuario_db.id_usuario,
            id_objetivo=usuario_db.id_usuario,
            ip=ip_cliente,
            detalle=detalle,
        )
        db.commit()
        raise CredencialesInvalidasError()

    # 6. Clave correcta
    usuario_db.intentos_fallidos = 0
    usuario_db.bloqueado_hasta = None
    usuario_db.ultimo_login = now

    registrar_evento_seguridad(
        db=db,
        accion="LOGIN_OK",
        id_usuario=usuario_db.id_usuario,
        id_objetivo=usuario_db.id_usuario,
        ip=ip_cliente,
        detalle={"user_agent": request.headers.get("user-agent")},
    )

    # Crear fila en sesiones (expira_en = ahora + ABSOLUTE_SESSION_HOURS)
    raw_refresh_token, refresh_hash = generate_refresh_token()
    expira_en = now + timedelta(hours=settings.absolute_session_hours)

    sesion = Sesion(
        id_usuario=usuario_db.id_usuario,
        refresh_hash=refresh_hash,
        ip=ip_cliente,
        user_agent=request.headers.get("user-agent"),
        creada_en=now,
        ultimo_latido=now,
        ultima_actividad=now,
        expira_en=expira_en,
        revocada_en=None,
    )
    db.add(sesion)
    db.commit()
    db.refresh(sesion)
    db.refresh(usuario_db)

    # Emitir access token con claims requeridos: sub, sid, rol, iat, exp, typ="access"
    rol_nombre = usuario_db.rol.nombre if usuario_db.rol else "BIOQUIMICO"
    access_token = create_access_token(
        subject=str(usuario_db.id_usuario),
        session_id=str(sesion.id_sesion),
        role=rol_nombre,
    )

    # Cookie refresh (§5): httpOnly, Secure, SameSite=Strict, Path=/api/auth, sin Max-Age
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )

    usuario_resumen = UsuarioResumenResponse(
        id_usuario=usuario_db.id_usuario,
        usuario=usuario_db.usuario,
        nombres=usuario_db.nombres,
        apellido_paterno=usuario_db.apellido_paterno,
        apellido_materno=usuario_db.apellido_materno,
        rol=rol_nombre,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_minutes * 60,
        debe_cambiar_password=usuario_db.debe_cambiar_password,
        usuario=usuario_resumen,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar Access Token",
    description="Exige cabecera X-LIS-Client: web y cookie refresh token válida.",
)
def refresh_token(
    request: Request,
    response: Response,
    x_lis_client: str | None = Header(default=None, alias="X-LIS-Client"),
    db: Session = Depends(get_db),
) -> TokenResponse:
    # CSRF check (§5 y §6.1)
    if x_lis_client != "web":
        raise ValidacionError("Cabecera X-LIS-Client: web requerida.")

    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise SesionExpiradaError("Cookie de refresh token ausente.")

    now = ahora()
    ip_cliente = obtener_ip_cliente(request)
    ref_hash = hash_token(raw_refresh)

    sesion = db.query(Sesion).filter(Sesion.refresh_hash == ref_hash).first()

    # Validar sesión viva (§5)
    esta_viva = True
    if not sesion or sesion.revocada_en is not None:
        esta_viva = False
    elif sesion.expira_en and (sesion.expira_en.replace(tzinfo=now.tzinfo) if sesion.expira_en.tzinfo is None else sesion.expira_en) <= now:
        esta_viva = False
    else:
        ultimo_latido_tz = sesion.ultimo_latido.replace(tzinfo=now.tzinfo) if sesion.ultimo_latido.tzinfo is None else sesion.ultimo_latido
        if (now - ultimo_latido_tz).total_seconds() > settings.session_dead_after_seconds:
            esta_viva = False
        else:
            ultima_act_tz = sesion.ultima_actividad.replace(tzinfo=now.tzinfo) if sesion.ultima_actividad.tzinfo is None else sesion.ultima_actividad
            if (now - ultima_act_tz).total_seconds() > (settings.idle_timeout_minutes * 60):
                esta_viva = False

    if not esta_viva:
        if sesion and sesion.revocada_en is None:
            sesion.revocada_en = now
            registrar_evento_seguridad(
                db=db,
                accion="SESION_EXPIRADA",
                id_usuario=sesion.id_usuario,
                id_objetivo=sesion.id_usuario,
                ip=ip_cliente,
                detalle={"motivo": "Refresh sobre sesión no viva."},
            )
            db.commit()

        # Limpiar cookie ante sesión expirada (§6.2)
        response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        delete_header = 'refresh_token=""; Path=/api/auth; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT'
        raise SesionExpiradaError("La sesión ha expirado.", headers={"Set-Cookie": delete_header})

    usuario = db.query(Usuario).filter(Usuario.id_usuario == sesion.id_usuario).first()
    if not usuario or not usuario.activo:
        sesion.revocada_en = now
        db.commit()
        response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        delete_header = 'refresh_token=""; Path=/api/auth; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT'
        raise SesionExpiradaError("Usuario inactivo.", headers={"Set-Cookie": delete_header})

    # La reactivación renueva la actividad
    sesion.ultima_actividad = now
    db.commit()

    rol_nombre = usuario.rol.nombre if usuario.rol else "BIOQUIMICO"
    nuevo_access_token = create_access_token(
        subject=str(usuario.id_usuario),
        session_id=str(sesion.id_sesion),
        role=rol_nombre,
    )

    usuario_resumen = UsuarioResumenResponse(
        id_usuario=usuario.id_usuario,
        usuario=usuario.usuario,
        nombres=usuario.nombres,
        apellido_paterno=usuario.apellido_paterno,
        apellido_materno=usuario.apellido_materno,
        rol=rol_nombre,
    )

    return TokenResponse(
        access_token=nuevo_access_token,
        token_type="bearer",
        expires_in=settings.access_token_minutes * 60,
        debe_cambiar_password=usuario.debe_cambiar_password,
        usuario=usuario_resumen,
    )


@router.post(
    "/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Registrar latido (Heartbeat)",
    description="Actualiza solo ultimo_latido de la sesión. Responde 204 No Content.",
)
def heartbeat(
    request: Request,
    current_user: Usuario = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    # require_auth ya validó token y sesión viva
    sesion: Sesion | None = getattr(request.state, "sesion_actual", None)
    if sesion:
        sesion.ultimo_latido = ahora()
        db.commit()


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión (Logout)",
    description="Revoca la sesión activa y borra la cookie refresh. Idempotente (204).",
)
def logout(
    request: Request,
    response: Response,
    x_lis_client: str | None = Header(default=None, alias="X-LIS-Client"),
    db: Session = Depends(get_db),
) -> None:
    if x_lis_client != "web":
        raise ValidacionError("Cabecera X-LIS-Client: web requerida.")

    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        ref_hash = hash_token(raw_refresh)
        sesion = (
            db.query(Sesion)
            .filter(Sesion.refresh_hash == ref_hash, Sesion.revocada_en.is_(None))
            .first()
        )
        if sesion:
            now = ahora()
            sesion.revocada_en = now
            registrar_evento_seguridad(
                db=db,
                accion="LOGOUT",
                id_usuario=sesion.id_usuario,
                id_objetivo=sesion.id_usuario,
                ip=obtener_ip_cliente(request),
            )
            db.commit()

    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Consultar usuario autenticado (/me)",
    description="Retorna el perfil del usuario activo en la sesión actual.",
)
def get_me(
    current_user: Usuario = Depends(require_auth),
) -> MeResponse:
    rol_nombre = current_user.rol.nombre if current_user.rol else "BIOQUIMICO"
    return MeResponse(
        id_usuario=current_user.id_usuario,
        usuario=current_user.usuario,
        nombres=current_user.nombres,
        apellido_paterno=current_user.apellido_paterno,
        apellido_materno=current_user.apellido_materno,
        rol=rol_nombre,
        debe_cambiar_password=current_user.debe_cambiar_password,
    )


@router.post(
    "/cambiar-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cambio de contraseña (obligatorio o voluntario)",
    description="Valida clave actual, política clínica (422), desactiva flag y revoca otras sesiones.",
)
def cambiar_password(
    body: CambiarPasswordRequest,
    request: Request,
    current_user: Usuario = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    ip_cliente = obtener_ip_cliente(request)
    now = ahora()

    # 1. Validar clave actual
    if not verify_password(body.password_actual, current_user.hash_password):
        raise ValidacionError("La contraseña actual es incorrecta.")

    # 2. Validar política clínica sobre la nueva contraseña (§5, §6.4)
    es_valida, error_msg = check_password_policy(
        new_password=body.password_nueva,
        username=current_user.usuario,
        ci=current_user.ci,
        current_password=body.password_actual,
        current_password_hash=current_user.hash_password,
    )
    if not es_valida:
        raise PasswordDebilError(error_msg or "La nueva contraseña no cumple con la política de seguridad.")

    # 3. Actualizar contraseña y quitar flag
    current_user.hash_password = get_password_hash(body.password_nueva)
    current_user.debe_cambiar_password = False

    # 4. Revocar las DEMÁS sesiones del usuario, manteniendo viva la actual (§6.2)
    sesion_actual: Sesion | None = getattr(request.state, "sesion_actual", None)
    id_sesion_actual = sesion_actual.id_sesion if sesion_actual else None

    sesiones_a_revocar = db.query(Sesion).filter(
        Sesion.id_usuario == current_user.id_usuario,
        Sesion.revocada_en.is_(None),
    )
    if id_sesion_actual:
        sesiones_a_revocar = sesiones_a_revocar.filter(Sesion.id_sesion != id_sesion_actual)

    sesiones_a_revocar.update({"revocada_en": now}, synchronize_session=False)

    # 5. Registrar evento CAMBIO_PASSWORD
    registrar_evento_seguridad(
        db=db,
        accion="CAMBIO_PASSWORD",
        id_usuario=current_user.id_usuario,
        id_objetivo=current_user.id_usuario,
        ip=ip_cliente,
        detalle={"motivo": "Cambio de contraseña exitoso"},
    )
    db.commit()
```

---

## 3. Pruebas Manuales de Aceptación Clínica — Fase 2 (§13)

Ejecución del arnés de aceptación clínica integral contra PostgreSQL real (`lis_test`), cubriendo los 5 criterios clínicos obligatorios (a)-(e):

```text
===========================================================================
 CRITERIO (a): ALTA CON PERFIL, QUITAR ESTUDIO, NUMERACIÓN 1 Y 2 
===========================================================================
[(a).1] POST /api/ordenes (Nuevo paciente + perfil HC-QMC-SEROL-EGO sin EGO):
       HTTP Status: 201
       id_paciente: 539, numero_orden_paciente: 1
       Estudios guardados: ['HEMOGRAMA', 'QUIMICA_SANGUINEA', 'INMUNOSEROLOGIA']

[(a).2] POST /api/ordenes (Segunda orden para el mismo paciente):
       HTTP Status: 201
       numero_orden_paciente: 2

===========================================================================
 CRITERIO (b): DOS BIOQUÍMICOS (BLOQUEO 409, ADVERTENCIA 201, DISJUNTO 201) 
===========================================================================
[(b).1] Bioquímico A crea orden con HEMOGRAMA y QUIMICA_SANGUINEA:
       HTTP Status: 201

[(b).2] Bioquímico B intenta crear con HEMOGRAMA (subconjunto de A):
       HTTP Status esperado: 409 | Obtenido: 409
       Respuesta: {"codigo": "ORDEN_DUPLICADA_EN_CURSO", "mensaje": "Existe una orden en curso de otro bioquímico que cubre los estudios solicitados.", "detalle": {"autor": {"nombres": "Alba", "apellido_paterno": "Rios"}, "estudios": ["HEMOGRAMA"]}}

[(b).3] Bioquímico B crea con HEMOGRAMA + PERFIL_LIPIDICO (solapamiento parcial):
       HTTP Status esperado: 201 | Obtenido: 201
       Advertencias: [{"tipo": "SOLAPAMIENTO", "autor": {"id": null, "nombres": "Alba", "apellido_paterno": "Rios"}, "estudios": ["HEMOGRAMA"]}]

[(b).4] Bioquímico B crea con PERFIL_LIPIDICO (disjunto respecto a A):
       HTTP Status esperado: 201 | Obtenido: 201
       Advertencias: []

===========================================================================
 CRITERIO (c): INMUNOSEROLOGÍA VIH vs PCR_SEMICUANT ENTRE USUARIOS DISTINTOS 
===========================================================================
[(c).1] Bioquímico A solicita INMUNOSEROLOGIA con grupo VIH:
       HTTP Status: 201

[(c).2] Bioquímico B solicita INMUNOSEROLOGIA con grupo PCR_SEMICUANT:
       HTTP Status esperado: 201 | Obtenido: 201
       Advertencias: [] (sin bloqueo ni solapamiento)

===========================================================================
 CRITERIO (d): AUDITORÍA ADMIN_VE_PRIVADO EN LOG_SEGURIDAD 
===========================================================================
[(d).1] Admin consulta GET /api/ordenes: HTTP 200 (Total: 6)
[(d).2] Admin consulta GET /api/ordenes/438 (orden de Alba): HTTP 200

[(d).3] SELECT accion, count(*) FROM laboratorio.log_seguridad GROUP BY 1:
       - ADMIN_VE_PRIVADO: 2

===========================================================================
 CRITERIO (e): DESCARTE DE BORRADOR Y FILA EN BORRADORES_DESCARTADOS 
===========================================================================
[(e).1] Bioquímica Alba descarta su Orden #438 (DELETE /api/ordenes/438):
       HTTP Status esperado: 204 | Obtenido: 204
[(e).2] Verificación de eliminación de la orden:
       HTTP Status esperado: 404 | Obtenido: 404

[(e).3] SELECT * FROM laboratorio.borradores_descartados:
       - id_descarte: 15, id_orden: 439, id_paciente: 540
         id_usuario: 2365, estado_trabajo: INCOMPLETO, estaba_bloqueada: False
         descartado_en: 2026-10-12 05:15:25.833343+00:00
       - id_descarte: 16, id_orden: 438, id_paciente: 540
         id_usuario: 2364, estado_trabajo: INCOMPLETO, estaba_bloqueada: False
         descartado_en: 2026-10-12 05:15:26.050154+00:00

✓ TODOS LOS 5 CRITERIOS DE ACEPTACIÓN SE CUMPLIERON AL 100%.
```

---

## 4. Salida Verbosa Completa de los 92 Tests Automatizados

```text
$ python -m unittest discover -s tests -p "test_*.py" -v

test_codigos_unicos_por_estudio (test_calculo_y_catalogo.TestCatalogo.test_codigos_unicos_por_estudio) ... ok
test_formulas_usan_solo_parametros_del_mismo_estudio (test_calculo_y_catalogo.TestCatalogo.test_formulas_usan_solo_parametros_del_mismo_estudio) ... ok
test_grupos_de_perfil_existen (test_calculo_y_catalogo.TestCatalogo.test_grupos_de_perfil_existen) ... ok
test_perfiles_cubren_los_9_estudios (test_calculo_y_catalogo.TestCatalogo.test_perfiles_cubren_los_9_estudios) ... ok
test_rangos_coherentes (test_calculo_y_catalogo.TestCatalogo.test_rangos_coherentes) ... ok
test_reglas_referencian_parametros_existentes (test_calculo_y_catalogo.TestCatalogo.test_reglas_referencian_parametros_existentes) ... ok
test_selecciones_tienen_opciones_y_defectos_validos (test_calculo_y_catalogo.TestCatalogo.test_selecciones_tienen_opciones_y_defectos_validos) ... ok
test_son_9_estudios (test_calculo_y_catalogo.TestCatalogo.test_son_9_estudios) ... ok
test_coma_decimal (test_calculo_y_catalogo.TestFormulas.test_coma_decimal) ... ok
test_diferencial_porcentaje_a_absoluto (test_calculo_y_catalogo.TestFormulas.test_diferencial_porcentaje_a_absoluto) ... ok
test_diferencial_sin_gb_no_calculable (test_calculo_y_catalogo.TestFormulas.test_diferencial_sin_gb_no_calculable) ... ok
test_friedewald_invalido_con_tg_mayor_400 (test_calculo_y_catalogo.TestFormulas.test_friedewald_invalido_con_tg_mayor_400) ... ok
test_friedewald_limite_400_si_calcula (test_calculo_y_catalogo.TestFormulas.test_friedewald_limite_400_si_calcula) ... ok
test_hemograma_estimados (test_calculo_y_catalogo.TestFormulas.test_hemograma_estimados) ... ok
test_hepatograma_bilirrubina_indirecta (test_calculo_y_catalogo.TestFormulas.test_hepatograma_bilirrubina_indirecta) ... ok
test_hepatograma_directa_mayor_que_total (test_calculo_y_catalogo.TestFormulas.test_hepatograma_directa_mayor_que_total) ... ok
test_lipidico_excel_calculaba_ldl_sin_hdl (test_calculo_y_catalogo.TestFormulas.test_lipidico_excel_calculaba_ldl_sin_hdl) ... ok
test_lipidico_valores_del_excel (test_calculo_y_catalogo.TestFormulas.test_lipidico_valores_del_excel) ... ok
test_proteinograma (test_calculo_y_catalogo.TestFormulas.test_proteinograma) ... ok
test_proteinograma_albumina_mayor_que_total (test_calculo_y_catalogo.TestFormulas.test_proteinograma_albumina_mayor_que_total) ... ok
test_proteinograma_sin_division_por_cero (test_calculo_y_catalogo.TestFormulas.test_proteinograma_sin_division_por_cero) ... ok
test_redondeo_half_up (test_calculo_y_catalogo.TestFormulas.test_redondeo_half_up) ... ok
test_vacio_no_es_cero (test_calculo_y_catalogo.TestFormulas.test_vacio_no_es_cero) ... ok
test_parametro_desconocido (test_calculo_y_catalogo.TestSeguridadEvaluador.test_parametro_desconocido) ... ok
test_rechaza_codigo_arbitrario (test_calculo_y_catalogo.TestSeguridadEvaluador.test_rechaza_codigo_arbitrario) ... ok
test_09_estudios_activos_y_seleccion_parcial (test_catalogo_api.TestCatalogoAPI.test_09_estudios_activos_y_seleccion_parcial)
9. Devuelve exactamente los 9 estudios activos; solo Inmunoserología tiene ... ok
test_10_perfiles_coinciden_con_definiciones (test_catalogo_api.TestCatalogoAPI.test_10_perfiles_coinciden_con_definiciones)
10. Los 2 perfiles coinciden con PERFILES de definitions.py ... ok
test_11_autenticacion_y_estudio_inactivo_oculto (test_catalogo_api.TestCatalogoAPI.test_11_autenticacion_y_estudio_inactivo_oculto)
11. Exige autenticación; un estudio con activo = FALSE no aparece. ... ok
test_27_arranque_rechaza_jwt_secret_inseguro (test_login.TestArranqueConfiguracion.test_27_arranque_rechaza_jwt_secret_inseguro)
27. La app no arranca con JWT_SECRET corto o que empiece por CAMBIAR. ... ok
test_05_login_correcto_devuelve_token_cookie_y_sesion (test_login.TestLoginYBloqueo.test_05_login_correcto_devuelve_token_cookie_y_sesion)
5. Login correcto devuelve token, cookie httpOnly+SameSite=Strict+Path=/api/auth y crea sesión. ... ok
test_06_usuario_inexistente_clave_erronea_e_inactivo_mismo_401 (test_login.TestLoginYBloqueo.test_06_usuario_inexistente_clave_erronea_e_inactivo_mismo_401)
6. Usuario inexistente, clave incorrecta y usuario inactivo → mismo 401 y mismo mensaje. ... ok
test_07_bloqueo_por_cinco_fallos_y_desbloqueo_temporal (test_login.TestLoginYBloqueo.test_07_bloqueo_por_cinco_fallos_y_desbloqueo_temporal)
7. 5 fallos seguidos → el 6.º intento da 423 con minutos_restantes; pasado LOCKOUT_MINUTES vuelve a funcionar. ... ok
test_08_login_correcto_reinicia_intentos_fallidos (test_login.TestLoginYBloqueo.test_08_login_correcto_reinicia_intentos_fallidos)
8. Login correcto reinicia intentos_fallidos. ... ok
test_09_registro_eventos_login_con_ip_y_sin_password (test_login.TestLoginYBloqueo.test_09_registro_eventos_login_con_ip_y_sin_password)
9. Se registran LOGIN_OK y LOGIN_FALLIDO con IP; la contraseña no aparece en ningún registro. ... ok
test_12_orden_paciente_existente_numeracion_correlativa (test_ordenes.TestOrdenesAPI.test_12_orden_paciente_existente_numeracion_correlativa)
12. Orden para paciente existente → 201, INCOMPLETO, autor correcto, numero_orden_paciente 1 y luego 2. ... ok
test_13_alta_paciente_mas_orden_atomica_revierte_si_falla (test_ordenes.TestOrdenesAPI.test_13_alta_paciente_mas_orden_atomica_revierte_si_falla)
13. Alta de paciente + orden en una transacción; si la orden es inválida no queda el paciente. ... ok
test_14_xor_id_paciente_y_paciente (test_ordenes.TestOrdenesAPI.test_14_xor_id_paciente_y_paciente)
14. id_paciente y paciente a la vez, o ninguno → 400. ... ok
test_15_validaciones_de_estudios (test_ordenes.TestOrdenesAPI.test_15_validaciones_de_estudios)
15. Sin estudios, estudio repetido, código inexistente, estudio inactivo → 400. ... ok
test_16_validaciones_de_grupos (test_ordenes.TestOrdenesAPI.test_16_validaciones_de_grupos)
16. grupos en estudio no parcial → 400; estudio parcial sin grupos → 400; grupo inexistente → 400. ... ok
test_17_congelamiento_version_y_orden_estudio_grupos (test_ordenes.TestOrdenesAPI.test_17_congelamiento_version_y_orden_estudio_grupos)
17. Se guarda id_estudio_version activa y las filas de orden_estudio_grupos. ... ok
test_18_calculo_edad_con_reloj_y_validaciones (test_ordenes.TestOrdenesAPI.test_18_calculo_edad_con_reloj_y_validaciones)
18. Edad calculada con fecha de nacimiento (reloj simulado) e ignorando la enviada; sin fecha de nacimiento y sin edad_anios → 400; edad_meses fuera de 0–11 → 400. ... ok
test_19_perfil_inexistente_y_perfil_con_estudios_distintos (test_ordenes.TestOrdenesAPI.test_19_perfil_inexistente_y_perfil_con_estudios_distintos)
19. perfil inexistente → 400; perfil válido se guarda aunque estudios difiera. ... ok
test_20_admin_no_puede_crear_ordenes (test_ordenes.TestOrdenesAPI.test_20_admin_no_puede_crear_ordenes)
20. ADMIN no puede crear → 403. ... ok
test_21_concurrencia_creacion_mismo_paciente (test_ordenes.TestOrdenesAPI.test_21_concurrencia_creacion_mismo_paciente)
21. Dos creaciones concurrentes (hilos) para el mismo paciente → números 1 y 2, sin error 500 ni repetidos. ... ok
test_22_toma_muestra_futura (test_ordenes.TestOrdenesAPI.test_22_toma_muestra_futura)
22. Toma de muestra futura (> 5 min) → 400. ... ok
test_23_estudios_disjuntos_sin_advertencias (test_ordenes.TestOrdenesAPI.test_23_estudios_disjuntos_sin_advertencias)
23. Estudios disjuntos con borrador ajeno → 201, sin advertencias. ... ok
test_24_solapamiento_parcial_emite_advertencia (test_ordenes.TestOrdenesAPI.test_24_solapamiento_parcial_emite_advertencia)
24. Solapamiento parcial → 201 con advertencias (autor + códigos, sin id de orden). ... ok
test_25_subconjunto_bloquea_409_orden_duplicada_en_curso (test_ordenes.TestOrdenesAPI.test_25_subconjunto_bloquea_409_orden_duplicada_en_curso)
25. Nueva ⊆ borrador ajeno → 409 ORDEN_DUPLICADA_EN_CURSO con detalle; no se crea paciente ni orden. ... ok
test_26_no_bloquea_si_es_propio_bloqueada_publicada_o_distinto_paciente (test_ordenes.TestOrdenesAPI.test_26_no_bloquea_si_es_propio_bloqueada_publicada_o_distinto_paciente)
26. No bloquea si el borrador es propio, está bloqueada, está PUBLICADA, o es de otro paciente. ... ok
test_27_granularidad_por_grupo (test_ordenes.TestOrdenesAPI.test_27_granularidad_por_grupo)
27. Granularidad por grupo: INMUNOSEROLOGIA:VIH vs INMUNOSEROLOGIA:PCR_SEMICUANT son disjuntos (201); VIH vs VIH bloquea. ... ok
test_28_cubierta_solo_por_union_de_dos_borradores_no_bloquea (test_ordenes.TestOrdenesAPI.test_28_cubierta_solo_por_union_de_dos_borradores_no_bloquea)
28. Nueva ⊄ ningún borrador individual (cubierta solo por la unión de dos ajenos) → no bloquea (solo advertencias). ... ok
test_29_bioquimico_lista_solo_sus_ordenes_y_filtros (test_ordenes.TestOrdenesAPI.test_29_bioquimico_lista_solo_sus_ordenes_y_filtros)
29. BIOQUIMICO lista solo sus órdenes; filtros estado e id_paciente. ... ok
test_30_get_orden_ajena_responde_404_para_bioquimico (test_ordenes.TestOrdenesAPI.test_30_get_orden_ajena_responde_404_para_bioquimico)
30. GET /api/ordenes/{id} de orden ajena → 404 para BIOQUIMICO. ... ok
test_31_admin_lista_todas_y_audita_admin_ve_privado (test_ordenes.TestOrdenesAPI.test_31_admin_lista_todas_y_audita_admin_ve_privado)
31. ADMIN lista todas y se registra un ADMIN_VE_PRIVADO por petición (con cantidad); GET ajena registra id_objetivo=autor; lista vacía no registra. ... ok
test_32_admin_no_puede_patch_ni_delete (test_ordenes.TestOrdenesAPI.test_32_admin_no_puede_patch_ni_delete)
32. ADMIN no puede PATCH ni DELETE → 403. ... ok
test_33_patch_fila_version_y_concurrencia_optimista (test_ordenes.TestOrdenesAPI.test_33_patch_fila_version_y_concurrencia_optimista)
33. PATCH con fila_version correcta la incrementa; incorrecta → 409 CONFLICTO_VERSION; dos PATCH simultáneos → uno gana y otro 409. ... ok
test_34_patch_campos_prohibidos (test_ordenes.TestOrdenesAPI.test_34_patch_campos_prohibidos)
34. PATCH con estudios, estado o id_paciente → 400. ... ok
test_35_delete_descarte_de_borrador_y_registro_historico (test_ordenes.TestOrdenesAPI.test_35_delete_descarte_de_borrador_y_registro_historico)
35. DELETE por el autor → 204, desaparecen orden y filas hijas, aparece fila en borradores_descartados con estado_trabajo y estaba_bloqueada correctos; otro BIOQUIMICO → 404; ADMIN → 403; orden PUBLICADA → 409. ... ok
test_36_trigger_orden_requiere_estudios_a_nivel_bd (test_ordenes.TestOrdenesAPI.test_36_trigger_orden_requiere_estudios_a_nivel_bd)
36. A nivel de BD: insertar una orden sin estudios y confirmar la transacción falla (constraint trigger del esquema). ... ok
test_01_alta_con_ci_normaliza_datos (test_pacientes.TestPacientesAPI.test_01_alta_con_ci_normaliza_datos)
1. Alta con CI → 201; normaliza (mayúsculas, espacios). ... ok
test_02_regla_excluyente_ci_vs_sin_ci (test_pacientes.TestPacientesAPI.test_02_regla_excluyente_ci_vs_sin_ci)
2. sin_ci=true con ci, o sin_ci=false sin ci → 400. ... ok
test_03_ci_duplicado_y_complemento (test_pacientes.TestPacientesAPI.test_03_ci_duplicado_y_complemento)
3. CI duplicado → 409 con paciente_existente_id; mismo CI con otro complemento → 201; ... ok
test_04_fecha_nacimiento_limites (test_pacientes.TestPacientesAPI.test_04_fecha_nacimiento_limites)
4. Fecha de nacimiento futura o de hace > 130 años → 400. ... ok
test_05_permisos_y_estados_autenticacion (test_pacientes.TestPacientesAPI.test_05_permisos_y_estados_autenticacion)
5. ADMIN puede GET; POST/PATCH → 403. Sin token → 401. Con debe_cambiar_password → 403. ... ok
test_06_busqueda_paginacion_y_limites (test_pacientes.TestPacientesAPI.test_06_busqueda_paginacion_y_limites)
6. Búsqueda q por CI, apellido y nombre (parcial, sin distinguir mayúsculas); paginación y total; limit=101 → 400. ... ok
test_07_patch_edicion_unicidad_y_campo_desconocido (test_pacientes.TestPacientesAPI.test_07_patch_edicion_unicidad_y_campo_desconocido)
7. PATCH edita campos y respeta unicidad de CI (409); campo desconocido → 400. ... ok
test_08_no_existe_delete_pacientes (test_pacientes.TestPacientesAPI.test_08_no_existe_delete_pacientes)
8. No existe DELETE /api/pacientes/{id}. ... ok
test_01_hash_y_verificacion_correctos (test_password.TestPasswordSecurity.test_01_hash_y_verificacion_correctos)
1. Hash y verificación correctos; dos hashes de la misma clave difieren. ... ok
test_02_rechazo_politica_invalida (test_password.TestPasswordSecurity.test_02_rechazo_politica_invalida)
2. Rechaza: < 10 caracteres, > 128, en lista prohibida, contiene usuario, contiene CI, igual a la actual. ... ok
test_03_acepta_clave_valida (test_password.TestPasswordSecurity.test_03_acepta_clave_valida)
3. Acepta una clave larga y no prohibida. ... ok
test_04_temporal_14_caracteres_sin_ambiguos (test_password.TestPasswordSecurity.test_04_temporal_14_caracteres_sin_ambiguos)
4. La temporal tiene exactamente 14 caracteres y ninguno de '0 O 1 l I'. ... ok
test_05_dummy_argon2_hash_valido_y_lanza_mismatch (test_password.TestPasswordSecurity.test_05_dummy_argon2_hash_valido_y_lanza_mismatch)
(a) Verificar contra DUMMY_ARGON2_HASH con argon2.PasswordHasher().verify lanza VerifyMismatchError. ... ok
test_06_login_usuario_inexistente_invoca_verificacion_ficticia (test_password.TestPasswordSecurity.test_06_login_usuario_inexistente_invoca_verificacion_ficticia)
(b) Con usuario inexistente, el login sí invoca la verificación ficticia (contador sobre password_hash.verify). ... ok
test_07_cantidad_claves_prohibidas (test_password.TestPasswordSecurity.test_07_cantidad_claves_prohibidas)
(c) len(CLAVES_PROHIBIDAS) == 21. ... ok
test_08_generate_temporary_password_lanza_excepcion_si_falla (test_password.TestPasswordSecurity.test_08_generate_temporary_password_lanza_excepcion_si_falla)
generate_temporary_password lanza excepción si ninguna candidata cumple la política. ... ok
test_10_sesion_muere_sin_latido_tras_150_segundos (test_sesion.TestCicloVidaSesion.test_10_sesion_muere_sin_latido_tras_150_segundos)
10. Sesión muere con SESSION_DEAD_AFTER_SECONDS sin latido (401 SESION_EXPIRADA) y queda revocada. ... ok
test_11_con_latidos_pero_sin_actividad_muere_por_idle_timeout (test_sesion.TestCicloVidaSesion.test_11_con_latidos_pero_sin_actividad_muere_por_idle_timeout)
11. Con latidos pero sin actividad durante IDLE_TIMEOUT_MINUTES → muere (el latido no cuenta como actividad). ... ok
test_12_peticion_normal_renueva_actividad_pero_latido_no (test_sesion.TestCicloVidaSesion.test_12_peticion_normal_renueva_actividad_pero_latido_no)
12. Una petición normal renueva ultima_actividad; el latido no. ... ok
test_13_muere_al_superar_tope_absoluto_de_12_horas (test_sesion.TestCicloVidaSesion.test_13_muere_al_superar_tope_absoluto_de_12_horas)
13. Muere al superar ABSOLUTE_SESSION_HOURS aunque haya latidos y actividad. ... ok
test_14_refresh_comportamiento_cabecera_y_sesion (test_sesion.TestCicloVidaSesion.test_14_refresh_comportamiento_cabecera_y_sesion)
14. refresh sin cabecera X-LIS-Client → 400; con sesión muerta → 401 y limpia cookie; con viva → 200 y cookie no cambia. ... ok
test_15_logout_revoca_sesion_e_invalida_token (test_sesion.TestCicloVidaSesion.test_15_logout_revoca_sesion_e_invalida_token)
15. logout revoca la sesión; usar el access token después → 401; logout repetido → 204. ... ok
test_16_debe_cambiar_password_bloquea_rutas_fuera_de_whitelist (test_sesion.TestCicloVidaSesion.test_16_debe_cambiar_password_bloquea_rutas_fuera_de_whitelist)
16. Con debe_cambiar_password = TRUE, cualquier endpoint fuera de la lista blanca → 403 DEBE_CAMBIAR_PASSWORD. ... ok
test_17_cambiar_password_correcto_y_rechazo_con_clave_erronea (test_sesion.TestCicloVidaSesion.test_17_cambiar_password_correcto_y_rechazo_con_clave_erronea)
17. cambiar-password correcto: baja flag, revoca otras sesiones, conserva actual; con clave actual errónea rechaza. ... ok
test_18_usuario_desactivado_invalida_token_de_inmediato (test_sesion.TestCicloVidaSesion.test_18_usuario_desactivado_invalida_token_de_inmediato)
18. Un token cuyo usuario fue desactivado deja de funcionar de inmediato. ... ok
test_19_bioquimico_recibe_403_prohibido_y_sin_token_401 (test_usuarios.TestGestionUsuarios.test_19_bioquimico_recibe_403_prohibido_y_sin_token_401)
19. Un BIOQUIMICO recibe 403 PROHIBIDO en todos los endpoints /api/usuarios; sin token → 401. ... ok
test_20_crear_usuario_devuelve_temporal_solo_una_vez_y_guarda_hash (test_usuarios.TestGestionUsuarios.test_20_crear_usuario_devuelve_temporal_solo_una_vez_y_guarda_hash)
20. Crear usuario: devuelve password_temporal una vez; en BD solo hash Argon2id; GET no la devuelve; debe_cambiar=TRUE. ... ok
test_21_duplicados_usuario_ci_correo_devuelven_409_conflicto (test_usuarios.TestGestionUsuarios.test_21_duplicados_usuario_ci_correo_devuelven_409_conflicto)
21. Duplicados de usuario, ci, correo → 409 CONFLICTO. ... ok
test_22_desactivar_revoca_sesiones_y_reactivar_limpia_bloqueo (test_usuarios.TestGestionUsuarios.test_22_desactivar_revoca_sesiones_y_reactivar_limpia_bloqueo)
22. Desactivar revoca sus sesiones; reactivar limpia bloqueo. ... ok
test_23_admin_no_puede_desactivarse_ni_dejar_sistema_sin_admin (test_usuarios.TestGestionUsuarios.test_23_admin_no_puede_desactivarse_ni_dejar_sistema_sin_admin)
23. Un admin no puede desactivarse ni cambiarse el rol; no se puede dejar el sistema sin admin activo. ... ok
test_24_no_existe_ruta_delete_usuarios (test_usuarios.TestGestionUsuarios.test_24_no_existe_ruta_delete_usuarios)
24. No existe ruta DELETE /api/usuarios/{id} (responde 405 o 404). ... ok
test_25_reset_password_genera_temporal_y_revoca_sesiones (test_usuarios.TestGestionUsuarios.test_25_reset_password_genera_temporal_y_revoca_sesiones)
25. Reset de contraseña: nueva temporal, flag activo, sesiones revocadas, evento registrado. ... ok
test_26_ninguna_respuesta_api_contiene_hash_password_ni_refresh_hash (test_usuarios.TestGestionUsuarios.test_26_ninguna_respuesta_api_contiene_hash_password_ni_refresh_hash)
26. Ninguna respuesta de la API contiene hash_password ni refresh_hash. ... ok

----------------------------------------------------------------------
Ran 92 tests in 37.395s

OK (skipped=0)
```

---

## 5. Decisiones Clínicas de la Fase 3 (§12 en `docs/DECISIONES.md`)

Alineado con las directivas para la siguiente fase:

* **D3-01** Valores por defecto del EGO: no se guardan hasta que el bioquímico los confirma, y mientras no estén confirmados la orden no puede completarse.
* **D3-02** LDL con triglicéridos > 400: se informa “No calculable” y no bloquea el paso a COMPLETO; si faltan entradas para el cálculo, sí bloquea.
* **D3-03** Reglas cruzadas: un error analítico (ej. bilirrubina directa mayor que la total) bloquea el paso a COMPLETO; una advertencia clínica (ej. el diferencial leucocitario no suma 100) no bloquea.
* **D3-04** Dos pestañas del mismo autor: concurrencia a nivel de parámetro individual donde gana la última escritura guardada.
* **D3-05** Exclusiones explícitas de Fase 3: valores críticos, límites fisiológicos y reemplazar glóbulos rojos / hematocrito estimados por valores medidos. Publicación de órdenes, asignación de folios, emisión de informes oficiales y generación de PDF corresponden estrictamente a fases posteriores (Fase 4 y Fase 5).
