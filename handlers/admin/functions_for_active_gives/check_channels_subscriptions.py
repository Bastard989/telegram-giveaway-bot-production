from aiogram.utils.exceptions import BadRequest

from database import GiveawayCondition
from app import bot




async def check_channels_subscriptions(
        give_callback_value: str,
        user_id: int,
        owner_id: int = False
) -> bool:

    channels_data = await GiveawayCondition().get_conditions(
        giveaway_callback_value=give_callback_value
    )

    if not channels_data:
        return False

    for channel in channels_data:

        channel_id = channel['target_channel_id']
        try:
            user_channel_info = await bot.get_chat_member(
                chat_id=channel_id,
                user_id=user_id
            )
        except BadRequest:
            return False

        if user_channel_info['status'] in ('member', 'administrator', 'creator'):
            continue

        else:
            return False

    else:
        return True


