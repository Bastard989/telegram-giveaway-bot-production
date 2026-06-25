import asyncio
import html
import os
import signal
import sys
from collections import deque
from pathlib import Path
from urllib.parse import urlencode

from aiohttp import web


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
LOG_LINES = deque(maxlen=160)
BOT_PROCESS: asyncio.subprocess.Process | None = None

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
    "DATABASE_URL": "sqlite://data/giveaway_bot.sqlite3",
    "OWNERS": "",
    "OWNER_USERNAMES": "",
    "TIMEZONE": "Europe/Moscow",
    "START_TEXT": "Главное меню:",
    "COMMENT_GIVEAWAY_KEYWORD": "Участвую",
}


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
    lines = []
    for key in ENV_KEYS:
        value = data.get(key, "")
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key}="{escaped}"')
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def redirect_with_message(message: str):
    raise web.HTTPFound("/?" + urlencode({"message": message}))


def bot_is_running() -> bool:
    return BOT_PROCESS is not None and BOT_PROCESS.returncode is None


def validate_config(config: dict[str, str]) -> list[str]:
    errors = []
    if not config.get("BOT_TOKEN"):
        errors.append("Укажите токен бота из BotFather.")
    if not config.get("DATABASE_URL"):
        errors.append("Укажите базу данных. Для простого запуска оставьте sqlite://data/giveaway_bot.sqlite3.")
    if not config.get("OWNERS") and not config.get("OWNER_USERNAMES"):
        errors.append("Укажите Telegram ID владельца или username владельца.")
    return errors


async def collect_logs(process: asyncio.subprocess.Process):
    if not process.stdout:
        return
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        LOG_LINES.append(line.decode("utf-8", errors="replace").rstrip())


async def start_bot_process() -> str:
    global BOT_PROCESS

    if bot_is_running():
        return "Бот уже запущен."

    config = read_env()
    errors = validate_config(config)
    if errors:
        return " ".join(errors)

    BOT_PROCESS = await asyncio.create_subprocess_exec(
        sys.executable,
        "app.py",
        cwd=str(BASE_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ},
    )
    LOG_LINES.append(f"Started bot process PID {BOT_PROCESS.pid}")
    asyncio.create_task(collect_logs(BOT_PROCESS))
    return "Бот запущен."


async def stop_bot_process() -> str:
    global BOT_PROCESS

    if not bot_is_running():
        BOT_PROCESS = None
        return "Бот уже остановлен."

    assert BOT_PROCESS is not None
    BOT_PROCESS.send_signal(signal.SIGTERM)
    try:
        await asyncio.wait_for(BOT_PROCESS.wait(), timeout=10)
    except asyncio.TimeoutError:
        BOT_PROCESS.kill()
        await BOT_PROCESS.wait()

    LOG_LINES.append("Bot process stopped")
    BOT_PROCESS = None
    return "Бот остановлен."


def render_page(config: dict[str, str], message: str = "") -> str:
    running = bot_is_running()
    status = "запущен" if running else "остановлен"
    status_class = "ok" if running else "muted"
    masked_token = "Токен уже сохранен. Оставьте поле пустым, чтобы не менять его." if config.get("BOT_TOKEN") else ""
    logs = "\n".join(html.escape(line) for line in LOG_LINES) or "Логи появятся после запуска."

    def value(key: str) -> str:
        return html.escape(config.get(key, ""), quote=True)

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Telegram Giveaway Bot</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #17202a;
      background: #f4f6f8;
    }}
    body {{
      margin: 0;
      padding: 28px;
    }}
    main {{
      max-width: 960px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    p {{
      margin: 0 0 18px;
      color: #4d5b67;
    }}
    section {{
      background: #ffffff;
      border: 1px solid #d9e0e7;
      border-radius: 8px;
      padding: 18px;
      margin-top: 16px;
    }}
    label {{
      display: block;
      margin: 14px 0 6px;
      font-weight: 650;
    }}
    input {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #c8d1da;
      border-radius: 6px;
      padding: 11px 12px;
      font: inherit;
      background: #fff;
    }}
    .hint {{
      margin-top: 5px;
      font-size: 13px;
      color: #667481;
    }}
    .row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    button {{
      border: 0;
      border-radius: 6px;
      padding: 11px 16px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      background: #136f63;
      color: #fff;
    }}
    button.secondary {{
      background: #314458;
    }}
    button.stop {{
      background: #a33b3b;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      padding: 0 12px;
      border-radius: 999px;
      font-weight: 750;
      background: #e8f4f1;
      color: #136f63;
    }}
    .status.muted {{
      background: #eef1f4;
      color: #5f6d78;
    }}
    .message {{
      padding: 10px 12px;
      background: #eef7ff;
      border: 1px solid #cfe6ff;
      border-radius: 6px;
      margin-top: 16px;
    }}
    pre {{
      min-height: 190px;
      overflow: auto;
      margin: 0;
      padding: 14px;
      border-radius: 6px;
      background: #111820;
      color: #d7e2ec;
      font-size: 13px;
      line-height: 1.45;
      white-space: pre-wrap;
    }}
    @media (max-width: 720px) {{
      body {{ padding: 16px; }}
      .row {{ grid-template-columns: 1fr; }}
      .actions {{ flex-direction: column; }}
      button {{ width: 100%; }}
    }}
  </style>
</head>
<body>
<main>
  <h1>Telegram Giveaway Bot</h1>
  <p>Локальная панель запуска. Данные сохраняются только в файл .env на этом компьютере.</p>
  <div class="status {status_class}">Статус: {status}</div>
  {f'<div class="message">{html.escape(message)}</div>' if message else ''}

  <section>
    <form method="post" action="/save">
      <label for="bot_token">Токен бота</label>
      <input id="bot_token" name="BOT_TOKEN" type="password" autocomplete="off" placeholder="123456:ABCDEF или оставьте пустым">
      <div class="hint">{html.escape(masked_token)}</div>

      <div class="row">
        <div>
          <label for="owners">Telegram ID владельца</label>
          <input id="owners" name="OWNERS" value="{value('OWNERS')}" placeholder="123456789">
          <div class="hint">Надёжнее username. Можно узнать через @userinfobot.</div>
        </div>
        <div>
          <label for="owner_usernames">Username владельца</label>
          <input id="owner_usernames" name="OWNER_USERNAMES" value="{value('OWNER_USERNAMES')}" placeholder="username без @">
          <div class="hint">Можно оставить пустым, если указан Telegram ID.</div>
        </div>
      </div>

      <label for="database_url">База данных</label>
      <input id="database_url" name="DATABASE_URL" value="{value('DATABASE_URL')}" placeholder="sqlite://data/giveaway_bot.sqlite3">
      <div class="hint">Для простого запуска оставьте SQLite. Для сервера можно указать PostgreSQL URL.</div>

      <div class="row">
        <div>
          <label for="timezone">Часовой пояс</label>
          <input id="timezone" name="TIMEZONE" value="{value('TIMEZONE')}">
        </div>
        <div>
          <label for="keyword">Ключевое слово комментария</label>
          <input id="keyword" name="COMMENT_GIVEAWAY_KEYWORD" value="{value('COMMENT_GIVEAWAY_KEYWORD')}">
        </div>
      </div>

      <label for="start_text">Текст стартового меню</label>
      <input id="start_text" name="START_TEXT" value="{value('START_TEXT')}">

      <div class="actions">
        <button type="submit">Сохранить настройки</button>
      </div>
    </form>
  </section>

  <section>
    <form class="actions" method="post" action="/start">
      <button type="submit">Запустить бота</button>
      <button class="stop" type="submit" formaction="/stop">Остановить бота</button>
      <button class="secondary" type="submit" formaction="/restart">Перезапустить</button>
    </form>
  </section>

  <section>
    <h2>Логи</h2>
    <pre>{logs}</pre>
  </section>
</main>
</body>
</html>"""


async def index(request: web.Request):
    return web.Response(
        text=render_page(read_env(), request.query.get("message", "")),
        content_type="text/html",
    )


async def save(request: web.Request):
    form = await request.post()
    current = read_env()
    updated = {}
    for key in ENV_KEYS:
        value = str(form.get(key, "")).strip()
        if key == "BOT_TOKEN" and not value:
            value = current.get("BOT_TOKEN", "")
        updated[key] = value

    write_env(updated)
    redirect_with_message("Настройки сохранены.")


async def start(request: web.Request):
    message = await start_bot_process()
    redirect_with_message(message)


async def stop(request: web.Request):
    message = await stop_bot_process()
    redirect_with_message(message)


async def restart(request: web.Request):
    await stop_bot_process()
    message = await start_bot_process()
    redirect_with_message(message)


async def cleanup(app: web.Application):
    if bot_is_running():
        await stop_bot_process()


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_post("/save", save)
    app.router.add_post("/start", start)
    app.router.add_post("/stop", stop)
    app.router.add_post("/restart", restart)
    app.on_cleanup.append(cleanup)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="127.0.0.1", port=8088)
