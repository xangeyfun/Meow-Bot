import logging

import discord
from discord import app_commands
from discord.ext import commands

from matcher import MAX_CUSTOM_TRIGGERS, RegexValidationError

logger = logging.getLogger("cogs.config")


def _format_labels(labels):
    if not labels:
        return "nothing"

    value = ", ".join(labels)
    if len(value) <= 1024:
        return value

    kept = []
    for label in labels:
        candidate = ", ".join(kept + [label])
        if len(candidate) > 980:
            break
        kept.append(label)

    remaining = len(labels) - len(kept)
    if remaining and kept:
        value = f"{', '.join(kept)}, and {remaining} more"
    elif remaining:
        value = f"{remaining} triggers"
    else:
        value = ", ".join(kept)
    return value[:1024]


class AuthorView(discord.ui.View):
    def __init__(self, cog, guild_id, author_id, timeout=300):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This panel is not for you.", ephemeral=True
            )
            return False
        return True

    async def back_to_panel(self, interaction: discord.Interaction):
        view = ConfigView(self.cog, self.guild_id, self.author_id)
        await interaction.response.edit_message(
            embed=self.cog.build_embed(self.guild_id), view=view
        )


class ConfigView(AuthorView):
    def __init__(self, cog, guild_id, author_id):
        super().__init__(cog, guild_id, author_id)
        items = cog.store.list_triggers(guild_id)
        builtins = [item for item in items if item["kind"] == "builtin"]
        customs = [item for item in items if item["kind"] == "custom"][:25]
        enabled = cog.store.get(guild_id).enabled

        self.add_item(
            TriggerToggleSelect(
                cog,
                guild_id,
                author_id,
                builtins,
                "toggle a built in trigger",
                row=0,
            )
        )
        if customs:
            self.add_item(
                TriggerToggleSelect(
                    cog,
                    guild_id,
                    author_id,
                    customs,
                    "toggle a custom trigger",
                    row=1,
                )
            )
        self.add_item(AddTriggerButton(cog, guild_id, author_id))
        self.add_item(RemoveTriggerButton(cog, guild_id, author_id))
        self.add_item(BotToggleButton(cog, guild_id, author_id, enabled))
        self.add_item(CloseButton(cog, guild_id, author_id))

    async def refresh(self, interaction: discord.Interaction):
        view = ConfigView(self.cog, self.guild_id, self.author_id)
        await interaction.response.edit_message(
            embed=self.cog.build_embed(self.guild_id), view=view
        )


class TriggerToggleSelect(discord.ui.Select):
    def __init__(self, cog, guild_id, author_id, items, placeholder, row):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        options = []
        for item in items:
            label = f"{item['label']} (custom)" if item["custom"] else item["label"]
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=f"{item['kind']}:{item['key']}",
                    description="enabled" if item["enabled"] else "disabled",
                )
            )
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        kind, key = self.values[0].split(":", 1)
        items = self.cog.store.list_triggers(self.guild_id)
        current = next(
            (
                item
                for item in items
                if item["kind"] == kind and item["key"] == key
            ),
            None,
        )
        if current is None:
            await interaction.response.send_message(
                "That trigger is gone.", ephemeral=True
            )
            return

        self.cog.store.set_trigger_enabled(
            self.guild_id, kind, key, not current["enabled"]
        )
        await self.view.refresh(interaction)


class AddTriggerButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="add trigger", style=discord.ButtonStyle.primary, row=2
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            AddTriggerModal(self.cog, self.guild_id, self.author_id)
        )


class RemoveTriggerButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="remove trigger", style=discord.ButtonStyle.secondary, row=2
        )

    async def callback(self, interaction: discord.Interaction):
        names = self.cog.store.custom_trigger_names(self.guild_id)
        if not names:
            await interaction.response.send_message(
                "No custom triggers to remove.", ephemeral=True
            )
            return
        view = RemoveTriggerView(self.cog, self.guild_id, self.author_id)
        await interaction.response.edit_message(
            embed=self.cog.build_remove_embed(names), view=view
        )


class BotToggleButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id, enabled):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        self.enabled = enabled
        super().__init__(
            label="turn bot off" if enabled else "turn bot on",
            style=(
                discord.ButtonStyle.danger
                if enabled
                else discord.ButtonStyle.success
            ),
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        self.cog.store.set_enabled(self.guild_id, not self.enabled)
        await self.view.refresh(interaction)


class CloseButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="close", style=discord.ButtonStyle.secondary, row=3
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="closed.", embed=None, view=None
        )


class AddTriggerModal(discord.ui.Modal, title="add trigger"):
    name = discord.ui.TextInput(
        label="name", placeholder="mrrp", max_length=32
    )
    pattern = discord.ui.TextInput(
        label="regex", placeholder="^(mrr+p)+$", max_length=200
    )

    def __init__(self, cog, guild_id, author_id):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This panel is not for you.", ephemeral=True
            )
            return

        try:
            name = self.cog.store.add_custom(
                self.guild_id, self.name.value, self.pattern.value, interaction.user.id
            )
        except RegexValidationError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        view = ConfigView(self.cog, self.guild_id, self.author_id)
        try:
            await interaction.response.edit_message(
                embed=self.cog.build_embed(self.guild_id), view=view
            )
        except discord.HTTPException:
            logger.exception("Failed to refresh config panel after adding a trigger")
            await interaction.followup.send(
                f"added {name}. reopen /config to see the panel.", ephemeral=True
            )
            return
        await interaction.followup.send(f"added {name}.", ephemeral=True)


class RemoveTriggerView(AuthorView):
    def __init__(self, cog, guild_id, author_id):
        super().__init__(cog, guild_id, author_id)
        names = cog.store.custom_trigger_names(guild_id)
        if names:
            self.add_item(RemoveTriggerSelect(cog, guild_id, author_id, names))
        self.add_item(BackButton(cog, guild_id, author_id))


class RemoveTriggerSelect(discord.ui.Select):
    def __init__(self, cog, guild_id, author_id, names):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        options = [
            discord.SelectOption(label=name[:100], value=name.lower())
            for name in names[:25]
        ]
        super().__init__(
            placeholder="pick a trigger to remove",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        name_lower = self.values[0]
        names = self.cog.store.custom_trigger_names(self.guild_id)
        display = next(
            (name for name in names if name.lower() == name_lower), name_lower
        )
        view = ConfirmRemoveView(
            self.cog, self.guild_id, self.author_id, name_lower, display
        )
        await interaction.response.edit_message(
            embed=self.cog.build_confirm_remove_embed(display), view=view
        )


class BackButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="back", style=discord.ButtonStyle.secondary, row=1
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.back_to_panel(interaction)


class ConfirmRemoveView(AuthorView):
    def __init__(self, cog, guild_id, author_id, name_lower, display_name):
        super().__init__(cog, guild_id, author_id)
        self.name_lower = name_lower
        self.display_name = display_name
        self.add_item(
            DeleteTriggerButton(
                cog, guild_id, author_id, name_lower, display_name
            )
        )
        self.add_item(CancelButton(cog, guild_id, author_id))


class DeleteTriggerButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id, name_lower, display_name):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        self.name_lower = name_lower
        self.display_name = display_name
        super().__init__(
            label="remove", style=discord.ButtonStyle.danger, row=0
        )

    async def callback(self, interaction: discord.Interaction):
        self.cog.store.remove_custom(self.guild_id, self.name_lower)
        await self.view.back_to_panel(interaction)
        await interaction.followup.send(
            f"removed {self.display_name}.", ephemeral=True
        )


class CancelButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="cancel", style=discord.ButtonStyle.secondary, row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.back_to_panel(interaction)


class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = bot.config_store

    def build_embed(self, guild_id):
        config = self.store.get(guild_id)
        items = self.store.list_triggers(guild_id)

        on = []
        off = []
        for item in items:
            label = f"{item['label']} (custom)" if item["custom"] else item["label"]
            if item["enabled"]:
                on.append(label)
            else:
                off.append(label)

        embed = discord.Embed(
            title="meow bot settings",
            description="server settings. only people with manage server can change these.",
            color=discord.Color(0xE85D2A),
        )
        embed.add_field(
            name="status", value="on" if config.enabled else "off", inline=True
        )
        embed.add_field(
            name="custom regex",
            value=f"{len(config.custom_triggers)} of {MAX_CUSTOM_TRIGGERS}",
            inline=True,
        )
        embed.add_field(name="on", value=_format_labels(on), inline=False)
        embed.add_field(name="off", value=_format_labels(off), inline=False)
        embed.set_footer(text="regex is tested before it is saved.")
        return embed

    def build_remove_embed(self, names):
        embed = discord.Embed(
            title="remove a custom trigger",
            description="pick one. this cannot be undone.",
            color=discord.Color(0xE85D2A),
        )
        embed.add_field(
            name="custom triggers", value=_format_labels(names), inline=False
        )
        return embed

    def build_confirm_remove_embed(self, display_name):
        return discord.Embed(
            title="remove a custom trigger",
            description=f"remove {display_name}?",
            color=discord.Color(0xE85D2A),
        )

    @app_commands.command(name="config", description="open server settings")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def config(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Use this in a server.", ephemeral=True
            )
            return
        view = ConfigView(self, interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(
            embed=self.build_embed(interaction.guild.id),
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
