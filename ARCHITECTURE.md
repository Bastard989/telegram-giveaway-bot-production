# Architecture

## Active Runtime

```text
app.py                     Telegram bot entry point
control_panel.py           Local browser Control Center, no external dependencies
config/                    Environment loading and owner access config
database/                  Tortoise ORM setup and active models
handlers/production.py     Active Telegram bot handlers and giveaway logic
middlewares/               Access-control middleware
runtime/                   Local runtime data, logs, PIDs, SQLite database
```

## Database

The product uses SQLite by default.

The local one-click setup creates a database file:

```text
runtime/giveaway-bot.sqlite3
```

Schema creation is handled by Tortoise ORM on bot startup.

## Process Management

The Control Center owns bot lifecycle:

- stores the bot PID in `runtime/bot.pid`;
- stops an existing bot before starting a new one;
- writes logs to `runtime/bot.log`;
- stops the child bot process when the Control Center exits.

The Control Center also stores its PID and selected port:

```text
runtime/control-panel.pid
runtime/control-panel.port
```

## Removed Legacy Code

The downloaded source contained an older inactive implementation:

- old `handlers/admin`;
- old reply/inline keyboard modules;
- old FSM state modules;
- bundled calendar helper;
- unused captcha helper;
- unused temporary-user/statistic models.

Those files were removed because the active product uses `handlers/production.py` and the current database models only.
