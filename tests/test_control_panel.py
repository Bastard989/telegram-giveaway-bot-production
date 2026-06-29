import tempfile
import unittest
import sqlite3
from pathlib import Path
from unittest.mock import patch

import control_panel


class ControlPanelTest(unittest.TestCase):
    def test_install_dependencies_retries_socks_error_in_isolated_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / ".venv").mkdir()
            python = tmp_path / ".venv" / "python.exe"
            socks_error = "ERROR: Missing dependencies for SOCKS support"

            with patch.object(control_panel, "BASE_DIR", tmp_path):
                with patch.object(control_panel, "python_executable", return_value=python):
                    with patch.object(control_panel, "supported_python", return_value=(True, "3.11.9")):
                        with patch.object(
                            control_panel,
                            "run_command",
                            side_effect=[(False, socks_error), (True, "installed")],
                        ) as run_command:
                            with patch.dict(
                                control_panel.os.environ,
                                {"ALL_PROXY": "socks5://127.0.0.1:1080", "PIP_PROXY": "socks5://127.0.0.1:1080"},
                                clear=False,
                            ):
                                message = control_panel.install_dependencies()

            self.assertIn("Зависимости установлены", message)
            retry_command = run_command.call_args_list[1].args[0]
            retry_env = run_command.call_args_list[1].kwargs["env"]
            self.assertIn("--isolated", retry_command)
            self.assertNotIn("ALL_PROXY", retry_env)
            self.assertNotIn("PIP_PROXY", retry_env)
            self.assertEqual(retry_env["PIP_CONFIG_FILE"], control_panel.os.devnull)

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
