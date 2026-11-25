import os

import discord

BOT_ID = "1446086806926786581"
VOTE_LINKS = (
    ("top.gg", f"https://top.gg/bot/{BOT_ID}/vote"),
    ("discordlist.gg", f"https://discordlist.gg/bot/{BOT_ID}/vote"),
)
VOTE_LABEL = "the cat says you should vote"


def vote_page_url():
    return os.getenv("SITE_URL", "http://localhost:8000").rstrip("/") + "/vote"


class VoteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=VOTE_LABEL, url=vote_page_url()))
