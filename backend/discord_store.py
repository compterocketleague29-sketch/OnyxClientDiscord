import os
import secrets
from datetime import datetime

import psycopg
from psycopg.rows import dict_row


def connect():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError('La variable DATABASE_URL est obligatoire.')
    return psycopg.connect(database_url, row_factory=dict_row)


def initialize_discord_storage():
    with connect() as con:
        con.execute(
            '''CREATE TABLE IF NOT EXISTS discord_giveaways (
                "messageId" BIGINT PRIMARY KEY,
                "guildId" BIGINT NOT NULL,
                "channelId" BIGINT NOT NULL,
                "prize" TEXT NOT NULL,
                "winnerCount" INTEGER NOT NULL CHECK ("winnerCount" BETWEEN 1 AND 10),
                "endsAt" TIMESTAMPTZ NOT NULL,
                "status" TEXT NOT NULL DEFAULT 'active'
                    CHECK ("status" IN ('active', 'ended', 'cancelled')),
                "winners" BIGINT[] NOT NULL DEFAULT '{}',
                "endedAt" TIMESTAMPTZ,
                "announced" BOOLEAN NOT NULL DEFAULT FALSE
            )'''
        )
        con.execute(
            '''ALTER TABLE discord_giveaways
               ADD COLUMN IF NOT EXISTS "announced" BOOLEAN NOT NULL DEFAULT FALSE'''
        )
        con.execute(
            '''CREATE TABLE IF NOT EXISTS discord_giveaway_entries (
                "messageId" BIGINT NOT NULL REFERENCES discord_giveaways("messageId")
                    ON DELETE CASCADE,
                "userId" BIGINT NOT NULL,
                "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY ("messageId", "userId")
            )'''
        )


def create_giveaway(message_id, guild_id, channel_id, prize, winner_count, ends_at):
    with connect() as con:
        con.execute(
            '''INSERT INTO discord_giveaways
               ("messageId", "guildId", "channelId", "prize", "winnerCount", "endsAt")
               VALUES (%s, %s, %s, %s, %s, %s)''',
            (message_id, guild_id, channel_id, prize, winner_count, ends_at),
        )


def enter_giveaway(message_id, user_id):
    with connect() as con:
        with con.transaction():
            giveaway = con.execute(
                '''SELECT "status", "endsAt" FROM discord_giveaways
                   WHERE "messageId"=%s FOR UPDATE''',
                (message_id,),
            ).fetchone()
            if not giveaway:
                return 'missing'
            if giveaway['status'] != 'active' or giveaway['endsAt'] <= datetime.now(
                giveaway['endsAt'].tzinfo
            ):
                return 'ended'
            result = con.execute(
                '''INSERT INTO discord_giveaway_entries ("messageId", "userId")
                   VALUES (%s, %s) ON CONFLICT DO NOTHING''',
                (message_id, user_id),
            )
            return 'joined' if result.rowcount else 'duplicate'


def finish_giveaway(message_id):
    with connect() as con:
        with con.transaction():
            giveaway = con.execute(
                '''SELECT "winnerCount", "endsAt" FROM discord_giveaways
                   WHERE "messageId"=%s AND "status"='active' FOR UPDATE''',
                (message_id,),
            ).fetchone()
            if not giveaway or giveaway['endsAt'] > datetime.now(giveaway['endsAt'].tzinfo):
                return None

            entries = con.execute(
                '''SELECT "userId" FROM discord_giveaway_entries
                   WHERE "messageId"=%s''',
                (message_id,),
            ).fetchall()
            winner_count = min(giveaway['winnerCount'], len(entries))
            winners = [
                entry['userId']
                for entry in secrets.SystemRandom().sample(entries, winner_count)
            ]
            con.execute(
                '''UPDATE discord_giveaways SET "status"='ended', "winners"=%s, "endedAt"=NOW()
                   WHERE "messageId"=%s''',
                (winners, message_id),
            )
            return winners


def get_active_giveaways():
    with connect() as con:
        return con.execute(
            '''SELECT "messageId", "guildId", "channelId", "prize", "winnerCount", "endsAt"
               FROM discord_giveaways WHERE "status"='active' ORDER BY "endsAt"'''
        ).fetchall()


def get_pending_giveaway_announcements():
    with connect() as con:
        return con.execute(
            '''SELECT "messageId", "guildId", "channelId", "prize", "winners"
               FROM discord_giveaways
               WHERE "status"='ended' AND "announced"=FALSE
               ORDER BY "endedAt"'''
        ).fetchall()


def mark_giveaway_announced(message_id):
    with connect() as con:
        con.execute(
            '''UPDATE discord_giveaways SET "announced"=TRUE
               WHERE "messageId"=%s AND "status"='ended' ''',
            (message_id,),
        )
