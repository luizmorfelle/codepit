import unittest
from lib.prs import github


class TestPrsGithub(unittest.TestCase):
    def test_normalize_open(self):
        pr = {"number": 7, "title": "feat(APP-1): x", "url": "u",
              "repository": {"name": "web-client"}, "_role": "author", "_category": "review",
              "_key": "APP-1",
              "_status": {"reviewDecision": "APPROVED", "isDraft": False,
                          "statusCheckRollup": [{"conclusion": "SUCCESS"}]}}
        n = github.normalize(pr)
        self.assertEqual(n["_repo"], "web-client")
        self.assertEqual(n["number"], 7)
        self.assertEqual(n["_review"], "✓ approved")
        self.assertEqual(n["_ci"], "🟢 CI")
        self.assertEqual(n["_key"], "APP-1")

    def test_normalize_merged_hides_review(self):
        pr = {"number": 9, "title": "done", "repository": {"name": "r"},
              "_role": "reviewer", "_category": "merged", "_key": None, "_status": None}
        n = github.normalize(pr)
        self.assertEqual(n["_review"], "")   # merged → no review glyph
        self.assertEqual(n["_ci"], "")


if __name__ == "__main__":
    unittest.main()
