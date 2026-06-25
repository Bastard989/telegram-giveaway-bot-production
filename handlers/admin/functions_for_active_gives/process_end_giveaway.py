import random

from app import bot
from database import GiveAway, GiveawayParticipant, GiveawayWinner, TelegramChannel, GiveAwayStatistic
from .inform_of_the_end_give import delete_and_inform_of_the_end_give


def format_user(user_info: dict) -> str:
    if user_info.get('username'):
        return f"@{user_info['username']}"

    full_name = " ".join(
        item for item in [user_info.get('first_name'), user_info.get('last_name')]
        if item
    )
    return full_name or str(user_info['user_id'])



async def process_end_of_giveaway(
        give_callback_value: str,
        owner_id: int
):
    giveaway_data = await GiveAway().filter(callback_value=give_callback_value).all().values(
        'name',
        'winners_count',
        'reserve_winners_count',
        'publish_channel_id',
    )

    if not giveaway_data:
        return

    giveaway = giveaway_data[0]
    publish_channel = await TelegramChannel().get_publish_channel(
        give_callback_value=give_callback_value
    )
    channel_id = giveaway['publish_channel_id']
    if not channel_id and publish_channel:
        channel_id = publish_channel['channel_id']

    participants = await GiveawayParticipant().get_participants(
        giveaway_callback_value=give_callback_value
    )
    random.shuffle(participants)

    winners_count = giveaway['winners_count']
    reserve_count = giveaway['reserve_winners_count']
    await GiveawayWinner().delete_winners(giveaway_callback_value)

    if len(participants) < winners_count:
        channel_text = '<b>🚫 Розыгрыш завершен, победителей выбрать не удалось: участников слишком мало</b>'

        if channel_id:
            await bot.send_message(
                chat_id=channel_id,
                text=channel_text,
            )

        await delete_and_inform_of_the_end_give(
            give_callback_value=give_callback_value,
            winners=[],
            summary_count_users=len(participants),
        )
        return

    total_needed = winners_count + reserve_count
    selected_users = participants[:total_needed]
    main_winners = selected_users[:winners_count]
    reserve_winners = selected_users[winners_count:]

    winners_for_text = []
    for place, user_info in enumerate(main_winners, start=1):
        await GiveawayWinner().add_winner(
            giveaway_callback_value=give_callback_value,
            user_id=user_info['user_id'],
            username=user_info['username'],
            first_name=user_info['first_name'],
            last_name=user_info['last_name'],
            place=place,
            is_reserve=False,
        )
        winners_for_text.append({**user_info, 'place': place, 'is_reserve': False})

    for place, user_info in enumerate(reserve_winners, start=1):
        await GiveawayWinner().add_winner(
            giveaway_callback_value=give_callback_value,
            user_id=user_info['user_id'],
            username=user_info['username'],
            first_name=user_info['first_name'],
            last_name=user_info['last_name'],
            place=place,
            is_reserve=True,
        )
        winners_for_text.append({**user_info, 'place': place, 'is_reserve': True})

    await GiveAwayStatistic().filter(
        giveaway_callback_value=give_callback_value
    ).update(
        winners=[
            {
                'place': user_info['place'],
                'user_id': user_info['user_id'],
                'username': user_info['username'],
                'is_reserve': user_info['is_reserve'],
            }
            for user_info in winners_for_text
        ]
    )

    channel_text = f'<b>Розыгрыш завершен ✅</b>\n\n<b>{giveaway["name"]}</b>\n\n<b>Победители:</b>\n'
    for user_info in winners_for_text:
        label = 'Запасной' if user_info['is_reserve'] else 'Место'
        channel_text += f'{label} {user_info["place"]}: {format_user(user_info)}\n'

    if channel_id:
        await bot.send_message(
            chat_id=channel_id,
            text=channel_text,
        )

    await delete_and_inform_of_the_end_give(
        give_callback_value=give_callback_value,
        winners=winners_for_text,
        summary_count_users=len(participants),
    )
