from pathlib import Path

from tortoise import Tortoise
from config import database_url, timezone_info


def ensure_database_path():
    if not database_url.startswith("sqlite://"):
        return

    sqlite_path = database_url.removeprefix("sqlite://")
    if sqlite_path and sqlite_path != ":memory:":
        Path(sqlite_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


async def ensure_runtime_schema():
    connection = Tortoise.get_connection("default")
    if not database_url.startswith(("postgres://", "postgresql://")):
        return

    await connection.execute_script(
        """
        ALTER TABLE IF EXISTS giveawaycondition
        ADD COLUMN IF NOT EXISTS target_channel_url TEXT;

        ALTER TABLE IF EXISTS giveawaycondition
        ADD COLUMN IF NOT EXISTS condition_type VARCHAR(16) DEFAULT 'strict';

        UPDATE giveawaycondition
        SET condition_type = 'strict'
        WHERE condition_type IS NULL;
        """
    )


async def initialize_database():
    ensure_database_path()
    await Tortoise.init(
        db_url=database_url,
        modules=
        {
            'models':
                [
                    'database.models.giveaway',
                    'database.models.telegram_channel',
                    'database.models.giveaway_statistic',
                    'database.models.temporary_users',
                    'database.models.giveaway_condition',
                    'database.models.giveaway_participant',
                    'database.models.giveaway_winner',
                ]
        },
        timezone=str(timezone_info.zone),
        _enable_global_fallback=True,
    )

    await Tortoise.generate_schemas()
    await ensure_runtime_schema()
