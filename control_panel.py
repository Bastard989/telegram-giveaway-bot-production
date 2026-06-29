import atexit
import html
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from urllib.parse import parse_qs, urlencode, urlparse


BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / "runtime"
ENV_PATH = BASE_DIR / ".env"
BOT_PID_PATH = RUNTIME_DIR / "bot.pid"
PANEL_PID_PATH = RUNTIME_DIR / "control-panel.pid"
PANEL_PORT_PATH = RUNTIME_DIR / "control-panel.port"
BOT_LOG_PATH = RUNTIME_DIR / "bot.log"
PANEL_LOG_PATH = RUNTIME_DIR / "control-panel.log"
BACKUP_DIR = RUNTIME_DIR / "backups"

REQUIRED_MODULES = {
    "aiogram": "aiogram",
    "aiohttp": "aiohttp",
    "aiosqlite": "aiosqlite",
    "pytz": "pytz",
    "tortoise": "tortoise-orm",
    "tzdata": "tzdata",
}
PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)

ENV_KEYS = [
    "BOT_TOKEN",
    "DATABASE_URL",
    "OWNERS",
    "OWNER_USERNAMES",
    "TIMEZONE",
    "START_TEXT",
    "COMMENT_GIVEAWAY_KEYWORD",
]

DEFAULT_ENV = {
    "BOT_TOKEN": "",
    "DATABASE_URL": "sqlite://runtime/giveaway-bot.sqlite3",
    "OWNERS": "",
    "OWNER_USERNAMES": "",
    "TIMEZONE": "Europe/Moscow",
    "START_TEXT": "Главное меню:",
    "COMMENT_GIVEAWAY_KEYWORD": "Участвую",
}


def ensure_runtime_dir():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def log(message: str):
    ensure_runtime_dir()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with PANEL_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"[{stamp}] {message}\n")


def read_env() -> dict[str, str]:
    data = DEFAULT_ENV.copy()
    if not ENV_PATH.exists():
        return data

    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in ENV_KEYS:
            data[key] = value.strip().strip('"').strip("'")

    return data


def write_env(data: dict[str, str]):
    ensure_runtime_dir()
    lines = []
    for key in ENV_KEYS:
        value = data.get(key, "")
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key}="{escaped}"')
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def local_sqlite_url() -> str:
    return "sqlite://runtime/giveaway-bot.sqlite3"


def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def find_free_port(start: int, end: int) -> int:
    for port in range(start, end + 1):
        if is_port_free(port):
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def terminate_pid(pid: int, timeout: float = 8):
    if not pid_is_running(pid):
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_is_running(pid):
            return
        time.sleep(0.2)

    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def terminate_pid_file(path: Path):
    pid = read_pid(path)
    if pid:
        terminate_pid(pid)
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def cleanup_processes():
    terminate_pid_file(BOT_PID_PATH)
    try:
        PANEL_PID_PATH.unlink()
    except FileNotFoundError:
        pass
    try:
        PANEL_PORT_PATH.unlink()
    except FileNotFoundError:
        pass


def python_executable() -> Path:
    if os.name == "nt":
        candidate = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = BASE_DIR / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def supported_python(python: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [str(python), "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
            cwd=BASE_DIR,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)

    version = (result.stdout or "неизвестно").strip()
    try:
        major, minor, *_ = (int(part) for part in version.split("."))
    except ValueError:
        return False, version
    return major == 3 and minor in (10, 11), version


def run_command(command: list[str], env: dict[str, str] | None = None, timeout: int | None = None) -> tuple[bool, str]:
    log("Running: " + " ".join(command))
    try:
        result = subprocess.run(
            command,
            cwd=BASE_DIR,
            env=env or os.environ.copy(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, f"Command not found: {command[0]}"
    except subprocess.TimeoutExpired as exc:
        return False, f"Command timed out: {' '.join(command)}\n{exc.stdout or ''}"

    output = result.stdout or ""
    if output:
        log(output.rstrip())
    return result.returncode == 0, output


def install_dependencies() -> str:
    venv_dir = BASE_DIR / ".venv"
    if not venv_dir.exists():
        compatible, version = supported_python(Path(sys.executable))
        if not compatible:
            return (
                f"Для этой версии бота нужен Python 3.10 или 3.11, сейчас запущен Python {version}. "
                "Закройте панель и снова запустите START.bat: он предложит установить Python 3.11."
            )
        ok, output = run_command([sys.executable, "-m", "venv", str(venv_dir)], timeout=120)
        if not ok:
            return "Не удалось создать .venv.\n" + output

    py = python_executable()
    compatible, version = supported_python(py)
    if not compatible:
        return (
            f"Папка .venv создана несовместимым или недоступным Python ({version}). "
            "Удалите только папку .venv, установите Python 3.11 и снова нажмите эту кнопку."
        )

    command = [str(py), "-m", "pip", "install", "-r", "requirements.txt"]
    ok, output = run_command(command, timeout=600)
    if not ok and "Missing dependencies for SOCKS support" in output:
        clean_env = os.environ.copy()
        for key in PROXY_ENV_KEYS:
            clean_env.pop(key, None)
        clean_env.pop("PIP_PROXY", None)
        clean_env.pop("pip_proxy", None)
        clean_env["PIP_CONFIG_FILE"] = os.devnull
        clean_env["NO_PROXY"] = "*"
        clean_env["no_proxy"] = "*"
        clean_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        isolated_command = [
            str(py),
            "-m",
            "pip",
            "--isolated",
            "install",
            "-r",
            "requirements.txt",
        ]
        log("Retrying pip in isolated mode without SOCKS or user pip configuration")
        ok, output = run_command(isolated_command, env=clean_env, timeout=600)
    if not ok:
        return "Не удалось установить зависимости.\n" + output

    return f"Зависимости установлены в .venv (Python {version})."


def prepare_database() -> str:
    config = read_env()
    config["DATABASE_URL"] = local_sqlite_url()
    write_env(config)

    db_path = BASE_DIR / "runtime" / "giveaway-bot.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch(exist_ok=True)
    return "Локальная база данных подготовлена. Она хранится в папке runtime внутри проекта."


def backup_database() -> str:
    config = read_env()
    db_path = database_file_path(config)
    if not db_path or not db_path.exists():
        return "База данных ещё не подготовлена, backup создать нельзя."

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"{db_path.stem}-{stamp}{db_path.suffix or '.sqlite3'}"
    try:
        with sqlite3.connect(db_path) as source, sqlite3.connect(backup_path) as destination:
            source.backup(destination)
    except sqlite3.Error as exc:
        try:
            backup_path.unlink()
        except FileNotFoundError:
            pass
        return f"Не удалось создать backup SQLite: {exc}"
    return f"Backup базы создан: {backup_path.relative_to(BASE_DIR)}"


def clear_saved_token() -> str:
    config = read_env()
    config["BOT_TOKEN"] = ""
    write_env(config)
    return "Токен очищен. Для публикации проекта используйте release zip: он не содержит .env."


def database_file_path(config: dict[str, str]) -> Path | None:
    database_url = config.get("DATABASE_URL", "")
    if not database_url.startswith("sqlite://"):
        return None

    raw_path = database_url.removeprefix("sqlite://")
    if not raw_path or raw_path == ":memory:":
        return None

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def validate_config(config: dict[str, str]) -> list[str]:
    errors = []
    if not config.get("BOT_TOKEN"):
        errors.append("Укажите токен бота из BotFather.")
    if not config.get("DATABASE_URL"):
        errors.append("Подготовьте базу данных кнопкой ниже.")
    if not config.get("OWNERS") and not config.get("OWNER_USERNAMES"):
        errors.append("Укажите, кто будет управлять ботом: Telegram ID или username.")
    return errors


def dependency_is_installed(module_name: str, python: Path | None = None) -> bool:
    py = python or python_executable()
    try:
        result = subprocess.run(
            [str(py), "-c", f"import {module_name}"],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def timezone_is_available(timezone_name: str, python: Path | None = None) -> bool:
    py = python or python_executable()
    try:
        result = subprocess.run(
            [str(py), "-c", "from zoneinfo import ZoneInfo; import sys; ZoneInfo(sys.argv[1])", timezone_name],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def check_token_valid(token: str) -> tuple[bool, str]:
    if not token:
        return False, "токен не указан"
    try:
        with urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=8) as response:
            body = response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        return False, f"не удалось проверить через Telegram API: {exc.reason}"
    except Exception as exc:
        return False, f"не удалось проверить: {exc}"
    if '"ok":true' in body:
        return True, "токен валиден"
    return False, "Telegram API не подтвердил токен"


def check_database_available(config: dict[str, str]) -> tuple[bool, str]:
    db_path = database_file_path(config)
    if not db_path:
        return False, "поддерживается автоматическая проверка только SQLite"
    if not db_path.exists():
        return False, "файл базы ещё не создан"
    try:
        with sqlite3.connect(db_path) as connection:
            connection.execute("SELECT 1").fetchone()
    except sqlite3.Error as exc:
        return False, f"ошибка SQLite: {exc}"
    return True, "база доступна"


def check_environment() -> str:
    config = read_env()
    py = python_executable()
    compatible, version = supported_python(py)
    missing_dependencies = [
        package_name
        for module_name, package_name in REQUIRED_MODULES.items()
        if not dependency_is_installed(module_name, py)
    ]
    timezone_name = config.get("TIMEZONE", "Europe/Moscow")
    timezone_ok = timezone_is_available(timezone_name, py)
    token_ok, token_message = check_token_valid(config.get("BOT_TOKEN", ""))
    db_ok, db_message = check_database_available(config)
    lines = [
        f"Python бота: {version} ({py})",
        "Версия Python совместима: " + ("да" if compatible else "нет — нужен Python 3.10 или 3.11"),
        "Зависимости установлены: " + ("да" if not missing_dependencies else "нет: " + ", ".join(missing_dependencies)),
        f"Часовой пояс {timezone_name}: " + ("доступен" if timezone_ok else "не найден — установите tzdata"),
        "Токен валиден: " + ("да" if token_ok else "нет") + f" ({token_message})",
        "База доступна: " + ("да" if db_ok else "нет") + f" ({db_message})",
    ]
    return "\n".join(lines)


def bot_is_running() -> bool:
    pid = read_pid(BOT_PID_PATH)
    return bool(pid and pid_is_running(pid))


def start_bot() -> str:
    terminate_pid_file(BOT_PID_PATH)
    config = read_env()
    if not config.get("DATABASE_URL"):
        config["DATABASE_URL"] = local_sqlite_url()
        write_env(config)

    errors = validate_config(config)
    if errors:
        return " ".join(errors)

    py = python_executable()
    compatible, version = supported_python(py)
    if not compatible:
        return f"Бот не запущен: нужен Python 3.10 или 3.11, найден {version}."
    missing_dependencies = [
        package_name
        for module_name, package_name in REQUIRED_MODULES.items()
        if not dependency_is_installed(module_name, py)
    ]
    if missing_dependencies:
        return "Бот не запущен. Сначала установите зависимости: " + ", ".join(missing_dependencies)
    timezone_name = config.get("TIMEZONE", "Europe/Moscow")
    if not timezone_is_available(timezone_name, py):
        return f"Бот не запущен: часовой пояс {timezone_name} недоступен. Установите tzdata."

    db_path = database_file_path(config)
    if db_path:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_runtime_dir()
    log_path = BOT_LOG_PATH
    try:
        log_file = log_path.open("a", encoding="utf-8")
    except PermissionError:
        log_path = RUNTIME_DIR / f"bot-{time.strftime('%Y%m%d-%H%M%S')}.log"
        log_file = log_path.open("a", encoding="utf-8")

    log_file.write(f"\n=== Запуск {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    log_file.flush()
    popen_options = {
        "cwd": BASE_DIR,
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
        "env": os.environ.copy(),
        "close_fds": True,
    }
    if os.name == "nt":
        popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_options["start_new_session"] = True
    try:
        process = subprocess.Popen(
            [str(py), "app.py"],
            **popen_options,
        )
    finally:
        log_file.close()

    time.sleep(0.5)
    if process.poll() is not None:
        return f"Бот завершился при запуске. Откройте лог {log_path.relative_to(BASE_DIR)}."

    BOT_PID_PATH.write_text(str(process.pid), encoding="utf-8")
    log(f"Started bot PID {process.pid}; log: {log_path.relative_to(BASE_DIR)}")
    return "Бот запущен."


def stop_bot() -> str:
    if not bot_is_running():
        terminate_pid_file(BOT_PID_PATH)
        return "Бот уже остановлен."
    terminate_pid_file(BOT_PID_PATH)
    log("Stopped bot")
    return "Бот остановлен."


def read_tail(path: Path, max_lines: int = 140) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def render_page(message: str = "") -> str:
    config = read_env()
    running = bot_is_running()
    status = "запущен" if running else "остановлен"
    status_class = "ok" if running else "muted"
    db_path = database_file_path(config)
    db_ready = bool(db_path and db_path.exists())
    settings_saved_at = "-"
    if ENV_PATH.exists():
        settings_saved_at = time.strftime("%d.%m.%Y %H:%M", time.localtime(ENV_PATH.stat().st_mtime))

    def value(key: str) -> str:
        return html.escape(config.get(key, ""), quote=True)

    token_saved = bool(config.get("BOT_TOKEN"))
    token_hint = "Токен уже сохранён. Оставьте поле пустым, чтобы не менять его." if token_saved else "Вставьте токен один раз. После сохранения панель его запомнит."
    token_placeholder = "Токен уже сохранён" if token_saved else "Вставьте токен из BotFather"
    owner_summary = config.get("OWNER_USERNAMES") or config.get("OWNERS") or "не указан"
    database_summary = "готова" if db_ready else "ещё не подготовлена"
    message_html = f'<div class="message">{html.escape(message)}</div>' if message else ""

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Панель запуска бота</title>
  <style>
    :root {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Arial, sans-serif;
      color: #15212f;
      background: #f3f5f7;
    }}
    body {{ margin: 0; padding: 24px; }}
    main {{ max-width: 1060px; margin: 0 auto; }}
    h1 {{ margin: 0 0 6px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    p {{ margin: 0 0 14px; color: #526171; line-height: 1.45; }}
    section {{
      background: #fff;
      border: 1px solid #d8e0e8;
      border-radius: 8px;
      padding: 18px;
      margin-top: 16px;
    }}
    label {{ display: block; margin: 13px 0 6px; font-weight: 700; }}
    input {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #c7d0da;
      border-radius: 6px;
      padding: 11px 12px;
      font: inherit;
    }}
    button {{
      border: 0;
      border-radius: 6px;
      padding: 11px 15px;
      font: inherit;
      font-weight: 750;
      color: #fff;
      background: #116b5f;
      cursor: pointer;
    }}
    button.secondary {{ background: #2f4358; }}
    button.warning {{ background: #946200; }}
    button.stop {{ background: #a13b3b; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }}
    .hint {{ margin-top: 5px; color: #657383; font-size: 13px; }}
    .status {{
      display: inline-flex;
      padding: 8px 12px;
      border-radius: 999px;
      font-weight: 800;
      color: #116b5f;
      background: #e6f4f1;
    }}
    .status.muted {{ color: #687685; background: #eef1f4; }}
    .message {{
      margin-top: 14px;
      padding: 11px 12px;
      border-radius: 6px;
      border: 1px solid #cfe4ff;
      background: #eef7ff;
      white-space: pre-wrap;
    }}
    .memory {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 16px;
    }}
    .memory-item {{
      border: 1px solid #d8e0e8;
      border-radius: 8px;
      padding: 12px;
      background: #fff;
    }}
    .memory-label {{
      color: #657383;
      font-size: 13px;
      margin-bottom: 4px;
    }}
    .memory-value {{
      font-weight: 800;
      overflow-wrap: anywhere;
    }}
    details {{
      margin-top: 14px;
      border: 1px solid #d8e0e8;
      border-radius: 6px;
      padding: 12px;
      background: #fafbfc;
    }}
    summary {{
      cursor: pointer;
      font-weight: 750;
    }}
    @media (max-width: 760px) {{
      body {{ padding: 14px; }}
      .row {{ grid-template-columns: 1fr; }}
      .memory {{ grid-template-columns: 1fr; }}
      button {{ width: 100%; }}
      .actions {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>
<main>
  <h1>Панель запуска бота</h1>
  <p>Заполните основные поля один раз. Панель запомнит настройки, и при следующем открытии можно будет сразу запускать бота.</p>
  <div class="status {status_class}">Бот: {status}</div>
  <div class="memory">
    <div class="memory-item">
      <div class="memory-label">Токен бота</div>
      <div class="memory-value">{'сохранён' if token_saved else 'не указан'}</div>
    </div>
    <div class="memory-item">
      <div class="memory-label">Владелец</div>
      <div class="memory-value">{html.escape(owner_summary)}</div>
    </div>
    <div class="memory-item">
      <div class="memory-label">База данных</div>
      <div class="memory-value">{database_summary}</div>
    </div>
    <div class="memory-item">
      <div class="memory-label">Настройки сохранены</div>
      <div class="memory-value">{html.escape(settings_saved_at)}</div>
    </div>
  </div>
  {message_html}

  <section>
    <h2>1. Основные настройки</h2>
    <form method="post" action="/save">
      <label>Токен бота</label>
      <input name="BOT_TOKEN" type="password" autocomplete="off" placeholder="{html.escape(token_placeholder)}">
      <div class="hint">Токен выдает BotFather при создании Telegram-бота. {html.escape(token_hint)}</div>

      <label>Кто будет управлять ботом</label>
      <p>Заполните одно из двух полей ниже. Telegram ID надежнее, username проще.</p>
      <div class="row">
        <div>
          <label>Telegram ID</label>
          <input name="OWNERS" value="{value('OWNERS')}" placeholder="123456789">
          <div class="hint">Можно узнать в Telegram у @userinfobot.</div>
        </div>
        <div>
          <label>Username</label>
          <input name="OWNER_USERNAMES" value="{value('OWNER_USERNAMES')}" placeholder="например: myusername">
          <div class="hint">Пишите без @. Можно оставить пустым, если указан Telegram ID.</div>
        </div>
      </div>

      <div class="row">
        <div>
          <label>Часовой пояс</label>
          <input name="TIMEZONE" value="{value('TIMEZONE')}">
          <div class="hint">Обычно оставьте Europe/Moscow.</div>
        </div>
        <div>
          <label>Фраза для участия через комментарии</label>
          <input name="COMMENT_GIVEAWAY_KEYWORD" value="{value('COMMENT_GIVEAWAY_KEYWORD')}">
          <div class="hint">Например: Участвую.</div>
        </div>
      </div>

      <label>Текст стартового меню</label>
      <input name="START_TEXT" value="{value('START_TEXT')}">
      <div class="hint">Этот текст видит владелец, когда пишет боту /start.</div>

      <details>
        <summary>Дополнительная настройка базы данных</summary>
        <label>Адрес базы данных</label>
        <input name="DATABASE_URL" value="{value('DATABASE_URL')}">
        <div class="hint">Обычно менять не нужно. Кнопка подготовки базы заполнит это поле сама.</div>
      </details>

      <div class="actions">
        <button type="submit">Сохранить настройки</button>
      </div>
    </form>
  </section>

  <section>
    <h2>2. Подготовка</h2>
    <form class="actions" method="post">
      <button class="secondary" formaction="/install-deps">Установить нужные файлы</button>
      <button class="warning" formaction="/prepare-database">Подготовить базу данных</button>
      <button class="secondary" formaction="/check-environment">Проверить окружение</button>
      <button class="secondary" formaction="/backup-database">Backup базы</button>
    </form>
    <p>Сначала нажмите установку нужных файлов, потом подготовку базы данных. База создаётся автоматически внутри папки проекта.</p>
  </section>

  <section>
    <h2>3. Управление ботом</h2>
    <form class="actions" method="post">
      <button formaction="/start-bot">Запустить с сохранёнными настройками</button>
      <button class="stop" formaction="/stop-bot">Остановить бота</button>
      <button class="secondary" formaction="/restart-bot">Перезапустить бота</button>
      <button class="warning" formaction="/clear-token">Очистить сохранённый токен</button>
    </form>
    <p>Если бот уже был запущен, новый запуск сначала остановит старый процесс.</p>
  </section>
</main>
</body>
</html>"""


def redirect(location: str, message: str = "") -> bytes:
    target = location
    if message:
        target += "?" + urlencode({"message": message})
    return target.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        message = parse_qs(parsed.query).get("message", [""])[0]
        body = render_page(message).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8")
        form = {key: values[0] for key, values in parse_qs(raw_body).items()}
        message = self.handle_action(urlparse(self.path).path, form)
        target = redirect("/", message).decode("utf-8")
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", target)
        self.end_headers()

    def handle_action(self, path: str, form: dict[str, str]) -> str:
        try:
            if path == "/save":
                current = read_env()
                updated = {}
                for key in ENV_KEYS:
                    value = form.get(key, "").strip()
                    if key == "BOT_TOKEN" and not value:
                        value = current.get("BOT_TOKEN", "")
                    elif key not in form:
                        value = current.get(key, DEFAULT_ENV.get(key, ""))
                    updated[key] = value
                write_env(updated)
                return "Настройки сохранены."
            if path == "/install-deps":
                return install_dependencies()
            if path == "/prepare-database":
                return prepare_database()
            if path == "/check-environment":
                return check_environment()
            if path == "/backup-database":
                return backup_database()
            if path == "/start-bot":
                return start_bot()
            if path == "/stop-bot":
                return stop_bot()
            if path == "/restart-bot":
                stop_bot()
                return start_bot()
            if path == "/clear-token":
                stop_bot()
                return clear_saved_token()
            return "Неизвестное действие."
        except Exception as exc:
            log(f"Action failed: {exc}")
            return f"Ошибка: {exc}"

    def log_message(self, format: str, *args):
        log(format % args)


def prepare_single_panel_instance(port: int):
    ensure_runtime_dir()
    old_pid = read_pid(PANEL_PID_PATH)
    if old_pid and old_pid != os.getpid() and pid_is_running(old_pid):
        terminate_pid(old_pid)
    PANEL_PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    PANEL_PORT_PATH.write_text(str(port), encoding="utf-8")


def start_server():
    ensure_runtime_dir()
    requested_port = int(os.environ.get("CONTROL_PANEL_PORT", "0") or "0")
    port = requested_port if requested_port and is_port_free(requested_port) else find_free_port(8088, 8188)
    prepare_single_panel_instance(port)
    atexit.register(cleanup_processes)

    def handle_signal(signum, frame):
        cleanup_processes()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    log(f"Control Center started on {url}")
    print(f"Control Center: {url}")

    if os.environ.get("NO_BROWSER") != "1":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    server.serve_forever()


if __name__ == "__main__":
    start_server()
