#!/bin/sh
# Respaldo diario de PostgreSQL con rotación. Corre dentro del contenedor `backup`.
# IMPORTANTE: copiar ./backups a un disco/NAS EXTERNO al servidor (un respaldo en el
# mismo equipo no protege contra falla de disco, robo o incendio).
set -eu
DESTINO=/backups
ARCHIVO="$DESTINO/lis_$(date +%Y%m%d_%H%M%S).dump"
mkdir -p "$DESTINO"
pg_dump --format=custom --file="$ARCHIVO"
echo "[backup] OK $ARCHIVO ($(du -h "$ARCHIVO" | cut -f1))"
find "$DESTINO" -name 'lis_*.dump' -mtime +"${BACKUP_RETENTION_DAYS:-30}" -delete
