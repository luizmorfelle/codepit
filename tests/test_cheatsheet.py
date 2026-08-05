import unittest
from lib import cheatsheet


class TestCheatsheet(unittest.TestCase):
    def test_one_line_contains_key_shortcuts(self):
        line = cheatsheet.one_line()
        for token in ("Alt+t", "Ctrl+q", "board"):
            self.assertIn(token, line)

    def test_one_line_is_single_line(self):
        self.assertNotIn("\n", cheatsheet.one_line())


if __name__ == "__main__":
    unittest.main()
