import asyncio
import logging
import os

import aiohttp
import discord
from discord.ext import commands, tasks

import botlists
import stats

logger = logging.getLogger("cogs.events")

GUILD_LOG_CHANNEL_ID = os.getenv("GUILD_LOG_CHANNEL_ID", "").strip()


def _guild_log_channel_id():
    if not GUILD_LOG_CHANNEL_ID:
        return None
    try:
        return int(GUILD_LOG_CHANNEL_ID)
    except ValueError:
        logger.warning(
            "GUILD_LOG_CHANNEL_ID is not a valid channel id: %r",
            GUILD_LOG_CHANNEL_ID,
        )
        return None


class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._ready_done = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready_done:
            logger.info("Reconnected as %s. Commands already synced.", self.bot.user)
            return

        guild_id = os.getenv("GUILD_ID")
        try:
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                self.bot.tree.copy_global_to(guild=guild)
                synced = await self.bot.tree.sync(guild=guild)
            else:
                synced = await self.bot.tree.sync()
        except Exception:
            logger.exception("Failed to sync commands")
            self.bot._exit_code = 1
            self.bot._stop_event.set()
            return

        logger.info("Logged in as %s", self.bot.user)
        logger.info("Synced %s commands", len(synced))
        if self.bot.user:
            logger.info(
                "Invite: https://discord.com/oauth2/authorize?client_id=%s"
                "&scope=bot%%20applications.commands&permissions=84992",
                self.bot.user.id,
            )

        try:
            await asyncio.to_thread(stats.bot_started)
            await asyncio.to_thread(stats.write_heartbeat, len(self.bot.guilds))
        except Exception:
            logger.exception("Failed to write startup stats")

        if botlists.TOPGG_TOKEN or botlists.DISCORDLIST_TOKEN:
            logger.info(
                "Bot list posting enabled (top.gg=%s, discordlist.gg=%s)",
                bool(botlists.TOPGG_TOKEN),
                bool(botlists.DISCORDLIST_TOKEN),
            )
            self.update_botlists.start()

        self._ready_done = True

    @commands.Cog.listener()
    async def on_message(self, message):
        logger.debug(
            "message guild=%s channel=%s author=%s(%s) content=%r",
            getattr(message.guild, "id", None),
            getattr(message.channel, "id", None),
            message.author,
            message.author.id,
            message.content,
        )

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        user = interaction.user
        if interaction.type is discord.InteractionType.application_command:
            command = interaction.command
            name = getattr(command, "qualified_name", None)
            if name is None and interaction.data:
                name = interaction.data.get("name", "?")
            logger.debug(
                "command /%s user=%s(%s) guild=%s channel=%s options=%r",
                name or "?",
                user,
                getattr(user, "id", None),
                getattr(interaction.guild, "id", None),
                getattr(interaction.channel, "id", None),
                interaction.data.get("options") if interaction.data else None,
            )
            return

        logger.debug(
            "interaction type=%s user=%s(%s) guild=%s channel=%s data=%r",
            interaction.type,
            user,
            getattr(user, "id", None),
            getattr(interaction.guild, "id", None),
            getattr(interaction.channel, "id", None),
            interaction.data,
        )

    def _guild_log_embed(self, guild, joined):
        total_members = sum(g.member_count or 0 for g in self.bot.guilds)
        total_guilds = len(self.bot.guilds)
        embed = discord.Embed(
            title="🎉 Joined a new guild!" if joined else "👋 Removed from a guild!",
            color=discord.Color(0xFFB6C1) if joined else discord.Color(0xF48FB1),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Guild Members",
            value=f"`{guild.member_count or 0}`",
            inline=True,
        )
        embed.add_field(name="Total Members", value=f"`{total_members}`", inline=True)
        embed.add_field(name="Total Guilds", value=f"`{total_guilds}`", inline=True)
        embed.set_footer(text="meow bot • /help")
        return embed

    async def _send_guild_log(self, embed):
        channel_id = _guild_log_channel_id()
        if channel_id is None:
            logger.debug("GUILD_LOG_CHANNEL_ID is not set, skipping guild log")
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.HTTPException:
                logger.warning(
                    "Could not find guild log channel %s, skipping guild log",
                    channel_id,
                )
                return

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            logger.exception(
                "Failed to send guild log to channel %s", channel_id
            )

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        logger.info("Joined guild %s (%s)", guild.name, guild.id)
        try:
            await asyncio.to_thread(stats.write_heartbeat, len(self.bot.guilds))
        except Exception:
            logger.exception("Heartbeat write failed")
        await self._send_guild_log(self._guild_log_embed(guild, joined=True))

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        try:
            await asyncio.to_thread(stats.write_heartbeat, len(self.bot.guilds))
        except Exception:
            logger.exception("Heartbeat write failed")

        if guild.name is None or guild.member_count is None:
            logger.debug("Skipping unavailable guild removal %s", guild.id)
            return

        logger.info("Left guild %s (%s)", guild.name, guild.id)
        await self._send_guild_log(self._guild_log_embed(guild, joined=False))

    @tasks.loop(minutes=30)
    async def update_botlists(self):
        async with aiohttp.ClientSession() as session:
            await botlists.post_stats(self.bot, session)


async def setup(bot):
    await bot.add_cog(EventsCog(bot))
