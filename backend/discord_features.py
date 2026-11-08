import asyncio
import html
import io
import logging
import os
import re
from datetime import datetime, timedelta, timezone

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
ticket_creation_locks = {}


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
    admin_role_ids = configured_ids('DISCORD_ADMIN_ROLE_IDS')
    return any(role.id in admin_role_ids for role in member_roles)


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

        @discord.ui.button(
            label='Ouvrir un ticket',
            style=discord.ButtonStyle.primary,
            emoji='🎫',
            custom_id='onyx:ticket:create',
        )
        async def open_ticket(self, interaction, button):
            if not interaction.guild or not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    'Les tickets sont disponibles uniquement sur le serveur.',
                    ephemeral=True,
                )
                return
            category_id = os.environ.get('TICKET_CATEGORY_ID')
            category = interaction.guild.get_channel(int(category_id)) if category_id else None
            if category_id and not isinstance(category, discord.CategoryChannel):
                await interaction.response.send_message(
                    'La catégorie des tickets est invalide. Contacte un administrateur.',
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
                        name=f'ticket-{safe_name[:80] or interaction.user.id}',
                        category=category,
                        overwrites=await ticket_overwrites(interaction.guild, interaction.user),
                        topic=f'{TICKET_TOPIC_PREFIX}owner={interaction.user.id}|status=open',
                        reason=f'Ticket ouvert par {interaction.user} ({interaction.user.id})',
                    )
                    embed = discord.Embed(
                        title='Bienvenue dans ton ticket',
                        description=(
                            f'{interaction.user.mention}, décris ta demande avec le plus de détails possible. '
                            'Un membre du staff te répondra dès que possible.'
                        ),
                        color=discord.Color.blurple(),
                    )
                    embed.set_footer(text='Onyx Client • Support privé')
                    await channel.send(
                        content=interaction.user.mention,
                        embed=embed,
                        view=TicketControlView(),
                        allowed_mentions=discord.AllowedMentions(users=[interaction.user]),
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

    class TicketControlView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(
            label='Fermer le ticket',
            style=discord.ButtonStyle.danger,
            emoji='🔒',
            custom_id='onyx:ticket:close',
        )
        async def close_ticket_button(self, interaction, button):
            await close_ticket(interaction)

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

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            logged = await send_transcript_to_logs(interaction.guild, channel)
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
                topic=topic,
                overwrites=overwrites,
                reason=f'Ticket fermé par {interaction.user} ({interaction.user.id})',
            )
            await channel.send(
                f'🔒 Ticket fermé par {interaction.user.mention}. '
                + (
                    'Le transcript a été envoyé au salon de logs.'
                    if logged
                    else 'Configure TICKET_LOG_CHANNEL_ID pour archiver automatiquement le transcript.'
                )
            )
        except discord.HTTPException:
            logger.exception('Impossible de fermer le ticket %s', channel.id)
            await interaction.followup.send(
                'La fermeture a échoué. Vérifie les permissions du bot.',
                ephemeral=True,
            )
            return
        await interaction.followup.send('Ticket fermé et archivé.', ephemeral=True)

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
                'Ouvre un ticket privé et notre équipe te répondra ici.\n\n'
                '**Un ticket ouvert par membre à la fois.**'
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text='Support Onyx Client')
        await channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message(f'Panneau publié dans {channel.mention}.', ephemeral=True)

    @bot.tree.command(name='ticket-close', description='Fermer et archiver le ticket actuel')
    @app_commands.guild_only()
    async def ticket_close(interaction: discord.Interaction):
        await close_ticket(interaction)

    @bot.tree.command(name='ticket-add', description='Ajouter un membre au ticket actuel')
    @app_commands.guild_only()
    async def ticket_add(interaction: discord.Interaction, membre: discord.Member):
        channel = interaction.channel
        owner_id = ticket_owner(channel) if isinstance(channel, discord.TextChannel) else None
        if owner_id is None:
            await interaction.response.send_message('Cette commande doit être utilisée dans un ticket.', ephemeral=True)
            return
        if interaction.user.id != owner_id and not is_staff(interaction):
            await interaction.response.send_message('Seul le propriétaire ou le staff peut ajouter un membre.', ephemeral=True)
            return
        if ticket_is_closed(channel):
            await interaction.response.send_message('Le ticket est fermé.', ephemeral=True)
            return
        await channel.set_permissions(
            membre,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
        )
        await interaction.response.send_message(
            f'{membre.mention} a été ajouté au ticket.',
            allowed_mentions=discord.AllowedMentions(users=[membre]),
        )

    @bot.tree.command(name='ticket-transcript', description='Télécharger le transcript HTML du ticket')
    @app_commands.guild_only()
    async def ticket_transcript(interaction: discord.Interaction):
        channel = interaction.channel
        owner_id = ticket_owner(channel) if isinstance(channel, discord.TextChannel) else None
        if owner_id is None:
            await interaction.response.send_message('Cette commande doit être utilisée dans un ticket.', ephemeral=True)
            return
        if interaction.user.id != owner_id and not is_staff(interaction):
            await interaction.response.send_message('Seul le propriétaire ou le staff peut consulter le transcript.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await interaction.followup.send(
            'Transcript du ticket :',
            file=await make_transcript(channel),
            ephemeral=True,
        )

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
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
            ephemeral=True,
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
        await interaction.followup.send(f'Giveaway lancé dans {channel.mention} !', ephemeral=True)

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

    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())
    bot.add_view(GiveawayView())
    await asyncio.to_thread(initialize_discord_storage)
    if not process_giveaways.is_running():
        process_giveaways.start()
