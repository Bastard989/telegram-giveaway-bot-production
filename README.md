# Telegram Giveaway Bot

Production-oriented Telegram bot for channel giveaways.

## What It Does

- Creates giveaways from Telegram admin panel.
- Publishes giveaway posts to a selected Telegram channel.
- Supports participation by button or by comments.
- Supports strict subscription checks and soft subscription links.
- Selects main and reserve winners.
- Allows manual winner selection by participant username.
- Exports participants to CSV.
- Uses PostgreSQL as the production database.
- Includes a local browser Control Center for non-technical setup.

## Fast Start For Client

1. Unzip the project.
2. Open `START.command` on macOS or `START.bat` on Windows.
3. The browser Control Center opens automatically.
4. Fill:
   - BotFather token.
   - Telegram owner ID or owner username.
5. Click `Save settings`.
6. Click `Install dependencies`.
7. Click `Prepare PostgreSQL`.
8. Click `Start bot`.
9. Open Telegram and send `/start` to the bot.

The Control Center chooses a free browser port automatically. Do not manually open `127.0.0.1:8088` unless the Control Center is running and printed that exact port.

## Database

The default database is PostgreSQL through Docker Compose.

The database files are stored inside the project:

```text
runtime/postgres-data/
```

The Control Center writes the correct `DATABASE_URL` to `.env` automatically after `Prepare PostgreSQL`.

Default local database URL:

```env
DATABASE_URL=postgres://giveaway_bot:giveaway_bot@127.0.0.1:55432/giveaway_bot
```

If port `55432` is busy, the Control Center selects another free port and updates `.env`.

Docker Desktop is required for the one-click PostgreSQL setup. If Docker is not installed, install Docker Desktop or use an external PostgreSQL database and paste its `DATABASE_URL` manually.

## Telegram Admin Rights

Publish channel:

- The bot must be admin because it publishes giveaway posts there.

Strict subscription condition:

- The bot must be admin in the condition channel.
- The bot checks whether the participant is subscribed.

Soft subscription condition:

- The bot does not need admin rights.
- The bot only shows a subscribe button/link.
- The participant can technically join without subscribing.

Comment giveaways:

- The bot must be admin in the linked discussion group while comments are collected.

## Manual Winner Selection

For an active giveaway, open the giveaway card and click:

```text
Выбрать победителя вручную
```

Then send the participant username, for example:

```text
@username
```

The user must already be in the participant list. The manual winner becomes the first main winner. If the giveaway has more main or reserve places, the remaining places are filled randomly from the other participants.

## Manual Start

If you do not use `START.command` or `START.bat`:

```bash
python3 control_panel.py
```

The Control Center prints the selected local URL and opens it in the browser.

## Environment

`.env` is generated locally and must not be committed or sent publicly.

Main fields:

```env
BOT_TOKEN=put_botfather_token_here
DATABASE_URL=postgres://giveaway_bot:giveaway_bot@127.0.0.1:55432/giveaway_bot
OWNERS=123456789
OWNER_USERNAMES=
TIMEZONE=Europe/Moscow
START_TEXT=Главное меню:
COMMENT_GIVEAWAY_KEYWORD=Участвую
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=55432
POSTGRES_DB=giveaway_bot
POSTGRES_USER=giveaway_bot
POSTGRES_PASSWORD=giveaway_bot
```

Prefer numeric `OWNERS`. Username access is convenient, but numeric ID is safer.

## Process Rules

- Only one bot process should run.
- When `Start bot` is pressed, an old bot process is stopped first.
- When `Restart bot` is pressed, the old process is stopped and a new one is started.
- When the Control Center process is closed, the bot process started by it is stopped too.
- Logs are stored in `runtime/bot.log` and `runtime/control-panel.log`.
- Logs are not shown in the simple UI, but remain available in `runtime/` for troubleshooting.

## Delivery Notes

To build a clean zip for the client:

```bash
python3 scripts/build_release_zip.py
```

or double-click:

```text
BUILD_ZIP.command
```

The zip is created at:

```text
dist/telegram-giveaway-bot.zip
```

Do not send:

- `.env`
- `.venv/`
- `.git/`
- `__pycache__/`
- `runtime/postgres-data/` unless you intentionally want to transfer local database contents
- `runtime/*.pid`
- `runtime/*.log`

Before delivery, rotate any token that was ever shared in chat.
