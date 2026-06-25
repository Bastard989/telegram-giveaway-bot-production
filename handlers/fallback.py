from aiogram import types
from aiogram.dispatcher import FSMContext

from app import dp
from config import is_owner
from keyboards import kb_admin_menu


@dp.message_handler(state='*')
async def fallback_message(jam: types.Message, state: FSMContext):
    if not is_owner(jam.from_user.id, jam.from_user.username):
        await jam.answer(
            'Это бот для участия в розыгрышах. Для участия нажмите кнопку в посте розыгрыша.'
        )
        return

    current_state = await state.get_state()
    if current_state:
        await jam.answer(
            'Я не понял это сообщение на текущем шаге. Нажмите «Назад» или отправьте /start, чтобы открыть меню заново.'
        )
        return

    await jam.answer(
        'Главное меню:',
        reply_markup=kb_admin_menu
    )
