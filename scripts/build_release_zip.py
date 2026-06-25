import zipfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "dist"
ZIP_PATH = DIST_DIR / "Бот_для_розыгрышей_Telegram.zip"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "scripts",
    "runtime",
    "tests",
}

EXCLUDED_FILES = {
    ".env",
    ".env.example",
    ".DS_Store",
    ".gitignore",
    "ARCHITECTURE.md",
    "BUILD_ZIP.command",
    "fsm_state.json",
    "README.md",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".log",
    ".pid",
    ".port",
    ".sqlite3",
    ".sqlite3-shm",
    ".sqlite3-wal",
    ".db",
    ".db-shm",
    ".db-wal",
}


def is_excluded(path: Path) -> bool:
    relative = path.relative_to(BASE_DIR)
    parts = set(relative.parts)

    if path.name in EXCLUDED_FILES:
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    if parts.intersection(EXCLUDED_DIRS):
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
