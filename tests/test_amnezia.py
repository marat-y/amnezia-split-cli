import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amnezia_split_cli.amnezia import apply_entries, write_plist


class AmneziaTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "backup.plist"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_backup_is_private_and_readable(self):
        preferences = {"Conf.ExceptSites": {"example.com": ["192.0.2.1"]}}
        write_plist(self.path, preferences)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        with self.path.open("rb") as backup_file:
            self.assertEqual(plistlib.load(backup_file), preferences)

    def test_unchanged_entries_do_not_restart_amnezia(self):
        entries = [{"hostname": "example.com", "ip": "192.0.2.1"}]
        preferences = {"Conf.ExceptSites": {"example.com": ["192.0.2.1"]}}
        with patch("amnezia_split_cli.amnezia.quit_amnezia") as quit_app:
            changed = apply_entries(entries, preferences, self.path)
        self.assertFalse(changed)
        self.assertFalse(self.path.exists())
        quit_app.assert_not_called()


if __name__ == "__main__":
    unittest.main()
