"""API de licences utilisée par le client Windows et le bot Discord."""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import stripe
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

load_dotenv()
from license_store import (
    PLANS,
    connect,
    fulfill_discord_checkout,
    initialize_database,
    validate_discord_checkout,
    verify_client_admin_credentials,
)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(value):
    return None if value is None else value.replace(tzinfo=timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(initialize_database)
    yield


app = FastAPI(title='Macro Client Licence API', docs_url=None, redoc_url=None, lifespan=lifespan)


class CheckRequest(BaseModel):
    key: str = Field(min_length=5, max_length=64)
    device_id: str = Field(min_length=16, max_length=128, pattern=r'^[^,]+$')


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/v1/admin/validate')
def validate_admin(payload: AdminLoginRequest):
    valid = verify_client_admin_credentials(payload.username, payload.password)
    return {
        'valid': valid,
        'message': 'Accès admin autorisé' if valid else 'Identifiants admin invalides.',
    }


@app.post('/v1/stripe/webhook')
async def stripe_webhook(request: Request):
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    signature = request.headers.get('stripe-signature')
    if not webhook_secret:
        raise HTTPException(status_code=503, detail='Webhook Stripe non configuré.')
    if not signature:
        raise HTTPException(status_code=400, detail='Signature Stripe manquante.')

    try:
        event = stripe.Webhook.construct_event(
            await request.body(),
            signature,
            webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError) as error:
        raise HTTPException(status_code=400, detail='Signature Stripe invalide.') from error

    if event.type in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
        session = event.data.object
        if (session.get('metadata') or {}).get('purchase_source') != 'discord':
            return {'received': True}
        if event.type == 'checkout.session.completed' and session.get('payment_status') != 'paid':
            return {'received': True}
        try:
            validate_discord_checkout(session)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        await asyncio.to_thread(fulfill_discord_checkout, session)

    return {'received': True}


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
