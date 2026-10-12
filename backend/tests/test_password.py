"""
Pruebas unitarias para contraseñas y política de seguridad (Fase 1).
Implementa estrictamente PROMPT_FASE_1.md §10 (Casos 1 al 4).
"""

import unittest

from app.core.security import (
    generate_temporary_password,
    get_password_hash,
    verify_password,
    check_password_policy,
    validate_password_policy,
    PasswordPolicyError,
)


class TestPasswordSecurity(unittest.TestCase):
    """Casos de prueba 1 al 4 de PROMPT_FASE_1.md §10."""

    def test_01_hash_y_verificacion_correctos(self):
        """1. Hash y verificación correctos; dos hashes de la misma clave difieren."""
        clave = "MiClaveSuperSegura123!"
        h1 = get_password_hash(clave)
        h2 = get_password_hash(clave)

        self.assertTrue(h1.startswith("$argon2id$"), f"El hash no es Argon2id: {h1}")
        self.assertNotEqual(h1, h2, "Dos hashes de la misma clave deben diferir debido al salt aleatorio.")
        self.assertTrue(verify_password(clave, h1))
        self.assertTrue(verify_password(clave, h2))
        self.assertFalse(verify_password("ClaveErronea123!", h1))

    def test_02_rechazo_politica_invalida(self):
        """2. Rechaza: < 10 caracteres, > 128, en lista prohibida, contiene usuario, contiene CI, igual a la actual."""
        usuario = "juan.perez"
        ci = "4567891-LP"
        actual = "ClaveActualValida1!"

        # < 10 caracteres
        valida, msg = check_password_policy("Corta1!", username=usuario, ci=ci)
        self.assertFalse(valida)
        self.assertIn("al menos 10 caracteres", msg)

        # > 128 caracteres
        valida, msg = check_password_policy("A" * 129, username=usuario, ci=ci)
        self.assertFalse(valida)
        self.assertIn("128 caracteres", msg)

        # En la lista prohibida (§6.4)
        for clave_prohibida in ["1234567890", "password", "contrasena", "admin123", "bioquimico"]:
            valida, msg = check_password_policy(clave_prohibida, username=usuario, ci=ci)
            self.assertFalse(valida, f"Debió rechazar clave prohibida '{clave_prohibida}'")

        # Contiene el usuario (case-insensitive o partes)
        valida, msg = check_password_policy("ClaveCon_juan.perez_99", username=usuario, ci=ci)
        self.assertFalse(valida)
        self.assertIn("nombre de usuario", msg)

        valida, msg = check_password_policy("ClaveCon_Juan_9999", username=usuario, ci=ci)
        self.assertFalse(valida)
        self.assertIn("nombre de usuario", msg)

        # Contiene el CI (directo o numérico)
        valida, msg = check_password_policy("ClaveCon_4567891_99", username=usuario, ci=ci)
        self.assertFalse(valida)
        self.assertIn("CI", msg)

        # Igual a la actual (en texto plano)
        valida, msg = check_password_policy(actual, username=usuario, ci=ci, current_password=actual)
        self.assertFalse(valida)
        self.assertIn("distinta de la contraseña actual", msg)

        # Igual a la actual (en hash)
        hash_actual = get_password_hash(actual)
        valida, msg = check_password_policy(actual, username=usuario, ci=ci, current_password_hash=hash_actual)
        self.assertFalse(valida)
        self.assertIn("distinta de la contraseña actual", msg)

    def test_03_acepta_clave_valida(self):
        """3. Acepta una clave larga y no prohibida."""
        clave_buena = "Bioquimica_Clinica_2026_Segura!"
        valida, msg = check_password_policy(
            clave_buena,
            username="maria.lopez",
            ci="9876543",
            current_password="OtraClaveTotalmenteDiferente1!",
        )
        self.assertTrue(valida)
        self.assertIsNone(msg)
        self.assertTrue(validate_password_policy(clave_buena, username="maria.lopez", ci="9876543"))

    def test_04_temporal_14_caracteres_sin_ambiguos(self):
        """4. La temporal tiene exactamente 14 caracteres y ninguno de '0 O 1 l I'."""
        caracteres_ambiguos = set("0O1lI")

        for _ in range(50):
            temp = generate_temporary_password(14)
            self.assertEqual(len(temp), 14, f"Longitud incorrecta: {len(temp)}")
            encontrados = set(temp).intersection(caracteres_ambiguos)
            self.assertEqual(
                len(encontrados),
                0,
                f"Contiene caracteres ambiguos prohibidos: {encontrados} en '{temp}'",
            )

    def test_05_dummy_argon2_hash_valido_y_lanza_mismatch(self):
        """(a) Verificar contra DUMMY_ARGON2_HASH con argon2.PasswordHasher().verify lanza VerifyMismatchError."""
        import argon2
        from argon2.exceptions import VerifyMismatchError
        from app.core.security import DUMMY_ARGON2_HASH

        self.assertTrue(DUMMY_ARGON2_HASH.startswith("$argon2id$"))
        hasher = argon2.PasswordHasher()
        with self.assertRaises(VerifyMismatchError):
            hasher.verify(DUMMY_ARGON2_HASH, "clave_cualquiera_erronea")

    def test_06_login_usuario_inexistente_invoca_verificacion_ficticia(self):
        """(b) Con usuario inexistente, el login sí invoca la verificación ficticia (contador sobre password_hash.verify)."""
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from app.core.security import password_hash
        from app.main import app

        with patch.object(password_hash, "verify", wraps=password_hash.verify) as mock_verify:
            client = TestClient(app)
            resp = client.post("/api/auth/login", json={"usuario": "no_existo_999", "password": "Password123!"})
            self.assertEqual(resp.status_code, 401)
            self.assertGreaterEqual(mock_verify.call_count, 1, "No se invocó la verificación ficticia")

    def test_07_cantidad_claves_prohibidas(self):
        """(c) len(CLAVES_PROHIBIDAS) == 21."""
        from app.core.security import CLAVES_PROHIBIDAS
        self.assertEqual(len(CLAVES_PROHIBIDAS), 21)

    def test_08_generate_temporary_password_lanza_excepcion_si_falla(self):
        """generate_temporary_password lanza excepción si ninguna candidata cumple la política."""
        from unittest.mock import patch
        with patch("app.core.security.check_password_policy", return_value=(False, "Invalida")):
            with self.assertRaises(PasswordPolicyError):
                generate_temporary_password(14)


if __name__ == "__main__":
    unittest.main()

