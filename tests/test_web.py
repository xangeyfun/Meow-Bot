import time

import app as webapp
import db
from db import get_db


def test_index(web_client):
    response = web_client.get("/")
    assert response.status_code == 200
    assert b"it says meow." in response.data


def test_commands(web_client):
    response = web_client.get("/commands")
    assert response.status_code == 200
    assert b"/config" in response.data
    assert b"built in triggers" in response.data


def test_stats_page(web_client):
    response = web_client.get("/stats")
    assert response.status_code == 200
    assert b"total meows" in response.data


def test_status_page(web_client):
    response = web_client.get("/status")
    assert response.status_code == 200
    assert b"offline" in response.data


def test_info_pages(web_client):
    for path in ["/info", "/privacy", "/terms", "/support"]:
        response = web_client.get(path)
        assert response.status_code == 200


def test_invite_redirect(web_client):
    response = web_client.get("/invite")
    assert response.status_code == 302
    assert "discord.com/oauth2/authorize" in response.headers["Location"]


def test_favicon_redirect(web_client):
    response = web_client.get("/favicon.ico")
    assert response.status_code == 302
    assert "/static/img/favicon.svg" in response.headers["Location"]


def test_404(web_client):
    response = web_client.get("/does-not-exist")
    assert response.status_code == 404
    assert b"no meows here" in response.data


def test_security_headers(web_client):
    response = web_client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_stats_render_from_database(web_client, schema):
    now = int(time.time())
    conn = get_db(str(schema))
    conn.execute(
        "UPDATE bot_stats SET total_meows = ?, total_guilds = ?, "
        "total_users = ?, started_at = ?, last_heartbeat = ? WHERE id = 1",
        (1234, 5, 42, now, now),
    )
    conn.commit()
    conn.close()

    webapp._stats_cache["value"] = None
    webapp._stats_cache["expires"] = 0.0

    response = web_client.get("/stats")
    assert response.status_code == 200
    assert b"1,234" in response.data
    assert b"42" in response.data


def test_website_without_database(monkeypatch, tmp_path):
    missing = tmp_path / "missing.db"
    monkeypatch.setattr(db, "DB_PATH", str(missing))
    webapp._stats_cache["value"] = None
    webapp._stats_cache["expires"] = 0.0

    with webapp.app.test_client() as client:
        response = client.get("/stats")

    assert response.status_code == 200
    assert b"offline" in response.data
    assert not missing.exists()


def test_static_assets(web_client):
    for path in [
        "/static/css/style.css",
        "/static/js/main.js",
        "/static/img/cat.svg",
        "/static/img/favicon.svg",
        "/static/img/og.svg",
    ]:
        response = web_client.get(path)
        assert response.status_code == 200
