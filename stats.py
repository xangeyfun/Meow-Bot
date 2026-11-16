import collections
import logging
import threading
import time

from db import get_db

logger = logging.getLogger("stats")
_flush_lock = threading.Lock()


class StatsBuffer:
    def __init__(self):
        self.counts = collections.Counter()
        self.guild_totals = collections.Counter()
        self.total = 0
        self._lock = threading.Lock()

    def record(self, guild_id, user_id):
        with self._lock:
            self.counts[(guild_id, user_id)] += 1
            self.guild_totals[guild_id] += 1
            self.total += 1

    def snapshot(self):
        with self._lock:
            return dict(self.counts), dict(self.guild_totals), self.total

    def clear(self, counts, guild_totals, total):
        with self._lock:
            for key, value in counts.items():
                self.counts[key] -= value
                if self.counts[key] <= 0:
                    self.counts.pop(key, None)
            for key, value in guild_totals.items():
                self.guild_totals[key] -= value
                if self.guild_totals[key] <= 0:
                    self.guild_totals.pop(key, None)
            self.total -= total


def flush_buffer(buffer, db_path=None):
    with _flush_lock:
        counts, guild_totals, total = buffer.snapshot()
        if not counts and not guild_totals and not total:
            return True

        now = int(time.time())
        conn = get_db(db_path)
        try:
            conn.executemany(
                "INSERT INTO meow_counts (guild_id, user_id, count, last_meow_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET "
                "count = count + excluded.count, last_meow_at = excluded.last_meow_at",
                [
                    (guild_id, user_id, count, now)
                    for (guild_id, user_id), count in counts.items()
                ],
            )
            conn.executemany(
                "INSERT INTO guild_stats (guild_id, total_meows) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET "
                "total_meows = total_meows + excluded.total_meows",
                [(guild_id, count) for guild_id, count in guild_totals.items()],
            )
            conn.execute(
                "UPDATE bot_stats SET total_meows = total_meows + ? WHERE id = 1", (total,)
            )
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Failed to flush meow stats")
            return False
        finally:
            conn.close()

        buffer.clear(counts, guild_totals, total)
        return True


def write_heartbeat(guild_count, db_path=None):
    conn = get_db(db_path)
    try:
        conn.execute(
            "UPDATE bot_stats SET last_heartbeat = ?, total_guilds = ? WHERE id = 1",
            (int(time.time()), int(guild_count)),
        )
        conn.commit()
    finally:
        conn.close()


def bot_started(db_path=None):
    now = int(time.time())
    conn = get_db(db_path)
    try:
        conn.execute(
            "UPDATE bot_stats SET started_at = ?, last_heartbeat = ? WHERE id = 1",
            (now, now),
        )
        conn.commit()
    finally:
        conn.close()


def refresh_user_count(db_path=None):
    conn = get_db(db_path)
    try:
        total = conn.execute("SELECT COUNT(DISTINCT user_id) FROM meow_counts").fetchone()[0]
        conn.execute("UPDATE bot_stats SET total_users = ? WHERE id = 1", (total,))
        conn.commit()
    finally:
        conn.close()


def server_user_stats(guild_id, user_id, db_path=None):
    conn = get_db(db_path, readonly=True)
    try:
        row = conn.execute(
            "SELECT count, last_meow_at FROM meow_counts "
            "WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        count = row["count"] if row else 0
        last_meow_at = row["last_meow_at"] if row else None

        server_row = conn.execute(
            "SELECT total_meows FROM guild_stats WHERE guild_id = ?", (guild_id,)
        ).fetchone()
        server_total = server_row["total_meows"] if server_row else 0
        server_meowers = conn.execute(
            "SELECT COUNT(*) FROM meow_counts WHERE guild_id = ?", (guild_id,)
        ).fetchone()[0]

        rank = 0
        if count:
            rank = (
                conn.execute(
                    "SELECT COUNT(*) FROM meow_counts WHERE guild_id = ? AND count > ?",
                    (guild_id, count),
                ).fetchone()[0]
                + 1
            )

        share = (count / server_total * 100) if server_total else 0.0
        return {
            "count": count,
            "rank": rank,
            "server_total": server_total,
            "server_meowers": server_meowers,
            "share": share,
            "last_meow_at": last_meow_at,
        }
    finally:
        conn.close()


def global_user_stats(user_id, db_path=None):
    conn = get_db(db_path, readonly=True)
    try:
        rows = conn.execute(
            "SELECT guild_id, count, last_meow_at FROM meow_counts "
            "WHERE user_id = ? ORDER BY count DESC, last_meow_at ASC",
            (user_id,),
        ).fetchall()
        count = sum(row["count"] for row in rows)
        best = rows[0] if rows else None
        last_meow_at = max(
            (row["last_meow_at"] for row in rows if row["last_meow_at"] is not None),
            default=None,
        )

        rank = 0
        if count:
            rank = (
                conn.execute(
                    "SELECT COUNT(*) + 1 FROM ("
                    "SELECT user_id, SUM(count) AS total FROM meow_counts "
                    "GROUP BY user_id"
                    ") WHERE total > ?",
                    (count,),
                ).fetchone()[0]
            )

        return {
            "count": count,
            "rank": rank,
            "servers": len(rows),
            "best_guild_id": best["guild_id"] if best else None,
            "best_count": best["count"] if best else 0,
            "last_meow_at": last_meow_at,
        }
    finally:
        conn.close()


def server_summary(guild_id, db_path=None):
    conn = get_db(db_path, readonly=True)
    try:
        row = conn.execute(
            "SELECT total_meows FROM guild_stats WHERE guild_id = ?", (guild_id,)
        ).fetchone()
        total = row["total_meows"] if row else 0
        meowers = conn.execute(
            "SELECT COUNT(*) FROM meow_counts WHERE guild_id = ?", (guild_id,)
        ).fetchone()[0]
        average = total / meowers if meowers else 0.0
        return {"total": total, "meowers": meowers, "average": average}
    finally:
        conn.close()


def global_summary(db_path=None):
    conn = get_db(db_path, readonly=True)
    try:
        row = conn.execute(
            "SELECT total_meows, total_guilds, total_users FROM bot_stats WHERE id = 1"
        ).fetchone()
        total = row["total_meows"] if row else 0
        servers = row["total_guilds"] if row else 0
        meowers = row["total_users"] if row else 0
        return {
            "total": total,
            "servers": servers,
            "meowers": meowers,
            "per_server": total / servers if servers else 0.0,
            "per_meower": total / meowers if meowers else 0.0,
        }
    finally:
        conn.close()


def server_leaderboard(guild_id, limit=10, db_path=None):
    conn = get_db(db_path, readonly=True)
    try:
        rows = conn.execute(
            "SELECT user_id, count FROM meow_counts WHERE guild_id = ? "
            "ORDER BY count DESC, last_meow_at ASC LIMIT ?",
            (guild_id, limit),
        ).fetchall()
        return [(row["user_id"], row["count"]) for row in rows]
    finally:
        conn.close()


def global_total(db_path=None):
    conn = get_db(db_path, readonly=True)
    try:
        row = conn.execute("SELECT total_meows FROM bot_stats WHERE id = 1").fetchone()
        return row["total_meows"] if row else 0
    finally:
        conn.close()


def website_stats(db_path=None):
    now = int(time.time())
    conn = get_db(db_path, readonly=True)
    try:
        row = conn.execute(
            "SELECT total_meows, total_guilds, total_users, started_at, last_heartbeat "
            "FROM bot_stats WHERE id = 1"
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {
            "total_meows": 0,
            "total_guilds": 0,
            "total_users": 0,
            "started_at": None,
            "last_heartbeat": None,
            "online": False,
            "uptime_seconds": 0,
        }

    last_heartbeat = row["last_heartbeat"]
    started_at = row["started_at"]
    online = bool(last_heartbeat and now - last_heartbeat <= 90)
    uptime_seconds = max(0, now - started_at) if started_at and online else 0

    return {
        "total_meows": row["total_meows"] or 0,
        "total_guilds": row["total_guilds"] or 0,
        "total_users": row["total_users"] or 0,
        "started_at": started_at,
        "last_heartbeat": last_heartbeat,
        "online": online,
        "uptime_seconds": uptime_seconds,
    }


def format_uptime(seconds):
    seconds = max(0, int(seconds or 0))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)
