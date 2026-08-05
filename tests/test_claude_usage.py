import unittest
from datetime import datetime, timezone
from lib import claude_usage

SAMPLE = {
    "five_hour": {"utilization": 63.0, "resets_at": "2026-06-11T21:29:00+00:00"},
    "seven_day": {"utilization": 32.0, "resets_at": "2026-06-17T11:00:00+00:00"},
    "seven_day_sonnet": None,
    "extra_usage": {"is_enabled": False},
}


class TestClaudeUsage(unittest.TestCase):
    def test_parse_usage(self):
        u = claude_usage.parse_usage(SAMPLE)
        self.assertEqual(u["five_hour"]["pct"], 63.0)
        self.assertEqual(u["five_hour"]["resets_at"], "2026-06-11T21:29:00+00:00")
        self.assertEqual(u["seven_day"]["pct"], 32.0)
        self.assertIsNone(u["sonnet"])

    def test_usage_bar(self):
        self.assertEqual(claude_usage.usage_bar(50, 10), "█████░░░░░")
        self.assertEqual(claude_usage.usage_bar(0, 4), "░░░░")
        self.assertEqual(claude_usage.usage_bar(100, 4), "████")

    def test_usage_color(self):
        self.assertEqual(claude_usage.usage_color(10), "green")
        self.assertEqual(claude_usage.usage_color(70), "yellow")
        self.assertEqual(claude_usage.usage_color(85), "orange")
        self.assertEqual(claude_usage.usage_color(99), "red")

    def test_human_reset(self):
        now = datetime(2026, 6, 11, 20, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(claude_usage.human_reset("2026-06-11T21:29:00+00:00", now), "1h29m")
        self.assertEqual(claude_usage.human_reset("2026-06-11T19:00:00+00:00", now), "now")
        self.assertEqual(claude_usage.human_reset("2026-06-14T20:00:00+00:00", now), "3d")


if __name__ == "__main__":
    unittest.main()
