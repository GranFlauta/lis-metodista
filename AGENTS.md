# Reglas del proyecto (para Cursor / Claude Code / cualquier asistente)

Lee `docs/DECISIONES.md` antes de tocar lógica de negocio. Es un sistema clínico: ante la duda, no inventes valores.

## No negociables
1. **Nunca `eval`/`exec`** para fórmulas. Usar `app/calculation/engine.py`.
2. **Decimal, jamás float**, para resultados clínicos. Vacío = `None`/`NULL`, **nunca 0**.
3. Un resultado no calculable se muestra como "No calculable", no como número.
4. Fórmulas y rangos viven **solo** en `backend/app/catalog/definitions.py`. No duplicarlos en el frontend.
5. Lo que tiene folio es **inmutable**: no hay UPDATE/DELETE sobre `informes` (salvo `estado`), `folios`, `informe_eventos`.
6. **Los usuarios no se borran** (`activo = false`). **Los borradores sí** se borran físicamente.
7. Permisos y visibilidad se aplican **en el backend**; ocultar un botón no es seguridad.
8. Publicar, desplazar versión y bloquear por concurrencia ocurren en **una sola transacción**.
9. Contraseñas con Argon2id; nunca registrar contraseñas ni datos de pacientes en logs.
10. **Datos ficticios** en pruebas y capturas. No subir informes reales al repositorio.

## Convenciones
* Código en inglés o español **de forma consistente con lo que ya existe** (el dominio está en español: `orden`, `informe`, `folio`).
* Cambios de esquema: migración Alembic (desde Fase 1). `001_schema.sql` es la línea base.
* Cambios de catálogo: editar `definitions.py` → `python scripts/generar_seed_sql.py` → tests.
* Cada regla de negocio nueva lleva test. Los de cálculo salen de casos reales del Excel.

## Interfaz
Antes de tocar `frontend/`, lee [docs/UX_GUIDE.md](docs/UX_GUIDE.md) y cúmplela. Prohibido usar skills de diseño externos.

