from aiogram import Dispatcher
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware

from config import is_owner


class OwnerAccessMiddleware(BaseMiddleware):
    async def on_pre_process_callback_query(self, callback_query, data):
        if callback_query.data and callback_query.data.startswith("admin_"):
            if not is_owner(callback_query.from_user.id, callback_query.from_user.username):
                await callback_query.answer("Доступ запрещен", show_alert=True)
                raise CancelHandler()

    async def on_pre_process_message(self, message, data):
        dispatcher = Dispatcher.get_current()
        if not dispatcher or not message.from_user:
            return

        state = dispatcher.current_state(
            chat=message.chat.id,
            user=message.from_user.id,
        )
        current_state = await state.get_state()

        if current_state and "Give" in current_state and not is_owner(message.from_user.id, message.from_user.username):
            await message.answer("Доступ запрещен")
            await state.finish()
            raise CancelHandler()
