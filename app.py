import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, url_for

import stats
from logconf import setup_logging
from matcher import BUILTIN_TRIGGERS

load_dotenv()
setup_logging()

logger = logging.getLogger("web")

BOT_NAME = "meow bot"
GITHUB_URL = os.getenv("GITHUB_URL", "https://github.com/xangeyfun/Meow-Bot")
GITHUB_ISSUES_URL = GITHUB_URL.rstrip("/") + "/issues"
SUPPORT_URL = os.getenv("SUPPORT_URL", "").strip()
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000").rstrip("/")
INVITE_URL = os.getenv(
    "DISCORD_INVITE_URL",
    "https://discord.com/oauth2/authorize?client_id=1446086806926786581"
    "&scope=bot%20applications.commands&permissions=84992",
)
CACHE_TTL = max(5, int(os.getenv("CACHE_TTL", "20")))

COMMANDS = (
    ("/help", "show the command list", "everyone"),
    ("/ping", "check latency", "everyone"),
    ("/stats [user]", "meow count for a user", "everyone"),
    ("/leaderboard", "top meowers in this server", "everyone"),
    ("/totalmeows", "total meows across all servers", "everyone"),
    ("/github", "get the source link", "everyone"),
    ("/config", "open server settings", "manage server"),
)

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

_stats_lock = threading.Lock()
_stats_cache = {"value": None, "expires": 0.0}


def _empty_stats():
    return {
        "total_meows": 0,
        "total_guilds": 0,
        "total_users": 0,
        "started_at": None,
        "last_heartbeat": None,
        "online": False,
        "uptime_seconds": 0,
        "uptime": "0s",
        "meows_per_guild": 0,
        "meows_per_user": 0,
    }


def _with_derived_stats(data):
    total = data.get("total_meows") or 0
    guilds = data.get("total_guilds") or 0
    users = data.get("total_users") or 0
    data["meows_per_guild"] = round(total / guilds, 1) if guilds else 0
    data["meows_per_user"] = round(total / users, 1) if users else 0
    return data


def get_site_stats():
    now = time.monotonic()
    with _stats_lock:
        cached = _stats_cache["value"]
        if cached is not None and now < _stats_cache["expires"]:
            return cached

    try:
        data = stats.website_stats()
    except sqlite3.OperationalError as exc:
        logger.warning("Stats database is not ready: %s", exc)
        data = _empty_stats()
    except Exception:
        logger.exception("Failed to read stats from the database")
        data = _empty_stats()

    data["uptime"] = stats.format_uptime(data.get("uptime_seconds", 0))
    _with_derived_stats(data)

    with _stats_lock:
        _stats_cache["value"] = data
        _stats_cache["expires"] = now + CACHE_TTL
    return data


@app.template_filter("timestamp")
def timestamp_filter(value):
    if not value:
        return "never"
    return datetime.fromtimestamp(value, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )


@app.context_processor
def inject_site():
    return {
        "bot_name": BOT_NAME,
        "github_url": GITHUB_URL,
        "github_issues_url": GITHUB_ISSUES_URL,
        "support_url": SUPPORT_URL,
        "site_url": SITE_URL,
        "invite_url": INVITE_URL,
        "current_year": datetime.now(timezone.utc).year,
    }


@app.after_request
def set_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self'; "
        "script-src 'self'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'"
    )
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index():
    return render_template("index.html", page="home", stats=get_site_stats())


@app.get("/commands")
def commands_page():
    return render_template(
        "commands.html",
        page="commands",
        commands=COMMANDS,
        triggers=BUILTIN_TRIGGERS,
    )


@app.get("/stats")
def stats_page():
    return render_template("stats.html", page="stats", stats=get_site_stats())


@app.get("/api/stats")
def stats_api():
    data = get_site_stats()
    return jsonify(
        {
            "total_meows": data["total_meows"],
            "total_guilds": data["total_guilds"],
            "total_users": data["total_users"],
        }
    )


@app.get("/status")
def status_page():
    return render_template("status.html", page="status", stats=get_site_stats())


@app.get("/info")
def info_page():
    return render_template("info.html", page="info")


@app.get("/privacy")
def privacy_page():
    return render_template("privacy.html", page="privacy")


@app.get("/terms")
def terms_page():
    return render_template("terms.html", page="terms")


@app.get("/support")
def support_page():
    return render_template("support.html", page="support")


@app.get("/invite")
def invite():
    return redirect(INVITE_URL, code=302)


@app.get("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="img/pfp.jpg"), code=302)


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html", page="404"), 404


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug)
