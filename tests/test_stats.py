import sqlite3
import time

import pytest

from db import get_db
from stats import (
    StatsBuffer,
    bot_started,
    flush_buffer,
    format_uptime,
    global_total,
    refresh_user_count,
    server_leaderboard,
    user_stats,
    website_stats,
    write_heartbeat,
)


def test_readonly_missing_database(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        get_db(str(path), readonly=True)
    assert not path.exists()


def test_buffer_record_and_clear():
    buffer = StatsBuffer()
    buffer.record(1, 10)
    buffer.record(1, 10)
    buffer.record(2, 20)
    counts, guilds, total = buffer.snapshot()
    assert counts == {(1, 10): 2, (2, 20): 1}
    assert guilds == {1: 2, 2: 1}
    assert total == 3
    buffer.clear(counts, guilds, total)
    counts, guilds, total = buffer.snapshot()
    assert counts == {}
    assert guilds == {}
    assert total == 0


def test_flush_buffer(schema):
    buffer = StatsBuffer()
    buffer.record(1, 10)
    buffer.record(1, 10)
    buffer.record(2, 20)
    assert flush_buffer(buffer, str(schema)) is True
    assert buffer.snapshot() == ({}, {}, 0)

    conn = get_db(str(schema), readonly=True)
    try:
        row = conn.execute(
            "SELECT count FROM meow_counts WHERE guild_id = 1 AND user_id = 10"
        ).fetchone()
        assert row["count"] == 2
        row = conn.execute(
            "SELECT total_meows FROM guild_stats WHERE guild_id = 1"
        ).fetchone()
        assert row["total_meows"] == 2
        row = conn.execute(
            "SELECT total_meows FROM bot_stats WHERE id = 1"
        ).fetchone()
        assert row["total_meows"] == 3
    finally:
        conn.close()


def test_flush_empty_buffer(schema):
    buffer = StatsBuffer()
    assert flush_buffer(buffer, str(schema)) is True
    assert buffer.snapshot() == ({}, {}, 0)


def test_user_stats_and_leaderboard(schema):
    buffer = StatsBuffer()
    for _ in range(5):
        buffer.record(1, 10)
    for _ in range(3):
        buffer.record(1, 20)
    buffer.record(1, 30)
    flush_buffer(buffer, str(schema))

    count, rank, server_total = user_stats(1, 10, str(schema))
    assert count == 5
    assert rank == 1
    assert server_total == 9

    count, rank, server_total = user_stats(1, 20, str(schema))
    assert count == 3
    assert rank == 2
    assert server_total == 9

    count, rank, server_total = user_stats(1, 30, str(schema))
    assert count == 1
    assert rank == 3
    assert server_total == 9

    count, rank, server_total = user_stats(1, 99, str(schema))
    assert count == 0
    assert rank == 0
    assert server_total == 9

    rows = server_leaderboard(1, limit=2, db_path=str(schema))
    assert rows == [(10, 5), (20, 3)]


def test_global_total(schema):
    buffer = StatsBuffer()
    buffer.record(1, 10)
    buffer.record(2, 20)
    flush_buffer(buffer, str(schema))
    assert global_total(str(schema)) == 2


def test_heartbeat_and_started(schema):
    now = int(time.time())
    bot_started(str(schema))
    write_heartbeat(4, str(schema))
    data = website_stats(str(schema))
    assert data["total_guilds"] == 4
    assert data["online"] is True
    assert data["started_at"] >= now
    assert data["last_heartbeat"] >= now
    assert data["uptime_seconds"] >= 0


def test_website_stats_offline(schema):
    conn = get_db(str(schema))
    conn.execute(
        "UPDATE bot_stats SET started_at = ?, last_heartbeat = ? WHERE id = 1",
        (100, 100),
    )
    conn.commit()
    conn.close()

    data = website_stats(str(schema))
    assert data["online"] is False
    assert data["uptime_seconds"] == 0


def test_website_stats_without_row(schema):
    conn = get_db(str(schema))
    conn.execute("DELETE FROM bot_stats")
    conn.commit()
    conn.close()

    data = website_stats(str(schema))
    assert data["total_meows"] == 0
    assert data["total_guilds"] == 0
    assert data["online"] is False


def test_refresh_user_count(schema):
    buffer = StatsBuffer()
    buffer.record(1, 10)
    buffer.record(1, 20)
    buffer.record(2, 20)
    flush_buffer(buffer, str(schema))

    refresh_user_count(str(schema))
    data = website_stats(str(schema))
    assert data["total_users"] == 2


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "0s"),
        (1, "1s"),
        (60, "1m"),
        (65, "1m"),
        (3600, "1h"),
        (3661, "1h 1m"),
        (86400, "1d"),
        (90061, "1d 1h 1m"),
    ],
)
def test_format_uptime(seconds, expected):
    assert format_uptime(seconds) == expected
