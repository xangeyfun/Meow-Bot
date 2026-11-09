import logging
import time
from dataclasses import dataclass, field

from db import get_db
from matcher import (
    BUILTIN_TRIGGERS,
    MAX_CUSTOM_TRIGGERS,
    CustomTrigger,
    RegexValidationError,
    compile_custom,
    compile_stored,
)

logger = logging.getLogger("store")


@dataclass
class GuildConfig:
    guild_id: int
    enabled: bool
    builtin_enabled: dict[str, bool]
    custom_triggers: list[CustomTrigger] = field(default_factory=list)


class GuildConfigStore:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self._cache = {}

    def _connect(self):
        return get_db(self.db_path)

    def invalidate(self, guild_id):
        self._cache.pop(guild_id, None)

    def get(self, guild_id):
        cached = self._cache.get(guild_id)
        if cached is not None:
            return cached

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT enabled FROM guild_settings WHERE guild_id = ?", (guild_id,)
            ).fetchone()
            enabled = bool(row["enabled"]) if row is not None else True

            overrides = {
                item["trigger_key"]: bool(item["enabled"])
                for item in conn.execute(
                    "SELECT trigger_key, enabled FROM trigger_overrides WHERE guild_id = ?",
                    (guild_id,),
                )
            }

            builtin_enabled = {
                trigger.key: overrides.get(trigger.key, trigger.default_enabled)
                for trigger in BUILTIN_TRIGGERS
            }

            custom_triggers = []
            for item in conn.execute(
                "SELECT name, name_lower, pattern, enabled FROM custom_triggers "
                "WHERE guild_id = ? ORDER BY id ASC",
                (guild_id,),
            ):
                compiled = compile_stored(item["pattern"])
                if compiled is None:
                    logger.warning(
                        "Skipping invalid custom trigger %r in guild %s",
                        item["name"],
                        guild_id,
                    )
                    continue
                custom_triggers.append(
                    CustomTrigger(
                        name=item["name"],
                        name_lower=item["name_lower"],
                        pattern=item["pattern"],
                        compiled=compiled,
                        enabled=bool(item["enabled"]),
                    )
                )
        finally:
            conn.close()

        config = GuildConfig(
            guild_id=guild_id,
            enabled=enabled,
            builtin_enabled=builtin_enabled,
            custom_triggers=custom_triggers,
        )
        self._cache[guild_id] = config
        return config

    def _ensure_guild(self, conn, guild_id):
        now = int(time.time())
        conn.execute(
            "INSERT OR IGNORE INTO guild_settings (guild_id, enabled, created_at, updated_at) "
            "VALUES (?, 1, ?, ?)",
            (guild_id, now, now),
        )

    def set_enabled(self, guild_id, enabled):
        conn = self._connect()
        try:
            self._ensure_guild(conn, guild_id)
            conn.execute(
                "UPDATE guild_settings SET enabled = ?, updated_at = ? WHERE guild_id = ?",
                (int(enabled), int(time.time()), guild_id),
            )
            conn.commit()
        finally:
            conn.close()
        self.invalidate(guild_id)

    def set_trigger_enabled(self, guild_id, kind, key, enabled):
        conn = self._connect()
        try:
            self._ensure_guild(conn, guild_id)
            if kind == "builtin":
                conn.execute(
                    "INSERT INTO trigger_overrides (guild_id, trigger_key, enabled) VALUES (?, ?, ?) "
                    "ON CONFLICT(guild_id, trigger_key) DO UPDATE SET enabled = excluded.enabled",
                    (guild_id, key, int(enabled)),
                )
            elif kind == "custom":
                conn.execute(
                    "UPDATE custom_triggers SET enabled = ? WHERE guild_id = ? AND name_lower = ?",
                    (int(enabled), guild_id, key),
                )
            else:
                raise ValueError(f"unknown trigger kind: {kind}")
            conn.commit()
        finally:
            conn.close()
        self.invalidate(guild_id)

    def add_custom(self, guild_id, name, pattern, created_by=None):
        name = (name or "").strip()
        if not name:
            raise RegexValidationError("Give the trigger a name.")
        if len(name) > 32:
            raise RegexValidationError(
                "That name is too long. Keep it under 32 characters."
            )

        name_lower = name.lower()
        compile_custom(pattern)

        conn = self._connect()
        try:
            self._ensure_guild(conn, guild_id)
            count = conn.execute(
                "SELECT COUNT(*) FROM custom_triggers WHERE guild_id = ?", (guild_id,)
            ).fetchone()[0]
            if count >= MAX_CUSTOM_TRIGGERS:
                raise RegexValidationError(
                    f"This server already has {MAX_CUSTOM_TRIGGERS} custom triggers. "
                    "Remove one first."
                )

            duplicate = conn.execute(
                "SELECT 1 FROM custom_triggers WHERE guild_id = ? AND name_lower = ?",
                (guild_id, name_lower),
            ).fetchone()
            if duplicate:
                raise RegexValidationError("A trigger with that name already exists.")

            conn.execute(
                "INSERT INTO custom_triggers "
                "(guild_id, name, name_lower, pattern, enabled, created_by, created_at) "
                "VALUES (?, ?, ?, ?, 1, ?, ?)",
                (guild_id, name, name_lower, pattern.strip(), created_by, int(time.time())),
            )
            conn.commit()
        finally:
            conn.close()

        self.invalidate(guild_id)
        return name

    def remove_custom(self, guild_id, name_lower):
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM custom_triggers WHERE guild_id = ? AND name_lower = ?",
                (guild_id, name_lower),
            )
            conn.commit()
        finally:
            conn.close()
        self.invalidate(guild_id)

    def list_triggers(self, guild_id):
        config = self.get(guild_id)
        items = []
        for trigger in BUILTIN_TRIGGERS:
            items.append(
                {
                    "kind": "builtin",
                    "key": trigger.key,
                    "label": trigger.label,
                    "enabled": config.builtin_enabled[trigger.key],
                    "custom": False,
                }
            )
        for trigger in config.custom_triggers:
            items.append(
                {
                    "kind": "custom",
                    "key": trigger.name_lower,
                    "label": trigger.name,
                    "enabled": trigger.enabled,
                    "custom": True,
                }
            )
        return items

    def custom_trigger_names(self, guild_id):
        return [trigger.name for trigger in self.get(guild_id).custom_triggers]
