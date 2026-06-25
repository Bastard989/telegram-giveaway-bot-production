import atexit
import html
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse


BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / "runtime"
ENV_PATH = BASE_DIR / ".env"
BOT_PID_PATH = RUNTIME_DIR / "bot.pid"
PANEL_PID_PATH = RUNTIME_DIR / "control-panel.pid"
PANEL_PORT_PATH = RUNTIME_DIR / "control-panel.port"
BOT_LOG_PATH = RUNTIME_DIR / "bot.log"
PANEL_LOG_PATH = RUNTIME_DIR / "control-panel.log"

ENV_KEYS = [
    "BOT_TOKEN",
    "DATABASE_URL",
    "OWNERS",
    "OWNER_USERNAMES",
    "TIMEZONE",
    "START_TEXT",
    "COMMENT_GIVEAWAY_KEYWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
]

DEFAULT_ENV = {
    "BOT_TOKEN": "",
    "DATABASE_URL": "postgres://giveaway_bot:giveaway_bot@127.0.0.1:55432/giveaway_bot",
    "OWNERS": "",
    "OWNER_USERNAMES": "",
    "TIMEZONE": "Europe/Moscow",
    "START_TEXT": "Главное меню:",
    "COMMENT_GIVEAWAY_KEYWORD": "Участвую",
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "55432",
    "POSTGRES_DB": "giveaway_bot",
    "POSTGRES_USER": "giveaway_bot",
    "POSTGRES_PASSWORD": "giveaway_bot",
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


def build_database_url(config: dict[str, str]) -> str:
    return (
        f"postgres://{config['POSTGRES_USER']}:{config['POSTGRES_PASSWORD']}"
        f"@{config['POSTGRES_HOST']}:{config['POSTGRES_PORT']}/{config['POSTGRES_DB']}"
    )


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


def pip_executable() -> Path:
    if os.name == "nt":
        candidate = BASE_DIR / ".venv" / "Scripts" / "pip.exe"
    else:
        candidate = BASE_DIR / ".venv" / "bin" / "pip"
    return candidate


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
        ok, output = run_command([sys.executable, "-m", "venv", str(venv_dir)], timeout=120)
        if not ok:
            return "Не удалось создать .venv.\n" + output

    pip_path = pip_executable()
    ok, output = run_command([str(pip_path), "install", "-r", "requirements.txt"], timeout=600)
    if not ok:
        return "Не удалось установить зависимости.\n" + output

    return "Зависимости установлены."


def docker_command() -> list[str] | None:
    ok, _ = run_command(["docker", "compose", "version"], timeout=15)
    if ok:
        return ["docker", "compose"]

    ok, _ = run_command(["docker-compose", "version"], timeout=15)
    if ok:
        return ["docker-compose"]

    return None


def prepare_postgres() -> str:
    config = read_env()
    config["POSTGRES_HOST"] = config.get("POSTGRES_HOST") or "127.0.0.1"
    config["POSTGRES_DB"] = config.get("POSTGRES_DB") or "giveaway_bot"
    config["POSTGRES_USER"] = config.get("POSTGRES_USER") or "giveaway_bot"
    config["POSTGRES_PASSWORD"] = config.get("POSTGRES_PASSWORD") or "giveaway_bot"

    current_port = int(config.get("POSTGRES_PORT") or "55432")
    if not is_port_free(current_port):
        current_port = find_free_port(55432, 55532)
    config["POSTGRES_PORT"] = str(current_port)
    config["DATABASE_URL"] = build_database_url(config)
    write_env(config)

    command = docker_command()
    if not command:
        return "Docker не найден. Установите Docker Desktop или подключите внешний PostgreSQL в поле DATABASE_URL."

    env = os.environ.copy()
    env.update(config)
    ok, output = run_command([*command, "up", "-d", "postgres"], env=env, timeout=180)
    if not ok:
        return "PostgreSQL не запустился.\n" + output

    return f"PostgreSQL запущен. База проекта: runtime/postgres-data, порт: {current_port}."


def validate_config(config: dict[str, str]) -> list[str]:
    errors = []
    if not config.get("BOT_TOKEN"):
        errors.append("Укажите токен бота из BotFather.")
    if not config.get("DATABASE_URL"):
        errors.append("Подготовьте базу данных кнопкой ниже.")
    if not config.get("OWNERS") and not config.get("OWNER_USERNAMES"):
        errors.append("Укажите, кто будет управлять ботом: Telegram ID или username.")
    return errors


def bot_is_running() -> bool:
    pid = read_pid(BOT_PID_PATH)
    return bool(pid and pid_is_running(pid))


def start_bot() -> str:
    terminate_pid_file(BOT_PID_PATH)
    config = read_env()
    errors = validate_config(config)
    if errors:
        return " ".join(errors)

    ensure_runtime_dir()
    BOT_LOG_PATH.write_text("", encoding="utf-8")
    py = python_executable()
    with BOT_LOG_PATH.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            [str(py), "app.py"],
            cwd=BASE_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            start_new_session=(os.name != "nt"),
        )

    BOT_PID_PATH.write_text(str(process.pid), encoding="utf-8")
    log(f"Started bot PID {process.pid}")
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

    def value(key: str) -> str:
        return html.escape(config.get(key, ""), quote=True)

    token_hint = "Токен сохранен. Оставьте поле пустым, чтобы не менять его." if config.get("BOT_TOKEN") else ""
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
      button {{ width: 100%; }}
      .actions {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>
<main>
  <h1>Панель запуска бота</h1>
  <p>Заполните основные поля, подготовьте базу данных и запустите бота. В код заходить не нужно.</p>
  <div class="status {status_class}">Бот: {status}</div>
  {message_html}

  <section>
    <h2>1. Основные настройки</h2>
    <form method="post" action="/save">
      <label>Токен бота</label>
      <input name="BOT_TOKEN" type="password" autocomplete="off" placeholder="Вставьте токен из BotFather">
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
        <summary>Дополнительные настройки базы данных</summary>
        <label>Адрес базы данных</label>
        <input name="DATABASE_URL" value="{value('DATABASE_URL')}">
        <div class="hint">Обычно менять не нужно. Кнопка подготовки базы заполнит это поле сама.</div>

        <div class="row">
          <div>
            <label>Порт базы</label>
            <input name="POSTGRES_PORT" value="{value('POSTGRES_PORT')}">
          </div>
          <div>
            <label>Название базы</label>
            <input name="POSTGRES_DB" value="{value('POSTGRES_DB')}">
          </div>
        </div>

        <div class="row">
          <div>
            <label>Логин базы</label>
            <input name="POSTGRES_USER" value="{value('POSTGRES_USER')}">
          </div>
          <div>
            <label>Пароль базы</label>
            <input name="POSTGRES_PASSWORD" value="{value('POSTGRES_PASSWORD')}">
          </div>
        </div>
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
      <button class="warning" formaction="/prepare-postgres">Подготовить базу данных</button>
    </form>
    <p>Сначала нажмите установку нужных файлов, потом подготовку базы данных. Для базы нужен Docker Desktop.</p>
  </section>

  <section>
    <h2>3. Управление ботом</h2>
    <form class="actions" method="post">
      <button formaction="/start-bot">Запустить бота</button>
      <button class="stop" formaction="/stop-bot">Остановить бота</button>
      <button class="secondary" formaction="/restart-bot">Перезапустить бота</button>
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
            if path == "/prepare-postgres":
                return prepare_postgres()
            if path == "/start-bot":
                return start_bot()
            if path == "/stop-bot":
                return stop_bot()
            if path == "/restart-bot":
                stop_bot()
                return start_bot()
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
