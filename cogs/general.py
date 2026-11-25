import os

import discord
from discord import app_commands
from discord.ext import commands

from vote import VOTE_LINKS, VoteView

GITHUB_URL = os.getenv("GITHUB_URL", "https://github.com/xangeyfun/Meow-Bot")
INVITE_URL = os.getenv(
    "DISCORD_INVITE_URL",
    "https://discord.com/oauth2/authorize?client_id=1446086806926786581"
    "&scope=bot%20applications.commands&permissions=84992",
)

HELP_TEXT = f"""meow bot

say meow, mreow, mew, mrow, mrrp, nya, or purr. it will meow back.
server admins can teach it new sounds, replies, and channel filters with /config.

commands
/help: this message
/config: server settings for admins
/ping: check latency
/github: source code
/stats [user]: server and global meow stats
/leaderboard: top meowers and server summary
/profile [user]: cross-server meow profile
/totalmeows: global meows and totals
/vote: vote for the cat

every command takes hidden:true if you want the reply only for you.

invite: {INVITE_URL}
"""

HIDDEN_DESCRIPTION = "only show the reply to you"


class GeneralCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="show the command list")
    @app_commands.describe(hidden=HIDDEN_DESCRIPTION)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def help_command(
        self, interaction: discord.Interaction, hidden: bool = False
    ):
        await interaction.response.send_message(
            HELP_TEXT, ephemeral=hidden, view=VoteView()
        )

    @app_commands.command(name="ping", description="check latency")
    @app_commands.describe(hidden=HIDDEN_DESCRIPTION)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def ping(self, interaction: discord.Interaction, hidden: bool = False):
        await interaction.response.send_message(
            f"pong. {round(self.bot.latency * 1000)}ms",
            ephemeral=hidden,
            view=VoteView(),
        )

    @app_commands.command(name="github", description="get the source link")
    @app_commands.describe(hidden=HIDDEN_DESCRIPTION)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def github(self, interaction: discord.Interaction, hidden: bool = False):
        await interaction.response.send_message(
            GITHUB_URL, ephemeral=hidden, view=VoteView()
        )

    @app_commands.command(name="vote", description="vote for meow bot")
    @app_commands.describe(hidden=HIDDEN_DESCRIPTION)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def vote(self, interaction: discord.Interaction, hidden: bool = False):
        links = "\n".join(f"{name}: {url}" for name, url in VOTE_LINKS)
        await interaction.response.send_message(
            f"the cat says you should vote:\n{links}", ephemeral=hidden
        )


async def setup(bot):
    await bot.add_cog(GeneralCog(bot))
