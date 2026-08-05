import unittest
from datetime import datetime, timedelta
from lib import agenda


class TestAgenda(unittest.TestCase):
    def test_human_delta(self):
        self.assertEqual(agenda.human_delta(timedelta(minutes=90)), "in 1h 30min")
        self.assertEqual(agenda.human_delta(timedelta(minutes=-5)), "past")

    def test_next_event_same_day(self):
        # Friday 2026-06-12 09:00 -> Review is 16:30 the same day
        dt, name = agenda.next_event(datetime(2026, 6, 12, 9, 0))
        self.assertEqual(name, "Review")
        self.assertEqual((dt.day, dt.hour), (12, 16))

    def test_next_event_rolls_to_next_day(self):
        # Wednesday 2026-06-10 09:00 -> Daily is past; next is Thursday 11th, Daily 08:30
        dt, name = agenda.next_event(datetime(2026, 6, 10, 9, 0))
        self.assertEqual(name, "Daily")
        self.assertEqual((dt.day, dt.hour, dt.minute), (11, 8, 30))

    def test_next_event_over_the_weekend(self):
        # Saturday 2026-06-13 -> next is Monday 15th (Daily/Planning 08:30)
        dt, _ = agenda.next_event(datetime(2026, 6, 13, 10, 0))
        self.assertEqual(dt.day, 15)

    def test_next_event_text_same_day(self):
        txt = agenda.next_event_text(datetime(2026, 6, 12, 15, 0))
        self.assertTrue(txt.startswith("Next: Review in "))

    def test_next_event_text_another_day(self):
        txt = agenda.next_event_text(datetime(2026, 6, 13, 10, 0))
        self.assertTrue(txt.startswith("Next: mon "))


if __name__ == "__main__":
    unittest.main()
