# Runtime Directory

This directory is created for local runtime data:

- `giveaway-bot.sqlite3` - local SQLite database file.
- `bot.pid` - running bot process id.
- `control-panel.pid` - running Control Center process id.
- `bot.log` - bot logs.
- `control-panel.log` - Control Center logs.

Do not commit runtime data or send it as source code history. For zip delivery, this directory can be empty; the Control Center creates what it needs.
