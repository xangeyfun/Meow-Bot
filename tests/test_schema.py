from db import get_db
from schema import create_schema


def test_migrates_custom_triggers_columns(tmp_path):
    path = tmp_path / "old.db"
    conn = get_db(str(path))
    conn.execute(
        """
        CREATE TABLE custom_triggers (
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
    conn.execute(
        "INSERT INTO custom_triggers "
        "(guild_id, name, name_lower, pattern, enabled, created_at) "
        "VALUES (1, 'mrrp', 'mrrp', '^mrrp$', 1, 0)"
    )
    conn.commit()

    create_schema(conn)

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(custom_triggers)")}
    assert "response" in columns
    assert "simple_text" in columns

    row = conn.execute(
        "SELECT response, simple_text FROM custom_triggers WHERE name_lower = 'mrrp'"
    ).fetchone()
    assert row["response"] == ""
    assert row["simple_text"] is None
    conn.close()
