# LIS — Sistema de Información de Laboratorio Clínico

Servidor local (on-premise): **PostgreSQL 16 + FastAPI + React/Vite + Caddy (HTTPS)** con Docker Compose.
Las reglas de negocio y todas las decisiones están en **[docs/DECISIONES.md](docs/DECISIONES.md)** (léelo primero).

## Estado: Fase 0

Listo: esquema de BD, catálogo de 9 estudios + 2 perfiles, motor de cálculo seguro con tests, infraestructura Docker.
Pendiente: API, autenticación, pantallas, PDF (ver hoja de ruta en DECISIONES.md §9).

## Estructura

```
db/init/001_schema.sql          Esquema (tablas, índices, triggers de inmutabilidad, folios)
db/init/002_seed_catalogo.sql   GENERADO desde definitions.py — no editar a mano
backend/app/calculation/        Motor de fórmulas (sin eval, Decimal, "No calculable")
backend/app/catalog/            definitions.py = fuente única del catálogo
backend/tests/                  Tests (unittest)
frontend/src/features/          Una carpeta por sección del sistema
scripts/                        generar_seed_sql.py, backup.sh, restaurar.sh
docker-compose.yml  .env.example
```

## Primeros pasos

```bash
# 1) Tests del motor y del catálogo (solo necesita Python 3.12, sin instalar nada)
cd backend && python -m unittest discover -s tests -v && cd ..

# 2) Si cambias el catálogo, regenera el seed
python scripts/generar_seed_sql.py

# 3) Levantar todo
cp .env.example .env        # editar contraseñas y JWT_SECRET
docker compose up -d --build
curl -k https://localhost/api/health
```

> Los scripts de `db/init` solo corren cuando el volumen de PostgreSQL está vacío.
> Para recrear la BD en desarrollo: `docker compose down -v && docker compose up -d --build`.

## Reglas para quien programe (persona o IA)

Ver `AGENTS.md`.
