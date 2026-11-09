import asyncio
import logging
import os
import signal
import time

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import stats
from db import get_db
from logconf import setup_logging
from schema import create_schema
from store import GuildConfigStore

load_dotenv()
setup_logging()
logger = logging.getLogger("bot")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned,
    intents=intents,
    help_command=None,
    status=discord.Status.online,
    activity=discord.Activity(type=discord.ActivityType.watching, name="for meows | /help"),
    chunk_guilds_at_startup=False,
)
TOKEN = os.getenv("TOKEN") or ""
bot.stats_buffer = stats.StatsBuffer()
bot.config_store = GuildConfigStore()
bot._exit_code = 0
bot._stop_event = asyncio.Event()

EXTENSIONS = (
    "cogs.events",
    "cogs.general",
    "cogs.reactions",
    "cogs.config",
    "cogs.stats",
)


async def setup_hook():
    for extension in EXTENSIONS:
        await bot.load_extension(extension)


bot.setup_hook = setup_hook


async def _reply_error(interaction: discord.Interaction, content: str) -> None:
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=True)
        else:
            await interaction.response.send_message(content, ephemeral=True)
    except discord.HTTPException:
        pass


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    name = getattr(interaction.command, "qualified_name", "?")

    if isinstance(error, app_commands.CommandOnCooldown):
        logger.warning("Cooldown on /%s used by %s: %s", name, interaction.user, error)
        await _reply_error(
            interaction,
            f"Slow down. Try /{name} again in {max(1, int(error.retry_after))} seconds.",
        )
        return

    if isinstance(
        error,
        (
            app_commands.MissingPermissions,
            app_commands.BotMissingPermissions,
            app_commands.MissingRole,
            app_commands.MissingAnyRole,
        ),
    ):
        logger.warning("Permission check failed on /%s used by %s: %s", name, interaction.user, error)
        await _reply_error(interaction, str(error))
        return

    if isinstance(error, app_commands.TransformerError):
        logger.warning("Bad argument for /%s used by %s: %s", name, interaction.user, error)
        await _reply_error(interaction, f"That value is not valid for /{name}.")
        return

    if isinstance(error, app_commands.CheckFailure):
        logger.warning("Check failed for /%s used by %s: %r", name, interaction.user, error)
        await _reply_error(interaction, "You cannot use that here right now.")
        return

    if isinstance(error, app_commands.CommandInvokeError):
        original = error.original
        if isinstance(original, discord.Forbidden):
            logger.error("Permission denied running /%s for %s: %s", name, interaction.user, original)
            await _reply_error(
                interaction,
                "I do not have permission to do that here. Ask a server admin to check my role permissions.",
            )
            return
        if isinstance(original, discord.NotFound):
            logger.error("Target missing for /%s used by %s: %s", name, interaction.user, original)
            await _reply_error(interaction, "That no longer exists.")
            return
        if isinstance(original, discord.HTTPException):
            logger.error("Discord rejected /%s for %s: %s", name, interaction.user, original)
            await _reply_error(interaction, "Discord rejected that request. Try again in a moment.")
            return
        logger.critical("Unhandled error in /%s used by %s", name, interaction.user, exc_info=original)
        await _reply_error(interaction, "Something went wrong. Try again later.")
        return

    logger.critical("Unhandled command error in /%s used by %s", name, interaction.user, exc_info=error)
    await _reply_error(interaction, "Something went wrong. Try again later.")


_STARTUP_TIMEOUT = 60
_CHECK_INTERVAL = 20
_GRACE_SECONDS = 90


async def _wait_until_ready(
    bot: commands.Bot, stop: asyncio.Event, bot_task: asyncio.Task
) -> None:
    ready = asyncio.ensure_future(bot.wait_until_ready())
    sigstop = asyncio.ensure_future(stop.wait())
    pending = set()
    try:
        done, pending = await asyncio.wait(
            {ready, sigstop, bot_task},
            timeout=_STARTUP_TIMEOUT,
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        for task in pending:
            if task is bot_task:
                continue
            task.cancel()

    if stop.is_set():
        return

    failed = None
    for task in (ready, bot_task):
        if task in done and not task.cancelled() and task.exception() is not None:
            failed = task.exception()
            break

    if failed is not None:
        logger.error(
            "Discord gateway failed during startup (%r). Exiting so the process manager can retry.",
            failed,
        )
    elif ready not in done:
        logger.error(
            "Bot did not reach on_ready within %ss. Exiting so the process manager can retry.",
            _STARTUP_TIMEOUT,
        )
    else:
        return

    bot._exit_code = 1
    stop.set()


async def _connection_watchdog(
    bot: commands.Bot, stop: asyncio.Event, bot_task: asyncio.Task
) -> None:
    closed_since = None
    while True:
        await asyncio.sleep(_CHECK_INTERVAL)
        if stop.is_set():
            return
        if bot_task.done():
            if bot_task.cancelled():
                return
            failed = bot_task.exception()
            logger.error(
                "Discord gateway connection ended without a stop request (%s). "
                "Exiting so the process manager can restart it.",
                repr(failed) if failed else "clean close",
            )
            bot._exit_code = 1
            stop.set()
            return

        websocket = bot.ws
        alive = websocket is not None and websocket.open
        if alive:
            closed_since = None
            continue

        now = time.monotonic()
        if closed_since is None:
            closed_since = now
        elif now - closed_since >= _GRACE_SECONDS:
            logger.error(
                "Gateway websocket has been closed for %ss. Exiting so the process manager can restart it.",
                _GRACE_SECONDS,
            )
            bot._exit_code = 1
            stop.set()
            break


async def _background_loop(bot: commands.Bot, stop: asyncio.Event) -> None:
    last_heartbeat = 0.0
    last_users = 0.0
    while not stop.is_set():
        now = time.monotonic()

        if now - last_heartbeat >= 30:
            try:
                await asyncio.to_thread(stats.write_heartbeat, len(bot.guilds))
            except Exception:
                logger.exception("Heartbeat write failed")
            last_heartbeat = now

        if now - last_users >= 300:
            try:
                await asyncio.to_thread(stats.refresh_user_count)
            except Exception:
                logger.exception("User count refresh failed")
            last_users = now

        try:
            await asyncio.to_thread(stats.flush_buffer, bot.stats_buffer)
        except Exception:
            logger.exception("Stats flush failed")

        try:
            await asyncio.wait_for(stop.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass


async def _run_bot() -> None:
    loop = asyncio.get_running_loop()
    stop = bot._stop_event

    def _request_stop():
        if not stop.is_set():
            logger.info("Shutdown signal received. Closing the Discord gateway.")
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda *_: _request_stop())

    bot_task = asyncio.ensure_future(bot.start(TOKEN))
    watchdog = asyncio.ensure_future(_connection_watchdog(bot, stop, bot_task))
    background = asyncio.ensure_future(_background_loop(bot, stop))

    try:
        await _wait_until_ready(bot, stop, bot_task)
        if not stop.is_set():
            await stop.wait()
    finally:
        background.cancel()
        await asyncio.gather(background, return_exceptions=True)

        try:
            await asyncio.to_thread(stats.flush_buffer, bot.stats_buffer)
        except Exception:
            logger.exception("Final stats flush failed")

        watchdog.cancel()
        await asyncio.gather(watchdog, return_exceptions=True)

        if not bot.is_closed():
            await bot.close()
        if not bot_task.done():
            bot_task.cancel()
            await asyncio.gather(bot_task, return_exceptions=True)


if __name__ == "__main__":
    if not TOKEN:
        logger.critical("TOKEN is not set. Add it to .env.")
        raise SystemExit(1)

    conn = get_db()
    create_schema(conn)
    conn.close()

    asyncio.run(_run_bot())

    exit_code = getattr(bot, "_exit_code", 0)
    if exit_code:
        raise SystemExit(exit_code)
