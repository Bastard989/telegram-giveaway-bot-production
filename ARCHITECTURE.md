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

On Windows, `RUN_BOT_WINDOWS.bat` wraps `START.bat` in a persistent Command Prompt so startup errors remain visible instead of disappearing with the window. Both launchers contain ASCII-only commands for compatibility with Windows command-shell encodings.

## Giveaway Completion

Manual winner selection is a two-phase flow:

1. `preselect_manual_winner` stores the chosen participant as the first-place winner while the giveaway remains active.
2. `finish_giveaway` preserves valid preselected winners, fills the remaining slots randomly, marks the giveaway finished, and publishes results.

Media posts store separate Telegram file IDs for photos, videos, and animations. Existing SQLite databases receive the nullable `animation_id` column through the runtime schema migration.

## Removed Legacy Code

The downloaded source contained an older inactive implementation:

- old `handlers/admin`;
- old reply/inline keyboard modules;
- old FSM state modules;
- bundled calendar helper;
- unused captcha helper;
- unused temporary-user/statistic models.

Those files were removed because the active product uses `handlers/production.py` and the current database models only.
