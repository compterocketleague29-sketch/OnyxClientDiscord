import os
import secrets
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.environ.get('DATABASE_URL')
ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
PLANS = {
    'semaine': {'days': 7, 'max_devices': 1, 'price_cents': 499, 'name': '1 semaine'},
    'mois': {'days': 30, 'max_devices': 1, 'price_cents': 999, 'name': '1 mois'},
    'vie': {'days': None, 'max_devices': 2, 'price_cents': 2999, 'name': 'À vie'},
}


def connect():
    if not DATABASE_URL:
        raise RuntimeError('La variable DATABASE_URL est obligatoire.')
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def initialize_database():
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS license_keys (
            "id" SERIAL PRIMARY KEY,
            "key" TEXT NOT NULL UNIQUE,
            "plan" TEXT NOT NULL,
            "status" TEXT NOT NULL DEFAULT 'active',
            "email" TEXT,
            "stripeSessionId" TEXT,
            "source" TEXT NOT NULL DEFAULT 'stripe',
            "amountCents" INTEGER,
            "hwid" TEXT,
            "activatedAt" TIMESTAMP,
            "expiresAt" TIMESTAMP,
            "note" TEXT,
            "createdAt" TIMESTAMP NOT NULL DEFAULT NOW(),
            "userId" TEXT,
            "discordUserId" TEXT
        )''')
        con.execute(
            'ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS "discordUserId" TEXT'
        )
        con.execute(
            'CREATE INDEX IF NOT EXISTS license_keys_discord_user_idx '
            'ON license_keys ("discordUserId")'
        )


def generate_license_key():
    groups = [
        ''.join(secrets.choice(ALPHABET) for _ in range(4))
        for _ in range(4)
    ]
    return f'ONYX-{"-".join(groups)}'


def validate_discord_checkout(session):
    metadata = session.get('metadata') or {}
    plan_id = metadata.get('plan')
    plan = PLANS.get(plan_id)
    if metadata.get('purchase_source') != 'discord':
        raise ValueError('Cette session Stripe ne provient pas du bot Discord.')
    if not metadata.get('discord_user_id'):
        raise ValueError('La session Stripe ne contient aucun utilisateur Discord.')
    if plan is None:
        raise ValueError('Offre inconnue.')
    if session.get('payment_status') != 'paid':
        raise ValueError('Le paiement Stripe n’est pas confirmé.')
    if session.get('currency') != 'eur' or session.get('amount_total') != plan['price_cents']:
        raise ValueError('Le montant du paiement ne correspond pas à l’offre.')
    if not session.get('id'):
        raise ValueError('La session Stripe ne contient aucun identifiant.')
    return plan_id, metadata['discord_user_id'], plan


def fulfill_discord_checkout(session):
    plan_id, discord_user_id, plan = validate_discord_checkout(session)
    session_id = session['id']
    customer_details = session.get('customer_details') or {}

    with connect() as con:
        with con.transaction():
            con.execute(
                'SELECT pg_advisory_xact_lock(hashtext(%s))',
                (session_id,),
            )
            existing = con.execute(
                '''SELECT "key", "discordUserId" FROM license_keys
                   WHERE "stripeSessionId"=%s AND "source"='discord' ''',
                (session_id,),
            ).fetchone()
            if existing:
                if existing['discordUserId'] != discord_user_id:
                    raise RuntimeError('La session Stripe est déjà liée à un autre compte Discord.')
                return existing['key']

            for _ in range(5):
                key = generate_license_key()
                row = con.execute(
                    '''INSERT INTO license_keys
                       ("key", "plan", "email", "stripeSessionId", "source",
                        "amountCents", "discordUserId", "note")
                       VALUES (%s, %s, %s, %s, 'discord', %s, %s, 'Achat Discord')
                       ON CONFLICT ("key") DO NOTHING
                       RETURNING "key"''',
                    (
                        key,
                        plan_id,
                        customer_details.get('email'),
                        session_id,
                        plan['price_cents'],
                        discord_user_id,
                    ),
                ).fetchone()
                if row:
                    return row['key']
    raise RuntimeError('Impossible de générer une clé de licence unique.')


def claim_license(key, discord_user_id):
    normalized_key = key.strip().upper()
    with connect() as con:
        with con.transaction():
            row = con.execute(
                '''SELECT "status", "expiresAt", "discordUserId"
                   FROM license_keys WHERE "key"=%s FOR UPDATE''',
                (normalized_key,),
            ).fetchone()
            if not row:
                raise ValueError('Clé inconnue.')
            if row['status'] != 'active':
                raise ValueError('Cette licence n’est pas active.')
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if row['expiresAt'] is not None and row['expiresAt'] <= now:
                raise ValueError('Cette licence a expiré.')
            owner_id = row['discordUserId']
            if owner_id and owner_id != discord_user_id:
                raise ValueError('Cette licence est déjà associée à un autre compte Discord.')
            con.execute(
                'UPDATE license_keys SET "discordUserId"=%s WHERE "key"=%s',
                (discord_user_id, normalized_key),
            )


def get_active_licenses(discord_user_id):
    with connect() as con:
        return con.execute(
            '''SELECT "key", "plan", "expiresAt" FROM license_keys
               WHERE "discordUserId"=%s AND "status"='active'
                 AND ("expiresAt" IS NULL OR "expiresAt" > NOW())
               ORDER BY "createdAt" DESC''',
            (discord_user_id,),
        ).fetchall()


def create_admin_license(plan_id, discord_user_id):
    if plan_id not in PLANS:
        raise ValueError('Offre inconnue.')
    with connect() as con:
        for _ in range(5):
            key = generate_license_key()
            row = con.execute(
                '''INSERT INTO license_keys
                   ("key", "plan", "source", "discordUserId", "note")
                   VALUES (%s, %s, 'admin', %s, 'Créée depuis Discord')
                   ON CONFLICT ("key") DO NOTHING
                   RETURNING "key"''',
                (key, plan_id, discord_user_id),
            ).fetchone()
            if row:
                return row['key']
    raise RuntimeError('Impossible de générer une clé de licence unique.')


def revoke_license(key):
    with connect() as con:
        result = con.execute(
            '''UPDATE license_keys SET "status"='revoked'
               WHERE "key"=%s AND "status"='active' ''',
            (key.strip().upper(),),
        )
        return result.rowcount > 0


def get_user_licenses(discord_user_id):
    with connect() as con:
        return con.execute(
            '''SELECT "key", "plan", "status", "expiresAt"
               FROM license_keys WHERE "discordUserId"=%s
               ORDER BY "createdAt" DESC LIMIT 20''',
            (discord_user_id,),
        ).fetchall()
