import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from amnezia_split_cli import cli
from amnezia_split_cli.amnezia import AmneziaError
from amnezia_split_cli.config import load_entries, write_entries


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.path = root / "exceptions.json"
        self.backup = root / "backup.plist"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def args(self, *arguments):
        return cli.build_parser().parse_args(
            ["--file", str(self.path), "--backup", str(self.backup), *arguments]
        )

    def test_add_preserves_gui_only_rules(self):
        write_entries(self.path, [{"hostname": "json.example", "ip": "192.0.2.1"}])
        preferences = {"Conf.ExceptSites": {"gui.example": ["192.0.2.2"]}}
        with patch.object(cli, "export_preferences", return_value=preferences), patch.object(
            cli, "resolve", return_value="192.0.2.3"
        ), patch.object(cli, "apply_entries") as apply:
            cli.add_hosts(self.args("add", "new.example", "--no-restart"))
        self.assertEqual(
            {entry["hostname"] for entry in load_entries(self.path)},
            {"json.example", "gui.example", "new.example"},
        )
        apply.assert_not_called()

    def test_sync_merges_current_rules_by_default(self):
        write_entries(self.path, [{"hostname": "json.example", "ip": "192.0.2.1"}])
        preferences = {"Conf.ExceptSites": {"gui.example": ["192.0.2.2"]}}
        with patch.object(cli, "export_preferences", return_value=preferences):
            cli.sync_entries(self.args("sync", "--no-restart"))
        self.assertEqual(
            {entry["hostname"] for entry in load_entries(self.path)},
            {"json.example", "gui.example"},
        )

    def test_sync_replace_removes_rules_absent_from_json(self):
        write_entries(self.path, [{"hostname": "json.example", "ip": "192.0.2.1"}])
        preferences = {"Conf.ExceptSites": {"gui.example": ["192.0.2.2"]}}
        with patch.object(cli, "export_preferences", return_value=preferences):
            cli.sync_entries(self.args("sync", "--replace", "--no-restart"))
        self.assertEqual(
            load_entries(self.path),
            [{"hostname": "json.example", "ip": "192.0.2.1"}],
        )

    def test_remove_accepts_ip(self):
        entries = [
            {"hostname": "one.example", "ip": "192.0.2.1"},
            {"hostname": "two.example", "ip": "192.0.2.2"},
        ]
        write_entries(self.path, entries)
        preferences = {"Conf.ExceptSites": {}}
        with patch.object(cli, "export_preferences", return_value=preferences):
            cli.remove_hosts(self.args("remove", "192.0.2.1", "--no-restart"))
        self.assertEqual(load_entries(self.path), entries[1:])

    def test_dry_run_does_not_write_or_apply(self):
        original = [{"hostname": "old.example", "ip": "192.0.2.1"}]
        write_entries(self.path, original)
        preferences = {"Conf.ExceptSites": {}}
        with patch.object(cli, "export_preferences", return_value=preferences), patch.object(
            cli, "resolve", return_value="192.0.2.2"
        ), patch.object(cli, "apply_entries") as apply:
            cli.add_hosts(self.args("add", "new.example", "--dry-run"))
        self.assertEqual(load_entries(self.path), original)
        apply.assert_not_called()

    def test_apply_failure_restores_original_json(self):
        original = [{"hostname": "old.example", "ip": "192.0.2.1"}]
        write_entries(self.path, original)
        preferences = {"Conf.ExceptSites": {}}
        with patch.object(cli, "export_preferences", return_value=preferences), patch.object(
            cli, "resolve", return_value="192.0.2.2"
        ), patch.object(cli, "apply_entries", side_effect=AmneziaError("failed")):
            with self.assertRaises(AmneziaError):
                cli.add_hosts(self.args("add", "new.example"))
        self.assertEqual(load_entries(self.path), original)

    def test_list_json_is_machine_readable(self):
        entries = [{"hostname": "example.com", "ip": "192.0.2.1"}]
        write_entries(self.path, entries)
        output = io.StringIO()
        with redirect_stdout(output):
            cli.list_entries(self.args("list", "--json"))
        self.assertEqual(json.loads(output.getvalue()), entries)


if __name__ == "__main__":
    unittest.main()
