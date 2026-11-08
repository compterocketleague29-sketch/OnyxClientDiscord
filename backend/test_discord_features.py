import json
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from discord_features import (
    TICKET_CATEGORY_CHANNEL_IDS,
    TICKET_PING_ROLE_ID,
    TranslationServiceError,
    ticket_delete_deadline,
    ticket_is_closed,
    ticket_owner,
    translate_french_to_english,
)


class TranslationTests(unittest.TestCase):
    @patch('discord_features.urlopen')
    def test_falls_back_to_mymemory_when_libretranslate_rejects_request(self, mock_urlopen):
        mock_urlopen.side_effect = [
            HTTPError('https://translate.example', 403, 'Forbidden', {}, None),
            BytesIO(json.dumps({
                'responseStatus': 200,
                'responseData': {'translatedText': 'Hello &amp; welcome'},
            }).encode('utf-8')),
        ]

        self.assertEqual(translate_french_to_english('Bonjour et bienvenue'), 'Hello & welcome')
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch('discord_features.urlopen')
    def test_reports_both_translation_service_failures(self, mock_urlopen):
        mock_urlopen.side_effect = [
            HTTPError('https://translate.example', 403, 'Forbidden', {}, None),
            HTTPError('https://mymemory.example', 503, 'Unavailable', {}, None),
        ]

        with self.assertRaises(TranslationServiceError) as error:
            translate_french_to_english('Bonjour')

        self.assertIn('HTTP 403', str(error.exception))
        self.assertIn('HTTP 503', str(error.exception))


class TicketMetadataTests(unittest.TestCase):
    def test_ticket_categories_and_notification_role_are_configured(self):
        self.assertEqual(
            TICKET_CATEGORY_CHANNEL_IDS,
            {
                'aide': 1567658172590854274,
                'paiement': 1568841537738121367,
                'cle': 1567658174134095921,
                'launcher': 1567658174490607696,
                'autre': 1567658174490607697,
            },
        )
        self.assertEqual(TICKET_PING_ROLE_ID, 1567658169424027852)

    def test_reads_ticket_owner(self):
        channel = SimpleNamespace(topic='onyx-ticket|owner=123456789|status=open')
        self.assertEqual(ticket_owner(channel), 123456789)
        self.assertFalse(ticket_is_closed(channel))

    def test_recognizes_closed_ticket(self):
        channel = SimpleNamespace(topic='onyx-ticket|owner=123456789|status=closed')
        self.assertEqual(ticket_owner(channel), 123456789)
        self.assertTrue(ticket_is_closed(channel))

    def test_ignores_non_ticket_channels_and_invalid_owner(self):
        self.assertIsNone(ticket_owner(SimpleNamespace(topic='general')))
        self.assertIsNone(ticket_owner(SimpleNamespace(topic='onyx-ticket|owner=invalid|status=open')))
        self.assertFalse(ticket_is_closed(SimpleNamespace(topic=None)))

    def test_reads_automatic_deletion_deadline(self):
        channel = SimpleNamespace(
            topic='onyx-ticket|owner=123456789|status=closed|delete_at=1794103000'
        )
        self.assertEqual(ticket_delete_deadline(channel), 1794103000)
        self.assertIsNone(
            ticket_delete_deadline(SimpleNamespace(topic='onyx-ticket|owner=123456789|status=open'))
        )


if __name__ == '__main__':
    unittest.main()
