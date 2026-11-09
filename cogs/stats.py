import discord
from discord import app_commands
from discord.ext import commands

import stats


class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stats", description="show meow stats for a user")
    @app_commands.describe(user="the user to check. defaults to you.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def stats_command(
        self, interaction: discord.Interaction, user: discord.Member = None
    ):
        target = user or interaction.user
        count, rank, server_total = stats.user_stats(interaction.guild.id, target.id)

        if count == 0:
            await interaction.response.send_message(
                f"{target.display_name} has no meows yet. say meow.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        await interaction.response.send_message(
            f"{target.display_name} has meowed {count:,} times in this server.\n"
            f"rank: {rank}\n"
            f"server total: {server_total:,}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="leaderboard", description="top meowers in this server")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def leaderboard(self, interaction: discord.Interaction):
        rows = stats.server_leaderboard(interaction.guild.id, limit=10)
        if not rows:
            await interaction.response.send_message(
                "no meows yet. be the first.", ephemeral=True
            )
            return

        lines = []
        for index, (user_id, count) in enumerate(rows, start=1):
            lines.append(f"{index}. <@{user_id}> {count:,}")

        _, _, server_total = stats.user_stats(
            interaction.guild.id, interaction.user.id
        )
        lines.append("")
        lines.append(f"server total: {server_total:,}")

        await interaction.response.send_message(
            "\n".join(lines),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="totalmeows", description="total meows across all servers")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def totalmeows(self, interaction: discord.Interaction):
        total = stats.global_total()
        await interaction.response.send_message(
            f"meow bot has meowed {total:,} times across all servers.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(StatsCog(bot))
