import asyncio
import logging
import os

import discord
from discord.ext import commands

import stats

logger = logging.getLogger("cogs.events")


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

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        logger.info("Joined guild %s (%s)", guild.name, guild.id)
        try:
            await asyncio.to_thread(stats.write_heartbeat, len(self.bot.guilds))
        except Exception:
            logger.exception("Heartbeat write failed")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        logger.info("Left guild %s (%s)", guild.name, guild.id)
        try:
            await asyncio.to_thread(stats.write_heartbeat, len(self.bot.guilds))
        except Exception:
            logger.exception("Heartbeat write failed")


async def setup(bot):
    await bot.add_cog(EventsCog(bot))
