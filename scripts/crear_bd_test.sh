#!/bin/sh
# Recrea la base de datos de pruebas (lis_test) y aplica el esquema y catálogo completos.
# Compatible con Docker y Podman mediante la variable de entorno CONTAINER_CLI.
# Uso:
#   ./scripts/crear_bd_test.sh                  (usa docker por defecto)
#   CONTAINER_CLI=podman ./scripts/crear_bd_test.sh
set -eu

CONTAINER_CLI="${CONTAINER_CLI:-docker}"
PG_USER="${POSTGRES_USER:-lis_app}"
TEST_DB="${TEST_POSTGRES_DB:-lis_test}"

echo "[$CONTAINER_CLI] Recreando base de datos de prueba '$TEST_DB'..."

# Terminar conexiones activas y recrear la base de datos en blanco
$CONTAINER_CLI compose exec -T db psql -U "$PG_USER" -d postgres <<EOF
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TEST_DB' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS $TEST_DB;
CREATE DATABASE $TEST_DB;
EOF

echo "[$CONTAINER_CLI] Aplicando db/init/001_schema.sql en '$TEST_DB'..."
$CONTAINER_CLI compose exec -T db psql -U "$PG_USER" -d "$TEST_DB" < db/init/001_schema.sql > /dev/null

echo "[$CONTAINER_CLI] Aplicando db/init/002_seed_catalogo.sql en '$TEST_DB'..."
$CONTAINER_CLI compose exec -T db psql -U "$PG_USER" -d "$TEST_DB" < db/init/002_seed_catalogo.sql > /dev/null

echo "[$CONTAINER_CLI] Aplicando migraciones Alembic (upgrade head) en '$TEST_DB'..."
if [ -f .env ]; then
    PG_PASSWORD=$(grep '^POSTGRES_PASSWORD=' .env | cut -d '=' -f2- | tr -d '\r"')
fi
PG_PASSWORD="${PG_PASSWORD:-CAMBIAR_por_una_clave_larga_y_aleatoria}"

TEST_DB_URL="postgresql+psycopg://${PG_USER}:${PG_PASSWORD}@127.0.0.1:5432/${TEST_DB}"

if [ -f .venv/bin/alembic ]; then
    (cd backend && DATABASE_URL="$TEST_DB_URL" ../.venv/bin/alembic upgrade head)
elif [ -f backend/venv/bin/alembic ]; then
    (cd backend && DATABASE_URL="$TEST_DB_URL" ./venv/bin/alembic upgrade head)
elif command -v alembic >/dev/null 2>&1; then
    (cd backend && DATABASE_URL="$TEST_DB_URL" alembic upgrade head)
else
    $CONTAINER_CLI compose exec -T -e DATABASE_URL="postgresql+psycopg://${PG_USER}:${PG_PASSWORD}@db:5432/${TEST_DB}" backend alembic upgrade head
fi

echo "[$CONTAINER_CLI] OK: Base de datos '$TEST_DB' recreada exitosamente con esquema, catálogo y migraciones."
