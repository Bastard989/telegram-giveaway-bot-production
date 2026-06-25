from aiogram import types
from aiogram.dispatcher import FSMContext

from app import bot, dp
from database import GiveAway, GiveawayCondition, TelegramChannel
from states import CreatedGivesStates
from keyboards import *



@dp.message_handler(
    state=CreatedGivesStates.add_channel,
)
async def get_channel_data(
    jam: types.Message,
    state: FSMContext
):
    try:

        channel_data = jam.forward_from_chat

        if channel_data.type == 'channel':

            try:
                member_info = await bot.get_chat_member(
                    chat_id=channel_data.id,
                    user_id=bot.id
                )

                if member_info.status == 'administrator':
                    model = TelegramChannel()
                    state_data = await state.get_data()
                    give_callback_value = state_data['give_callback_value']

                    if not await model.exists_channel(
                            channel_id=channel_data.id,
                            give_callback_value=give_callback_value,
                            role="condition",
                    ):

                        await model.add_channel(
                            owner_id=jam.from_user.id,
                            channel_id=channel_data.id,
                            give_callback_value=give_callback_value,
                            name=channel_data.title,
                            role="condition",
                        )
                        await GiveawayCondition().add_condition(
                            giveaway_callback_value=give_callback_value,
                            target_channel_id=channel_data.id,
                            target_channel_name=channel_data.title,
                        )

                        await jam.answer(
                            '✅  <b>Канал успешно добавлен</b>',
                            reply_markup=kb_admin_manage_channels
                        )
                        await CreatedGivesStates.manage_channels.set()

                    else:
                        await jam.answer(
                            '🚫  <b>Данный канал уже добавлен, попробуйте другой:</b> ',
                            reply_markup=kb_admin_cancel_action
                        )


                else:
                    await jam.answer(
                        '🚫  Ошибка! </b>Проверьте права бота и перешлите репостом сообщение из канала еще раз:</b> ',
                        reply_markup=kb_admin_cancel_action
                    )


            except Exception as error:
                print(error)
                await jam.answer(
                    '🚫  <b>Ошибка! Проверьте права бота и перешлите репостом сообщение из канала еще раз:</b> ',
                    reply_markup=kb_admin_cancel_action
                )


        else:
            await jam.answer(
                '🚫  <b>Это не канал, попробуйте еще раз:</b>',
                reply_markup=kb_admin_cancel_action
            )

    except AttributeError:
        await jam.answer(
            '🚫  <b>Это не канал, попробуйте еще раз:</b>',
            reply_markup=kb_admin_cancel_action
        )


@dp.message_handler(
    state=CreatedGivesStates.add_publish_channel,
)
async def get_publish_channel_data(
    jam: types.Message,
    state: FSMContext
):
    try:
        channel_data = jam.forward_from_chat

        if channel_data.type == 'channel':
            try:
                member_info = await bot.get_chat_member(
                    chat_id=channel_data.id,
                    user_id=bot.id
                )

                if member_info.status == 'administrator':
                    state_data = await state.get_data()
                    give_callback_value = state_data['give_callback_value']

                    await TelegramChannel().filter(
                        give_callback_value=give_callback_value,
                        role="publish",
                    ).delete()

                    await TelegramChannel().add_channel(
                        owner_id=jam.from_user.id,
                        channel_id=channel_data.id,
                        give_callback_value=give_callback_value,
                        name=channel_data.title,
                        role="publish",
                    )
                    await GiveAway().set_publish_channel(
                        callback_value=give_callback_value,
                        channel_id=channel_data.id,
                        channel_name=channel_data.title,
                    )

                    await jam.answer(
                        '✅  <b>Канал публикации успешно выбран</b>',
                        reply_markup=kb_admin_manage_channels
                    )
                    await CreatedGivesStates.manage_channels.set()

                else:
                    await jam.answer(
                        '🚫  <b>Ошибка! Проверьте права бота и перешлите репостом сообщение из канала еще раз:</b> ',
                        reply_markup=kb_admin_cancel_action
                    )

            except Exception as error:
                print(error)
                await jam.answer(
                    '🚫  <b>Ошибка! Проверьте права бота и перешлите репостом сообщение из канала еще раз:</b> ',
                    reply_markup=kb_admin_cancel_action
                )

        else:
            await jam.answer(
                '🚫  <b>Это не канал, попробуйте еще раз:</b>',
                reply_markup=kb_admin_cancel_action
            )

    except AttributeError:
        await jam.answer(
            '🚫  <b>Это не канал, попробуйте еще раз:</b>',
            reply_markup=kb_admin_cancel_action
        )


