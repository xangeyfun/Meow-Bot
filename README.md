# meow bot

a discord bot that says meow.

it watches chat for meow like messages and replies with a random meow. server admins can add custom regex triggers, toggle built in triggers, and turn the bot off per server. it also counts successful replies and shows live stats on a Flask website.

## features

- replies to meow, mreow, mew, mrow, mrrp, nya, purr, and similar cat noises
- optional woof trigger, off by default
- per server settings with one `/config` panel
- up to 25 custom regex triggers per server, tested before saving
- per channel rate limit of 5 replies per 5 seconds
- server leaderboards and global meow totals
- commands reply in chat by default, with an optional `hidden` flag
- Flask website with landing, commands, stats, status, info, privacy, terms, and support pages
- light and dark website themes with a saved preference
- shared SQLite database between the bot and website

## requirements

- Python 3.11 or newer
- a Discord application and bot token
- message content intent enabled in the Discord developer portal

## setup

1. create a virtual environment and install dependencies:

   ```sh
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
   ```

2. copy `.env.example` to `.env` and fill in `TOKEN`. The bot and website use the same `MEOW_DB_PATH`.

3. start the bot. it creates the database and syncs commands on startup:

   ```sh
   .venv/bin/python bot.py
   ```

4. run the website in a second process:

   ```sh
   .venv/bin/python app.py
   ```

   The default address is `http://127.0.0.1:8000`. Set `FLASK_HOST` and `FLASK_PORT` to change it.

## environment

| variable | required | purpose |
| --- | --- | --- |
| `TOKEN` | yes | Discord bot token |
| `MEOW_DB_PATH` | no | SQLite file shared by the bot and website. Defaults to `database.db` |
| `GUILD_ID` | no | sync slash commands to one server during development |
| `DISCORD_INVITE_URL` | no | invite link used by the bot and website |
| `SITE_URL` | no | public website URL used for canonical and Open Graph tags |
| `SUPPORT_URL` | no | optional support link. If empty, the site points to GitHub issues |
| `GITHUB_URL` | no | source link. Defaults to the project repository |
| `ERROR_WEBHOOK_URL` | no | Discord webhook for ERROR level logs |
| `ALLOWED_USER_ID` | no | user id to ping on critical errors |
| `FLASK_HOST` | no | website host. Defaults to `127.0.0.1` |
| `FLASK_PORT` | no | website port. Defaults to `8000` |
| `FLASK_DEBUG` | no | set to `1` for Flask debug mode |
| `CACHE_TTL` | no | website stats cache in seconds. Defaults to `20` |

## commands

| command | description |
| --- | --- |
| `/help` | show the command list |
| `/config` | open the server settings panel. requires manage server |
| `/ping` | check latency |
| `/github` | get the source link |
| `/stats [user]` | meow count for a user |
| `/leaderboard` | top meowers in the server |
| `/totalmeows` | total meows across all servers |

every command accepts `hidden:true` to show the reply only to the person who ran it. replies are public by default.

## custom regex safety

custom patterns are limited to 200 characters. each pattern is compiled with the `regex` package and tested against a corpus of awkward inputs before it is saved. patterns that match an empty message, time out, or fail a safety test are rejected. stored patterns are checked again when they are loaded. matching also uses a 50 ms timeout.

## website

the website reads the same SQLite database as the bot. it only runs read queries and caches stats for 20 seconds by default. the Flask development server is fine for local use. for a public deployment, put it behind a reverse proxy and run it with a production WSGI server.

pages:

- `/` landing
- `/commands`
- `/stats`
- `/status`
- `/info`
- `/privacy`
- `/terms`
- `/support`
- `/invite` redirects to the Discord invite

## tests

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
```

## contributing

bug reports and small pull requests are welcome. see [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) for setup, checks, and the security policy.

## project layout

```text
bot.py              bot startup, lifecycle, and command error handling
app.py              Flask website
cogs/               bot cogs
matcher.py          built in triggers and regex safety
store.py            per server settings and cache
stats.py            in memory counters and database queries
schema.py           SQLite schema
templates/          website templates
static/             website CSS, JS, SVG assets, and screenshots
tests/              unit and website tests
.github/            issue templates, pull request template, and CI
```

## license

MIT. See `LICENSE`.
