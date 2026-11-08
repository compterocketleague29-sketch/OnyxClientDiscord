import asyncio
import logging
import os
from datetime import timezone

import discord
import stripe
from discord import app_commands
from dotenv import load_dotenv
from discord_features import register_discord_features

load_dotenv()
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

from license_store import (
    PLANS,
    claim_license,
    create_admin_license,
    get_active_licenses,
    get_user_licenses,
    initialize_database,
    revoke_license,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('onyx.discord')
ADMIN_USER_IDS = {
    value.strip()
    for value in os.environ.get('DISCORD_ADMIN_USER_IDS', '').split(',')
    if value.strip()
}
ADMIN_ROLE_IDS = {
    value.strip()
    for value in os.environ.get('DISCORD_ADMIN_ROLE_IDS', '').split(',')
    if value.strip()
}
DOWNLOAD_URL = os.environ.get(
    'DOWNLOAD_URL',
    'https://github.com/compterocketleague29-sketch/onyx-client-releases/releases/download/v1.0/Onyx-Client.exe',
)


def is_admin(interaction):
    if str(interaction.user.id) in ADMIN_USER_IDS:
        return True
    member_roles = getattr(interaction.user, 'roles', ())
    return any(str(role.id) in ADMIN_ROLE_IDS for role in member_roles)


def license_summary(license_row):
    plan_details = PLANS.get(license_row['plan'])
    plan = plan_details['name'] if plan_details else license_row['plan']
    expires_at = license_row['expiresAt']
    if expires_at is None:
        expiry = (
            'à vie'
            if plan_details and plan_details['days'] is None
            else 'durée à partir de la première activation'
        )
    else:
        expiry = expires_at.replace(tzinfo=timezone.utc).strftime('%d/%m/%Y')
    return f'**{plan}** — `{license_row["key"]}` — expiration : {expiry}'


class OnyxDiscordBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await asyncio.to_thread(initialize_database)
        await register_discord_features(self)
        guild_id = os.environ.get('DISCORD_GUILD_ID')
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info('Commandes Discord synchronisées sur le serveur %s', guild_id)
        else:
            await self.tree.sync()
            logger.info('Commandes Discord globales synchronisées')


bot = OnyxDiscordBot()
plan_choices = [
    app_commands.Choice(name=plan['name'], value=plan_id)
    for plan_id, plan in PLANS.items()
]


@bot.tree.command(name='acheter', description='Acheter une licence Onyx Client')
@app_commands.choices(offre=plan_choices)
async def acheter(interaction: discord.Interaction, offre: app_commands.Choice[str]):
    secret_key = os.environ.get('STRIPE_SECRET_KEY')
    if not secret_key:
        await interaction.response.send_message(
            'Les paiements ne sont pas configurés. Contacte un administrateur.',
            ephemeral=True,
        )
        return

    plan = PLANS[offre.value]
    try:
        checkout = await asyncio.to_thread(
            stripe.checkout.Session.create,
            mode='payment',
            success_url='https://discord.com/channels/@me',
            cancel_url='https://discord.com/channels/@me',
            client_reference_id=str(interaction.user.id),
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f'Licence Onyx Client — {plan["name"]}',
                    },
                    'unit_amount': plan['price_cents'],
                },
                'quantity': 1,
            }],
            metadata={
                'purchase_source': 'discord',
                'discord_user_id': str(interaction.user.id),
                'plan': offre.value,
            },
        )
    except stripe.StripeError:
        logger.exception('Échec de création du paiement Stripe pour %s', interaction.user.id)
        await interaction.response.send_message(
            'Impossible de créer le paiement pour le moment. Réessaie plus tard.',
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f'Paiement sécurisé pour **{plan["name"]}** ({plan["price_cents"] / 100:.2f} €) :\n'
        f'{checkout.url}\n'
        'Après le paiement, récupère ta clé avec `/mes-licences`.',
        ephemeral=True,
    )


@bot.tree.command(name='mes-licences', description='Afficher tes licences actives')
async def mes_licences(interaction: discord.Interaction):
    licenses = await asyncio.to_thread(get_active_licenses, str(interaction.user.id))
    if not licenses:
        await interaction.response.send_message(
            'Aucune licence active liée à ce compte. Après un achat, réessaie dans quelques instants '
            'ou utilise `/lier-cle` pour associer une clé existante.',
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        '\n'.join(license_summary(row) for row in licenses),
        ephemeral=True,
    )


@bot.tree.command(name='lier-cle', description='Associer une clé existante à ton compte Discord')
async def lier_cle(interaction: discord.Interaction, cle: str):
    try:
        await asyncio.to_thread(claim_license, cle, str(interaction.user.id))
    except ValueError as error:
        await interaction.response.send_message(str(error), ephemeral=True)
        return
    await interaction.response.send_message(
        'Clé associée à ton compte. Tu peux maintenant utiliser `/mes-licences` ou `/telecharger`.',
        ephemeral=True,
    )


@bot.tree.command(name='telecharger', description='Obtenir le lien de téléchargement du client')
async def telecharger(interaction: discord.Interaction):
    licenses = await asyncio.to_thread(get_active_licenses, str(interaction.user.id))
    if not licenses:
        await interaction.response.send_message(
            'Aucune licence active n’est associée à ton compte Discord.',
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f'Téléchargement d’Onyx Client : {DOWNLOAD_URL}',
        ephemeral=True,
    )


@bot.tree.command(name='admin-creer-cle', description='Créer une licence pour un membre')
@app_commands.guild_only()
@app_commands.choices(offre=plan_choices)
async def admin_creer_cle(
    interaction: discord.Interaction,
    membre: discord.User,
    offre: app_commands.Choice[str],
):
    if not is_admin(interaction):
        await interaction.response.send_message('Commande réservée aux administrateurs.', ephemeral=True)
        return
    key = await asyncio.to_thread(create_admin_license, offre.value, str(membre.id))
    await interaction.response.send_message(
        f'Licence **{PLANS[offre.value]["name"]}** créée pour {membre.mention} : `{key}`',
        ephemeral=True,
    )


@bot.tree.command(name='admin-revoquer-cle', description='Révoquer une licence')
@app_commands.guild_only()
async def admin_revoquer_cle(interaction: discord.Interaction, cle: str):
    if not is_admin(interaction):
        await interaction.response.send_message('Commande réservée aux administrateurs.', ephemeral=True)
        return
    revoked = await asyncio.to_thread(revoke_license, cle)
    message = 'Licence révoquée.' if revoked else 'Aucune licence active ne correspond à cette clé.'
    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name='admin-licences', description='Voir les licences liées à un membre')
@app_commands.guild_only()
async def admin_licences(interaction: discord.Interaction, membre: discord.User):
    if not is_admin(interaction):
        await interaction.response.send_message('Commande réservée aux administrateurs.', ephemeral=True)
        return
    licenses = await asyncio.to_thread(get_user_licenses, str(membre.id))
    if not licenses:
        await interaction.response.send_message('Aucune licence trouvée.', ephemeral=True)
        return
    lines = [
        f'{license_summary(row)} — statut : {row["status"]}'
        for row in licenses
    ]
    await interaction.response.send_message('\n'.join(lines), ephemeral=True)


def main():
    token = os.environ.get('DISCORD_BOT_TOKEN')
    if not token:
        raise RuntimeError('La variable DISCORD_BOT_TOKEN est obligatoire.')
    bot.run(token)


if __name__ == '__main__':
    main()
