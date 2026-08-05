import unittest
from lib import theme


class TestTheme(unittest.TestCase):
    def test_fg(self):
        self.assertEqual(theme.fg("blue"), "\033[38;5;111m")

    def test_bg(self):
        self.assertEqual(theme.bg("green"), "\033[48;5;150m")

    def test_badge_wraps_label_and_resets(self):
        b = theme.badge("To Do", "blue")
        self.assertIn("To Do", b)
        self.assertTrue(b.endswith(theme.RESET))

    def test_every_color_has_an_int_index(self):
        for name, idx in theme.COLORS.items():
            self.assertIsInstance(idx, int)


if __name__ == "__main__":
    unittest.main()
