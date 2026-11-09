def create_schema(conn):
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            created_at INTEGER,
            updated_at INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trigger_overrides (
            guild_id INTEGER NOT NULL,
            trigger_key TEXT NOT NULL,
            enabled BOOLEAN NOT NULL,
            PRIMARY KEY (guild_id, trigger_key)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_lower TEXT NOT NULL,
            pattern TEXT NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            created_by INTEGER,
            created_at INTEGER NOT NULL,
            UNIQUE (guild_id, name_lower)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meow_counts (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            last_meow_at INTEGER,
            PRIMARY KEY (guild_id, user_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_stats (
            guild_id INTEGER PRIMARY KEY,
            total_meows INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            total_meows INTEGER NOT NULL DEFAULT 0,
            total_guilds INTEGER NOT NULL DEFAULT 0,
            total_users INTEGER NOT NULL DEFAULT 0,
            started_at INTEGER,
            last_heartbeat INTEGER
        )
        """
    )

    cur.execute(
        "INSERT OR IGNORE INTO bot_stats (id, total_meows, total_guilds, total_users) VALUES (1, 0, 0, 0)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_meow_counts_guild_count ON meow_counts(guild_id, count DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_custom_triggers_guild ON custom_triggers(guild_id)"
    )

    conn.commit()
