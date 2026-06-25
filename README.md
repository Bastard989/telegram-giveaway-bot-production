# Telegram Giveaway Bot

Telegram bot for channel giveaways with a simple browser setup panel.

## What It Does

- Creates giveaways from Telegram admin panel.
- Publishes giveaway posts to a selected Telegram channel.
- Supports participation by button or by comments.
- Supports strict subscription checks and soft subscription links.
- Selects winners by prize places.
- Allows manual winner selection by participant username.
- Exports participants to CSV.
- Stores data in a local database file inside the project.
- Includes a local browser panel for non-technical setup.

## Fast Start For Client

For a detailed non-technical manual, open:

```text
РУКОВОДСТВО_ПО_ИСПОЛЬЗОВАНИЮ.md
```

1. Unzip the project.
2. On macOS, run the startup command from the unzipped folder that contains `START.command`:

```bash
xattr -dr com.apple.quarantine . 2>/dev/null || true; chmod +x ./START.command; ./START.command
```

On Windows, open `START.bat`.
3. The browser setup panel opens automatically.
4. Fill:
   - BotFather token.
   - Telegram owner ID or owner username.
5. Click `Сохранить настройки`.
6. Click `Установить нужные файлы`.
7. Click `Подготовить базу данных`.
8. Click `Проверить окружение`.
9. Click `Запустить с сохранёнными настройками`.
10. Open Telegram and send `/start` to the bot.

No separate database program is required.

The panel remembers saved settings in the local `.env` file. On the next launch, the client does not need to paste the token again; they can open the panel and click `Запустить с сохранёнными настройками`.

## Database

The default database is SQLite.

It is a normal file inside the project:

```text
runtime/giveaway-bot.sqlite3
```

The setup panel creates it automatically when you click:

```text
Подготовить базу данных
```

Default database URL:

```env
DATABASE_URL=sqlite://runtime/giveaway-bot.sqlite3
```

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

## Prize Places Logic

The bot asks two separate questions:

1. Prize places count.
2. Winners per each place.

Examples:

- `1` prize place and `1` winner per place = 1 total winner.
- `5` prize places and `1` winner per place = places 1, 2, 3, 4, 5 with one winner each.
- `5` prize places and `2` winners per place = 10 total winners: two people for each place.

## Manual Winner Selection

For an active giveaway, open the giveaway card and click:

```text
Выбрать победителя вручную
```

Then send the participant username, for example:

```text
@username
```

The user must already be in the participant list. The manual winner becomes one of the winners for place 1. If the giveaway has more winner slots, the remaining slots are filled randomly from the other participants.

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
dist/Бот_для_розыгрышей_Telegram.zip
```

Do not send:

- `.env`
- `.venv/`
- `.git/`
- `__pycache__/`
- `runtime/giveaway-bot.sqlite3` unless you intentionally want to transfer local data
- `runtime/*.pid`
- `runtime/*.log`

Before delivery, rotate any token that was ever shared in chat.

Before sending a working folder to a client, click:

```text
Очистить токен перед передачей
```

The release zip built by `scripts/build_release_zip.py` does not include `.env`,
`.venv`, local runtime data, logs, or SQLite database files.

## Tests

Run unit tests from the project virtual environment:

```bash
.venv/bin/python -m unittest discover -s tests
```
