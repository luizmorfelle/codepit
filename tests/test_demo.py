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

    def test_heatmap_shape(self):
        cal = demo.heatmap()
        self.assertEqual(len(cal), 84)
        for d in cal:
            self.assertEqual(set(d), {"date", "count"})
            self.assertIsInstance(d["count"], int)
            self.assertGreaterEqual(d["count"], 0)

    def test_omniroute_usage_shape(self):
        u = demo.omniroute_usage()
        self.assertIn("connections", u)
        self.assertIn("fetched_at", u)
        for conn in u["connections"]:
            self.assertIn("provider", conn)
            self.assertIn("name", conn)


if __name__ == "__main__":
    unittest.main()
