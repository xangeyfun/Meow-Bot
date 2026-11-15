import logging
import os

import aiohttp

logger = logging.getLogger("botlists")

TOPGG_TOKEN = os.getenv("TOPGG_TOKEN")
DISCORDLIST_TOKEN = os.getenv("DISCORDLIST_TOKEN")

TOPGG_API = "https://top.gg/api/v1"
DISCORDLIST_API = "https://api.discordlist.gg/v0"


async def _request(session, method, url, label, **kwargs):
    try:
        async with session.request(method, url, **kwargs) as response:
            if not 200 <= response.status < 300:
                body = await response.text()
                logger.warning("%s failed: %s %s", label, response.status, body)
    except Exception:
        logger.exception("%s failed", label)


async def _command_payloads(bot):
    try:
        commands = await bot.tree.fetch_commands()
    except Exception:
        logger.exception("Failed to fetch commands from Discord")
        commands = []
    if not commands:
        commands = list(bot.tree.get_commands())
    return [command.to_dict() for command in commands]


async def post_stats(bot, session: aiohttp.ClientSession):
    bot_id = str(bot.user.id) if bot.user else None
    guild_count = len(bot.guilds)

    if TOPGG_TOKEN:
        headers = {"Authorization": f"Bearer {TOPGG_TOKEN}"}
        await _request(
            session,
            "PATCH",
            f"{TOPGG_API}/projects/@me/metrics",
            "top.gg metrics",
            headers=headers,
            json={"server_count": guild_count, "shard_count": bot.shard_count or 1},
        )
        commands = await _command_payloads(bot)
        if commands:
            await _request(
                session,
                "PUT",
                f"{TOPGG_API}/projects/@me/commands",
                "top.gg commands",
                headers=headers,
                json=commands,
            )

    if DISCORDLIST_TOKEN and bot_id:
        await _request(
            session,
            "PUT",
            f"{DISCORDLIST_API}/bots/{bot_id}/guilds",
            "discordlist.gg guild count",
            headers={"Authorization": f"Bearer {DISCORDLIST_TOKEN}"},
            params={"count": str(guild_count)},
        )
