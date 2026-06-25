from datetime import datetime

from app import bot
from config import timezone_info
from database import GiveAway, TemporaryUsers


async def delete_and_inform_of_the_end_give(
    give_callback_value: str,
    winners: list,
    summary_count_users: int,
):
    give_data = await GiveAway().filter(callback_value=give_callback_value).all().values(
        'owner_id',
        'name'
    )



    for give in give_data:

        if summary_count_users >= len(winners):

            text = f'🎁  <b>Розыгрыш завершен</b>\n\n<b>Название:</b> {give["name"]}\n<b>Общее количество участников:</b> {summary_count_users}\n\n<b>Победители:</b>\n\n'
            for i in range(len(winners)):
                user_info = winners[i]
                username = user_info.get('username')
                name = f"@{username}" if username else user_info.get('first_name') or user_info['user_id']
                prefix = 'Запасной ' if user_info.get('is_reserve') else ''
                text += f"{prefix}{user_info['place']} место - {name}"
                if i < len(winners) - 1:
                    text += "\n"


            await bot.send_message(
                chat_id=give['owner_id'],
                text=text
            )

        else:
            await bot.send_message(
                chat_id=give['owner_id'],
                text=f'🎁  <b>Розыгрыш завершен</b>\n\n<b>Название:</b> {give["name"]}\n<b>Победителей выбрать не удалось, участников слишком мало</b>'
            )


    await GiveAway().filter(callback_value=give_callback_value).update(
        run_status=False,
        finished_at=datetime.now(timezone_info),
    )
    await TemporaryUsers().filter(giveaway_callback_value=give_callback_value).delete()
