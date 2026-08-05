import unittest
from lib import demo


class TestDemo(unittest.TestCase):
    def test_issues_shape(self):
        items = demo.issues()
        self.assertTrue(items)
        for it in items:
            self.assertEqual(set(it), {"key", "status", "summary", "project", "url"})

    def test_prs_shape(self):
        items = demo.prs()
        self.assertTrue(items)
        for pr in items:
            for k in ("number", "title", "_repo", "_role", "_category", "_key"):
                self.assertIn(k, pr)

    def test_usage_shape(self):
        u = demo.usage()
        for k in ("five_hour", "seven_day", "sonnet", "plan"):
            self.assertIn(k, u)
        self.assertIn("pct", u["five_hour"])
        self.assertIn("resets_at", u["five_hour"])


if __name__ == "__main__":
    unittest.main()
