"""overrides_obs_visitante

Revision ID: 0003_overrides_obs_visitante
Revises: 0002_config_sesion
Create Date: 2026-10-26 00:00:00.000000

- Agrega columna 'observaciones' a laboratorio.ordenes (observaciones finales del informe).
- Agrega columna 'observaciones' a laboratorio.orden_estudios (observaciones específicas por estudio).
- Agrega columnas de override a laboratorio.resultados_borrador:
    ref_inferior_override (NUMERIC(20,6))
    ref_superior_override (NUMERIC(20,6))
    ref_texto_override (TEXT)
    ref_modificada (BOOLEAN DEFAULT FALSE)
- Inserta el rol 'VISITANTE' en laboratorio.roles (on conflict do nothing).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_overrides_obs_visitante"
down_revision: Union[str, None] = "0002_config_sesion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Agregar observaciones a ordenes si no existe
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'laboratorio' 
                  AND table_name = 'ordenes' 
                  AND column_name = 'observaciones'
            ) THEN
                ALTER TABLE laboratorio.ordenes ADD COLUMN observaciones TEXT;
            END IF;
        END $$;
    """)

    # 2. Agregar observaciones a orden_estudios si no existe
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'laboratorio' 
                  AND table_name = 'orden_estudios' 
                  AND column_name = 'observaciones'
            ) THEN
                ALTER TABLE laboratorio.orden_estudios ADD COLUMN observaciones TEXT;
            END IF;
        END $$;
    """)

    # 3. Agregar columnas de override en resultados_borrador si no existen
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'laboratorio' 
                  AND table_name = 'resultados_borrador' 
                  AND column_name = 'ref_inferior_override'
            ) THEN
                ALTER TABLE laboratorio.resultados_borrador ADD COLUMN ref_inferior_override NUMERIC(20,6);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'laboratorio' 
                  AND table_name = 'resultados_borrador' 
                  AND column_name = 'ref_superior_override'
            ) THEN
                ALTER TABLE laboratorio.resultados_borrador ADD COLUMN ref_superior_override NUMERIC(20,6);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'laboratorio' 
                  AND table_name = 'resultados_borrador' 
                  AND column_name = 'ref_texto_override'
            ) THEN
                ALTER TABLE laboratorio.resultados_borrador ADD COLUMN ref_texto_override TEXT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'laboratorio' 
                  AND table_name = 'resultados_borrador' 
                  AND column_name = 'ref_modificada'
            ) THEN
                ALTER TABLE laboratorio.resultados_borrador ADD COLUMN ref_modificada BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
        END $$;
    """)

    # 4. Asegurar existencia del rol VISITANTE en roles
    op.execute("""
        INSERT INTO laboratorio.roles (nombre, descripcion)
        VALUES ('VISITANTE', 'Auditor o lector de informes clínicos (solo lectura, sin descargas ni capturas)')
        ON CONFLICT (nombre) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE laboratorio.resultados_borrador 
            DROP COLUMN IF EXISTS ref_inferior_override,
            DROP COLUMN IF EXISTS ref_superior_override,
            DROP COLUMN IF EXISTS ref_texto_override,
            DROP COLUMN IF EXISTS ref_modificada;
    """)
    op.execute("ALTER TABLE laboratorio.orden_estudios DROP COLUMN IF EXISTS observaciones;")
    op.execute("ALTER TABLE laboratorio.ordenes DROP COLUMN IF EXISTS observaciones;")
    op.execute("DELETE FROM laboratorio.roles WHERE nombre = 'VISITANTE';")
