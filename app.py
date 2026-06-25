import asyncio
import logging

from aiogram.contrib.fsm_storage.files import JSONStorage
from aiogram import Bot, Dispatcher, executor
from aiogram.types import ParseMode

from config import *
from database import initialize_database
from middlewares import OwnerAccessMiddleware


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

missing_config = []
if not bot_token:
    missing_config.append("BOT_TOKEN")
if not database_url:
    missing_config.append("DATABASE_URL")
if not OWNERS and not OWNER_USERNAMES:
    missing_config.append("OWNERS или OWNER_USERNAMES")

if missing_config:
    raise RuntimeError(
        "Не заполнен конфиг: " + ", ".join(missing_config) + ". "
        "Создайте .env по примеру .env.example."
    )



bot = Bot(
    token=bot_token,
    parse_mode=ParseMode.HTML
)

storage = JSONStorage("fsm_state.json")
dp = Dispatcher(
    bot,
    storage=storage
)
dp.middleware.setup(OwnerAccessMiddleware())



async def on_startup(dispatcher):
    await initialize_database()
    asyncio.create_task(manage_active_giveaways())




if __name__ == '__main__':
    from handlers import dp, manage_active_giveaways

    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
