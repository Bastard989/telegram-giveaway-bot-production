from aiogram import types

from database import GiveawayParticipant, TelegramChannel, GiveAwayStatistic
from .check_channels_subscriptions import check_channels_subscriptions
from config import text_for_participation_in_comments_giveaways


async def handle_new_users_in_groups(message: types.Message):
    try:

        if message.text == text_for_participation_in_comments_giveaways:

            if not message.reply_to_message:
                return

            give_data = await TelegramChannel().filter(
                group_id=message.chat.id,
                role="publish",
            ).all().values(
                'give_callback_value',
                'post_id',
                'owner_id'
            )


            for give in give_data:

                if await check_channels_subscriptions(
                        give_callback_value=give['give_callback_value'],
                        user_id=message.from_user.id,
                        owner_id=give['owner_id']
                ):

                    if int(give['post_id']) == message.reply_to_message.forward_from_message_id:

                        is_added = await GiveawayParticipant().add_participant(
                            giveaway_callback_value=give['give_callback_value'],
                            user_id=message.from_user.id,
                            username=message.from_user.username,
                            first_name=message.from_user.first_name,
                            last_name=message.from_user.last_name,
                            subscription_checked=True,
                            captcha_passed=False,
                        )

                        if is_added:
                            await GiveAwayStatistic().update_statistic_members(
                                giveaway_callback_value=give['give_callback_value'],
                                new_member_username=message.from_user.username,
                                new_member_id=message.from_user.id,
                            )

                            await message.reply(
                                'Спасибо за участие!'
                            )

                        else:
                            await message.reply(
                                'Вы уже участвуете!'
                            )

                else:
                    await message.reply(
                        '💎  <b>Вы не подписаны на все каналы!</b>',
                    )

    except AttributeError:
        return
