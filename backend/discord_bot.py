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
    get_all_licenses,
    get_user_licenses,
    initialize_database,
    delete_license,
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


def format_euros(amount_cents):
    euros, cents = divmod(amount_cents, 100)
    return f'{euros},{cents:02d} €'


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
    app_commands.Choice(
        name=(
            f'{plan["name"]} · {format_euros(plan["price_cents"])} · '
            f'{plan["max_devices"]} PC'
        ),
        value=plan_id,
    )
    for plan_id, plan in PLANS.items()
]
admin_plan_choices = [
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
        f'Paiement sécurisé pour **{plan["name"]}** ({format_euros(plan["price_cents"])}):\n'
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
        )
        return
    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label='Télécharger le launcher',
            style=discord.ButtonStyle.link,
            url=DOWNLOAD_URL,
            emoji='⬇️',
        )
    )
    await interaction.response.send_message(
        'Ta licence est active. Clique sur le bouton ci-dessous pour télécharger le launcher.',
        view=view,
    )


@bot.tree.command(name='admin-creer-cle', description='Créer une licence pour un membre')
@app_commands.guild_only()
@app_commands.choices(offre=admin_plan_choices)
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


@bot.tree.command(name='admin-lister-cles', description='Lister toutes les clés de licence')
@app_commands.guild_only()
async def admin_lister_cles(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message('Commande réservée aux administrateurs.', ephemeral=True)
        return
    licenses = await asyncio.to_thread(get_all_licenses)
    if not licenses:
        await interaction.response.send_message('Aucune clé de licence trouvée.')
        return

    class PublicLicenseListView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.page = 0
            self.page_size = 10
            self.update_buttons()

        def update_buttons(self):
            self.previous.disabled = self.page == 0
            self.next.disabled = (self.page + 1) * self.page_size >= len(licenses)

        def display_page(self):
            start = self.page * self.page_size
            rows = licenses[start:start + self.page_size]
            lines = []
            for row in rows:
                plan = PLANS.get(row['plan'], {}).get('name', row['plan'])
                expires = row['expiresAt']
                expiry = expires.replace(tzinfo=timezone.utc).strftime('%d/%m/%Y') if expires else '—'
                key_suffix = row['key'][-4:]
                lines.append(
                    f'`****{key_suffix}` · **{plan}** · {row["status"]} · '
                    f'{"Associée" if row["discordUserId"] else "Non associée"} · '
                    f'expiration : {expiry}'
                )
            embed = discord.Embed(
                title='Inventaire public des licences',
                description='\n'.join(lines),
                color=discord.Color.blurple(),
            )
            embed.set_footer(
                text=f'{start + 1}–{start + len(rows)} sur {len(licenses)} clés • clés masquées'
            )
            return embed

        @discord.ui.button(label='Précédent', style=discord.ButtonStyle.secondary)
        async def previous(self, component_interaction, button):
            self.page -= 1
            self.update_buttons()
            await component_interaction.response.edit_message(
                embed=self.display_page(),
                view=self,
            )

        @discord.ui.button(label='Suivant', style=discord.ButtonStyle.secondary)
        async def next(self, component_interaction, button):
            self.page += 1
            self.update_buttons()
            await component_interaction.response.edit_message(
                embed=self.display_page(),
                view=self,
            )

    class LicenseListView(discord.ui.View):
        def __init__(self, owner_id):
            super().__init__(timeout=300)
            self.owner_id = owner_id
            self.page = 0
            self.page_size = 10
            self.selected_key = None
            self.message = None
            self.update_buttons()

        def update_buttons(self):
            self.previous.disabled = self.page == 0
            self.next.disabled = (self.page + 1) * self.page_size >= len(licenses)
            self.revoke.disabled = self.selected_key is None
            self.delete.disabled = self.selected_key is None

        def display_page(self):
            self.clear_items()
            start = self.page * self.page_size
            self.add_item(LicenseSelect(licenses[start:start + self.page_size], self))
            self.add_item(self.previous)
            self.add_item(self.next)
            self.add_item(self.revoke)
            self.add_item(self.delete)
            self.update_buttons()
            return self.make_embed()

        def make_embed(self):
            start = self.page * self.page_size
            rows = licenses[start:start + self.page_size]
            lines = []
            for row in rows:
                plan = PLANS.get(row['plan'], {}).get('name', row['plan'])
                expires = row['expiresAt']
                expiry = expires.replace(tzinfo=timezone.utc).strftime('%d/%m/%Y') if expires else '—'
                owner = f"<@{row['discordUserId']}>" if row['discordUserId'] else 'Non associée'
                lines.append(
                    f'`{row["key"]}` · **{plan}** · {row["status"]} · '
                    f'{owner} · expiration : {expiry}'
                )
            embed = discord.Embed(
                title='Inventaire des licences',
                description='\n'.join(lines),
                color=discord.Color.blurple(),
            )
            embed.set_footer(
                text=f'{start + 1}–{start + len(rows)} sur {len(licenses)} clés • liste privée'
            )
            return embed

        async def interaction_check(self, component_interaction):
            if component_interaction.user.id != self.owner_id:
                await component_interaction.response.send_message(
                    'Cette liste privée appartient à un autre administrateur.',
                    ephemeral=True,
                )
                return False
            return True

        @discord.ui.button(label='Précédent', style=discord.ButtonStyle.secondary, row=1)
        async def previous(self, component_interaction, button):
            self.page -= 1
            self.selected_key = None
            await component_interaction.response.edit_message(
                embed=self.display_page(),
                view=self,
            )

        @discord.ui.button(label='Suivant', style=discord.ButtonStyle.secondary, row=1)
        async def next(self, component_interaction, button):
            self.page += 1
            self.selected_key = None
            await component_interaction.response.edit_message(
                embed=self.display_page(),
                view=self,
            )

        @discord.ui.button(
            label='Révoquer',
            style=discord.ButtonStyle.secondary,
            emoji='🚫',
            disabled=True,
            row=1,
        )
        async def revoke(self, component_interaction, button):
            await confirm_license_action(component_interaction, self, 'revoke')

        @discord.ui.button(
            label='Supprimer',
            style=discord.ButtonStyle.danger,
            emoji='🗑️',
            disabled=True,
            row=1,
        )
        async def delete(self, component_interaction, button):
            await confirm_license_action(component_interaction, self, 'delete')

    class LicenseSelect(discord.ui.Select):
        def __init__(self, rows, parent):
            self.list_view = parent
            super().__init__(
                placeholder='Choisir une clé à gérer…',
                min_values=1,
                max_values=1,
                row=0,
                options=[
                    discord.SelectOption(
                        label=row['key'],
                        value=row['key'],
                        description=(
                            f'{PLANS.get(row["plan"], {}).get("name", row["plan"])} · '
                            f'{row["status"]}'
                        )[:100],
                    )
                    for row in rows
                ],
            )

        async def callback(self, component_interaction):
            self.list_view.selected_key = self.values[0]
            self.list_view.update_buttons()
            self.list_view.message = component_interaction.message
            await component_interaction.response.edit_message(
                embed=self.list_view.make_embed(),
                view=self.list_view,
            )

    async def confirm_license_action(component_interaction, list_view, action):
        key = list_view.selected_key
        if not key:
            await component_interaction.response.send_message(
                'Sélectionne d’abord une clé.',
                ephemeral=True,
            )
            return

        action_label = 'révoquer' if action == 'revoke' else 'supprimer définitivement'
        confirmation = discord.ui.View(timeout=60)

        async def confirm(confirm_interaction):
            if confirm_interaction.user.id != list_view.owner_id:
                await confirm_interaction.response.send_message(
                    'Seul l’administrateur qui a ouvert cette liste peut confirmer.',
                    ephemeral=True,
                )
                return
            pending_message = (
                'Révocation en cours…'
                if action == 'revoke'
                else 'Suppression en cours…'
            )
            await confirm_interaction.response.edit_message(
                content=pending_message,
                view=None,
            )
            try:
                changed = await asyncio.to_thread(
                    revoke_license if action == 'revoke' else delete_license,
                    key,
                )
            except Exception:
                logger.exception('Échec de l’action %s sur une licence.', action)
                await confirm_interaction.edit_original_response(
                    content=(
                        'Une erreur est survenue pendant le traitement. '
                        'Vérifie la liste avant de réessayer.'
                    ),
                    view=None,
                )
                return
            for index, row in enumerate(licenses):
                if row['key'] == key:
                    if action == 'delete':
                        licenses.pop(index)
                        if list_view.page and list_view.page * list_view.page_size >= len(licenses):
                            list_view.page -= 1
                    else:
                        row['status'] = 'revoked'
                    break

            completed_action = (
                'a été révoquée' if action == 'revoke' else 'a été supprimée définitivement'
            )
            result = (
                f'La clé `{key}` {completed_action}.'
                if changed
                else 'Cette clé n’existe plus ou n’est plus active.'
            )
            await confirm_interaction.edit_original_response(content=result)
            list_view.selected_key = None
            if licenses:
                await list_view.message.edit(
                    embed=list_view.display_page(),
                    view=list_view,
                )
            else:
                await list_view.message.edit(
                    content='Aucune clé de licence trouvée.',
                    embed=None,
                    view=None,
                )

        async def cancel(cancel_interaction):
            await cancel_interaction.response.edit_message(
                content='Action annulée.',
                view=None,
            )

        confirm_button = discord.ui.Button(
            label=f'Confirmer : {action_label}',
            style=discord.ButtonStyle.danger,
        )
        confirm_button.callback = confirm
        cancel_button = discord.ui.Button(
            label='Annuler',
            style=discord.ButtonStyle.secondary,
        )
        cancel_button.callback = cancel
        confirmation.add_item(confirm_button)
        confirmation.add_item(cancel_button)
        list_view.message = component_interaction.message
        await component_interaction.response.send_message(
            f'Confirmer **{action_label}** pour la clé `{key}` ?',
            view=confirmation,
            ephemeral=True,
        )

    view = LicenseListView(interaction.user.id)
    public_view = PublicLicenseListView()
    await interaction.response.send_message(
        embed=public_view.display_page(),
        view=public_view,
    )
    view.message = await interaction.followup.send(
        embed=view.display_page(),
        view=view,
        ephemeral=True,
        wait=True,
    )


def main():
    token = os.environ.get('DISCORD_BOT_TOKEN')
    if not token:
        raise RuntimeError('La variable DISCORD_BOT_TOKEN est obligatoire.')
    bot.run(token)


if __name__ == '__main__':
    main()
