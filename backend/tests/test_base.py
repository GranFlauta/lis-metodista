"""
Pruebas unitarias de la infraestructura base de tests (Fase 3.5 T2 / Hallazgo A3 / D35-04).
Pruebas sin base de datos para la guarda de seguridad contra borrado accidental.
"""

from __future__ import annotations

import unittest

from tests.base import validar_database_url_test


class TestGuardaBaseDatos(unittest.TestCase):
    """
    T2: Guarda contra borrado accidental en los tests (hallazgo A3, D35-04).
    Verifica que la función pura validar_database_url_test:
    - Rechaza una URL terminada en /lis
    - Acepta una URL terminada en /lis_test
    - Falla con mensaje explicativo si TEST_DATABASE_URL no está definida
    """

    def test_guarda_database_url_rechaza_lis_y_acepta_lis_test(self) -> None:
        """T2. Una URL terminada en /lis es rechazada; una terminada en /lis_test es aceptada."""
        # 1. URL terminada en /lis es rechazada (protege base de datos de producción / desarrollo)
        url_produccion = "postgresql+psycopg://lis_app:clave_segura@127.0.0.1:5432/lis"
        with self.assertRaises(ValueError) as ctx_rechazo:
            validar_database_url_test(url_produccion)
        self.assertIn("_test", str(ctx_rechazo.exception))
        self.assertIn("lis", str(ctx_rechazo.exception))

        # 2. URL terminada en /lis_test es aceptada
        url_test = "postgresql+psycopg://lis_app:clave_segura@127.0.0.1:5432/lis_test"
        resultado = validar_database_url_test(url_test)
        self.assertEqual(resultado, url_test)

        # 3. URL no definida (None o vacía) falla indicando cómo definirla sin clave por defecto
        with self.assertRaises(ValueError) as ctx_none:
            validar_database_url_test(None)
        self.assertIn("TEST_DATABASE_URL no está definida", str(ctx_none.exception))

        with self.assertRaises(ValueError) as ctx_vacia:
            validar_database_url_test("   ")
        self.assertIn("TEST_DATABASE_URL no está definida", str(ctx_vacia.exception))
