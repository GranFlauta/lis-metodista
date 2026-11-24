# LIS — Sistema de Información de Laboratorio Clínico

Servidor local (on-premise): **PostgreSQL 16 + FastAPI + React/Vite + Caddy (HTTPS)** con Podman / Docker Compose.
Para retomar trabajo, lee primero **[docs/CONTEXTO_PROYECTO.md](docs/CONTEXTO_PROYECTO.md)**, luego [AGENTS.md](AGENTS.md) y [docs/DECISIONES.md](docs/DECISIONES.md). Antes de cambios frontend, consulta [docs/UX_GUIDE.md](docs/UX_GUIDE.md).

## Estado

El proyecto ya incluye autenticación y roles, pacientes, órdenes, captura y cálculo clínico, catálogo versionado, informes oficiales y vista previa PDF, perfiles, curva de tolerancia, coproparasitología y estadísticas. Los documentos de fases conservan el historial; **no uses sus etiquetas de fase como estado actual**.

Último estado reportado el 24/11/2026: la base activa estaba en Alembic `0019`; `0020_inmunoserologia_chagas_asto.py` está creada y pendiente de autorización/aplicación. Verifica la base antes de ejecutar migraciones. El mapa de módulos y cambios pendientes está en [docs/CONTEXTO_PROYECTO.md](docs/CONTEXTO_PROYECTO.md).

## Estructura del Proyecto

```
db/init/001_schema.sql          Esquema (tablas, índices, triggers de inmutabilidad, folios)
db/init/002_seed_catalogo.sql   GENERADO desde definitions.py — no editar a mano
backend/alembic/                Migraciones Alembic (0001_baseline.py = línea base)
backend/app/api/                Endpoints: auth, usuarios, pacientes, ordenes, catalogo, resultados
backend/app/services/           evaluacion_service.py (cálculo, banderas, reglas, completitud)
backend/app/calculation/        Motor de fórmulas (sin eval, Decimal)
backend/app/catalog/            definitions.py = fuente única del catálogo
backend/app/reports/            Presentación, plantilla HTML Jinja, generación de vista previa/PDF y assets
backend/app/core/               clock.py (reloj determinista), errors.py, security.py, config.py
backend/app/cli.py              CLI para crear administrador inicial
backend/tests/                  Pruebas unitarias e integración (esta última requiere PostgreSQL _test)
frontend/src/api/               Cliente HTTP con Bearer en memoria y reintento de refresh
frontend/src/features/          auth, admin, home, pacientes, ordenes, informes, catalogo, estadisticas
backend/app/reports/templates/informe.html  Plantilla real compartida por vista previa y PDF oficial
frontend/index.html             Carcasa de Vite; monta la aplicación React
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

La cantidad de pruebas cambia al ampliar el catálogo. Las pruebas de integración usan una base PostgreSQL exclusiva cuyo nombre termina en `_test`; no apuntes la suite a la base activa.

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

