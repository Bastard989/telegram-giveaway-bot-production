import traceback

from app import dp, bot
from config import OWNERS



@dp.errors_handler(
    exception=Exception
)
async def handle_bot_exceptions(
        update,
        error
):
    traceback.print_exception(type(error), error, error.__traceback__)

    update_data = update.to_python() if hasattr(update, "to_python") else update
    message = update_data.get("message") or update_data.get("callback_query", {}).get("message", {})
    user = update_data.get("callback_query", {}).get("from") or message.get("from", {})

    user_id = user.get("id", "unknown")
    username = user.get("username", "unknown")
    message_text = message.get("text", "")

    for owner_id in OWNERS:
        await bot.send_message(
            chat_id=owner_id,
            text=f'<b>🚫  Произошла непредвиденная ошибка</b>\n\nID пользователя: {user_id}\nUsername пользователя: {username}\n\nТекст сообщения:\n<code>{message_text}</code>\n\nТекст ошибки:\n<code>{error}</code>'
        )

    return True
