import unittest
from unittest.mock import MagicMock, patch

from license_store import (
    _admin_password_hash,
    create_client_admin_credentials,
    verify_client_admin_credentials,
)
from app import AdminLoginRequest, validate_admin


class ClientAdminCredentialTests(unittest.TestCase):
    def test_password_hash_is_salted_and_repeatable(self):
        first_salt = b'a' * 16
        second_salt = b'b' * 16

        self.assertEqual(
            _admin_password_hash('secret', first_salt),
            _admin_password_hash('secret', first_salt),
        )
        self.assertNotEqual(
            _admin_password_hash('secret', first_salt),
            _admin_password_hash('secret', second_salt),
        )
        self.assertNotEqual(
            _admin_password_hash('different', first_salt),
            _admin_password_hash('secret', first_salt),
        )

    def test_generated_credentials_store_only_password_hash(self):
        connection = MagicMock()
        context = MagicMock()
        context.__enter__.return_value = connection

        with patch('license_store.connect', return_value=context):
            username, password = create_client_admin_credentials('123456')

        self.assertTrue(username.startswith('onyx-'))
        self.assertGreaterEqual(len(password), 32)
        stored_values = connection.execute.call_args.args[1]
        self.assertEqual(stored_values[0], username)
        self.assertNotIn(password, stored_values)
        self.assertEqual(len(stored_values[1]), 16)
        self.assertEqual(len(stored_values[2]), 32)
        self.assertEqual(stored_values[3], '123456')

    def test_verifies_correct_password_and_rejects_wrong_or_unknown_credentials(self):
        salt = b's' * 16
        account = {
            'passwordSalt': salt,
            'passwordHash': _admin_password_hash('secret', salt),
        }
        connection = MagicMock()
        context = MagicMock()
        context.__enter__.return_value = connection

        with patch('license_store.connect', return_value=context):
            connection.execute.return_value.fetchone.return_value = account
            self.assertTrue(verify_client_admin_credentials('onyx-user', 'secret'))
            self.assertFalse(verify_client_admin_credentials('onyx-user', 'wrong'))
            connection.execute.return_value.fetchone.return_value = None
            self.assertFalse(verify_client_admin_credentials('unknown', 'secret'))

    def test_api_endpoint_returns_authentication_result(self):
        payload = AdminLoginRequest(username='onyx-user', password='secret')
        with patch('app.verify_client_admin_credentials', return_value=True) as verify:
            response = validate_admin(payload)

        verify.assert_called_once_with('onyx-user', 'secret')
        self.assertEqual(response, {'valid': True, 'message': 'Accès admin autorisé'})


if __name__ == '__main__':
    unittest.main()
