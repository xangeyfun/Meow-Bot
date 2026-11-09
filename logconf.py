import logging
import os

from dotenv import load_dotenv

load_dotenv()

LOG_FORMAT = "%(levelname)-8s %(name)s  %(message)s"


def setup_logging():
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)

    if os.getenv("ERROR_WEBHOOK_URL"):
        from notify import DiscordAlertHandler

        root = logging.getLogger()
        if not any(isinstance(handler, DiscordAlertHandler) for handler in root.handlers):
            root.addHandler(DiscordAlertHandler())
