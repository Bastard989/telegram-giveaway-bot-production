from aiogram import types
from aiogram.dispatcher import FSMContext
from app import dp
from datetime import datetime, timedelta

from config import timezone_info
from database import GiveawayParticipant
from keyboards import *
from states import ActiveGivesStates




@dp.callback_query_handler(
    text=bt_admin_show_statistic.callback_data,
    state=ActiveGivesStates.manage_selected_give
)
async def show_give_statistic(
    jam: types.CallbackQuery,
    state: FSMContext
):
    await ActiveGivesStates.show_statistic.set()
    state_data = await state.get_data()

    participants = await GiveawayParticipant().get_participants(
        giveaway_callback_value=state_data['give_callback_value']
    )

    if participants:
        count_members_in_24_hours = 0
        for participant in participants:
            joined_at = participant['joined_at']
            if joined_at > datetime.now(timezone_info) - timedelta(days=1):
                count_members_in_24_hours += 1

        await jam.message.edit_text(
            f'➖  <b>Количество участников за последние 24 часа:</b> {count_members_in_24_hours}\n➖  <b>Общее количество участников:</b> {len(participants)}',
            reply_markup=kb_admin_cancel_action
        )

    else:
        await jam.answer('В розыгрыше нет участников')
