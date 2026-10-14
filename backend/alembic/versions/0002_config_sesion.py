"""config_sesion

Revision ID: 0002_config_sesion
Revises: 0001_baseline
Create Date: 2026-10-14 00:00:00.000000

D35-02 / D35-05 / T4:
- Amplía el CHECK de log_seguridad.accion añadiendo CONFIG_SESION_EDITADA.
- Inserta en laboratorio_config (con ON CONFLICT DO NOTHING):
    sesion_intervalo_latido_seg=30
    sesion_muerta_tras_seg=150
    sesion_inactividad_min=30
    sesion_tope_absoluto_horas=12
- downgrade() revierte ambos cambios.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_config_sesion"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ampliar el CHECK de log_seguridad.accion añadiendo CONFIG_SESION_EDITADA
    op.execute(
        sa.text(
            """
            ALTER TABLE laboratorio.log_seguridad
                DROP CONSTRAINT IF EXISTS log_seguridad_accion_check;
            ALTER TABLE laboratorio.log_seguridad
                ADD CONSTRAINT log_seguridad_accion_check
                CHECK (accion IN (
                    'LOGIN_OK', 'LOGIN_FALLIDO', 'LOGOUT', 'SESION_EXPIRADA', 'CAMBIO_PASSWORD',
                    'RESET_PASSWORD_ADMIN', 'USUARIO_CREADO', 'USUARIO_EDITADO', 'USUARIO_DESACTIVADO',
                    'ADMIN_VE_PRIVADO', 'CONFIG_SESION_EDITADA'
                ));
            """
        )
    )

    # 2. Insertar configuración por defecto de sesión en laboratorio_config
    op.execute(
        sa.text(
            """
            INSERT INTO laboratorio.laboratorio_config (clave, valor) VALUES
                ('sesion_intervalo_latido_seg', '30'),
                ('sesion_muerta_tras_seg', '150'),
                ('sesion_inactividad_min', '30'),
                ('sesion_tope_absoluto_horas', '12')
            ON CONFLICT (clave) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    # 1. Revertir claves de sesión en laboratorio_config
    op.execute(
        sa.text(
            """
            DELETE FROM laboratorio.laboratorio_config
            WHERE clave IN (
                'sesion_intervalo_latido_seg',
                'sesion_muerta_tras_seg',
                'sesion_inactividad_min',
                'sesion_tope_absoluto_horas'
            );
            """
        )
    )

    # 2. Revertir CHECK de log_seguridad.accion al conjunto original
    op.execute(
        sa.text(
            """
            DELETE FROM laboratorio.log_seguridad
            WHERE accion = 'CONFIG_SESION_EDITADA';

            ALTER TABLE laboratorio.log_seguridad
                DROP CONSTRAINT IF EXISTS log_seguridad_accion_check;
            ALTER TABLE laboratorio.log_seguridad
                ADD CONSTRAINT log_seguridad_accion_check
                CHECK (accion IN (
                    'LOGIN_OK', 'LOGIN_FALLIDO', 'LOGOUT', 'SESION_EXPIRADA', 'CAMBIO_PASSWORD',
                    'RESET_PASSWORD_ADMIN', 'USUARIO_CREADO', 'USUARIO_EDITADO', 'USUARIO_DESACTIVADO',
                    'ADMIN_VE_PRIVADO'
                ));
            """
        )
    )
