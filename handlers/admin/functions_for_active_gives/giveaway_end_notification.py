from app import bot
from database import GiveawayParticipant


async def send_giveaway_end_notification(
    give_callback_value: str
):
    members = await GiveawayParticipant().get_participants(
        giveaway_callback_value=give_callback_value
    )

    for member in members:
        await bot.send_message(
            chat_id=member['user_id'],
            text='💎  <b>Конкурс скоро будет завершен – поторопись!</b>'
        )
