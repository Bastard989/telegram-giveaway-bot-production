import os
from pathlib import Path

import pytz


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _parse_owners(value: str) -> list[int]:
    owners = []
    for item in value.split(","):
        item = item.strip()
        if item and item.isdigit():
            owners.append(int(item))

    return owners


_load_env_file()

OWNERS = _parse_owners(os.getenv("OWNERS", ""))
OWNER_USERNAMES = {
    item.strip().lstrip("@").lower()
    for item in os.getenv("OWNER_USERNAMES", "").split(",")
    if item.strip()
}

bot_token = os.getenv("BOT_TOKEN", "")
database_url = os.getenv("DATABASE_URL", "")
timezone_info = pytz.timezone(os.getenv("TIMEZONE", "Europe/Moscow"))

start_text = os.getenv("START_TEXT", "Главное меню: ")
text_for_participation_in_comments_giveaways = os.getenv("COMMENT_GIVEAWAY_KEYWORD", "Участвую")


def is_owner(user_id: int, username: str | None = None) -> bool:
    if user_id in OWNERS:
        return True

    if username and username.lower() in OWNER_USERNAMES:
        return True

    return False
