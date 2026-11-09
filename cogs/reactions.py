import json
import logging
import random
from pathlib import Path

import discord
from discord.ext import commands

from matcher import match_message
from ratelimit import ChannelTokenBucket

logger = logging.getLogger("cogs.reactions")

RESPONSES_PATH = Path(__file__).resolve().parents[1] / "responses.json"
with RESPONSES_PATH.open(encoding="utf-8") as handle:
    RESPONSES = json.load(handle)


class ReactionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = bot.config_store
        self.buckets = ChannelTokenBucket(capacity=5, refill_rate=1.0)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            await self._handle_message(message)
        except Exception:
            logger.exception("Failed to handle a message")

    async def _handle_message(self, message: discord.Message):
        if message.guild is None:
            return
        if message.author.bot or getattr(message, "webhook_id", None):
            return

        content = message.content.strip()
        if not content:
            return

        config = self.store.get(message.guild.id)
        if not config.enabled:
            return

        result = match_message(content, config.custom_triggers, config.builtin_enabled)
        if result is None:
            return

        if not self.buckets.allow(message.guild.id, message.channel.id):
            return

        pool = RESPONSES.get(result.pool) or RESPONSES["meow"]
        reply = random.choice(pool)

        try:
            await message.reply(
                reply,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            logger.debug(
                "Reply failed in guild %s channel %s",
                message.guild.id,
                message.channel.id,
            )
            try:
                await message.channel.send(
                    reply, allowed_mentions=discord.AllowedMentions.none()
                )
            except discord.HTTPException:
                logger.debug(
                    "Send fallback failed in guild %s channel %s",
                    message.guild.id,
                    message.channel.id,
                )
                return

        self.bot.stats_buffer.record(message.guild.id, message.author.id)
        logger.debug("meowed at %s in guild %s", message.author, message.guild.id)


async def setup(bot):
    await bot.add_cog(ReactionsCog(bot))
