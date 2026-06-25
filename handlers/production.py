import asyncio
import csv
import html
import logging
import random
import re
import string
from datetime import datetime
from pathlib import Path

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from tortoise.exceptions import IntegrityError

from app import bot, dp
from config import is_owner, start_text, text_for_participation_in_comments_giveaways, timezone_info
from database import (
    GiveAway,
    GiveawayCondition,
    GiveawayParticipant,
    GiveawayWinner,
    TelegramChannel,
)


logger = logging.getLogger(__name__)
secure_random = random.SystemRandom()
PUBLIC_CHANNEL_LINK_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?t\.me/(?:s/)?([A-Za-z0-9_]{5,32})(?:/(\d+))?/?(?:\?.*)?$",
    re.IGNORECASE,
)
PRIVATE_CHANNEL_LINK_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?t\.me/c/(\d+)(?:/(\d+))?/?(?:\?.*)?$",
    re.IGNORECASE,
)
USERNAME_RE = re.compile(r"^@?([A-Za-z0-9_]{5,32})$")


class AdminStates(StatesGroup):
    create_mode = State()
    create_name = State()
    create_text = State()
    create_media = State()
    create_end_at = State()
    create_winners_count = State()
    create_reserve_count = State()
    create_captcha = State()
    add_publish_channel = State()
    add_condition_channel = State()
    add_discussion_group = State()


class CaptchaStates(StatesGroup):
    waiting = State()


def owner_only(user: types.User) -> bool:
    return is_owner(user.id, user.username)


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("Создать розыгрыш", callback_data="admin:create"),
        InlineKeyboardButton("Черновики", callback_data="admin:list:draft"),
        InlineKeyboardButton("Активные розыгрыши", callback_data="admin:list:active"),
        InlineKeyboardButton("Завершенные", callback_data="admin:list:finished"),
    )


def back_menu(target: str = "admin:menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup().add(InlineKeyboardButton("Назад", callback_data=target))


def mode_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("По кнопке", callback_data="admin:create:mode:button"),
        InlineKeyboardButton("По комментариям", callback_data="admin:create:mode:comments"),
        InlineKeyboardButton("Назад", callback_data="admin:menu"),
    )


def yes_no_menu(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Да", callback_data=f"{prefix}:yes"),
        InlineKeyboardButton("Нет", callback_data=f"{prefix}:no"),
    )


def giveaway_actions(callback_value: str, status: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    if status == "draft":
        markup.add(
            InlineKeyboardButton("Канал публикации", callback_data=f"admin:publish:{callback_value}"),
            InlineKeyboardButton("Добавить условие подписки", callback_data=f"admin:condition:add:{callback_value}"),
            InlineKeyboardButton("Каналы и условия", callback_data=f"admin:channels:{callback_value}"),
            InlineKeyboardButton("Запустить", callback_data=f"admin:start:{callback_value}"),
            InlineKeyboardButton("Удалить", callback_data=f"admin:delete:{callback_value}"),
        )
    elif status == "active":
        markup.add(
            InlineKeyboardButton("Статистика", callback_data=f"admin:stats:{callback_value}"),
            InlineKeyboardButton("Экспорт участников CSV", callback_data=f"admin:export:{callback_value}"),
            InlineKeyboardButton("Завершить сейчас", callback_data=f"admin:finish:{callback_value}"),
            InlineKeyboardButton("Остановить", callback_data=f"admin:stop:{callback_value}"),
        )
    else:
        markup.add(
            InlineKeyboardButton("Результаты", callback_data=f"admin:results:{callback_value}"),
            InlineKeyboardButton("Экспорт участников CSV", callback_data=f"admin:export:{callback_value}"),
        )
    markup.add(InlineKeyboardButton("Главное меню", callback_data="admin:menu"))
    return markup


def captcha_keyboard(giveaway_id: str, target_index: int) -> InlineKeyboardMarkup:
    icons = ["🍎", "🚗", "🌳", "🌈", "🍌", "📱"]
    target = icons[target_index]
    markup = InlineKeyboardMarkup(row_width=3)
    for index, icon in enumerate(icons):
        markup.insert(
            InlineKeyboardButton(
                icon,
                callback_data=f"join:captcha:{giveaway_id}:{1 if icon == target else 0}",
            )
        )
    return markup


def user_label(user_data: dict) -> str:
    username = user_data.get("username")
    if username:
        return f"@{username}"
    full_name = " ".join(
        part for part in [user_data.get("first_name"), user_data.get("last_name")]
        if part
    )
    return full_name or str(user_data.get("user_id"))


def parse_channel_reference(text: str | None) -> dict | None:
    if not text:
        return None

    value = text.strip()
    private_match = PRIVATE_CHANNEL_LINK_RE.match(value)
    if private_match:
        internal_id, post_id = private_match.groups()
        return {
            "chat_ref": int(f"-100{internal_id}"),
            "post_id": int(post_id) if post_id else None,
            "url": value if value.startswith("http") else f"https://{value}",
        }

    public_match = PUBLIC_CHANNEL_LINK_RE.match(value)
    if public_match:
        username, post_id = public_match.groups()
        url = f"https://t.me/{username}"
        if post_id:
            url = f"{url}/{post_id}"
        return {
            "chat_ref": f"@{username}",
            "username": username,
            "post_id": int(post_id) if post_id else None,
            "url": url,
        }

    username_match = USERNAME_RE.match(value)
    if username_match:
        username = username_match.group(1)
        return {
            "chat_ref": f"@{username}",
            "username": username,
            "post_id": None,
            "url": f"https://t.me/{username}",
        }

    return None


def channel_display_name(channel: dict) -> str:
    if channel.get("username"):
        return f"@{channel['username']}"
    return channel.get("title") or str(channel["id"])


def channel_anchor(channel: dict) -> str:
    label = html.escape(channel_display_name(channel))
    url = channel.get("url")
    if not url:
        return label
    return f'<a href="{html.escape(url, quote=True)}">{label}</a>'


async def resolve_channel_from_message(message: types.Message) -> tuple[dict | None, str | None]:
    forwarded_chat = message.forward_from_chat
    if forwarded_chat:
        if forwarded_chat.type != "channel":
            return None, "Это не канал. Отправьте @username канала, ссылку t.me/... или перешлите пост именно из канала."

        username = getattr(forwarded_chat, "username", None)
        post_id = getattr(message, "forward_from_message_id", None)
        url = None
        if username:
            url = f"https://t.me/{username}"
            if post_id:
                url = f"{url}/{post_id}"

        return {
            "id": forwarded_chat.id,
            "title": forwarded_chat.title,
            "username": username,
            "post_id": post_id,
            "url": url,
        }, None

    parsed = parse_channel_reference(message.text or message.caption)
    if not parsed:
        return None, "Не смог определить канал. Пришлите @username, ссылку t.me/channel, ссылку t.me/channel/123 или перешлите пост из канала."

    try:
        chat = await bot.get_chat(parsed["chat_ref"])
    except Exception:
        return None, "Telegram не дал открыть этот канал. Проверьте ссылку/юзертег и добавьте бота в канал администратором."

    if chat.type != "channel":
        return None, "Это не канал. Для условия подписки и публикации нужен именно Telegram-канал."

    username = getattr(chat, "username", None) or parsed.get("username")
    url = parsed.get("url")
    if not url and username:
        url = f"https://t.me/{username}"

    return {
        "id": chat.id,
        "title": chat.title,
        "username": username,
        "post_id": parsed.get("post_id"),
        "url": url,
    }, None


async def ensure_bot_channel_admin(channel_id: int, error_text: str) -> tuple[bool, str | None]:
    try:
        member = await bot.get_chat_member(channel_id, bot.id)
    except Exception:
        return False, error_text

    if member.status not in ("administrator", "creator"):
        return False, error_text

    return True, None


async def get_giveaway(callback_value: str) -> GiveAway | None:
    return await GiveAway.get_or_none(callback_value=callback_value)


async def giveaway_status(giveaway: GiveAway) -> str:
    if giveaway.run_status:
        return "active"
    if giveaway.finished_at:
        return "finished"
    return "draft"


async def render_giveaway(giveaway: GiveAway) -> str:
    conditions = await GiveawayCondition().get_conditions(giveaway.callback_value)
    participants_count = await GiveawayParticipant().count_participants(giveaway.callback_value)
    status = await giveaway_status(giveaway)
    mode = "по комментариям" if giveaway.type == "comments" else "по кнопке"
    publish = giveaway.publish_channel_name or "не выбран"
    conditions_text = "\n".join(
        f"- {item['target_channel_name']} ({item['target_channel_id']})"
        for item in conditions
    ) or "не добавлены"
    finished = giveaway.finished_at.strftime("%d.%m.%Y %H:%M") if giveaway.finished_at else "-"

    return (
        f"<b>{giveaway.name}</b>\n\n"
        f"<b>Статус:</b> {status}\n"
        f"<b>Тип:</b> {mode}\n"
        f"<b>Канал публикации:</b> {publish}\n"
        f"<b>Окончание:</b> {giveaway.over_date.strftime('%d.%m.%Y %H:%M')}\n"
        f"<b>Победителей:</b> {giveaway.winners_count}\n"
        f"<b>Запасных:</b> {giveaway.reserve_winners_count}\n"
        f"<b>Капча:</b> {'да' if giveaway.captcha else 'нет'}\n"
        f"<b>Участников:</b> {participants_count}\n"
        f"<b>Завершен:</b> {finished}\n\n"
        f"<b>Условия подписки:</b>\n{conditions_text}\n\n"
        f"<b>Текст:</b>\n{giveaway.text}"
    )


async def show_giveaway(message: types.Message, giveaway: GiveAway):
    status = await giveaway_status(giveaway)
    await message.edit_text(
        await render_giveaway(giveaway),
        reply_markup=giveaway_actions(giveaway.callback_value, status),
        disable_web_page_preview=True,
    )


async def create_giveaway_record(owner_id: int, data: dict) -> GiveAway:
    callback_value = "".join(secure_random.choices(string.ascii_letters + string.digits, k=32))
    over_date = data["over_date"]
    if isinstance(over_date, str):
        over_date = datetime.fromisoformat(over_date)

    return await GiveAway.create(
        owner_id=owner_id,
        run_status=False,
        type=data["mode"],
        name=data["name"],
        callback_value=callback_value,
        text=data["text"],
        photo_id=data.get("photo_id"),
        video_id=data.get("video_id"),
        over_date=over_date,
        captcha=data.get("captcha", False),
        winners_count=data["winners_count"],
        reserve_winners_count=data["reserve_winners_count"],
        participation_mode=data["mode"],
    )


async def add_participant(giveaway_id: str, user: types.User, captcha_passed: bool = False) -> bool:
    try:
        return await GiveawayParticipant().add_participant(
            giveaway_callback_value=giveaway_id,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            subscription_checked=True,
            captcha_passed=captcha_passed,
        )
    except IntegrityError:
        return False


async def check_subscriptions(giveaway_id: str, user_id: int) -> tuple[bool, list[str]]:
    conditions = await GiveawayCondition().get_conditions(giveaway_id)
    missing = []
    if not conditions:
        return False, ["условия подписки не настроены"]

    for condition in conditions:
        try:
            member = await bot.get_chat_member(condition["target_channel_id"], user_id)
        except Exception:
            missing.append(condition["target_channel_name"] or str(condition["target_channel_id"]))
            continue

        if member.status not in ("member", "administrator", "creator"):
            missing.append(condition["target_channel_name"] or str(condition["target_channel_id"]))

    return not missing, missing


async def finish_giveaway(giveaway: GiveAway, reason: str = "schedule") -> list[dict]:
    if giveaway.finished_at:
        return await GiveawayWinner().get_winners(giveaway.callback_value)

    participants = await GiveawayParticipant().get_participants(giveaway.callback_value)
    secure_random.shuffle(participants)

    await GiveawayWinner().delete_winners(giveaway.callback_value)

    if len(participants) < giveaway.winners_count:
        giveaway.run_status = False
        giveaway.finished_at = datetime.now(timezone_info)
        await giveaway.save()
        await notify_finish(giveaway, [], len(participants), too_few=True)
        return []

    selected = participants[: giveaway.winners_count + giveaway.reserve_winners_count]
    winners = []

    for place, participant in enumerate(selected[: giveaway.winners_count], start=1):
        await GiveawayWinner().add_winner(
            giveaway_callback_value=giveaway.callback_value,
            user_id=participant["user_id"],
            username=participant["username"],
            first_name=participant["first_name"],
            last_name=participant["last_name"],
            place=place,
            is_reserve=False,
        )
        winners.append({**participant, "place": place, "is_reserve": False})

    for place, participant in enumerate(selected[giveaway.winners_count :], start=1):
        await GiveawayWinner().add_winner(
            giveaway_callback_value=giveaway.callback_value,
            user_id=participant["user_id"],
            username=participant["username"],
            first_name=participant["first_name"],
            last_name=participant["last_name"],
            place=place,
            is_reserve=True,
        )
        winners.append({**participant, "place": place, "is_reserve": True})

    giveaway.run_status = False
    giveaway.finished_at = datetime.now(timezone_info)
    await giveaway.save()
    await notify_finish(giveaway, winners, len(participants), too_few=False)
    logger.info("Giveaway %s finished by %s", giveaway.callback_value, reason)
    return winners


async def notify_finish(giveaway: GiveAway, winners: list[dict], participants_count: int, too_few: bool):
    owner_text = (
        f"Розыгрыш завершен\n\n"
        f"<b>{giveaway.name}</b>\n"
        f"Участников: {participants_count}\n"
    )
    channel_text = f"<b>Розыгрыш завершен ✅</b>\n\n<b>{giveaway.name}</b>\n\n"

    if too_few:
        owner_text += "Победителей выбрать не удалось: участников меньше, чем призовых мест."
        channel_text += "Победителей выбрать не удалось: участников слишком мало."
    else:
        owner_text += "\n<b>Победители:</b>\n"
        channel_text += "<b>Победители:</b>\n"
        for winner in winners:
            label = "Запасной" if winner["is_reserve"] else "Место"
            line = f"{label} {winner['place']}: {user_label(winner)}\n"
            owner_text += line
            channel_text += line

    if giveaway.publish_channel_id:
        try:
            await bot.send_message(giveaway.publish_channel_id, channel_text)
        except Exception:
            logger.exception("Failed to publish finish message for %s", giveaway.callback_value)

    try:
        await bot.send_message(giveaway.owner_id, owner_text)
    except Exception:
        logger.exception("Failed to notify owner for %s", giveaway.callback_value)


async def export_participants_csv(giveaway: GiveAway) -> Path:
    export_dir = Path("exports")
    export_dir.mkdir(exist_ok=True)
    path = export_dir / f"participants_{giveaway.callback_value}.csv"
    participants = await GiveawayParticipant().get_participants(giveaway.callback_value)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["user_id", "username", "first_name", "last_name", "joined_at"],
        )
        writer.writeheader()
        for participant in participants:
            writer.writerow(participant)

    return path


async def register_publish_channel(message: types.Message, state: FSMContext):
    data = await state.get_data()
    giveaway = await get_giveaway(data["giveaway_id"])
    channel, error = await resolve_channel_from_message(message)
    if not giveaway:
        await message.answer("Розыгрыш не найден.", reply_markup=main_menu())
        await state.finish()
        return

    if error or not channel:
        await message.answer(error, reply_markup=back_menu(f"admin:show:{giveaway.callback_value}"))
        return

    ok, admin_error = await ensure_bot_channel_admin(
        channel["id"],
        "Бот должен быть администратором этого канала, иначе он не сможет опубликовать пост.",
    )
    if not ok:
        await message.answer(admin_error)
        return

    saved_name = channel_display_name(channel)
    await TelegramChannel.filter(give_callback_value=giveaway.callback_value, role="publish").delete()
    await TelegramChannel().add_channel(
        owner_id=message.from_user.id,
        channel_id=channel["id"],
        give_callback_value=giveaway.callback_value,
        name=saved_name,
        role="publish",
    )
    await GiveAway().set_publish_channel(giveaway.callback_value, channel["id"], saved_name)
    await state.finish()
    await message.answer(f"Канал публикации сохранен: {channel_anchor(channel)}.", disable_web_page_preview=True)
    await message.answer(await render_giveaway(await get_giveaway(giveaway.callback_value)), reply_markup=giveaway_actions(giveaway.callback_value, "draft"))


async def register_condition_channel(message: types.Message, state: FSMContext):
    data = await state.get_data()
    giveaway = await get_giveaway(data["giveaway_id"])
    channel, error = await resolve_channel_from_message(message)
    if not giveaway:
        await message.answer("Розыгрыш не найден.", reply_markup=main_menu())
        await state.finish()
        return

    if error or not channel:
        await message.answer(error, reply_markup=back_menu(f"admin:show:{giveaway.callback_value}"))
        return

    ok, admin_error = await ensure_bot_channel_admin(
        channel["id"],
        "Бот должен быть администратором канала, чтобы проверять подписку участников.",
    )
    if not ok:
        await message.answer(admin_error)
        return

    saved_name = channel_display_name(channel)
    if not await TelegramChannel().exists_channel(channel["id"], giveaway.callback_value, "condition"):
        await TelegramChannel().add_channel(
            owner_id=message.from_user.id,
            channel_id=channel["id"],
            give_callback_value=giveaway.callback_value,
            name=saved_name,
            role="condition",
        )
    added = await GiveawayCondition().add_condition(giveaway.callback_value, channel["id"], saved_name)
    await state.finish()
    if added:
        await message.answer(f"Условие подписки добавлено: {channel_anchor(channel)}.", disable_web_page_preview=True)
    else:
        await message.answer(f"Это условие уже было добавлено: {channel_anchor(channel)}.", disable_web_page_preview=True)
    await message.answer(await render_giveaway(await get_giveaway(giveaway.callback_value)), reply_markup=giveaway_actions(giveaway.callback_value, "draft"))


async def register_discussion_group(message: types.Message, state: FSMContext):
    data = await state.get_data()
    giveaway = await get_giveaway(data["giveaway_id"])
    group = message.forward_from_chat
    if not giveaway or not group or group.type != "supergroup":
        await message.answer("Перешлите сообщение именно из группы обсуждения.")
        return

    member = await bot.get_chat_member(group.id, bot.id)
    if member.status not in ("administrator", "creator"):
        await message.answer("Бот должен быть администратором группы обсуждения.")
        return

    await TelegramChannel.filter(give_callback_value=giveaway.callback_value, role="publish").update(group_id=group.id)
    await state.finish()
    await message.answer("Группа обсуждения подключена.")
    await message.answer(await render_giveaway(await get_giveaway(giveaway.callback_value)), reply_markup=giveaway_actions(giveaway.callback_value, "draft"))


async def publish_giveaway(giveaway: GiveAway) -> tuple[bool, str]:
    if giveaway.run_status:
        return False, "Розыгрыш уже запущен."
    if giveaway.finished_at:
        return False, "Розыгрыш уже завершен."
    if not giveaway.publish_channel_id:
        return False, "Не выбран канал публикации."

    conditions = await GiveawayCondition().get_conditions(giveaway.callback_value)
    if not conditions:
        return False, "Добавьте хотя бы одно условие подписки."

    publish_channel = await TelegramChannel().get_publish_channel(giveaway.callback_value)
    if giveaway.type == "comments" and (not publish_channel or not publish_channel.get("group_id")):
        return False, "Для комментариев подключите группу обсуждения к каналу публикации."

    text = (
        f"<b>{giveaway.name}</b>\n\n"
        f"{giveaway.text}\n\n"
        f"Победителей: {giveaway.winners_count}\n"
        f"Запасных: {giveaway.reserve_winners_count}\n"
        f"Дата завершения: {giveaway.over_date.strftime('%d.%m.%Y %H:%M')}"
    )

    reply_markup = None
    if giveaway.type == "button":
        me = await bot.get_me()
        reply_markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("Участвовать", url=f"https://t.me/{me.username}?start={giveaway.callback_value}")
        )
    else:
        text += f"\n\nДля участия напишите в комментариях: <code>{text_for_participation_in_comments_giveaways}</code>"

    if giveaway.photo_id:
        sent = await bot.send_photo(giveaway.publish_channel_id, giveaway.photo_id, caption=text, reply_markup=reply_markup)
    elif giveaway.video_id:
        sent = await bot.send_video(giveaway.publish_channel_id, giveaway.video_id, caption=text, reply_markup=reply_markup)
    else:
        sent = await bot.send_message(giveaway.publish_channel_id, text, reply_markup=reply_markup)

    post_link = f"{await sent.chat.get_url()}/{sent.message_id}"
    await TelegramChannel.filter(give_callback_value=giveaway.callback_value, role="publish").update(post_id=sent.message_id)
    await GiveAway().set_publish_post(giveaway.callback_value, sent.message_id, post_link)
    giveaway.run_status = True
    await giveaway.save()
    return True, "Розыгрыш опубликован и запущен."


@dp.message_handler(commands=["start"], state="*")
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    parts = message.text.split(maxsplit=1)

    if len(parts) > 1:
        giveaway_id = parts[1].strip()
        giveaway = await get_giveaway(giveaway_id)
        if not giveaway or not giveaway.run_status or giveaway.type != "button":
            await message.answer("Этот розыгрыш недоступен.")
            return

        if await GiveawayParticipant().exists_participant(giveaway_id, message.from_user.id):
            await message.answer("Вы уже участвуете.")
            return

        ok, missing = await check_subscriptions(giveaway_id, message.from_user.id)
        if not ok:
            await message.answer("Для участия подпишитесь на каналы условий:\n" + "\n".join(missing))
            return

        if giveaway.captcha:
            target_index = secure_random.randrange(0, 6)
            await state.update_data(giveaway_id=giveaway_id, captcha_target=target_index)
            await CaptchaStates.waiting.set()
            target_icon = ["🍎", "🚗", "🌳", "🌈", "🍌", "📱"][target_index]
            await message.answer(f"Подтвердите участие: нажмите {target_icon}", reply_markup=captcha_keyboard(giveaway_id, target_index))
            return

        added = await add_participant(giveaway_id, message.from_user)
        await message.answer("Вы участвуете!" if added else "Вы уже участвуете.")
        return

    if owner_only(message.from_user):
        await message.answer(start_text, reply_markup=main_menu())
    else:
        await message.answer("Это бот для участия в розыгрышах. Нажмите кнопку участия в посте розыгрыша.")


@dp.callback_query_handler(lambda c: c.data == "admin:menu", state="*")
async def admin_menu(callback: types.CallbackQuery, state: FSMContext):
    if not owner_only(callback.from_user):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await state.finish()
    await callback.message.edit_text(start_text, reply_markup=main_menu())


@dp.callback_query_handler(lambda c: c.data == "admin:create", state="*")
async def create_start(callback: types.CallbackQuery, state: FSMContext):
    if not owner_only(callback.from_user):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await state.finish()
    await AdminStates.create_mode.set()
    await callback.message.edit_text("Выберите тип розыгрыша:", reply_markup=mode_menu())


@dp.callback_query_handler(lambda c: c.data.startswith("admin:create:mode:"), state=AdminStates.create_mode)
async def create_mode(callback: types.CallbackQuery, state: FSMContext):
    mode = callback.data.rsplit(":", 1)[1]
    await state.update_data(mode=mode)
    await AdminStates.create_name.set()
    await callback.message.edit_text("Введите название розыгрыша:", reply_markup=back_menu())


@dp.message_handler(state=AdminStates.create_name)
async def create_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое.")
        return
    await state.update_data(name=name)
    await AdminStates.create_text.set()
    await message.answer("Введите текст розыгрыша. HTML-разметка поддерживается.", reply_markup=back_menu())


@dp.message_handler(state=AdminStates.create_text)
async def create_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.html_text or message.text)
    await AdminStates.create_media.set()
    await message.answer(
        "Отправьте фото/видео для поста или напишите <code>нет</code>.",
        reply_markup=back_menu(),
    )


@dp.message_handler(content_types=["photo", "video", "text"], state=AdminStates.create_media)
async def create_media(message: types.Message, state: FSMContext):
    if message.content_type == "photo":
        await state.update_data(photo_id=message.photo[-1].file_id, video_id=None)
    elif message.content_type == "video":
        await state.update_data(photo_id=None, video_id=message.video.file_id)
    elif message.text and message.text.lower().strip() in ("нет", "no", "-"):
        await state.update_data(photo_id=None, video_id=None)
    else:
        await message.answer("Отправьте фото/видео или напишите <code>нет</code>.")
        return

    await AdminStates.create_end_at.set()
    await message.answer("Введите дату окончания в формате <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>.")


@dp.message_handler(state=AdminStates.create_end_at)
async def create_end_at(message: types.Message, state: FSMContext):
    try:
        over_date = timezone_info.localize(datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M"))
    except ValueError:
        await message.answer("Неверный формат. Пример: <code>25.06.2026 19:30</code>")
        return

    if over_date <= datetime.now(timezone_info):
        await message.answer("Дата окончания должна быть в будущем.")
        return

    await state.update_data(over_date=over_date.isoformat())
    await AdminStates.create_winners_count.set()
    await message.answer("Введите количество основных победителей.")


@dp.message_handler(state=AdminStates.create_winners_count)
async def create_winners_count(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("Введите положительное число.")
        return
    await state.update_data(winners_count=int(message.text))
    await AdminStates.create_reserve_count.set()
    await message.answer("Введите количество запасных победителей. Можно 0.")


@dp.message_handler(state=AdminStates.create_reserve_count)
async def create_reserve_count(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 0:
        await message.answer("Введите число 0 или больше.")
        return
    await state.update_data(reserve_winners_count=int(message.text))
    data = await state.get_data()
    if data["mode"] == "button":
        await AdminStates.create_captcha.set()
        await message.answer("Включить капчу?", reply_markup=yes_no_menu("admin:create:captcha"))
    else:
        data["captcha"] = False
        giveaway = await create_giveaway_record(message.from_user.id, data)
        await state.finish()
        await message.answer("Розыгрыш создан. Теперь настройте канал публикации и условия.")
        await message.answer(await render_giveaway(giveaway), reply_markup=giveaway_actions(giveaway.callback_value, "draft"))


@dp.callback_query_handler(lambda c: c.data.startswith("admin:create:captcha:"), state=AdminStates.create_captcha)
async def create_captcha(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    data["captcha"] = callback.data.endswith(":yes")
    giveaway = await create_giveaway_record(callback.from_user.id, data)
    await state.finish()
    await callback.message.edit_text("Розыгрыш создан. Теперь настройте канал публикации и условия.")
    await callback.message.answer(await render_giveaway(giveaway), reply_markup=giveaway_actions(giveaway.callback_value, "draft"))


@dp.callback_query_handler(lambda c: c.data.startswith("admin:list:"), state="*")
async def list_giveaways(callback: types.CallbackQuery, state: FSMContext):
    if not owner_only(callback.from_user):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await state.finish()

    list_type = callback.data.rsplit(":", 1)[1]
    query = GiveAway.filter(owner_id=callback.from_user.id)
    if list_type == "draft":
        query = query.filter(run_status=False, finished_at=None)
        title = "Черновики"
    elif list_type == "active":
        query = query.filter(run_status=True)
        title = "Активные розыгрыши"
    else:
        query = query.exclude(finished_at=None)
        title = "Завершенные"

    giveaways = await query.order_by("-created_at").limit(20)
    markup = InlineKeyboardMarkup(row_width=1)
    for giveaway in giveaways:
        markup.add(InlineKeyboardButton(giveaway.name, callback_data=f"admin:show:{giveaway.callback_value}"))
    markup.add(InlineKeyboardButton("Главное меню", callback_data="admin:menu"))
    await callback.message.edit_text(title if giveaways else f"{title}: пусто", reply_markup=markup)


@dp.callback_query_handler(lambda c: c.data.startswith("admin:show:"), state="*")
async def show_selected(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    giveaway = await get_giveaway(callback.data.rsplit(":", 1)[1])
    if not giveaway or giveaway.owner_id != callback.from_user.id:
        await callback.answer("Розыгрыш не найден", show_alert=True)
        return
    await show_giveaway(callback.message, giveaway)


@dp.callback_query_handler(lambda c: c.data.startswith("admin:publish:"), state="*")
async def ask_publish_channel(callback: types.CallbackQuery, state: FSMContext):
    giveaway_id = callback.data.rsplit(":", 1)[1]
    await state.update_data(giveaway_id=giveaway_id)
    await AdminStates.add_publish_channel.set()
    await callback.message.edit_text(
        "Отправьте @username канала публикации, ссылку t.me/channel, ссылку на пост t.me/channel/123 или перешлите пост из канала. Бот должен быть администратором канала.",
        reply_markup=back_menu(f"admin:show:{giveaway_id}"),
    )


@dp.message_handler(state=AdminStates.add_publish_channel, content_types=types.ContentTypes.ANY)
async def publish_channel_message(message: types.Message, state: FSMContext):
    await register_publish_channel(message, state)


@dp.callback_query_handler(lambda c: c.data.startswith("admin:condition:add:"), state="*")
async def ask_condition_channel(callback: types.CallbackQuery, state: FSMContext):
    giveaway_id = callback.data.rsplit(":", 1)[1]
    await state.update_data(giveaway_id=giveaway_id)
    await AdminStates.add_condition_channel.set()
    await callback.message.edit_text(
        "Отправьте @username канала, ссылку t.me/channel, ссылку на пост t.me/channel/123 или перешлите пост из канала, подписку на который нужно проверять.",
        reply_markup=back_menu(f"admin:show:{giveaway_id}"),
    )


@dp.message_handler(state=AdminStates.add_condition_channel, content_types=types.ContentTypes.ANY)
async def condition_channel_message(message: types.Message, state: FSMContext):
    await register_condition_channel(message, state)


@dp.callback_query_handler(lambda c: c.data.startswith("admin:discussion:"), state="*")
async def ask_discussion_group(callback: types.CallbackQuery, state: FSMContext):
    giveaway_id = callback.data.rsplit(":", 1)[1]
    await state.update_data(giveaway_id=giveaway_id)
    await AdminStates.add_discussion_group.set()
    await callback.message.edit_text(
        "Перешлите любое сообщение из группы обсуждения канала.",
        reply_markup=back_menu(f"admin:show:{giveaway_id}"),
    )


@dp.message_handler(state=AdminStates.add_discussion_group, content_types=types.ContentTypes.ANY)
async def discussion_group_message(message: types.Message, state: FSMContext):
    await register_discussion_group(message, state)


@dp.callback_query_handler(lambda c: c.data.startswith("admin:channels:"), state="*")
async def show_channels(callback: types.CallbackQuery):
    giveaway_id = callback.data.rsplit(":", 1)[1]
    channels = await TelegramChannel.filter(give_callback_value=giveaway_id).values("channel_id", "name", "role", "group_id")
    conditions = await GiveawayCondition().get_conditions(giveaway_id)
    text = "<b>Каналы розыгрыша</b>\n\n"
    if not channels:
        text += "Каналы не добавлены.\n"
    for channel in channels:
        role = "публикация" if channel["role"] == "publish" else "условие"
        group = f", группа: {channel['group_id']}" if channel.get("group_id") else ""
        text += f"- {role}: {channel['name']} ({channel['channel_id']}){group}\n"
    text += "\n<b>Условия подписки:</b>\n"
    text += "\n".join(f"- {item['target_channel_name']}" for item in conditions) or "не добавлены"

    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("Добавить группу обсуждения", callback_data=f"admin:discussion:{giveaway_id}"),
        InlineKeyboardButton("Назад", callback_data=f"admin:show:{giveaway_id}"),
    )
    await callback.message.edit_text(text, reply_markup=markup)


@dp.callback_query_handler(lambda c: c.data.startswith("admin:start:"), state="*")
async def start_giveaway(callback: types.CallbackQuery):
    giveaway = await get_giveaway(callback.data.rsplit(":", 1)[1])
    if not giveaway:
        await callback.answer("Розыгрыш не найден", show_alert=True)
        return
    ok, text = await publish_giveaway(giveaway)
    await callback.answer(text, show_alert=not ok)
    await show_giveaway(callback.message, await get_giveaway(giveaway.callback_value))


@dp.callback_query_handler(lambda c: c.data.startswith("admin:finish:"), state="*")
async def finish_now(callback: types.CallbackQuery):
    giveaway = await get_giveaway(callback.data.rsplit(":", 1)[1])
    if not giveaway:
        await callback.answer("Розыгрыш не найден", show_alert=True)
        return
    await finish_giveaway(giveaway, reason="manual")
    await callback.answer("Розыгрыш завершен.")
    await show_giveaway(callback.message, await get_giveaway(giveaway.callback_value))


@dp.callback_query_handler(lambda c: c.data.startswith("admin:stop:"), state="*")
async def stop_giveaway(callback: types.CallbackQuery):
    giveaway = await get_giveaway(callback.data.rsplit(":", 1)[1])
    if not giveaway:
        await callback.answer("Розыгрыш не найден", show_alert=True)
        return
    giveaway.run_status = False
    await giveaway.save()
    await callback.answer("Розыгрыш остановлен.")
    await show_giveaway(callback.message, giveaway)


@dp.callback_query_handler(lambda c: c.data.startswith("admin:delete:"), state="*")
async def delete_giveaway(callback: types.CallbackQuery):
    giveaway_id = callback.data.rsplit(":", 1)[1]
    giveaway = await get_giveaway(giveaway_id)
    if not giveaway:
        await callback.answer("Розыгрыш не найден", show_alert=True)
        return
    await TelegramChannel.filter(give_callback_value=giveaway_id).delete()
    await GiveawayCondition().delete_conditions(giveaway_id)
    await GiveawayParticipant().delete_participants(giveaway_id)
    await GiveawayWinner().delete_winners(giveaway_id)
    await giveaway.delete()
    await callback.message.edit_text("Розыгрыш удален.", reply_markup=main_menu())


@dp.callback_query_handler(lambda c: c.data.startswith("admin:stats:"), state="*")
async def stats(callback: types.CallbackQuery):
    giveaway = await get_giveaway(callback.data.rsplit(":", 1)[1])
    if not giveaway:
        await callback.answer("Розыгрыш не найден", show_alert=True)
        return
    count = await GiveawayParticipant().count_participants(giveaway.callback_value)
    winners = await GiveawayWinner().get_winners(giveaway.callback_value)
    await callback.message.edit_text(
        f"<b>{giveaway.name}</b>\n\nУчастников: {count}\nПобедителей выбрано: {len(winners)}",
        reply_markup=back_menu(f"admin:show:{giveaway.callback_value}"),
    )


@dp.callback_query_handler(lambda c: c.data.startswith("admin:results:"), state="*")
async def results(callback: types.CallbackQuery):
    giveaway = await get_giveaway(callback.data.rsplit(":", 1)[1])
    if not giveaway:
        await callback.answer("Розыгрыш не найден", show_alert=True)
        return
    winners = await GiveawayWinner().get_winners(giveaway.callback_value)
    text = f"<b>Результаты: {giveaway.name}</b>\n\n"
    text += "\n".join(
        f"{'Запасной' if winner['is_reserve'] else 'Место'} {winner['place']}: {user_label(winner)}"
        for winner in winners
    ) or "Победители не выбраны."
    await callback.message.edit_text(text, reply_markup=back_menu(f"admin:show:{giveaway.callback_value}"))


@dp.callback_query_handler(lambda c: c.data.startswith("admin:export:"), state="*")
async def export_csv(callback: types.CallbackQuery):
    giveaway = await get_giveaway(callback.data.rsplit(":", 1)[1])
    if not giveaway:
        await callback.answer("Розыгрыш не найден", show_alert=True)
        return
    path = await export_participants_csv(giveaway)
    await callback.message.answer_document(InputFile(path), caption=f"Участники: {giveaway.name}")
    await callback.answer("Экспорт готов.")


@dp.callback_query_handler(lambda c: c.data.startswith("join:captcha:"), state=CaptchaStates.waiting)
async def captcha_answer(callback: types.CallbackQuery, state: FSMContext):
    _, _, giveaway_id, is_correct = callback.data.split(":")
    if is_correct != "1":
        await callback.answer("Неверно, попробуйте ещё раз.", show_alert=True)
        return
    data = await state.get_data()
    if data.get("giveaway_id") != giveaway_id:
        await callback.answer("Капча устарела.", show_alert=True)
        await state.finish()
        return
    added = await add_participant(giveaway_id, callback.from_user, captcha_passed=True)
    await state.finish()
    await callback.message.edit_text("Вы участвуете!" if added else "Вы уже участвуете.")


@dp.message_handler(chat_type=types.ChatType.SUPERGROUP, content_types=["text"], state="*")
async def comment_participation(message: types.Message):
    if message.text.strip() != text_for_participation_in_comments_giveaways:
        return
    if not message.reply_to_message:
        return

    forward_message_id = getattr(message.reply_to_message, "forward_from_message_id", None)
    if not forward_message_id:
        return

    channels = await TelegramChannel.filter(role="publish", group_id=message.chat.id, post_id=forward_message_id).values(
        "give_callback_value"
    )
    if not channels:
        return

    for channel in channels:
        giveaway = await get_giveaway(channel["give_callback_value"])
        if not giveaway or not giveaway.run_status or giveaway.type != "comments":
            continue
        if giveaway.over_date <= datetime.now(timezone_info):
            continue
        if await GiveawayParticipant().exists_participant(giveaway.callback_value, message.from_user.id):
            await message.reply("Вы уже участвуете.")
            return
        ok, missing = await check_subscriptions(giveaway.callback_value, message.from_user.id)
        if not ok:
            await message.reply("Для участия подпишитесь на каналы условий:\n" + "\n".join(missing))
            return
        added = await add_participant(giveaway.callback_value, message.from_user)
        await message.reply("Спасибо за участие!" if added else "Вы уже участвуете.")
        return


@dp.message_handler(state="*")
async def fallback(message: types.Message, state: FSMContext):
    if owner_only(message.from_user):
        current_state = await state.get_state()
        if current_state:
            await message.answer("Я не понял сообщение на текущем шаге. Отправьте /start, чтобы открыть меню заново.")
        else:
            await message.answer(start_text, reply_markup=main_menu())
    else:
        await message.answer("Это бот для участия в розыгрышах. Нажмите кнопку участия в посте розыгрыша.")


async def manage_active_giveaways():
    while True:
        try:
            now = datetime.now(timezone_info)
            giveaways = await GiveAway.filter(run_status=True, over_date__lte=now).all()
            for giveaway in giveaways:
                await finish_giveaway(giveaway, reason="schedule")
        except Exception:
            logger.exception("Giveaway monitor failed")
        await asyncio.sleep(15)
