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
- PostgreSQL storage through Tortoise ORM.
- Persistent FSM state in `fsm_state.json`.

## Requirements

- Python 3.10 or 3.11.
- PostgreSQL.
- Telegram bot token from BotFather.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
createdb giveaway_bot
```

Fill `.env`:

```env
BOT_TOKEN=put_botfather_token_here
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/giveaway_bot
OWNERS=123456789
OWNER_USERNAMES=
TIMEZONE=Europe/Moscow
START_TEXT=Главное меню:
COMMENT_GIVEAWAY_KEYWORD=Участвую
```

Use numeric `OWNERS` in production. `OWNER_USERNAMES` is convenient for local testing, but numeric IDs are safer.

`DATABASE_URL` must point to an existing PostgreSQL database. The bot creates missing tables automatically on the first run.

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
- The bot must stay admin in every condition channel while active giveaways need subscription checks for that channel.
- For comment giveaways, the bot must also stay admin in the linked discussion group while comments are being collected.

## Admin Flow

1. Send `/start` to the bot.
2. Create a giveaway.
3. Select mode: button or comments.
4. Fill name, text, media, end date, winners and reserve winners.
5. Open the draft.
6. Set publish channel.
7. Add subscription conditions.
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
