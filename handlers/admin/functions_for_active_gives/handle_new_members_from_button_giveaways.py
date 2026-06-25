from aiogram import types
from aiogram.dispatcher import FSMContext

from app import dp, bot
from database import GiveAway, GiveawayParticipant, GiveAwayStatistic
from utils import Captcha


captcha = Captcha()



async def manage_new_members_from_button_gives(
    jam: types.Message,
    give_callback_value: str,
    state: FSMContext
):


    if not await GiveawayParticipant().exists_participant(
        giveaway_callback_value=give_callback_value,
        user_id=jam.from_user.id,
    ):

        give_data = await GiveAway().filter(callback_value=give_callback_value).all().values(
            'over_date',
            'captcha',
            'run_status'
        )

        if not give_data:
            await jam.answer(
                '<b>Розыгрыш не найден</b>'
            )
            return

        for give in give_data:
            if not give['run_status']:
                await jam.answer(
                    '<b>Этот розыгрыш еще не запущен или уже завершен</b>'
                )
                return

            if give['captcha']:
                await state.update_data(give_callback_value=give_callback_value)

                captcha.register_handlers(dp)
                await bot.send_message(
                    jam.from_user.id,
                    captcha.get_caption(),
                    reply_markup=captcha.get_captcha_keyboard()
                )


            else:
                await jam.answer(
                    '<b>Замечательно! Вы участвуете!</b>'
                )


                await GiveawayParticipant().add_participant(
                    giveaway_callback_value=give_callback_value,
                    user_id=jam.from_user.id,
                    username=jam.from_user.username,
                    first_name=jam.from_user.first_name,
                    last_name=jam.from_user.last_name,
                    subscription_checked=True,
                    captcha_passed=False,
                )
                await GiveAwayStatistic().update_statistic_members(
                    giveaway_callback_value=give_callback_value,
                    new_member_username=jam.from_user.username,
                    new_member_id=jam.from_user.id
                )

    else:
        await jam.answer(
            '<b>Вы уже участвуете! Ожидайте итогов!</b>'
        )
