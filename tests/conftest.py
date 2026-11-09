import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
from db import get_db
from schema import create_schema


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def schema(db_path):
    conn = get_db(str(db_path))
    create_schema(conn)
    conn.close()
    return db_path


@pytest.fixture
def store(schema):
    from store import GuildConfigStore

    return GuildConfigStore(str(schema))


@pytest.fixture
def web_client(monkeypatch, schema):
    import app as webapp

    monkeypatch.setattr(db, "DB_PATH", str(schema))
    webapp._stats_cache["value"] = None
    webapp._stats_cache["expires"] = 0.0
    webapp.app.config.update(TESTING=True)

    with webapp.app.test_client() as client:
        yield client
