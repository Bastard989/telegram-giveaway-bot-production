import csv
import os
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

    async def add_winner(self, **kwargs):
        self.saved.append(kwargs)

    async def get_winners(self, callback_value):
        return list(self.saved)


class BusinessLogicTest(unittest.IsolatedAsyncioTestCase):
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
