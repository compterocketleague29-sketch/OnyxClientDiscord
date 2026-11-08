import unittest
from unittest.mock import Mock, patch

import requests

from admin_auth import validate_admin_credentials


class AdminAuthClientTests(unittest.TestCase):
    @patch('admin_auth.requests.post')
    def test_accepts_credentials_confirmed_by_api(self, mock_post):
        response = Mock()
        response.json.return_value = {'valid': True, 'message': 'Accès admin autorisé'}
        mock_post.return_value = response

        self.assertEqual(
            validate_admin_credentials('onyx-user', 'secret', 'https://api.example'),
            (True, 'Accès admin autorisé'),
        )
        mock_post.assert_called_once_with(
            'https://api.example/v1/admin/validate',
            json={'username': 'onyx-user', 'password': 'secret'},
            timeout=8,
        )

    @patch('admin_auth.requests.post')
    def test_reports_invalid_credentials(self, mock_post):
        response = Mock()
        response.json.return_value = {
            'valid': False,
            'message': 'Identifiants admin invalides.',
        }
        mock_post.return_value = response

        self.assertEqual(
            validate_admin_credentials('onyx-user', 'wrong', 'https://api.example'),
            (False, 'Identifiants admin invalides.'),
        )

    @patch('admin_auth.requests.post', side_effect=requests.Timeout)
    def test_reports_api_unavailable(self, _mock_post):
        self.assertEqual(
            validate_admin_credentials('onyx-user', 'secret', 'https://api.example'),
            (False, 'Serveur indisponible. Verifiez Internet.'),
        )


if __name__ == '__main__':
    unittest.main()
