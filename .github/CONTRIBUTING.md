# contributing to meow bot

small changes are welcome. please keep the project small, readable, and cat themed.

## before you start

- search the issue tracker to avoid duplicates
- keep pull requests focused on one thing
- never include a real bot token, webhook URL, or other secret

## setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

fill in `TOKEN` in `.env`, then run:

```sh
.venv/bin/python bot.py
.venv/bin/python app.py
```

## checks

run both before opening a pull request:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
```

## style

- follow the existing lowercase writing style in user facing text
- keep comments rare and useful
- match the existing code style and structure
- add or update tests when behavior changes
