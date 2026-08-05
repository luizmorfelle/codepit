import json
import os
import tempfile
import unittest
from lib import pet_state


class TestPetState(unittest.TestCase):
    def test_load_defaults_on_missing_file(self):
        path = tempfile.mktemp(suffix=".json")
        try:
            state = pet_state.load(path)
            self.assertEqual(state["name"], "Bit")
            self.assertTrue(state["created_at"])
            self.assertTrue(os.path.exists(path))  # persisted for next time
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_load_reads_existing_state(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"name": "Rex", "created_at": "2026-01-01"}, f)
            path = f.name
        try:
            state = pet_state.load(path)
            self.assertEqual(state["name"], "Rex")
            self.assertEqual(state["created_at"], "2026-01-01")
        finally:
            os.unlink(path)

    def test_mood_happy_when_committed_today(self):
        self.assertEqual(pet_state.mood(commits_today=2, claude_pct_5h=0), "happy")

    def test_mood_thinking_when_no_commit_but_claude_used(self):
        self.assertEqual(pet_state.mood(commits_today=0, claude_pct_5h=15), "thinking")

    def test_mood_hungry_when_no_activity(self):
        self.assertEqual(pet_state.mood(commits_today=0, claude_pct_5h=0), "hungry")

    def test_streak_counts_consecutive_days_ending_today(self):
        calendar = [
            {"date": "2026-07-28", "count": 1},
            {"date": "2026-07-29", "count": 2},
            {"date": "2026-07-30", "count": 1},
        ]
        self.assertEqual(pet_state.streak_from_calendar(calendar, "2026-07-30"), 3)

    def test_streak_ignores_todays_zero_and_uses_yesterday(self):
        calendar = [
            {"date": "2026-07-29", "count": 1},
            {"date": "2026-07-30", "count": 0},  # today, no commit yet
        ]
        self.assertEqual(pet_state.streak_from_calendar(calendar, "2026-07-30"), 1)

    def test_streak_zero_when_yesterday_also_empty(self):
        calendar = [
            {"date": "2026-07-29", "count": 0},
            {"date": "2026-07-30", "count": 0},
        ]
        self.assertEqual(pet_state.streak_from_calendar(calendar, "2026-07-30"), 0)

    def test_streak_missing_dates_treated_as_zero(self):
        self.assertEqual(pet_state.streak_from_calendar([], "2026-07-30"), 0)


if __name__ == "__main__":
    unittest.main()
