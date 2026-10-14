# LIS — Sistema de Información de Laboratorio Clínico

Servidor local (on-premise): **PostgreSQL 16 + FastAPI + React/Vite + Caddy (HTTPS)** con Podman / Docker Compose.
Las reglas de negocio y todas las decisiones están en **[docs/DECISIONES.md](docs/DECISIONES.md)** (léelo primero).

## Estado: Fase 3.5 (En curso)

- **Listo (Fases 0 a 3)** — tag `fase-3-cerrada`:
  - Esquema de base de datos (`001_schema.sql`) con bajas lógicas y auditoría.
  - Catálogo de 9 estudios y 2 perfiles con motor de cálculo determinista (sin `eval`, `Decimal`).
  - Autenticación Argon2id, sesiones por latido con access token en memoria y refresh en cookie `HttpOnly` `SameSite=Strict`.
  - Gestión de usuarios (`ADMIN`) y CLI `crear-admin`.
  - Pacientes, órdenes en borrador y detección de trabajo duplicado (Fase 2).
  - Captura de resultados, cálculo en vivo, banderas por sexo/edad, reglas cruzadas y completitud (Fase 3).
  - Suite de **119 tests** (`unittest`) pasando contra PostgreSQL real, sin `skipped`.
- **En curso (Fase 3.5)**: endurecimiento de red (sin CORS ni ngrok), guarda de BD de pruebas, sesión configurable por el ADMIN con actividad real del usuario. Ver `PROMPT_FASE_3_5_CORRECCIONES.md` y `docs/DECISIONES.md §13`.
- **Siguiente (Fase 3.6)**: rediseño UX fiel a Excel según `docs/UX_GUIDE.md` (`PROMPT_FASE_3_6_UX.md`).
- **Pendiente (Fases 4+)**: publicación con folio, PDF oficial, versiones, delegación (ver `docs/DECISIONES.md §9`).

## Estructura del Proyecto

```
db/init/001_schema.sql          Esquema (tablas, índices, triggers de inmutabilidad, folios)
db/init/002_seed_catalogo.sql   GENERADO desde definitions.py — no editar a mano
backend/alembic/                Migraciones Alembic (0001_baseline.py = línea base)
backend/app/api/                Endpoints: auth, usuarios, pacientes, ordenes, catalogo, resultados
backend/app/services/           evaluacion_service.py (cálculo, banderas, reglas, completitud)
backend/app/calculation/        Motor de fórmulas (sin eval, Decimal)
backend/app/catalog/            definitions.py = fuente única del catálogo
backend/app/core/               clock.py (reloj determinista), errors.py, security.py, config.py
backend/app/cli.py              CLI para crear administrador inicial
backend/tests/                  Suite de 119 tests (unittest, PostgreSQL real)
frontend/src/api/               Cliente HTTP con Bearer en memoria y reintento de refresh
frontend/src/features/          auth, admin, home, pacientes, ordenes, ...
scripts/                        crear_bd_test.sh, backup.sh, restaurar.sh, generar_seed_sql.py
docs/                           DECISIONES, SUPUESTOS, UX_GUIDE, CONTEXTO_PROYECTO
docs/historial/                 Prompts, evaluaciones y evidencias de fases cerradas
docker-compose.yml  .env.example
```

## Puesta en Marcha con Podman

```bash
# 1) Configurar variables de entorno
cp .env.example .env        # configurar contraseñas seguras y JWT_SECRET

# 2) Levantar los contenedores en Podman
podman compose up -d --build

# 3) Verificar estado del servicio
curl -k --resolve lis.local:8443:127.0.0.1 https://lis.local:8443/api/health
# Respuesta esperada: {"status":"ok"}

# 4) Crear el primer usuario administrador (CLI interactivo)
podman exec -it lis_backend_1 python -m app.cli crear-admin
```

> **Nota TLS / Dominio**: Caddy genera un certificado TLS interno para el host configurado en `.env` (`LIS_HOST=lis.local`). Para acceder desde el navegador local, añade a tu `/etc/hosts`:
> ```
> 127.0.0.1 lis.local
> ```
> Y accede a: `https://lis.local:8443` (o puerto `8080` vía HTTP).

## Ejecución de Tests

La suite completa consta de **119 pruebas**:

| Archivo | Tests |
|---|---|
| `test_calculo_y_catalogo.py` | 25 |
| `test_ordenes.py` | 25 |
| `test_resultados_api.py` | 16 |
| `test_evaluacion.py` | 11 |
| `test_sesion.py` | 9 |
| `test_pacientes.py` | 8 |
| `test_password.py` | 8 |
| `test_usuarios.py` | 8 |
| `test_login.py` | 6 |
| `test_catalogo_api.py` | 3 |

```bash
# A) Tests unitarios (sin base de datos)
cd backend
./venv/bin/python -m unittest tests/test_calculo_y_catalogo.py tests/test_password.py -v

# B) Suite completa con PostgreSQL real (desde la raíz del repo):
# 1. Levantar la base de datos
podman compose up -d db

# 2. Recrear lis_test con esquema y catálogo (borra y crea la BD de pruebas)
CONTAINER_CLI=podman ./scripts/crear_bd_test.sh

# 3. Ejecutar la suite (el nombre de la BD debe terminar en _test)
cd backend
TEST_DATABASE_URL="postgresql+psycopg://lis_app:<POSTGRES_PASSWORD>@127.0.0.1:5432/lis_test" \
./venv/bin/python -m unittest discover -s tests -v
```

## Reglas de Desarrollo

Consultar [`AGENTS.md`](AGENTS.md) y [`docs/DECISIONES.md`](docs/DECISIONES.md).

