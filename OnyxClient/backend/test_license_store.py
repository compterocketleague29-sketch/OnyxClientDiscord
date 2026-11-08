import re
import unittest

from license_store import generate_license_key, validate_discord_checkout


class LicenseStoreTests(unittest.TestCase):
    def setUp(self):
        self.session = {
            'id': 'cs_test_onyx',
            'payment_status': 'paid',
            'currency': 'eur',
            'amount_total': 999,
            'metadata': {
                'purchase_source': 'discord',
                'discord_user_id': '123456789',
                'plan': 'mois',
            },
        }

    def test_paid_discord_checkout_matches_plan(self):
        plan_id, discord_user_id, plan = validate_discord_checkout(self.session)

        self.assertEqual(plan_id, 'mois')
        self.assertEqual(discord_user_id, '123456789')
        self.assertEqual(plan['price_cents'], 999)

    def test_rejects_unpaid_checkout(self):
        self.session['payment_status'] = 'unpaid'

        with self.assertRaisesRegex(ValueError, 'pas confirmé'):
            validate_discord_checkout(self.session)

    def test_rejects_amount_mismatch(self):
        self.session['amount_total'] = 1

        with self.assertRaisesRegex(ValueError, 'montant'):
            validate_discord_checkout(self.session)

    def test_rejects_non_discord_checkout(self):
        self.session['metadata']['purchase_source'] = 'website'

        with self.assertRaisesRegex(ValueError, 'bot Discord'):
            validate_discord_checkout(self.session)

    def test_generated_key_has_expected_format(self):
        self.assertRegex(
            generate_license_key(),
            re.compile(r'^ONYX-[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{4}(?:-[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{4}){3}$'),
        )


if __name__ == '__main__':
    unittest.main()
