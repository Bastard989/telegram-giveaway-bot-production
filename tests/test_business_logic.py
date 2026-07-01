import csv
import html
import os
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


os.environ.setdefault("BOT_TOKEN", "123456:TEST_TOKEN")
os.environ.setdefault("DATABASE_URL", "sqlite://runtime/test-business.sqlite3")
os.environ.setdefault("OWNERS", "1")

from handlers import production


class FakeGiveaway:
    def __init__(self, callback_value="give-test", winners_count=1, reserve_winners_count=1):
        self.callback_value = callback_value
        self.name = "Test Giveaway"
        self.winners_count = winners_count
        self.reserve_winners_count = reserve_winners_count
        self.finished_at = None
        self.run_status = True
        self.publish_channel_id = None
        self.owner_id = 1

    async def save(self):
        return None


class FakeParticipantRepo:
    def __init__(self, participants):
        self.participants = participants

    async def get_participants(self, callback_value):
        return list(self.participants)


class FakeWinnerRepo:
    def __init__(self):
        self.saved = []
        self.deleted = False

    async def delete_winners(self, callback_value):
        self.deleted = True
        self.saved = []

    async def add_winner(self, **kwargs):
        self.saved.append(kwargs)

    async def get_winners(self, callback_value):
        return list(self.saved)


class BusinessLogicTest(unittest.IsolatedAsyncioTestCase):
    def test_long_telegram_html_is_split_into_valid_chunks(self):
        source = "<b>Начало &amp; тест</b>\n<blockquote>" + ("длинный текст " * 80) + "</blockquote>"

        chunks = production.split_telegram_html(source, limit=180)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            visible = html.unescape(re.sub(r"<[^>]+>", "", chunk))
            self.assertLessEqual(production.telegram_text_units(visible), 180)
            self.assertEqual(chunk.count("<blockquote>"), chunk.count("</blockquote>"))
            self.assertEqual(chunk.count("<b>"), chunk.count("</b>"))
        original_visible = html.unescape(re.sub(r"<[^>]+>", "", source))
        chunked_visible = "".join(html.unescape(re.sub(r"<[^>]+>", "", chunk)) for chunk in chunks)
        self.assertEqual(chunked_visible, original_visible)

    async def test_long_animation_description_is_sent_as_separate_messages(self):
        giveaway = SimpleNamespace(
            publish_channel_id=-100123,
            photo_id=None,
            animation_id="gif-file-id",
            video_id=None,
        )
        media_message = SimpleNamespace(chat=SimpleNamespace(id=-100123), message_id=10)
        text_messages = [
            SimpleNamespace(chat=SimpleNamespace(id=-100123), message_id=11),
            SimpleNamespace(chat=SimpleNamespace(id=-100123), message_id=12),
        ]
        markup = object()
        long_text = "<blockquote>" + ("текст " * 900) + "</blockquote>"

        with patch.object(production.bot, "send_animation", new=AsyncMock(return_value=media_message)) as send_animation:
            with patch.object(production.bot, "send_message", new=AsyncMock(side_effect=text_messages)) as send_message:
                sent = await production.send_giveaway_messages(giveaway, long_text, markup)

        self.assertEqual(sent.message_id, 12)
        send_animation.assert_awaited_once_with(-100123, "gif-file-id", caption=None, reply_markup=None)
        self.assertEqual(send_message.await_count, 2)
        self.assertIsNone(send_message.await_args_list[0].kwargs["reply_markup"])
        self.assertIs(send_message.await_args_list[-1].kwargs["reply_markup"], markup)

    def test_giveaway_text_supports_quote_prefix_and_formatting(self):
        text = "Заголовок\n> Строка с цитатой"
        bold = SimpleNamespace(type="bold", offset=0, length=9)

        rendered = production.format_giveaway_text(text, [bold])

        self.assertEqual(rendered, "<b>Заголовок</b>\n<blockquote>Строка с цитатой</blockquote>")

    def test_giveaway_text_keeps_native_telegram_blockquote(self):
        text = "Нативная цитата"
        blockquote = SimpleNamespace(type="blockquote", offset=0, length=len(text))

        rendered = production.format_giveaway_text(text, [blockquote])

        self.assertEqual(rendered, "<blockquote>Нативная цитата</blockquote>")

    async def test_create_media_accepts_telegram_animation(self):
        message = SimpleNamespace(
            content_type="animation",
            animation=SimpleNamespace(file_id="gif-file-id"),
            answer=AsyncMock(),
        )
        state = SimpleNamespace(update_data=AsyncMock())

        with patch.object(production.AdminStates.create_end_at, "set", new=AsyncMock()):
            await production.create_media(message, state)

        state.update_data.assert_awaited_once_with(
            photo_id=None,
            video_id=None,
            animation_id="gif-file-id",
        )

    def test_prize_place_count_and_total_slots(self):
        giveaway = SimpleNamespace(winners_count=5, reserve_winners_count=2)

        self.assertEqual(production.prize_place_count(giveaway), 5)
        self.assertEqual(production.winners_per_prize_place(giveaway), 2)
        self.assertEqual(production.total_winner_slots(giveaway), 10)
        self.assertEqual(production.winner_slots(giveaway), [1, 1, 2, 2, 3, 3, 4, 4, 5, 5])

    async def test_finish_giveaway_selects_expected_winners(self):
        giveaway = FakeGiveaway(winners_count=2, reserve_winners_count=1)
        participants = [
            {"user_id": 1, "username": "one", "first_name": "One", "last_name": ""},
            {"user_id": 2, "username": "two", "first_name": "Two", "last_name": ""},
            {"user_id": 3, "username": "three", "first_name": "Three", "last_name": ""},
        ]
        winner_repo = FakeWinnerRepo()

        with patch.object(production, "GiveawayParticipant", return_value=FakeParticipantRepo(participants)):
            with patch.object(production, "GiveawayWinner", return_value=winner_repo):
                with patch.object(production.secure_random, "shuffle", lambda items: None):
                    with patch.object(production, "notify_finish", new=AsyncMock()):
                        winners = await production.finish_giveaway(giveaway, reason="test")

        self.assertEqual([winner["user_id"] for winner in winners], [1, 2])
        self.assertEqual([winner["place"] for winner in winners], [1, 2])
        self.assertFalse(giveaway.run_status)
        self.assertIsNotNone(giveaway.finished_at)
        self.assertEqual(len(winner_repo.saved), 2)

    async def test_manual_winner_is_preselected_without_finishing_giveaway(self):
        giveaway = FakeGiveaway()
        winner_repo = FakeWinnerRepo()
        participant = {
            "user_id": 7,
            "username": "manual",
            "first_name": "Manual",
            "last_name": "Winner",
        }

        with patch.object(production, "GiveawayWinner", return_value=winner_repo):
            winner = await production.preselect_manual_winner(giveaway, participant)

        self.assertTrue(giveaway.run_status)
        self.assertIsNone(giveaway.finished_at)
        self.assertEqual(winner["user_id"], 7)
        self.assertEqual(winner_repo.saved[0]["place"], 1)

    async def test_finish_giveaway_preserves_preselected_winner(self):
        giveaway = FakeGiveaway(winners_count=2, reserve_winners_count=1)
        participants = [
            {"user_id": 1, "username": "one", "first_name": "One", "last_name": ""},
            {"user_id": 2, "username": "two", "first_name": "Two", "last_name": ""},
            {"user_id": 3, "username": "manual", "first_name": "Manual", "last_name": ""},
        ]
        winner_repo = FakeWinnerRepo()
        winner_repo.saved = [
            {
                "user_id": 3,
                "username": "manual",
                "first_name": "Manual",
                "last_name": "",
                "place": 1,
                "is_reserve": False,
            }
        ]

        with patch.object(production, "GiveawayParticipant", return_value=FakeParticipantRepo(participants)):
            with patch.object(production, "GiveawayWinner", return_value=winner_repo):
                with patch.object(production.secure_random, "shuffle", lambda items: None):
                    with patch.object(production, "notify_finish", new=AsyncMock()):
                        winners = await production.finish_giveaway(giveaway, reason="test")

        self.assertEqual([winner["user_id"] for winner in winners], [3, 1])
        self.assertEqual([winner["place"] for winner in winners], [1, 2])
        self.assertFalse(giveaway.run_status)
        self.assertIsNotNone(giveaway.finished_at)

    def test_strict_subscription_conditions_ignore_soft_links(self):
        conditions = [
            {"target_channel_id": 1, "target_channel_name": "Strict", "condition_type": "strict"},
            {"target_channel_id": 2, "target_channel_name": "Soft", "condition_type": "soft"},
            {"target_channel_id": 3, "target_channel_name": "Default"},
        ]

        strict = production.strict_subscription_conditions(conditions)

        self.assertEqual([item["target_channel_id"] for item in strict], [1, 3])

    async def test_export_participants_csv_writes_expected_columns(self):
        giveaway = FakeGiveaway(callback_value="csv-test")
        participants = [
            {
                "user_id": 10,
                "username": "winner",
                "first_name": "Win",
                "last_name": "Ner",
                "joined_at": "2026-06-25T12:00:00",
            }
        ]

        with patch.object(production, "GiveawayParticipant", return_value=FakeParticipantRepo(participants)):
            path = await production.export_participants_csv(giveaway)

        try:
            with path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(rows[0]["user_id"], "10")
            self.assertEqual(rows[0]["username"], "winner")
            self.assertEqual(rows[0]["first_name"], "Win")
            self.assertEqual(rows[0]["last_name"], "Ner")
            self.assertEqual(rows[0]["joined_at"], "2026-06-25T12:00:00")
        finally:
            path.unlink(missing_ok=True)
            try:
                Path("exports").rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
