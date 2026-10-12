# LIS — Sistema de Información de Laboratorio Clínico

Servidor local (on-premise): **PostgreSQL 16 + FastAPI + React/Vite + Caddy (HTTPS)** con Podman / Docker Compose.
Las reglas de negocio y todas las decisiones están en **[docs/DECISIONES.md](docs/DECISIONES.md)** (léelo primero).

## Estado: Fase 1 (Completada)

- **Listo (Fase 0 y Fase 1)**:
  - Esquema de base de datos (`001_schema.sql`) con bajas lógicas y auditoría.
  - Catálogo de 9 estudios y 2 perfiles con motor de cálculo determinista.
  - Autenticación criptográfica con Argon2id y política estricta de contraseñas.
  - Sesiones por latido clínico cada 30 s con access tokens en memoria y cookies de refresco `SameSite=Strict`.
  - API REST de autenticación y gestión de usuarios (`ADMIN`).
  - Frontend SPA en React + Vite + TypeScript (Login, Cambio obligatorio de clave, Gestión de usuarios).
  - Comando CLI `crear-admin` y baseline de Alembic (`0001_baseline.py`).
  - Suite de 52 tests automatizados pasando al 100%.
- **Pendiente (Fases 2 en adelante)**:
  - Órdenes, pacientes, folios, carga de resultados, firmas e informes PDF (ver `docs/DECISIONES.md §9`).

## Estructura del Proyecto

```
db/init/001_schema.sql          Esquema (tablas, índices, triggers de inmutabilidad, folios)
db/init/002_seed_catalogo.sql   GENERADO desde definitions.py — no editar a mano
backend/alembic/                Configuración de Alembic y 0001_baseline.py vacía
backend/app/api/                Endpoints de auth y usuarios (FastAPI)
backend/app/calculation/        Motor de fórmulas (sin eval, Decimal)
backend/app/catalog/            definitions.py = fuente única del catálogo
backend/app/core/               clock.py (reloj determinista), errors.py, security.py, config.py
backend/app/cli.py              CLI para crear administrador inicial
backend/tests/                  Suite de tests (52 tests con unittest)
frontend/src/api/               Cliente HTTP con Bearer en memoria y reintento de refresh
frontend/src/features/auth/     AuthProvider, Login, Cambio de contraseña, RutaProtegida
frontend/src/features/admin/    Administración de usuarios (solo ADMIN)
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

La suite completa consta de 52 pruebas (25 de cálculo/catálogo + 27 de seguridad/autenticación/usuarios).

```bash
# A) Tests unitarios (sin requerir base de datos)
cd backend
./venv/bin/python -m unittest tests/test_calculo_y_catalogo.py tests/test_password.py -v

# B) Suite completa de 52 tests con PostgreSQL real:
# 1. Asegurar que la base de datos esté levantada
podman compose up -d db

# 2. Crear la base de datos de test si no existe
podman exec lis_db_1 psql -U lis_app -d postgres -c "CREATE DATABASE lis_test;"
podman exec -i lis_db_1 psql -U lis_app -d lis_test < db/init/001_schema.sql

# 3. Ejecutar los 52 tests pasando la URL de conexión
TEST_DATABASE_URL="postgresql+psycopg://lis_app:CAMBIAR_por_una_clave_larga_y_aleatoria@localhost:5432/lis_test" \
./venv/bin/python -m unittest discover -s tests -v
```

## Reglas de Desarrollo

Consultar [`AGENTS.md`](AGENTS.md) y [`docs/DECISIONES.md`](docs/DECISIONES.md).

