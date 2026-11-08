import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord

from discord_bot import send_license_key_dm


class LicenseKeyDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_welcome_message_with_key_as_spoiler(self):
        member = SimpleNamespace(id=123, send=AsyncMock())

        delivered = await send_license_key_dm(member, 'À vie', 'ONYX-SECRET-KEY')

        self.assertTrue(delivered)
        member.send.assert_awaited_once()
        message = member.send.await_args.args[0]
        self.assertIn('Merci de faire confiance à Onyx Client', message)
        self.assertIn('||ONYX-SECRET-KEY||', message)
        self.assertIn('/mes-licences', message)

    async def test_reports_when_member_does_not_accept_private_messages(self):
        member = SimpleNamespace(id=123, send=AsyncMock(
            side_effect=discord.Forbidden(
                SimpleNamespace(status=403, reason='Forbidden'),
                'Cannot send messages to this user',
            )
        ))

        with self.assertLogs('onyx.discord', level='WARNING'):
            delivered = await send_license_key_dm(member, 'À vie', 'ONYX-SECRET-KEY')

        self.assertFalse(delivered)


if __name__ == '__main__':
    unittest.main()
