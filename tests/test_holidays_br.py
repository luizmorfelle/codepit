import unittest
from datetime import date
from lib import holidays_br


class TestHolidaysBr(unittest.TestCase):
    def test_easter_2026(self):
        self.assertEqual(holidays_br.easter(2026), date(2026, 4, 5))

    def test_easter_2024(self):
        self.assertEqual(holidays_br.easter(2024), date(2024, 3, 31))

    def test_fixed_holiday_christmas(self):
        self.assertEqual(holidays_br.holiday_for(date(2026, 12, 25))[0], "Christmas Day")

    def test_movable_corpus_christi_2026(self):
        # Easter 2026 = Apr 5th; Corpus Christi = Easter + 60 = Jun 4th
        self.assertEqual(holidays_br.holiday_for(date(2026, 6, 4))[0], "Corpus Christi")

    def test_black_consciousness_is_national_since_2024(self):
        self.assertEqual(holidays_br.holiday_for(date(2026, 11, 20))[0], "Black Consciousness Day")

    def test_non_holiday_returns_none(self):
        self.assertIsNone(holidays_br.holiday_for(date(2026, 6, 11)))

    def test_black_consciousness_absent_before_2024(self):
        self.assertIsNone(holidays_br.holiday_for(date(2023, 11, 20)))

    def test_collision_merges_names(self):
        # Easter 2000 = Apr 23rd → Good Friday = Apr 21st = Tiradentes Day
        name = holidays_br.holiday_for(date(2000, 4, 21))[0]
        self.assertIn("Tiradentes", name)
        self.assertIn("Good Friday", name)


if __name__ == "__main__":
    unittest.main()
