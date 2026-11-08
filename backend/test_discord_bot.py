import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from discord_bot import send_license_key_dm, telecharger


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


class DownloadCommandTests(unittest.IsolatedAsyncioTestCase):
    def make_interaction(self):
        return SimpleNamespace(
            user=SimpleNamespace(id=123),
            response=SimpleNamespace(defer=AsyncMock()),
            edit_original_response=AsyncMock(),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_acknowledges_interaction_before_database_lookup(self):
        interaction = self.make_interaction()
        events = []

        async def defer():
            events.append('deferred')

        async def get_licenses(*args):
            events.append('database')
            self.assertEqual(args, (get_active_licenses, '123'))
            return []

        from discord_bot import get_active_licenses

        interaction.response.defer.side_effect = defer
        with patch('discord_bot.asyncio.to_thread', side_effect=get_licenses):
            await telecharger.callback(interaction)

        self.assertEqual(events, ['deferred', 'database'])
        interaction.edit_original_response.assert_awaited_once_with(
            content='Aucune licence active n’est associée à ton compte Discord.'
        )

    async def test_returns_download_button_for_active_license(self):
        interaction = self.make_interaction()
        active_license = {'key': 'ONYX-TEST', 'plan': 'vie', 'expiresAt': None}

        with patch('discord_bot.asyncio.to_thread', return_value=[active_license]):
            await telecharger.callback(interaction)

        interaction.response.defer.assert_awaited_once_with()
        interaction.edit_original_response.assert_awaited_once()
        self.assertIn('Ta licence est active', interaction.edit_original_response.await_args.kwargs['content'])
        self.assertIsNotNone(interaction.edit_original_response.await_args.kwargs['view'])

    async def test_reports_database_failure_after_acknowledging(self):
        interaction = self.make_interaction()
        with (
            self.assertLogs('onyx.discord', level='ERROR'),
            patch(
                'discord_bot.asyncio.to_thread',
                side_effect=RuntimeError('database unavailable'),
            ),
        ):
            await telecharger.callback(interaction)

        interaction.response.defer.assert_awaited_once_with()
        interaction.followup.send.assert_awaited_once_with(
            'Impossible de vérifier ta licence pour le moment. Réessaie dans quelques instants.',
            ephemeral=True,
        )


if __name__ == '__main__':
    unittest.main()
