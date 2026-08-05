import json
import os
import tempfile
import unittest
from lib import config


class TestConfig(unittest.TestCase):
    def test_load_defaults_when_missing(self):
        cfg = config.load("/no/such/file.json")
        self.assertEqual(cfg["panels"], config.PANELS)
        self.assertEqual(cfg["tickets"]["source"], "github")
        self.assertEqual(cfg["prs"]["source"], "github")

    def test_load_merges_user_over_defaults(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"panels": ["clock"], "tickets": {"source": "mcp"}}, f)
            path = f.name
        try:
            cfg = config.load(path)
            self.assertEqual(cfg["panels"], ["clock"])
            self.assertEqual(cfg["tickets"]["source"], "mcp")
            self.assertEqual(cfg["prs"]["source"], "github")  # untouched default
        finally:
            os.unlink(path)

    def test_panel_and_board_enabled(self):
        cfg = {"panels": ["clock", "tickets"]}
        self.assertTrue(config.panel_enabled(cfg, "tickets"))
        self.assertFalse(config.panel_enabled(cfg, "prs"))
        self.assertTrue(config.board_enabled(cfg))  # tickets is a board card
        self.assertFalse(config.board_enabled({"panels": ["clock"]}))

    def test_build_layout_clock_toggle(self):
        with_clock = config.build_layout({"panels": ["clock", "tickets"]}, "/x")
        self.assertIn("Clock", with_clock)
        self.assertIn("Board", with_clock)
        no_clock = config.build_layout({"panels": ["tickets"]}, "/x")
        self.assertNotIn("Clock", no_clock)

    def test_build_layout_no_board(self):
        only_clock = config.build_layout({"panels": ["clock"]}, "/x")
        self.assertIn("Clock", only_clock)
        self.assertNotIn("Board", only_clock)
        self.assertNotIn('split_direction="vertical"', only_clock)

    def test_build_layout_shortcuts_bar_always_present(self):
        for panels in (["clock", "tickets"], ["clock"], ["prs"]):
            self.assertIn("Shortcuts", config.build_layout({"panels": panels}, "/x"))


if __name__ == "__main__":
    unittest.main()
