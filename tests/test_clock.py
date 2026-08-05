import unittest
from datetime import date
from widgets import clock


class TestClock(unittest.TestCase):
    def test_glyph_has_5_rows(self):
        self.assertEqual(len(clock.glyph("0")), 5)

    def test_big_time_size1_has_5_rows(self):
        self.assertEqual(len(clock.big_time("12:34", 1)), 5)

    def test_big_time_size2_has_10_rows(self):
        self.assertEqual(len(clock.big_time("12:34", 2)), 10)

    def test_big_time_charset(self):
        for r in clock.big_time("00:00", 1):
            self.assertTrue(set(r) <= set("█ "))

    def test_format_date(self):
        self.assertEqual(clock.format_date(date(2026, 6, 11)),
                         "Thursday, June 11, 2026")


if __name__ == "__main__":
    unittest.main()
