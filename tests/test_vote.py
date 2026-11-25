import discord

import vote


def test_vote_links():
    assert vote.VOTE_LINKS == (
        ("top.gg", "https://top.gg/bot/1446086806926786581/vote"),
        ("discordlist.gg", "https://discordlist.gg/bot/1446086806926786581/vote"),
    )


def test_vote_page_url(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://example.test/")
    assert vote.vote_page_url() == "https://example.test/vote"


def test_vote_view(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://example.test")

    view = vote.VoteView()

    assert view.timeout is None
    assert len(view.children) == 1
    button = view.children[0]
    assert button.label == "the cat says you should vote"
    assert button.url == "https://example.test/vote"
    assert button.style is discord.ButtonStyle.link
