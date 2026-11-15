import asyncio
import logging

import botlists

METRICS_URL = "https://top.gg/api/v1/projects/@me/metrics"
COMMANDS_URL = "https://top.gg/api/v1/projects/@me/commands"
DLIST_URL = "https://api.discordlist.gg/v0/bots/123456789/guilds"


class FakeResponse:
    def __init__(self, status=204, text=""):
        self.status = status
        self._text = text

    async def text(self):
        return self._text


class FakeContext:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc_info):
        return False


class FakeSession:
    def __init__(self, statuses=None, errors=None):
        self.requests = []
        self._statuses = statuses or {}
        self._errors = errors or {}

    def request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        if (method, url) in self._errors:
            raise self._errors[(method, url)]
        status, text = self._statuses.get((method, url), (204, ""))
        return FakeContext(FakeResponse(status, text))


class FakeUser:
    def __init__(self, user_id):
        self.id = user_id


class FakeCommand:
    def __init__(self, name, description):
        self.name = name
        self.description = description

    def to_dict(self):
        return {"name": self.name, "description": self.description}


class FakeTree:
    def __init__(self, fetched=None, local=None, error=None):
        self._fetched = fetched or []
        self._local = local or []
        self._error = error

    async def fetch_commands(self):
        if self._error:
            raise self._error
        return self._fetched

    def get_commands(self):
        return self._local


class FakeBot:
    def __init__(self, guilds=5, shard_count=1, tree=None):
        self.guilds = [object() for _ in range(guilds)]
        self.shard_count = shard_count
        self.user = FakeUser(123456789)
        self.tree = tree if tree is not None else FakeTree()


def _run(bot, session):
    asyncio.run(botlists.post_stats(bot, session))


def test_no_tokens_skips_all_requests(monkeypatch):
    monkeypatch.setattr(botlists, "TOPGG_TOKEN", None)
    monkeypatch.setattr(botlists, "DISCORDLIST_TOKEN", None)
    session = FakeSession()
    _run(FakeBot(), session)
    assert session.requests == []


def test_topgg_posts_metrics_and_commands(monkeypatch):
    monkeypatch.setattr(botlists, "TOPGG_TOKEN", "topgg-secret")
    monkeypatch.setattr(botlists, "DISCORDLIST_TOKEN", None)
    session = FakeSession()
    commands = [FakeCommand("help", "show the command list")]
    _run(FakeBot(guilds=7, tree=FakeTree(fetched=commands)), session)

    assert len(session.requests) == 2
    metrics, commands_put = session.requests
    assert metrics["method"] == "PATCH"
    assert metrics["url"] == METRICS_URL
    assert metrics["headers"] == {"Authorization": "Bearer topgg-secret"}
    assert metrics["json"] == {"server_count": 7, "shard_count": 1}
    assert commands_put["method"] == "PUT"
    assert commands_put["url"] == COMMANDS_URL
    assert commands_put["headers"] == {"Authorization": "Bearer topgg-secret"}
    assert commands_put["json"] == [{"name": "help", "description": "show the command list"}]


def test_topgg_defaults_shard_count(monkeypatch):
    monkeypatch.setattr(botlists, "TOPGG_TOKEN", "topgg-secret")
    monkeypatch.setattr(botlists, "DISCORDLIST_TOKEN", None)
    session = FakeSession()
    _run(FakeBot(guilds=3, shard_count=None), session)
    assert session.requests[0]["json"] == {"server_count": 3, "shard_count": 1}


def test_discordlist_posts_guild_count(monkeypatch):
    monkeypatch.setattr(botlists, "TOPGG_TOKEN", None)
    monkeypatch.setattr(botlists, "DISCORDLIST_TOKEN", "dlist-secret")
    session = FakeSession()
    _run(FakeBot(guilds=9), session)

    assert len(session.requests) == 1
    request = session.requests[0]
    assert request["method"] == "PUT"
    assert request["url"] == DLIST_URL
    assert request["headers"] == {"Authorization": "Bearer dlist-secret"}
    assert request["params"] == {"count": "9"}


def test_both_tokens_post_to_both_sites(monkeypatch):
    monkeypatch.setattr(botlists, "TOPGG_TOKEN", "topgg-secret")
    monkeypatch.setattr(botlists, "DISCORDLIST_TOKEN", "dlist-secret")
    session = FakeSession()
    _run(FakeBot(guilds=4, tree=FakeTree(fetched=[FakeCommand("ping", "check latency")])), session)

    assert [request["url"] for request in session.requests] == [METRICS_URL, COMMANDS_URL, DLIST_URL]


def test_empty_fetch_falls_back_to_local_commands(monkeypatch):
    monkeypatch.setattr(botlists, "TOPGG_TOKEN", "topgg-secret")
    monkeypatch.setattr(botlists, "DISCORDLIST_TOKEN", None)
    session = FakeSession()
    commands = [FakeCommand("ping", "check latency")]
    _run(FakeBot(tree=FakeTree(fetched=[], local=commands)), session)
    assert session.requests[-1]["json"] == [{"name": "ping", "description": "check latency"}]


def test_fetch_error_falls_back_to_local_commands(monkeypatch):
    monkeypatch.setattr(botlists, "TOPGG_TOKEN", "topgg-secret")
    monkeypatch.setattr(botlists, "DISCORDLIST_TOKEN", None)
    session = FakeSession()
    commands = [FakeCommand("stats", "show meow stats for a user")]
    _run(FakeBot(tree=FakeTree(error=RuntimeError("fetch failed"), local=commands)), session)
    assert session.requests[-1]["json"] == [{"name": "stats", "description": "show meow stats for a user"}]


def test_no_commands_skips_commands_put(monkeypatch):
    monkeypatch.setattr(botlists, "TOPGG_TOKEN", "topgg-secret")
    monkeypatch.setattr(botlists, "DISCORDLIST_TOKEN", None)
    session = FakeSession()
    _run(FakeBot(tree=FakeTree(fetched=[], local=[])), session)
    assert [request["url"] for request in session.requests] == [METRICS_URL]


def test_non_2xx_logs_warning(monkeypatch, caplog):
    monkeypatch.setattr(botlists, "TOPGG_TOKEN", "topgg-secret")
    monkeypatch.setattr(botlists, "DISCORDLIST_TOKEN", None)
    session = FakeSession(statuses={("PATCH", METRICS_URL): (401, "bad token")})
    with caplog.at_level(logging.WARNING, logger="botlists"):
        _run(FakeBot(), session)
    assert any("top.gg metrics failed: 401 bad token" in record.getMessage() for record in caplog.records)


def test_request_error_is_logged_not_raised(monkeypatch, caplog):
    monkeypatch.setattr(botlists, "TOPGG_TOKEN", "topgg-secret")
    monkeypatch.setattr(botlists, "DISCORDLIST_TOKEN", "dlist-secret")
    session = FakeSession(errors={("PATCH", METRICS_URL): RuntimeError("network down")})
    bot = FakeBot(tree=FakeTree(fetched=[FakeCommand("ping", "check latency")]))
    with caplog.at_level(logging.ERROR, logger="botlists"):
        _run(bot, session)
    assert any("top.gg metrics failed" in record.getMessage() for record in caplog.records)
    assert any(record.exc_info for record in caplog.records)
    assert [request["url"] for request in session.requests] == [METRICS_URL, COMMANDS_URL, DLIST_URL]
