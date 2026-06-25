from aiogram import types
from aiogram.dispatcher import FSMContext
from app import dp
from database import GiveAway
from keyboards import *
from states import ActiveGivesStates



@dp.callback_query_handler(
    lambda c: c.data != bt_admin_cancel_action.callback_data,
    state=ActiveGivesStates.select_give,
)
async def show_active_selected_give(
    jam: types.CallbackQuery,
    state: FSMContext,
    give_callback_value: str = False
):

    if not give_callback_value:
        give_callback_value = jam.data
    await state.update_data(give_callback_value=give_callback_value)

    give_data = await GiveAway().get_give_data(
        user_id=jam.from_user.id,
        callback_value=give_callback_value
    )

    message_text = ''
    for give in give_data:
        await state.update_data(type_of_give=give['type'])
        publish_channel = give["publish_channel_name"] or "не выбран"
        give_type = "По комментариям" if give["type"] == "comments" else "По кнопке"
        message_text = f'<b>Тип розыгрыша:</b> <code>{give_type}</code>\n<b>Название розыгрыша:</b> <code>{give["name"]}</code>\n<b>Канал публикации:</b> <code>{publish_channel}</code>\n\n<b>Текст:</b>\n{give["text"]}\n\n<b>Фото:</b> <code>{"Нет" if give["photo_id"] == "False" else "Да"}</code>\n<b>Дата окончания:</b> <code>{give["over_date"]}</code>\n<b>Капча:</b> <code>{"Да" if give["captcha"] else "Нет"}</code>\n<b>Количество победителей:</b> <code' \
                       f'>{give["winners_count"]}</code>\n<b>Запасных победителей:</b> <code>{give["reserve_winners_count"]}</code>'


    await jam.message.edit_text(
        message_text,
        reply_markup=kb_admin_active_gives
    )
    await ActiveGivesStates.manage_selected_give.set()
