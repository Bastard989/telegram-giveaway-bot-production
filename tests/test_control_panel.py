import tempfile
import unittest
import sqlite3
from pathlib import Path
from unittest.mock import patch

import control_panel


class ControlPanelTest(unittest.TestCase):
    def test_backup_database_copies_sqlite_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "giveaway.sqlite3"
            with sqlite3.connect(db_path) as connection:
                connection.execute("CREATE TABLE sample (value TEXT)")
                connection.execute("INSERT INTO sample VALUES ('database')")
            backup_dir = tmp_path / "backups"

            with patch.object(control_panel, "BACKUP_DIR", backup_dir):
                with patch.object(control_panel, "BASE_DIR", tmp_path):
                    with patch.object(control_panel, "read_env", return_value={"DATABASE_URL": f"sqlite://{db_path}"}):
                        message = control_panel.backup_database()

            self.assertIn("Backup базы создан", message)
            backups = list(backup_dir.glob("giveaway-*.sqlite3"))
            self.assertEqual(len(backups), 1)
            with sqlite3.connect(backups[0]) as connection:
                value = connection.execute("SELECT value FROM sample").fetchone()[0]
            self.assertEqual(value, "database")

    def test_clear_saved_token_keeps_other_settings(self):
        saved = {}

        def fake_write_env(data):
            saved.update(data)

        with patch.object(
            control_panel,
            "read_env",
            return_value={"BOT_TOKEN": "123:token", "OWNERS": "1", "DATABASE_URL": "sqlite://runtime/db.sqlite3"},
        ):
            with patch.object(control_panel, "write_env", fake_write_env):
                message = control_panel.clear_saved_token()

        self.assertIn("Токен очищен", message)
        self.assertEqual(saved["BOT_TOKEN"], "")
        self.assertEqual(saved["OWNERS"], "1")

    def test_check_environment_reports_core_items(self):
        with patch.object(control_panel, "read_env", return_value={"BOT_TOKEN": "123:token", "DATABASE_URL": "sqlite://runtime/missing.sqlite3"}):
            with patch.object(control_panel, "check_token_valid", return_value=(True, "токен валиден")):
                message = control_panel.check_environment()

        self.assertIn("Python бота", message)
        self.assertIn("Зависимости установлены", message)
        self.assertIn("Часовой пояс Europe/Moscow", message)
        self.assertIn("Токен валиден: да", message)
        self.assertIn("База доступна", message)


if __name__ == "__main__":
    unittest.main()
