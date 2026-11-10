import logging
import os

from dotenv import load_dotenv

load_dotenv()

LOG_FORMAT = "%(levelname)-8s %(name)s  %(message)s"
TRUTHY = {"1", "true", "yes", "on"}


def _env_flag(name):
    return os.getenv(name, "").strip().lower() in TRUTHY


def setup_logging():
    debug = _env_flag("DEBUG")
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(level=level, format=LOG_FORMAT)
    logging.getLogger().setLevel(level)
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)

    if os.getenv("ERROR_WEBHOOK_URL"):
        from notify import DiscordAlertHandler

        root = logging.getLogger()
        if not any(isinstance(handler, DiscordAlertHandler) for handler in root.handlers):
            root.addHandler(DiscordAlertHandler())
