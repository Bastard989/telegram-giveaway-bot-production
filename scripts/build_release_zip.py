import zipfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "dist"
ZIP_PATH = DIST_DIR / "telegram-giveaway-bot.zip"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "runtime/postgres-data",
}

EXCLUDED_FILES = {
    ".env",
    ".DS_Store",
    "fsm_state.json",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".log",
    ".pid",
}


def is_excluded(path: Path) -> bool:
    relative = path.relative_to(BASE_DIR)
    parts = set(relative.parts)
    relative_text = relative.as_posix()

    if path.name in EXCLUDED_FILES:
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    if parts.intersection(EXCLUDED_DIRS):
        return True
    if relative_text.startswith("runtime/postgres-data/"):
        return True

    return False


def main():
    DIST_DIR.mkdir(exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(BASE_DIR.rglob("*")):
            if path.is_dir() or is_excluded(path):
                continue
            archive.write(path, path.relative_to(BASE_DIR))

    print(ZIP_PATH)


if __name__ == "__main__":
    main()
