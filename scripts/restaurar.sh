#!/bin/sh
# Uso: ./scripts/restaurar.sh backups/lis_YYYYMMDD_HHMMSS.dump
# Restaura en una BD vacía. PRUEBA la restauración periódicamente: un respaldo no probado no es un respaldo.
set -eu
[ $# -eq 1 ] || { echo "Uso: $0 archivo.dump"; exit 1; }
docker compose exec -T db pg_restore --clean --if-exists --no-owner -U "${POSTGRES_USER:-lis_app}" -d "${POSTGRES_DB:-lis}" < "$1"
