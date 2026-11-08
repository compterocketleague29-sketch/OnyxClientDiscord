import asyncio
import html
import io
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import discord
from discord import app_commands
from discord.ext import tasks

from discord_store import (
    create_giveaway,
    enter_giveaway,
    finish_giveaway,
    get_active_giveaways,
    get_pending_giveaway_announcements,
    initialize_discord_storage,
    mark_giveaway_announced,
)


logger = logging.getLogger('onyx.discord.features')
TICKET_TOPIC_PREFIX = 'onyx-ticket|'
TICKET_PING_ROLE_ID = 1567658169424027852
TICKET_CATEGORY_CHANNEL_IDS = {
    'aide': 1567658172590854274,
    'paiement': 1568841537738121367,
    'cle': 1567658174134095921,
    'launcher': 1567658174490607696,
    'autre': 1567658174490607697,
}
ticket_creation_locks = {}


class TranslationServiceError(RuntimeError):
    pass


def translate_french_to_english(text):
    endpoint = os.environ.get(
        'LIBRETRANSLATE_URL',
        'https://libretranslate.com/translate',
    )
    payload = {
        'q': text,
        'source': 'fr',
        'target': 'en',
        'format': 'text',
    }
    api_key = os.environ.get('LIBRETRANSLATE_API_KEY')
    if api_key:
        payload['api_key'] = api_key
    request = Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        raise TranslationServiceError(
            f'Le service de traduction a répondu HTTP {error.code}.'
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise TranslationServiceError('Le service de traduction est inaccessible.') from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TranslationServiceError('La réponse du service de traduction est invalide.') from error

    translated = result.get('translatedText') if isinstance(result, dict) else None
    if not isinstance(translated, str) or not translated.strip():
        raise TranslationServiceError('Aucune traduction n’a été renvoyée.')
    return translated.strip()


def configured_ids(variable_name):
    return {
        int(value.strip())
        for value in os.environ.get(variable_name, '').split(',')
        if value.strip()
    }


def configured_user_ids():
    return {
        int(value.strip())
        for value in os.environ.get('DISCORD_ADMIN_USER_IDS', '').split(',')
        if value.strip()
    }


def is_staff(interaction):
    permissions = getattr(interaction.user, 'guild_permissions', None)
    if permissions and (permissions.administrator or permissions.manage_guild):
        return True
    if interaction.user.id in configured_user_ids():
        return True
    member_roles = getattr(interaction.user, 'roles', ())
    staff_role_ids = configured_ids('DISCORD_ADMIN_ROLE_IDS')
    staff_role_ids.add(TICKET_PING_ROLE_ID)
    return any(role.id in staff_role_ids for role in member_roles)


def ticket_owner(channel):
    topic = channel.topic or ''
    if not topic.startswith(TICKET_TOPIC_PREFIX):
        return None
    fields = dict(
        field.split('=', 1)
        for field in topic[len(TICKET_TOPIC_PREFIX):].split('|')
        if '=' in field
    )
    return int(fields['owner']) if fields.get('owner', '').isdigit() else None


def ticket_is_closed(channel):
    topic = channel.topic or ''
    return topic.startswith(TICKET_TOPIC_PREFIX) and 'status=closed' in topic


def ticket_delete_deadline(channel):
    topic = channel.topic or ''
    if not topic.startswith(TICKET_TOPIC_PREFIX):
        return None
    fields = dict(
        field.split('=', 1)
        for field in topic[len(TICKET_TOPIC_PREFIX):].split('|')
        if '=' in field
    )
    try:
        return int(fields['delete_at'])
    except (KeyError, ValueError):
        return None


async def ticket_overwrites(guild, member):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        ),
    }
    if guild.me:
        overwrites[guild.me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            attach_files=True,
            embed_links=True,
        )
    staff_role_ids = configured_ids('DISCORD_ADMIN_ROLE_IDS')
    staff_role_ids.add(TICKET_PING_ROLE_ID)
    for role in guild.roles:
        if role.id in staff_role_ids or role.permissions.administrator or role.permissions.manage_guild:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
            )
    for user_id in configured_user_ids():
        try:
            staff_member = guild.get_member(user_id) or await guild.fetch_member(user_id)
        except discord.NotFound:
            logger.warning('L’administrateur Discord %s n’est pas membre du serveur.', user_id)
            continue
        overwrites[staff_member] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
        )
    return overwrites


async def make_transcript(channel):
    messages = [message async for message in channel.history(limit=1000, oldest_first=True)]
    rows = []
    for message in messages:
        timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
        author = html.escape(f'{message.author} ({message.author.id})')
        content = html.escape(message.clean_content).replace('\n', '<br>')
        attachments = ''.join(
            f'<br><a href="{html.escape(item.url, quote=True)}">'
            f'{html.escape(item.filename)}</a>'
            for item in message.attachments
        )
        rows.append(
            f'<article><small>{html.escape(timestamp)}</small> '
            f'<strong>{author}</strong><p>{content}{attachments}</p></article>'
        )
    document = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<title>Transcript - {html.escape(channel.name)}</title>'
        '<style>body{font:14px system-ui;max-width:900px;margin:2rem auto;padding:0 1rem}'
        'article{border-bottom:1px solid #ddd;padding:.7rem 0}small{color:#777}'
        'p{overflow-wrap:anywhere}</style></head><body>'
        f'<h1>Transcript: {html.escape(channel.name)}</h1>'
        f'<p>{len(messages)} messages</p>{"".join(rows)}</body></html>'
    )
    return discord.File(
        io.BytesIO(document.encode('utf-8')),
        filename=f'{channel.name}-transcript.html',
    )


async def send_transcript_to_logs(guild, channel):
    logs_id = os.environ.get('TICKET_LOG_CHANNEL_ID')
    if not logs_id:
        return False
    logs_channel = guild.get_channel(int(logs_id))
    if not isinstance(logs_channel, discord.TextChannel):
        logger.error('TICKET_LOG_CHANNEL_ID=%s ne désigne pas un salon textuel accessible.', logs_id)
        return False
    owner_id = ticket_owner(channel)
    await logs_channel.send(
        f'Transcript du ticket **{channel.name}** (membre <@{owner_id}>).',
        file=await make_transcript(channel),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    return True


async def register_discord_features(bot):
    async def report_app_command_error(interaction, error):
        original = getattr(error, 'original', error)
        if isinstance(original, app_commands.MissingPermissions):
            message = 'Tu n’as pas les permissions Discord nécessaires pour cette commande.'
        elif isinstance(original, app_commands.CheckFailure):
            message = 'Cette commande est réservée au serveur ou au staff.'
        else:
            logger.exception(
                'Erreur de commande slash %s',
                interaction.command.name if interaction.command else 'inconnue',
                exc_info=(type(original), original, original.__traceback__),
            )
            message = 'Une erreur est survenue. Réessaie plus tard ou contacte un administrateur.'
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    bot.tree.error(report_app_command_error)

    class TicketPanelView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(TicketCategorySelect())

        async def open_ticket(self, interaction, category_key):
            if not interaction.guild or not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    'Les tickets sont disponibles uniquement sur le serveur.',
                    ephemeral=True,
                )
                return

            category_label, category_description = TICKET_CATEGORIES[category_key]
            category_id = TICKET_CATEGORY_CHANNEL_IDS[category_key]
            category = interaction.guild.get_channel(category_id)
            if not isinstance(category, discord.CategoryChannel):
                await interaction.response.send_message(
                    f'La catégorie Discord « {category_label} » est introuvable. '
                    'Contacte un administrateur.',
                    ephemeral=True,
                )
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            lock_key = (interaction.guild.id, interaction.user.id)
            async with ticket_creation_locks.setdefault(lock_key, asyncio.Lock()):
                existing = next(
                    (
                        channel for channel in interaction.guild.text_channels
                        if ticket_owner(channel) == interaction.user.id
                        and not ticket_is_closed(channel)
                    ),
                    None,
                )
                if existing:
                    await interaction.followup.send(
                        f'Tu as déjà un ticket ouvert : {existing.mention}',
                        ephemeral=True,
                    )
                    return

                safe_name = re.sub(r'[^a-z0-9-]+', '-', interaction.user.name.lower()).strip('-')
                try:
                    channel = await interaction.guild.create_text_channel(
                        name=f'ticket-{category_key}-{safe_name[:70] or interaction.user.id}',
                        category=category,
                        overwrites=await ticket_overwrites(interaction.guild, interaction.user),
                        topic=(
                            f'{TICKET_TOPIC_PREFIX}owner={interaction.user.id}|'
                            f'status=open|category={category_key}'
                        ),
                        reason=f'Ticket ouvert par {interaction.user} ({interaction.user.id})',
                    )
                    embed = discord.Embed(
                        title=f'Ticket : {category_label}',
                        description=(
                            f'{interaction.user.mention}, {category_description}\n\n'
                            'Un membre du staff te répondra dès que possible.'
                        ),
                        color=discord.Color.blurple(),
                    )
                    embed.set_footer(text='Onyx Client • Support privé')
                    staff_role = interaction.guild.get_role(TICKET_PING_ROLE_ID)
                    if staff_role is None:
                        logger.error(
                            'Le rôle de notification des tickets %s est introuvable sur le serveur %s.',
                            TICKET_PING_ROLE_ID,
                            interaction.guild.id,
                        )
                    mentions = [interaction.user]
                    role_mentions = [staff_role] if staff_role else []
                    content = interaction.user.mention
                    if staff_role:
                        content = f'{content} {staff_role.mention}'
                    await channel.send(
                        content=content,
                        embed=embed,
                        view=TicketControlView(),
                        allowed_mentions=discord.AllowedMentions(
                            users=mentions,
                            roles=role_mentions,
                        ),
                    )
                except discord.HTTPException:
                    logger.exception('Impossible de créer un ticket pour %s', interaction.user.id)
                    await interaction.followup.send(
                        'Impossible de créer le ticket. Vérifie que le bot peut gérer les salons.',
                        ephemeral=True,
                    )
                    return
                await interaction.followup.send(
                    f'Ton ticket est prêt : {channel.mention}',
                    ephemeral=True,
                )

    TICKET_CATEGORIES = {
        'aide': ('Aide', 'Explique comment nous pouvons t’aider.'),
        'paiement': ('Problème de paiement', 'Décris le problème rencontré lors de ton paiement.'),
        'cle': ('Problème de clé', 'Indique le problème avec ta clé de licence. Ne publie pas ta clé dans un salon public.'),
        'launcher': ('Problème avec le launcher', 'Décris le problème rencontré avec le launcher.'),
        'autre': ('Autre demande', 'Décris ta demande.'),
    }

    class TicketCategorySelect(discord.ui.Select):
        def __init__(self):
            super().__init__(
                placeholder='Choisis le motif de ton ticket…',
                min_values=1,
                max_values=1,
                custom_id='onyx:ticket:category',
                options=[
                    discord.SelectOption(
                        label=label,
                        value=key,
                        description=description,
                        emoji={
                            'aide': '❓',
                            'paiement': '💳',
                            'cle': '🔑',
                            'launcher': '🖥️',
                            'autre': '📝',
                        }[key],
                    )
                    for key, (label, description) in TICKET_CATEGORIES.items()
                ],
            )

        async def callback(self, interaction):
            await self.view.open_ticket(interaction, self.values[0])

    class TicketControlView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(TicketMemberSelect())

        @discord.ui.button(
            label='Prendre en charge',
            style=discord.ButtonStyle.primary,
            emoji='🙋',
            custom_id='onyx:ticket:claim',
        )
        async def claim_ticket_button(self, interaction, button):
            if not is_staff(interaction):
                await interaction.response.send_message(
                    'Seul le staff peut prendre ce ticket en charge.',
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                f'🙋 Ticket pris en charge par {interaction.user.mention}.'
            )

        @discord.ui.button(
            label='Transcript',
            style=discord.ButtonStyle.secondary,
            emoji='📄',
            custom_id='onyx:ticket:transcript',
        )
        async def transcript_ticket_button(self, interaction, button):
            await send_ticket_transcript(interaction)

        @discord.ui.button(
            label='Fermer et supprimer',
            style=discord.ButtonStyle.danger,
            emoji='🔒',
            custom_id='onyx:ticket:close',
        )
        async def close_ticket_button(self, interaction, button):
            await close_ticket(interaction)

    class TicketMemberSelect(discord.ui.UserSelect):
        def __init__(self):
            super().__init__(
                placeholder='Ajouter un membre au ticket…',
                min_values=1,
                max_values=1,
                custom_id='onyx:ticket:add_member',
            )

        async def callback(self, interaction):
            channel = interaction.channel
            owner_id = ticket_owner(channel) if isinstance(channel, discord.TextChannel) else None
            if owner_id is None or ticket_is_closed(channel):
                await interaction.response.send_message(
                    'Cette action est uniquement disponible dans un ticket ouvert.',
                    ephemeral=True,
                )
                return
            if interaction.user.id != owner_id and not is_staff(interaction):
                await interaction.response.send_message(
                    'Seul le propriétaire du ticket ou le staff peut ajouter un membre.',
                    ephemeral=True,
                )
                return
            member = self.values[0]
            if not isinstance(member, discord.Member) or member.bot:
                await interaction.response.send_message(
                    'Sélectionne un membre humain de ce serveur.',
                    ephemeral=True,
                )
                return
            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            )
            await interaction.response.send_message(
                f'{member.mention} a été ajouté au ticket.',
                allowed_mentions=discord.AllowedMentions(users=[member]),
            )

    class GiveawayView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(
            label='Participer',
            style=discord.ButtonStyle.success,
            emoji='🎉',
            custom_id='onyx:giveaway:enter',
        )
        async def enter_giveaway_button(self, interaction, button):
            result = await asyncio.to_thread(
                enter_giveaway,
                interaction.message.id,
                interaction.user.id,
            )
            messages = {
                'joined': 'Ta participation est enregistrée. Bonne chance !',
                'duplicate': 'Tu participes déjà à ce giveaway.',
                'ended': 'Ce giveaway est terminé.',
                'missing': 'Ce giveaway n’est plus disponible.',
            }
            await interaction.response.send_message(messages[result], ephemeral=True)

    async def close_ticket(interaction):
        channel = interaction.channel
        owner_id = ticket_owner(channel) if isinstance(channel, discord.TextChannel) else None
        if owner_id is None:
            await interaction.response.send_message('Cette commande doit être utilisée dans un ticket.', ephemeral=True)
            return
        if interaction.user.id != owner_id and not is_staff(interaction):
            await interaction.response.send_message(
                'Seul le propriétaire du ticket ou le staff peut le fermer.',
                ephemeral=True,
            )
            return
        if ticket_is_closed(channel):
            await interaction.response.send_message('Ce ticket est déjà fermé.', ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        try:
            logged = await send_transcript_to_logs(interaction.guild, channel)
            if not logged:
                owner_member = interaction.guild.get_member(owner_id)
                if owner_member is None:
                    try:
                        owner_member = await interaction.guild.fetch_member(owner_id)
                    except discord.NotFound:
                        owner_member = None
                if owner_member is None:
                    await interaction.followup.send(
                        'Impossible de remettre le transcript au propriétaire. '
                        'Configure un salon de logs avant de fermer ce ticket.',
                    )
                    return
                try:
                    await owner_member.send(
                        f'Transcript du ticket **{channel.name}** :',
                        file=await make_transcript(channel),
                    )
                    logged = True
                except discord.Forbidden:
                    logger.warning('DM fermé pour le propriétaire du ticket %s.', owner_id)
                    await interaction.followup.send(
                        'Je ne peux pas envoyer le transcript en message privé. '
                        'Configure `TICKET_LOG_CHANNEL_ID` puis réessaie.',
                    )
                    return

            owner = interaction.guild.get_member(owner_id)
            overwrites = channel.overwrites
            for target, overwrite in overwrites.items():
                staff_target = (
                    isinstance(target, discord.Role)
                    and (
                        target.permissions.administrator
                        or target.permissions.manage_guild
                        or target.id in configured_ids('DISCORD_ADMIN_ROLE_IDS')
                    )
                ) or (
                    isinstance(target, discord.Member)
                    and target.id in configured_user_ids()
                )
                if target == owner or not staff_target:
                    overwrite.send_messages = False
                    overwrite.add_reactions = False
                    overwrites[target] = overwrite
            topic = f'{TICKET_TOPIC_PREFIX}owner={owner_id}|status=closed'
            await channel.edit(
                name=f'closed-{channel.name.removeprefix("ticket-")}'[:100],
                topic=f'{topic}|delete_at={int(time.time()) + 10}',
                overwrites=overwrites,
                reason=f'Ticket fermé par {interaction.user} ({interaction.user.id})',
            )
            closure_message = await channel.send(
                f'🔒 Ticket fermé par {interaction.user.mention}. '
                f'Le transcript a été archivé. Ce salon sera supprimé dans 10 secondes.'
            )
            if interaction.message:
                try:
                    await interaction.message.edit(view=None)
                except discord.HTTPException:
                    logger.exception('Impossible de désactiver les actions du ticket %s.', channel.id)
        except discord.HTTPException:
            logger.exception('Impossible de fermer le ticket %s', channel.id)
            await interaction.followup.send(
                'La fermeture a échoué. Vérifie les permissions du bot.',
            )
            return

        await interaction.followup.send(
            'Ticket fermé; transcript archivé. Le salon sera supprimé dans 10 secondes.'
        )
        await asyncio.sleep(10)
        try:
            await channel.delete(reason=f'Ticket archivé; fermeture par {interaction.user}')
        except discord.NotFound:
            pass
        except discord.HTTPException:
            logger.exception('Impossible de supprimer le ticket fermé %s.', channel.id)
            try:
                await closure_message.reply('La suppression automatique a échoué; un administrateur peut supprimer ce salon.')
            except discord.HTTPException:
                logger.exception('Impossible de signaler la suppression manquée du ticket %s.', channel.id)

    async def ensure_ticket_member(interaction, member):
        if member.bot:
            await interaction.response.send_message(
                'Seuls les membres humains peuvent être ajoutés au ticket.',
                ephemeral=True,
            )
            return False
        channel = interaction.channel
        owner_id = ticket_owner(channel) if isinstance(channel, discord.TextChannel) else None
        if owner_id is None or ticket_is_closed(channel):
            await interaction.response.send_message(
                'Cette action est uniquement disponible dans un ticket ouvert.',
                ephemeral=True,
            )
            return False
        if interaction.user.id != owner_id and not is_staff(interaction):
            await interaction.response.send_message(
                'Seul le propriétaire du ticket ou le staff peut ajouter un membre.',
                ephemeral=True,
            )
            return False
        await channel.set_permissions(
            member,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
        )
        await interaction.response.send_message(
            f'{member.mention} a été ajouté au ticket.',
            allowed_mentions=discord.AllowedMentions(users=[member]),
        )
        return True

    async def send_ticket_transcript(interaction):
        channel = interaction.channel
        owner_id = ticket_owner(channel) if isinstance(channel, discord.TextChannel) else None
        if owner_id is None:
            await interaction.response.send_message(
                'Cette action est uniquement disponible dans un ticket.',
                ephemeral=True,
            )
            return
        if interaction.user.id != owner_id and not is_staff(interaction):
            await interaction.response.send_message(
                'Seul le propriétaire du ticket ou le staff peut consulter le transcript.',
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await interaction.followup.send(
            'Transcript du ticket :',
            file=await make_transcript(channel),
            ephemeral=True,
        )

    @bot.tree.command(name='ticket-panel', description='Publier le panneau de support Onyx')
    @app_commands.guild_only()
    async def ticket_panel(
        interaction: discord.Interaction,
        salon: discord.TextChannel | None = None,
    ):
        if not is_staff(interaction):
            await interaction.response.send_message('Commande réservée au staff.', ephemeral=True)
            return
        channel = salon or interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message('Choisis un salon textuel.', ephemeral=True)
            return
        embed = discord.Embed(
            title='Centre de support Onyx',
            description=(
                'Besoin d’aide avec Onyx Client, ta licence ou ton achat ? '
                'Choisis un motif dans le menu pour ouvrir un ticket privé.\n\n'
                '**Un ticket ouvert par membre à la fois.**\n'
                'Dans le ticket : ajouter un membre, prise en charge staff, transcript ou fermeture.'
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text='Support Onyx Client')
        await channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message(f'Panneau publié dans {channel.mention}.', ephemeral=True)

    @bot.tree.command(name='ticket-actions', description='Afficher les actions du ticket actuel')
    @app_commands.guild_only()
    async def ticket_actions(interaction: discord.Interaction):
        channel = interaction.channel
        owner_id = ticket_owner(channel) if isinstance(channel, discord.TextChannel) else None
        if owner_id is None or ticket_is_closed(channel):
            await interaction.response.send_message(
                'Cette commande doit être utilisée dans un ticket ouvert.',
                ephemeral=True,
            )
            return
        if interaction.user.id != owner_id and not is_staff(interaction):
            await interaction.response.send_message(
                'Seul le propriétaire du ticket ou le staff peut afficher ces actions.',
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            'Actions du ticket :',
            view=TicketControlView(),
        )

    @bot.tree.command(name='ticket-close', description='Fermer et archiver le ticket actuel')
    @app_commands.guild_only()
    async def ticket_close(interaction: discord.Interaction):
        await close_ticket(interaction)

    @bot.tree.command(name='ticket-add', description='Ajouter un membre au ticket actuel')
    @app_commands.guild_only()
    async def ticket_add(interaction: discord.Interaction, membre: discord.Member):
        await ensure_ticket_member(interaction, membre)

    @bot.tree.command(name='ticket-transcript', description='Télécharger le transcript HTML du ticket')
    @app_commands.guild_only()
    async def ticket_transcript(interaction: discord.Interaction):
        await send_ticket_transcript(interaction)

    @bot.tree.command(name='aide', description='Afficher les commandes Onyx Client')
    async def aide(interaction: discord.Interaction):
        embed = discord.Embed(
            title='Aide Onyx Client',
            description='Commandes rapides pour ta licence et le client.',
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name='Licence et client',
            value=(
                '`/acheter` acheter une licence • `/lier-cle` associer une clé\n'
                '`/mes-licences` consulter tes licences • `/telecharger` obtenir le client'
            ),
            inline=False,
        )
        embed.add_field(
            name='Support',
            value='Utilise le panneau de support du serveur pour ouvrir un ticket privé.',
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(
        name='annonce-bilingue',
        description='Composer une annonce française et la publier aussi en anglais',
    )
    @app_commands.guild_only()
    async def bilingual_announcement(interaction: discord.Interaction):
        if not is_staff(interaction):
            await interaction.response.send_message(
                'Commande réservée au staff.',
                ephemeral=True,
            )
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                'Utilise cette commande dans un salon textuel.',
                ephemeral=True,
            )
            return

        class BilingualAnnouncementModal(discord.ui.Modal, title='Annonce bilingue'):
            french_text = discord.ui.TextInput(
                label='Message en français',
                placeholder='Écris le message à publier…',
                style=discord.TextStyle.paragraph,
                max_length=2000,
            )

            async def on_submit(self, modal_interaction):
                await modal_interaction.response.defer(ephemeral=True, thinking=True)
                try:
                    english_text = await asyncio.to_thread(
                        translate_french_to_english,
                        self.french_text.value,
                    )
                except TranslationServiceError:
                    logger.exception('Échec de la traduction d’une annonce bilingue.')
                    await modal_interaction.followup.send(
                        'La traduction automatique a échoué. Réessaie plus tard ou contacte un administrateur.',
                        ephemeral=True,
                    )
                    return

                description = (
                    f'🇫🇷 **Français**\n{self.french_text.value}\n\n'
                    f'🇬🇧 **English**\n{english_text}'
                )
                if len(description) > 4096:
                    await modal_interaction.followup.send(
                        'Le message traduit dépasse la taille maximale. Raccourcis le texte français et réessaie.',
                        ephemeral=True,
                    )
                    return

                embed = discord.Embed(
                    description=description,
                    color=discord.Color.blurple(),
                )
                try:
                    await modal_interaction.channel.send(
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except (discord.Forbidden, discord.HTTPException):
                    logger.exception(
                        'Impossible de publier l’annonce bilingue dans le salon %s.',
                        modal_interaction.channel.id,
                    )
                    await modal_interaction.followup.send(
                        'La traduction est prête, mais je n’ai pas pu publier le message dans ce salon.',
                        ephemeral=True,
                    )
                    return
                await modal_interaction.followup.send(
                    'Annonce publiée en français et en anglais.',
                    ephemeral=True,
                )

        await interaction.response.send_modal(BilingualAnnouncementModal())

    @bot.tree.command(name='clear', description='Supprimer des messages récents dans un salon')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear_messages(
        interaction: discord.Interaction,
        nombre: app_commands.Range[int, 1, 100],
        salon: discord.TextChannel | None = None,
    ):
        channel = salon or interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message('Choisis un salon textuel.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        deleted = await channel.purge(limit=nombre, bulk=True)
        await interaction.followup.send(
            f'{len(deleted)} message(s) supprimé(s) dans {channel.mention}.',
        )

    @bot.tree.command(name='ban', description='Bannir un membre du serveur')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.describe(raison='Motif ajouté au journal de modération')
    async def ban_member(
        interaction: discord.Interaction,
        membre: discord.Member,
        raison: app_commands.Range[str, 1, 400] = 'Aucune raison fournie',
    ):
        if membre.id == interaction.user.id or membre.id == interaction.guild.me.id:
            await interaction.response.send_message(
                'Tu ne peux pas bannir cette personne.',
                ephemeral=True,
            )
            return
        if (
            interaction.user.id != interaction.guild.owner_id
            and membre.top_role >= interaction.user.top_role
        ):
            await interaction.response.send_message(
                'Tu ne peux pas bannir un membre ayant un rôle égal ou supérieur au tien.',
                ephemeral=True,
            )
            return
        if membre.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                'Le rôle le plus élevé du bot doit être au-dessus de celui du membre.',
                ephemeral=True,
            )
            return
        await membre.ban(reason=f'{interaction.user}: {raison}', delete_message_seconds=0)
        await interaction.response.send_message(
            f'🔨 {membre.mention} a été banni. Motif : {raison}',
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @bot.tree.command(name='unban', description='Débannir un utilisateur par son identifiant Discord')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.describe(identifiant='Identifiant Discord de l’utilisateur banni')
    async def unban_member(
        interaction: discord.Interaction,
        identifiant: app_commands.Range[str, 17, 20],
        raison: app_commands.Range[str, 1, 400] = 'Aucune raison fournie',
    ):
        if not identifiant.isdecimal():
            await interaction.response.send_message(
                'L’identifiant Discord doit être numérique.',
                ephemeral=True,
            )
            return
        user = discord.Object(id=int(identifiant))
        try:
            await interaction.guild.unban(user, reason=f'{interaction.user}: {raison}')
        except discord.NotFound:
            await interaction.response.send_message(
                'Cet utilisateur ne figure pas dans la liste des bannis.',
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f'✅ <@{identifiant}> a été débanni. Motif : {raison}',
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @bot.tree.command(name='timeout', description='Mettre un membre en timeout')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    @app_commands.describe(duree_minutes='Durée de 1 minute à 28 jours')
    async def timeout_member(
        interaction: discord.Interaction,
        membre: discord.Member,
        duree_minutes: app_commands.Range[int, 1, 40320],
        raison: app_commands.Range[str, 1, 400] = 'Aucune raison fournie',
    ):
        if membre.id == interaction.user.id or membre.id == interaction.guild.me.id:
            await interaction.response.send_message(
                'Tu ne peux pas appliquer un timeout à cette personne.',
                ephemeral=True,
            )
            return
        if (
            interaction.user.id != interaction.guild.owner_id
            and membre.top_role >= interaction.user.top_role
        ):
            await interaction.response.send_message(
                'Tu ne peux pas modérer un membre ayant un rôle égal ou supérieur au tien.',
                ephemeral=True,
            )
            return
        if membre.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                'Le rôle le plus élevé du bot doit être au-dessus de celui du membre.',
                ephemeral=True,
            )
            return
        await membre.timeout(
            timedelta(minutes=duree_minutes),
            reason=f'{interaction.user}: {raison}',
        )
        await interaction.response.send_message(
            f'⏳ {membre.mention} est en timeout pour {duree_minutes} minute(s). Motif : {raison}',
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @bot.tree.command(name='untimeout', description='Retirer le timeout d’un membre')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def remove_timeout(
        interaction: discord.Interaction,
        membre: discord.Member,
        raison: app_commands.Range[str, 1, 400] = 'Aucune raison fournie',
    ):
        if membre.id == interaction.user.id or membre.id == interaction.guild.me.id:
            await interaction.response.send_message(
                'Cette action ne peut pas être appliquée à cette personne.',
                ephemeral=True,
            )
            return
        if (
            interaction.user.id != interaction.guild.owner_id
            and membre.top_role >= interaction.user.top_role
        ):
            await interaction.response.send_message(
                'Tu ne peux pas modérer un membre ayant un rôle égal ou supérieur au tien.',
                ephemeral=True,
            )
            return
        if membre.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                'Le rôle le plus élevé du bot doit être au-dessus de celui du membre.',
                ephemeral=True,
            )
            return
        await membre.timeout(None, reason=f'{interaction.user}: {raison}')
        await interaction.response.send_message(
            f'✅ Timeout retiré pour {membre.mention}. Motif : {raison}',
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @bot.tree.command(name='giveaway', description='Lancer un giveaway Onyx avec tirage automatique')
    @app_commands.guild_only()
    async def giveaway(
        interaction: discord.Interaction,
        prix: app_commands.Range[str, 1, 100],
        duree_heures: app_commands.Range[int, 1, 720],
        gagnants: app_commands.Range[int, 1, 10] = 1,
        salon: discord.TextChannel | None = None,
    ):
        if not is_staff(interaction):
            await interaction.response.send_message('Commande réservée au staff.', ephemeral=True)
            return
        channel = salon or interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message('Choisis un salon textuel.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        ends_at = datetime.now(timezone.utc) + timedelta(hours=duree_heures)
        embed = discord.Embed(
            title='🎉 Giveaway Onyx Client',
            description=f'**Prix :** {prix}\n**Gagnant(s) :** {gagnants}\n'
            f'**Fin :** <t:{int(ends_at.timestamp())}:R>\n\nClique sur **Participer** pour tenter ta chance.',
            color=discord.Color.gold(),
            timestamp=ends_at,
        )
        embed.set_footer(text='Une participation par compte • Tirage automatique')
        message = await channel.send(embed=embed, view=GiveawayView())
        try:
            await asyncio.to_thread(
                create_giveaway,
                message.id,
                interaction.guild_id,
                channel.id,
                prix,
                gagnants,
                ends_at,
            )
        except Exception:
            logger.exception('Impossible d’enregistrer le giveaway %s', message.id)
            await message.delete()
            raise
        await interaction.followup.send(f'Giveaway lancé dans {channel.mention} !')

    @tasks.loop(seconds=30)
    async def process_giveaways():
        try:
            giveaways = await asyncio.to_thread(get_active_giveaways)
        except Exception:
            logger.exception('Impossible de charger les giveaways actifs.')
            return
        for giveaway_row in giveaways:
            if giveaway_row['endsAt'] > datetime.now(timezone.utc):
                continue
            try:
                await asyncio.to_thread(finish_giveaway, giveaway_row['messageId'])
            except Exception:
                logger.exception('Échec du tirage pour le giveaway %s.', giveaway_row['messageId'])

        try:
            pending_announcements = await asyncio.to_thread(get_pending_giveaway_announcements)
        except Exception:
            logger.exception('Impossible de charger les annonces de giveaway en attente.')
            return
        for giveaway_row in pending_announcements:
            try:
                channel = bot.get_channel(giveaway_row['channelId'])
                if not isinstance(channel, discord.TextChannel):
                    logger.error('Salon %s introuvable pour le giveaway %s.', giveaway_row['channelId'], giveaway_row['messageId'])
                    continue
                try:
                    message = await channel.fetch_message(giveaway_row['messageId'])
                    embed = message.embeds[0] if message.embeds else discord.Embed()
                    embed.title = '🏁 Giveaway terminé'
                    embed.color = discord.Color.dark_grey()
                    embed.set_footer(text='Tirage terminé')
                    await message.edit(embed=embed, view=None)
                except discord.NotFound:
                    logger.warning('Message du giveaway %s supprimé avant le tirage.', giveaway_row['messageId'])
                if giveaway_row['winners']:
                    mentions = ', '.join(f'<@{winner_id}>' for winner_id in giveaway_row['winners'])
                    announcement = f'🎉 Félicitations {mentions} ! Vous remportez **{giveaway_row["prize"]}**.'
                    allowed = discord.AllowedMentions(
                        users=[discord.Object(id=value) for value in giveaway_row['winners']]
                    )
                else:
                    announcement = f'Le giveaway **{giveaway_row["prize"]}** est terminé sans participant.'
                    allowed = discord.AllowedMentions.none()
                await channel.send(announcement, allowed_mentions=allowed)
                await asyncio.to_thread(mark_giveaway_announced, giveaway_row['messageId'])
            except Exception:
                logger.exception('Échec de l’annonce du giveaway %s.', giveaway_row['messageId'])

    @process_giveaways.before_loop
    async def before_giveaways():
        await bot.wait_until_ready()

    @tasks.loop(seconds=30)
    async def cleanup_closed_tickets():
        now = int(time.time())
        for guild in bot.guilds:
            for channel in guild.text_channels:
                if not ticket_is_closed(channel):
                    continue
                deadline = ticket_delete_deadline(channel)
                if deadline is None:
                    try:
                        await channel.edit(
                            topic=f'{channel.topic}|delete_at={now + 10}',
                            reason='Programmer le nettoyage d’un ancien ticket fermé',
                        )
                    except discord.HTTPException:
                        logger.exception(
                            'Impossible de programmer la suppression du ticket fermé %s.',
                            channel.id,
                        )
                    continue
                if deadline <= now:
                    try:
                        await channel.delete(reason='Nettoyage automatique du ticket archivé')
                    except discord.NotFound:
                        continue
                    except discord.HTTPException:
                        logger.exception('Impossible de supprimer le ticket fermé %s.', channel.id)

    @cleanup_closed_tickets.before_loop
    async def before_ticket_cleanup():
        await bot.wait_until_ready()

    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())
    bot.add_view(GiveawayView())
    await asyncio.to_thread(initialize_discord_storage)
    if not process_giveaways.is_running():
        process_giveaways.start()
    if not cleanup_closed_tickets.is_running():
        cleanup_closed_tickets.start()
