"""API de licences pour le client Windows.

Les cles sont creees par le site (achat Stripe ou page /admin) dans la table
`license_keys`. Cette API lit et met a jour cette meme table : une seule base.
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

load_dotenv()
DATABASE_URL = os.environ['DATABASE_URL']

# Doit rester identique a web/lib/products.ts (durationDays, maxDevices).
PLANS = {
    'semaine': {'days': 7, 'max_devices': 1},
    'mois': {'days': 30, 'max_devices': 1},
    'vie': {'days': None, 'max_devices': 2},
}


def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def utcnow():
    # Les colonnes du site sont des `timestamp` sans fuseau, stockees en UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(value):
    return None if value is None else value.replace(tzinfo=timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app):
    # Meme schema que web/lib/db/schema.ts ; ne fait rien si la table existe deja.
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
            "userId" TEXT
        )''')
    yield


app = FastAPI(title='Macro Client Licence API', docs_url=None, redoc_url=None, lifespan=lifespan)


class CheckRequest(BaseModel):
    key: str = Field(min_length=5, max_length=64)
    device_id: str = Field(min_length=16, max_length=128, pattern=r'^[^,]+$')


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/v1/validate')
def validate(payload: CheckRequest):
    key = payload.key.strip().upper()
    device_id = payload.device_id.strip()

    with connect() as con:
        # FOR UPDATE : deux activations simultanees ne peuvent pas depasser la limite de PC.
        row = con.execute(
            '''SELECT "id", "plan", "status", "hwid", "activatedAt", "expiresAt"
               FROM license_keys WHERE "key"=%s FOR UPDATE''',
            (key,)
        ).fetchone()

        if not row:
            return {'valid': False, 'message': 'Cle inconnue'}
        if row['status'] != 'active':
            return {'valid': False, 'message': 'Licence revoquee'}
        plan = PLANS.get(row['plan'])
        if plan is None:
            return {'valid': False, 'message': 'Offre inconnue'}

        now = utcnow()
        expires_at = row['expiresAt']
        if expires_at is not None and expires_at <= now:
            return {'valid': False, 'message': 'Licence expiree'}

        devices = row['hwid'].split(',') if row['hwid'] else []
        if device_id not in devices:
            if len(devices) >= plan['max_devices']:
                return {'valid': False, 'message': 'Licence deja utilisee sur le nombre maximum de PC'}
            devices.append(device_id)

        activated_at = row['activatedAt']
        if activated_at is None:
            # La duree commence a la premiere activation, comme affiche sur le site.
            activated_at = now
            if plan['days'] is not None:
                expires_at = now + timedelta(days=plan['days'])

        con.execute(
            '''UPDATE license_keys SET "hwid"=%s, "activatedAt"=%s, "expiresAt"=%s WHERE "id"=%s''',
            (','.join(devices), activated_at, expires_at, row['id'])
        )

    return {
        'valid': True,
        'message': 'Licence active',
        'plan': row['plan'],
        'expires_at': iso_utc(expires_at),
    }
