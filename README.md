# Telegram Giveaway Bot

Production-oriented Telegram bot for channel giveaways.

## Features

- Admin-only control panel.
- Giveaway modes:
  - join by button;
  - join by comment under the giveaway post.
- One publish channel per giveaway.
- Separate subscription conditions per giveaway.
- Optional captcha for button giveaways.
- Main and reserve winners.
- Participant deduplication by Telegram `user_id`.
- Manual finish and scheduled finish.
- Participant export to CSV.
- SQLite for simple local launch or PostgreSQL for server production launch.
- Persistent FSM state in `fsm_state.json`.
- Local browser control panel for non-technical setup and start/stop.

## Requirements

- Python 3.10 or 3.11.
- Telegram bot token from BotFather.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Fill `.env`:

```env
BOT_TOKEN=put_botfather_token_here
DATABASE_URL=sqlite://data/giveaway_bot.sqlite3
OWNERS=123456789
OWNER_USERNAMES=
TIMEZONE=Europe/Moscow
START_TEXT=Главное меню:
COMMENT_GIVEAWAY_KEYWORD=Участвую
```

Use numeric `OWNERS` in production. `OWNER_USERNAMES` is convenient for local testing, but numeric IDs are safer.

`DATABASE_URL` can be SQLite for simple setups or PostgreSQL for server setups. The bot creates missing tables automatically on the first run.

## Browser Control Panel

For non-technical setup, run:

```bash
.venv/bin/python control_panel.py
```

Open:

```text
http://127.0.0.1:8088
```

The panel lets you fill:

- BotFather token.
- Telegram owner ID or owner username.
- Database URL.
- Timezone.
- Comment keyword.

Then click "Save settings" and "Start bot".

The panel writes only the local `.env` file. `.env` is ignored by git and must not be committed.

## Run

```bash
.venv/bin/python app.py
```

## Telegram Setup

For button giveaways:

1. Add the bot as admin to the publish channel.
2. Add the bot as admin to all channels used as subscription conditions.

For comment giveaways:

1. Add the bot as admin to the publish channel.
2. Add the bot as admin to the linked discussion group.
3. Add the bot as admin to all condition channels.
4. In the bot admin panel, connect both publish channel and discussion group.

Channels can be connected by sending one of these formats in the admin panel:

- `@channel_username`
- `https://t.me/channel_username`
- `https://t.me/channel_username/123`
- `https://t.me/c/123456/123` for private channel post links available to the bot
- a forwarded post from the channel

Telegram Bot API limitations still apply:

- The bot must stay admin in the publish channel while it needs to publish giveaway posts there.
- For strict subscription conditions, the bot must stay admin in every condition channel while active giveaways need subscription checks for that channel.
- For soft subscription conditions, the bot only shows a button/link and does not need admin rights in that condition channel.
- For comment giveaways, the bot must also stay admin in the linked discussion group while comments are being collected.

## Admin Flow

1. Send `/start` to the bot.
2. Create a giveaway.
3. Select mode: button or comments.
4. Fill name, text, media, end date, winners and reserve winners.
5. Open the draft.
6. Set publish channel.
7. Add subscription conditions:
   - strict check: real subscription verification, bot must be admin in that channel;
   - soft link: only shows a subscribe button, no real verification and no admin rights required.
8. For comments mode, connect the discussion group.
9. Start the giveaway.

## Delivery Notes

Do not deliver `.env`, `.venv`, `fsm_state.json`, `exports/`, `__pycache__/`, or `.DS_Store`.

Before handing the bot to a client, rotate the Telegram token in BotFather and put the fresh token into the client's `.env`.

Recommended production handoff:

1. Create a fresh bot token in BotFather or rotate the current token.
2. Create the PostgreSQL database on the target server.
3. Copy `.env.example` to `.env` on the target server and fill real values there.
4. Add the bot as admin to all publish, condition, and discussion channels.
5. Start the bot with a process manager such as systemd, supervisor, Docker, or a hosting platform worker.

If the client uses the browser control panel on a personal computer, the bot works only while that computer, internet connection, and panel/bot process are running. For 24/7 operation, deploy it to a VPS or hosting platform.
