import logging

import discord
from discord import app_commands
from discord.ext import commands

from matcher import (
    BUILTIN_TRIGGERS,
    MAX_CUSTOM_TRIGGERS,
    MAX_NAME_LENGTH,
    MAX_PATTERN_LENGTH,
    MAX_RESPONSE_LENGTH,
    MAX_SIMPLE_LENGTH,
    RegexValidationError,
    build_simple_pattern,
)

logger = logging.getLogger("cogs.config")

COLOR = discord.Color(0xE85D2A)


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


def _format_lines(lines, limit=1024):
    if not lines:
        return "nothing"

    kept = []
    for line in lines:
        candidate = "\n".join(kept + [line])
        if len(candidate) > limit - 24 and kept:
            break
        kept.append(line)

    remaining = len(lines) - len(kept)
    value = "\n".join(kept)
    if remaining:
        value = f"{value}\nand {remaining} more"
    return value[:limit]


def _format_builtin_status(config):
    lines = []
    for trigger in BUILTIN_TRIGGERS:
        enabled = config.builtin_enabled.get(trigger.key, trigger.default_enabled)
        lines.append(f"{trigger.label}: {'on' if enabled else 'off'}")
    return "\n".join(lines)


def _format_custom_status(triggers):
    if not triggers:
        return "none yet"

    lines = []
    for trigger in triggers:
        state = "on" if trigger.enabled else "off"
        response = (trigger.response or "meow pool").replace("\n", " ")
        if len(response) > 60:
            response = response[:57] + "..."
        lines.append(f"{trigger.name} ({state}): {response}")
    return _format_lines(lines)


async def _finish_manage(
    interaction, cog, guild_id, author_id, message, old_view=None
):
    if old_view is not None:
        old_view.stop()
    view = ManageTriggersView.from_interaction(
        interaction, cog, guild_id, author_id
    )
    try:
        await interaction.response.edit_message(
            embed=cog.build_manage_embed(guild_id), view=view
        )
    except discord.HTTPException:
        logger.exception("Failed to refresh the trigger panel")
        await interaction.followup.send(
            f"{message} reopen /config to see the panel.", ephemeral=True
        )
        return
    await interaction.followup.send(message, ephemeral=True)


class AuthorView(discord.ui.View):
    def __init__(self, cog, guild_id, author_id, timeout=300):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        self.source_interaction = None
        self.source_message = None

    @classmethod
    def from_interaction(
        cls, interaction, cog, guild_id, author_id, *args, **kwargs
    ):
        view = cls(cog, guild_id, author_id, *args, **kwargs)
        view.source_interaction = interaction
        view.source_message = interaction.message
        return view

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This panel is not for you.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.source_interaction is not None:
            try:
                await self.source_interaction.edit_original_response(view=self)
                return
            except discord.HTTPException:
                pass
        if self.source_message is None:
            return
        try:
            await self.source_message.edit(view=self)
        except discord.HTTPException:
            pass

    async def show_overview(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(
            embed=self.cog.build_overview_embed(self.guild_id),
            view=ConfigView.from_interaction(
                interaction, self.cog, self.guild_id, self.author_id
            ),
        )

    async def show_manage(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(
            embed=self.cog.build_manage_embed(self.guild_id),
            view=ManageTriggersView.from_interaction(
                interaction, self.cog, self.guild_id, self.author_id
            ),
        )


class ConfigView(AuthorView):
    def __init__(self, cog, guild_id, author_id):
        super().__init__(cog, guild_id, author_id)
        enabled = cog.store.get(guild_id).enabled

        self.add_item(ManageTriggersButton(cog, guild_id, author_id))
        self.add_item(BotToggleButton(cog, guild_id, author_id, enabled))
        self.add_item(CloseButton(cog, guild_id, author_id))

    async def refresh(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(
            embed=self.cog.build_overview_embed(self.guild_id),
            view=ConfigView.from_interaction(
                interaction, self.cog, self.guild_id, self.author_id
            ),
        )


class ManageTriggersView(AuthorView):
    def __init__(self, cog, guild_id, author_id):
        super().__init__(cog, guild_id, author_id)
        items = cog.store.list_triggers(guild_id)
        builtins = [item for item in items if item["kind"] == "builtin"]
        customs = [item for item in items if item["kind"] == "custom"][:25]
        at_limit = len(customs) >= MAX_CUSTOM_TRIGGERS

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
        self.add_item(AddTriggerButton(cog, guild_id, author_id, at_limit))
        self.add_item(EditTriggerButton(cog, guild_id, author_id, not customs))
        self.add_item(RemoveTriggerButton(cog, guild_id, author_id, not customs))
        self.add_item(OverviewButton(cog, guild_id, author_id))
        self.add_item(CloseButton(cog, guild_id, author_id))

    async def refresh(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(
            embed=self.cog.build_manage_embed(self.guild_id),
            view=ManageTriggersView.from_interaction(
                interaction, self.cog, self.guild_id, self.author_id
            ),
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
                    description=(
                        "on, pick to turn off"
                        if item["enabled"]
                        else "off, pick to turn on"
                    ),
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


class ManageTriggersButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="manage triggers", style=discord.ButtonStyle.primary, row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.show_manage(interaction)


class AddTriggerButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id, disabled=False):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="add trigger",
            style=discord.ButtonStyle.primary,
            row=2,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.stop()
        view = AddTriggerView.from_interaction(
            interaction, self.cog, self.guild_id, self.author_id
        )
        await interaction.response.edit_message(
            embed=self.cog.build_add_embed(), view=view
        )


class EditTriggerButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id, disabled=False):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="edit trigger",
            style=discord.ButtonStyle.secondary,
            row=2,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        names = self.cog.store.custom_trigger_names(self.guild_id)
        if not names:
            await interaction.response.send_message(
                "No custom triggers to edit.", ephemeral=True
            )
            return
        self.view.stop()
        view = EditTriggerView.from_interaction(
            interaction, self.cog, self.guild_id, self.author_id
        )
        await interaction.response.edit_message(
            embed=self.cog.build_edit_embed(names), view=view
        )


class RemoveTriggerButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id, disabled=False):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="remove trigger",
            style=discord.ButtonStyle.secondary,
            row=2,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        names = self.cog.store.custom_trigger_names(self.guild_id)
        if not names:
            await interaction.response.send_message(
                "No custom triggers to remove.", ephemeral=True
            )
            return
        self.view.stop()
        view = RemoveTriggerView.from_interaction(
            interaction, self.cog, self.guild_id, self.author_id
        )
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
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.enabled:
            self.view.stop()
            view = ConfirmBotOffView.from_interaction(
                interaction, self.cog, self.guild_id, self.author_id
            )
            await interaction.response.edit_message(
                embed=self.cog.build_confirm_bot_off_embed(), view=view
            )
            return
        self.cog.store.set_enabled(self.guild_id, True)
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
        self.view.stop()
        await interaction.response.edit_message(
            content="closed.", embed=None, view=None
        )


class ConfirmBotOffView(AuthorView):
    def __init__(self, cog, guild_id, author_id):
        super().__init__(cog, guild_id, author_id)
        self.add_item(ConfirmBotOffButton(cog, guild_id, author_id))
        self.add_item(CancelBotOffButton(cog, guild_id, author_id))


class ConfirmBotOffButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="turn off", style=discord.ButtonStyle.danger, row=0
        )

    async def callback(self, interaction: discord.Interaction):
        self.cog.store.set_enabled(self.guild_id, False)
        await self.view.show_overview(interaction)
        await interaction.followup.send("bot turned off.", ephemeral=True)


class CancelBotOffButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="cancel", style=discord.ButtonStyle.secondary, row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.show_overview(interaction)


class AddTriggerView(AuthorView):
    def __init__(self, cog, guild_id, author_id):
        super().__init__(cog, guild_id, author_id)
        self.add_item(SimpleAddButton(cog, guild_id, author_id))
        self.add_item(AdvancedAddButton(cog, guild_id, author_id))
        self.add_item(BackButton(cog, guild_id, author_id, row=0))


class SimpleAddButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="simple", style=discord.ButtonStyle.primary, row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            SimpleTriggerModal(
                self.cog, self.guild_id, self.author_id, parent_view=self.view
            )
        )


class AdvancedAddButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="advanced", style=discord.ButtonStyle.secondary, row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            AdvancedTriggerModal(
                self.cog, self.guild_id, self.author_id, parent_view=self.view
            )
        )


class SimpleTriggerModal(discord.ui.Modal):
    def __init__(self, cog, guild_id, author_id, trigger=None, parent_view=None):
        editing = trigger is not None
        super().__init__(
            title="edit simple trigger" if editing else "add simple trigger"
        )
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        self.trigger = trigger
        self.parent_view = parent_view

        self.trigger_input = discord.ui.TextInput(
            label="phrase to watch for",
            placeholder="mrrp",
            max_length=MAX_SIMPLE_LENGTH,
            default=(trigger.simple_text or trigger.name) if editing else None,
        )
        self.response_input = discord.ui.TextInput(
            label="bot reply",
            placeholder="mrrp back :3",
            max_length=MAX_RESPONSE_LENGTH,
            style=discord.TextStyle.paragraph,
            default=trigger.response if editing else None,
        )
        self.add_item(self.trigger_input)
        self.add_item(self.response_input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This panel is not for you.", ephemeral=True
            )
            return

        phrase = self.trigger_input.value.strip()
        try:
            pattern = build_simple_pattern(phrase)
            if self.trigger is None:
                name = self.cog.store.add_custom(
                    self.guild_id,
                    phrase,
                    pattern,
                    self.response_input.value,
                    simple_text=phrase,
                    created_by=interaction.user.id,
                )
                message = f"added {name}."
            else:
                name = self.cog.store.update_custom(
                    self.guild_id,
                    self.trigger.name_lower,
                    phrase,
                    pattern,
                    self.response_input.value,
                    simple_text=phrase,
                )
                message = f"saved {name}."
        except RegexValidationError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await _finish_manage(
            interaction,
            self.cog,
            self.guild_id,
            self.author_id,
            message,
            old_view=self.parent_view,
        )


class AdvancedTriggerModal(discord.ui.Modal):
    def __init__(self, cog, guild_id, author_id, trigger=None, parent_view=None):
        editing = trigger is not None
        super().__init__(
            title="edit advanced trigger" if editing else "add advanced trigger"
        )
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        self.trigger = trigger
        self.parent_view = parent_view

        self.name_input = discord.ui.TextInput(
            label="name",
            placeholder="mrrp",
            max_length=MAX_NAME_LENGTH,
            default=trigger.name if editing else None,
        )
        self.pattern_input = discord.ui.TextInput(
            label="regex",
            placeholder="^(mrr+p)+$",
            max_length=MAX_PATTERN_LENGTH,
            default=trigger.pattern if editing else None,
        )
        self.response_input = discord.ui.TextInput(
            label="bot reply",
            placeholder="mrrp back :3",
            max_length=MAX_RESPONSE_LENGTH,
            style=discord.TextStyle.paragraph,
            default=trigger.response if editing else None,
        )
        self.add_item(self.name_input)
        self.add_item(self.pattern_input)
        self.add_item(self.response_input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This panel is not for you.", ephemeral=True
            )
            return

        try:
            if self.trigger is None:
                name = self.cog.store.add_custom(
                    self.guild_id,
                    self.name_input.value,
                    self.pattern_input.value,
                    self.response_input.value,
                    created_by=interaction.user.id,
                )
                message = f"added {name}."
            else:
                name = self.cog.store.update_custom(
                    self.guild_id,
                    self.trigger.name_lower,
                    self.name_input.value,
                    self.pattern_input.value,
                    self.response_input.value,
                )
                message = f"saved {name}."
        except RegexValidationError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await _finish_manage(
            interaction,
            self.cog,
            self.guild_id,
            self.author_id,
            message,
            old_view=self.parent_view,
        )


class EditTriggerView(AuthorView):
    def __init__(self, cog, guild_id, author_id):
        super().__init__(cog, guild_id, author_id)
        items = [
            item
            for item in cog.store.list_triggers(guild_id)
            if item["kind"] == "custom"
        ][:25]
        if items:
            self.add_item(EditTriggerSelect(cog, guild_id, author_id, items))
        self.add_item(BackButton(cog, guild_id, author_id, row=1))


class EditTriggerSelect(discord.ui.Select):
    def __init__(self, cog, guild_id, author_id, items):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        options = [
            discord.SelectOption(
                label=item["label"][:100],
                value=item["key"],
                description="simple mode" if item["simple"] else "regex mode",
            )
            for item in items
        ]
        super().__init__(
            placeholder="pick a trigger to edit",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        name_lower = self.values[0]
        trigger = self.cog.store.get_custom(self.guild_id, name_lower)
        if trigger is None:
            await interaction.response.send_message(
                "That trigger is gone.", ephemeral=True
            )
            return

        if trigger.simple_text is not None:
            modal = SimpleTriggerModal(
                self.cog,
                self.guild_id,
                self.author_id,
                trigger,
                parent_view=self.view,
            )
        else:
            modal = AdvancedTriggerModal(
                self.cog,
                self.guild_id,
                self.author_id,
                trigger,
                parent_view=self.view,
            )
        await interaction.response.send_modal(modal)


class RemoveTriggerView(AuthorView):
    def __init__(self, cog, guild_id, author_id):
        super().__init__(cog, guild_id, author_id)
        names = cog.store.custom_trigger_names(guild_id)
        if names:
            self.add_item(RemoveTriggerSelect(cog, guild_id, author_id, names))
        self.add_item(BackButton(cog, guild_id, author_id, row=1))


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
        trigger = self.cog.store.get_custom(self.guild_id, name_lower)
        response = trigger.response if trigger is not None else None
        self.view.stop()
        view = ConfirmRemoveView.from_interaction(
            interaction, self.cog, self.guild_id, self.author_id, name_lower, display
        )
        await interaction.response.edit_message(
            embed=self.cog.build_confirm_remove_embed(display, response), view=view
        )


class OverviewButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="back", style=discord.ButtonStyle.secondary, row=3
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.show_overview(interaction)


class BackButton(discord.ui.Button):
    def __init__(self, cog, guild_id, author_id, row=1):
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        super().__init__(
            label="back", style=discord.ButtonStyle.secondary, row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.show_manage(interaction)


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
        await _finish_manage(
            interaction,
            self.cog,
            self.guild_id,
            self.author_id,
            f"removed {self.display_name}.",
            old_view=self.view,
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
        await self.view.show_manage(interaction)


class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = bot.config_store

    def build_overview_embed(self, guild_id):
        config = self.store.get(guild_id)

        embed = discord.Embed(
            title="meow bot settings",
            description="server settings. only people with manage server can change these.",
            color=COLOR,
        )
        embed.add_field(
            name="status", value="on" if config.enabled else "off", inline=True
        )
        embed.add_field(
            name="custom triggers",
            value=f"{len(config.custom_triggers)} of {MAX_CUSTOM_TRIGGERS}",
            inline=True,
        )
        embed.add_field(
            name="built in",
            value=_format_builtin_status(config),
            inline=False,
        )
        embed.add_field(
            name="custom",
            value=_format_custom_status(config.custom_triggers),
            inline=False,
        )
        embed.set_footer(
            text="open manage triggers to add, edit, or remove custom triggers."
        )
        return embed

    def build_manage_embed(self, guild_id):
        config = self.store.get(guild_id)

        embed = discord.Embed(
            title="manage triggers",
            description=(
                "turn triggers on or off, or add, edit, and remove custom triggers. "
                "simple mode is best for most servers. advanced mode takes regex."
            ),
            color=COLOR,
        )
        embed.add_field(
            name="built in",
            value=_format_builtin_status(config),
            inline=False,
        )
        embed.add_field(
            name=f"custom triggers ({len(config.custom_triggers)} of {MAX_CUSTOM_TRIGGERS})",
            value=_format_custom_status(config.custom_triggers),
            inline=False,
        )
        embed.set_footer(text="custom triggers reply with their own message.")
        return embed

    def build_add_embed(self):
        embed = discord.Embed(
            title="add a trigger",
            description="pick simple for a word or phrase and a reply.",
            color=COLOR,
        )
        embed.add_field(
            name="simple",
            value=(
                "type a word or phrase and the reply. "
                "the bot answers when a message contains that phrase."
            ),
            inline=False,
        )
        embed.add_field(
            name="advanced",
            value="write a regex and the reply. for exact control.",
            inline=False,
        )
        return embed

    def build_edit_embed(self, names):
        embed = discord.Embed(
            title="edit a custom trigger",
            description="pick one. simple triggers open the simple editor. "
            "advanced triggers open the regex editor.",
            color=COLOR,
        )
        embed.add_field(
            name="custom triggers", value=_format_labels(names), inline=False
        )
        return embed

    def build_remove_embed(self, names):
        embed = discord.Embed(
            title="remove a custom trigger",
            description="pick one. this cannot be undone.",
            color=COLOR,
        )
        embed.add_field(
            name="custom triggers", value=_format_labels(names), inline=False
        )
        return embed

    def build_confirm_remove_embed(self, display_name, response=None):
        embed = discord.Embed(
            title="remove a custom trigger",
            description=f"remove {display_name}?",
            color=COLOR,
        )
        if response:
            value = response.replace("\n", " ")
            if len(value) > 200:
                value = value[:197] + "..."
            embed.add_field(name="reply", value=value, inline=False)
        return embed

    def build_confirm_bot_off_embed(self):
        return discord.Embed(
            title="turn the bot off?",
            description=(
                "meow bot will stop replying in this server. "
                "you can turn it back on from /config."
            ),
            color=discord.Color.red(),
        )

    @app_commands.command(name="config", description="open server settings")
    @app_commands.describe(hidden="only show the panel to you")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def config(
        self, interaction: discord.Interaction, hidden: bool = False
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Use this in a server.", ephemeral=hidden
            )
            return
        view = ConfigView(self, interaction.guild.id, interaction.user.id)
        view.source_interaction = interaction
        await interaction.response.send_message(
            embed=self.build_overview_embed(interaction.guild.id),
            view=view,
            ephemeral=hidden,
        )


async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
