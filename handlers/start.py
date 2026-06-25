from aiogram import types
from aiogram.dispatcher import FSMContext

from app import dp
from keyboards import kb_admin_menu
from .admin.functions_for_active_gives.handle_new_members_from_button_giveaways import manage_new_members_from_button_gives
from .admin.functions_for_active_gives.check_channels_subscriptions import check_channels_subscriptions
from database import GiveawayWinner, TemporaryUsers, GiveAwayStatistic
from config import is_owner, start_text


@dp.message_handler(
    commands=['start'],
    state='*'
)
async def process_start(jam: types.Message, state: FSMContext):
    await state.finish()


    if ' ' in jam.text:
        give_callback_value = jam.text.split(' ')[1]

        if '=watchresult' in give_callback_value:
            give_callback_value = give_callback_value.split('=')[0]

            await TemporaryUsers().add_user(
                callback_value=give_callback_value,
                new_member_id=jam.from_user.id,
                new_member_username=jam.from_user.username
            )

            await jam.answer(
                '💎  <b>Вы подписались на результаты розыгрыша, ожидайте!</b>',
            )


        elif '=getresults' in give_callback_value:
            give_callback_value = give_callback_value.split('=')[0]

            text = "💎  <b>Результаты розыгрыша:</b>\n\n"
            winners_users = await GiveawayWinner().get_winners(
                giveaway_callback_value=give_callback_value
            )
            if not winners_users:
                winners_data = await GiveAwayStatistic().filter(
                    giveaway_callback_value=give_callback_value
                ).all().values('winners')
                winners_users = winners_data[0]['winners'] or [] if winners_data else []

            if not winners_users:
                await jam.answer('Результаты еще не опубликованы.')
                return

            for i in range(len(winners_users)):
                user_info = winners_users[i]
                username = user_info.get('username') or user_info.get('first_name') or user_info['user_id']
                prefix = 'запасной ' if user_info.get('is_reserve') else ''
                name = f"@{username}" if user_info.get('username') else str(username)
                text += f"{prefix}{user_info['place']} место - {name}"
                if i < len(winners_users) - 1:
                    text += "\n"

            await jam.answer(text=text)



        else:
            if await check_channels_subscriptions(
                    give_callback_value=give_callback_value,
                    user_id=jam.from_user.id
            ):

                await manage_new_members_from_button_gives(
                    jam=jam,
                    state=state,
                    give_callback_value=give_callback_value
                )

            else:
                await jam.answer(
                    '💎  <b>Вы не подписаны на все каналы!</b>'
                )


    else:
        await state.finish()
        if is_owner(jam.from_user.id, jam.from_user.username):
            await jam.answer(
                start_text,
                reply_markup=kb_admin_menu
            )
        else:
            await jam.answer(
                'Это бот для участия в розыгрышах. Для участия нажмите кнопку в посте розыгрыша.'
            )
