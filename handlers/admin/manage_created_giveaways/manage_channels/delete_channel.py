from aiogram import types
from aiogram.dispatcher import FSMContext

from app import dp
from database import GiveAway, GiveawayCondition, TelegramChannel
from states import CreatedGivesStates
from keyboards import *



@dp.callback_query_handler(
    text=bt_admin_delete_channel.callback_data,
    state=CreatedGivesStates.show_connected_channel
)
async def delete_channel(
    jam: types.CallbackQuery,
    state: FSMContext
):
    state_data = await state.get_data()
    channel_data = await TelegramChannel().get_channel_data(
        channel_callback_value=state_data['channel_callback_value']
    )

    for channel in channel_data:
        if channel['role'] == 'condition':
            await GiveawayCondition().delete_condition(
                giveaway_callback_value=state_data['give_callback_value'],
                target_channel_id=channel['channel_id'],
            )
        elif channel['role'] == 'publish':
            await GiveAway().clear_publish_channel(
                callback_value=state_data['give_callback_value'],
            )

    await TelegramChannel().delete_channel(
        channel_callback_value=state_data['channel_callback_value']
    )

    await jam.message.edit_text(
        '✅  <b>Канал успешно удален</b>',
        reply_markup=kb_admin_manage_channels
    )

    await CreatedGivesStates.manage_channels.set()
