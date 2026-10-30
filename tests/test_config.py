import json
import tempfile
import unittest
from pathlib import Path

from amnezia_split_cli.config import (
    ConfigError,
    entries_to_sites,
    load_entries,
    merge_entries,
    sites_to_entries,
    write_entries,
)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "exceptions.json"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_merge_preserves_gui_rules_and_prefers_json_for_conflicts(self):
        entries = [{"hostname": "example.com", "ip": "192.0.2.1"}]
        sites = {
            "example.com": ["192.0.2.200"],
            "gui-only.example": ["192.0.2.2"],
        }
        self.assertEqual(
            merge_entries(entries, sites),
            [
                {"hostname": "example.com", "ip": "192.0.2.1"},
                {"hostname": "gui-only.example", "ip": "192.0.2.2"},
            ],
        )

    def test_write_and_load_round_trip(self):
        entries = [{"hostname": "example.com", "ip": "192.0.2.1"}]
        write_entries(self.path, entries)
        self.assertEqual(load_entries(self.path), entries)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_missing_file_is_an_empty_list(self):
        self.assertEqual(load_entries(self.path), [])

    def test_invalid_json_shape_is_rejected(self):
        self.path.write_text(json.dumps({"hostname": "example.com"}))
        with self.assertRaises(ConfigError):
            load_entries(self.path)

    def test_sites_conversion_preserves_empty_addresses(self):
        sites = {"empty.example": []}
        self.assertEqual(
            sites_to_entries(sites),
            [{"hostname": "empty.example", "ip": ""}],
        )
        self.assertEqual(
            entries_to_sites([{"hostname": "empty.example", "ip": ""}]),
            sites,
        )


if __name__ == "__main__":
    unittest.main()
