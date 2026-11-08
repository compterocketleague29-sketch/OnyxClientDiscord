import re
import unittest

from license_store import generate_license_key, validate_discord_checkout


class LicenseStoreTests(unittest.TestCase):
    def setUp(self):
        self.session = {
            'id': 'cs_test_onyx',
            'payment_status': 'paid',
            'currency': 'eur',
            'amount_total': 1499,
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
        self.assertEqual(plan['price_cents'], 1499)

    def test_accepts_checkout_created_with_previous_monthly_price(self):
        self.session['amount_total'] = 999

        plan_id, _, plan = validate_discord_checkout(self.session)

        self.assertEqual(plan_id, 'mois')
        self.assertEqual(plan['price_cents'], 1499)

    def test_accepts_existing_weekly_and_lifetime_checkouts(self):
        for plan_id, old_price in (('semaine', 499), ('vie', 2999)):
            with self.subTest(plan=plan_id):
                self.session['metadata']['plan'] = plan_id
                self.session['amount_total'] = old_price

                validated_plan_id, _, _ = validate_discord_checkout(self.session)

                self.assertEqual(validated_plan_id, plan_id)

    def test_all_five_offers_have_expected_duration_and_price(self):
        from license_store import PLANS

        self.assertEqual(
            {
                plan_id: (plan['days'], plan['price_cents'])
                for plan_id, plan in PLANS.items()
            },
            {
                '3jours': (3, 499),
                'semaine': (7, 799),
                'mois': (30, 1499),
                '3mois': (90, 2999),
                'vie': (None, 5999),
            },
        )

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
