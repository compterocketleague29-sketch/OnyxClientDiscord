import requests


def validate_admin_credentials(username, password, api_url):
    if not api_url:
        return False, 'Serveur de licence non configuré. Contactez un administrateur.'
    try:
        response = requests.post(
            api_url + '/v1/admin/validate',
            json={'username': username, 'password': password},
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError, TypeError):
        return False, 'Serveur indisponible. Verifiez Internet.'

    if not isinstance(data, dict):
        return False, 'Réponse invalide du serveur.'
    if data.get('valid') is True:
        return True, 'Accès admin autorisé'
    message = data.get('message')
    return False, message if isinstance(message, str) else 'Identifiants admin invalides.'
