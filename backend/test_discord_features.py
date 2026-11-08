import unittest
from types import SimpleNamespace

from discord_features import ticket_delete_deadline, ticket_is_closed, ticket_owner


class TicketMetadataTests(unittest.TestCase):
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
