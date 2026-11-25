import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import stats
from vote import VoteView

HIDDEN_DESCRIPTION = "only show the reply to you"
COLOR = discord.Color(0xF4A261)


def _embed(title, description=None):
    return discord.Embed(title=title, description=description, color=COLOR)


def _last_meow(value):
    if not value:
        return "unknown"
    return f"<t:{int(value)}:R>"


def _guild_name(interaction, guild_id):
    guild = interaction.client.get_guild(guild_id) if guild_id else None
    return guild.name if guild else f"server {guild_id}"


class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stats", description="show meow stats for a user")
    @app_commands.describe(
        user="the user to check. defaults to you.",
        hidden=HIDDEN_DESCRIPTION,
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def stats_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        hidden: bool = False,
    ):
        target = user or interaction.user
        server_data, global_data = await asyncio.gather(
            asyncio.to_thread(
                stats.server_user_stats, interaction.guild.id, target.id
            ),
            asyncio.to_thread(stats.global_user_stats, target.id),
        )

        embed = _embed(f"meow stats for {target.display_name}")
        if server_data["count"] == 0:
            if global_data["count"]:
                embed.description = "no meows in this server yet."
                embed.add_field(
                    name="global meows",
                    value=f"{global_data['count']:,}",
                    inline=True,
                )
                embed.add_field(
                    name="global rank",
                    value=f"{global_data['rank']}",
                    inline=True,
                )
            else:
                embed.description = "no meows yet. say meow."
        else:
            embed.description = (
                f"**{server_data['count']:,}** meows in this server."
            )
            embed.add_field(
                name="this server",
                value=(
                    f"rank: {server_data['rank']} of "
                    f"{server_data['server_meowers']}\n"
                    f"share: {server_data['share']:.1f}%\n"
                    f"last meow: {_last_meow(server_data['last_meow_at'])}\n"
                    f"server total: {server_data['server_total']:,}"
                ),
                inline=True,
            )
            embed.add_field(
                name="all servers",
                value=(
                    f"meows: {global_data['count']:,}\n"
                    f"rank: {global_data['rank']}"
                ),
                inline=True,
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=hidden,
            view=VoteView(),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="leaderboard", description="top meowers in this server")
    @app_commands.describe(hidden=HIDDEN_DESCRIPTION)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def leaderboard(
        self, interaction: discord.Interaction, hidden: bool = False
    ):
        rows, summary, mine = await asyncio.gather(
            asyncio.to_thread(
                stats.server_leaderboard, interaction.guild.id, limit=10
            ),
            asyncio.to_thread(stats.server_summary, interaction.guild.id),
            asyncio.to_thread(
                stats.server_user_stats, interaction.guild.id, interaction.user.id
            ),
        )
        if not rows:
            embed = _embed("top meowers", "no meows yet. be the first.")
        else:
            lines = [
                f"{index}. <@{user_id}> {count:,}"
                for index, (user_id, count) in enumerate(rows, start=1)
            ]
            embed = _embed("top meowers", "\n".join(lines))
            embed.add_field(
                name="server",
                value=(
                    f"{summary['total']:,} meows\n"
                    f"{summary['meowers']:,} meowers\n"
                    f"average {summary['average']:,.1f}"
                ),
                inline=True,
            )
            if mine["count"]:
                your_rank = (
                    f"rank {mine['rank']} of {mine['server_meowers']}\n"
                    f"{mine['count']:,} meows"
                )
            else:
                your_rank = "not ranked yet"
            embed.add_field(name="you", value=your_rank, inline=True)

        await interaction.response.send_message(
            embed=embed,
            ephemeral=hidden,
            view=VoteView(),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(
        name="totalmeows", description="total meows across all servers"
    )
    @app_commands.describe(hidden=HIDDEN_DESCRIPTION)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def totalmeows(
        self, interaction: discord.Interaction, hidden: bool = False
    ):
        summary = await asyncio.to_thread(stats.global_summary)
        embed = _embed(
            "global meows",
            f"meow bot has meowed **{summary['total']:,}** times across all servers.",
        )
        embed.add_field(name="servers", value=f"{summary['servers']:,}", inline=True)
        embed.add_field(name="meowers", value=f"{summary['meowers']:,}", inline=True)
        await interaction.response.send_message(
            embed=embed,
            ephemeral=hidden,
            view=VoteView(),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(
        name="profile", description="show a user's cross-server meow profile"
    )
    @app_commands.describe(
        user="the user to check. defaults to you.",
        hidden=HIDDEN_DESCRIPTION,
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def profile(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        hidden: bool = False,
    ):
        target = user or interaction.user
        data = await asyncio.to_thread(stats.global_user_stats, target.id)

        embed = _embed(f"meow profile for {target.display_name}")
        if data["count"] == 0:
            embed.description = "no meows yet. say meow."
        else:
            embed.description = (
                f"**{data['count']:,}** meows across "
                f"**{data['servers']:,}** servers."
            )
            best_server = "unknown"
            if data["best_guild_id"]:
                best_server = _guild_name(interaction, data["best_guild_id"])
            embed.add_field(
                name="global rank", value=f"{data['rank']}", inline=True
            )
            embed.add_field(
                name="best server",
                value=f"{best_server} ({data['best_count']:,})",
                inline=True,
            )
            embed.add_field(
                name="last meow",
                value=_last_meow(data["last_meow_at"]),
                inline=True,
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=hidden,
            view=VoteView(),
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot):
    await bot.add_cog(StatsCog(bot))
