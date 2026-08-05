import unittest
from lib import github_api


class TestGithubApi(unittest.TestCase):
    def test_ticket_key(self):
        self.assertEqual(github_api.ticket_key("feat(APP-428): dark mode"), "APP-428")
        self.assertEqual(github_api.ticket_key("WEB-330 - refund flow"), "WEB-330")
        self.assertEqual(github_api.ticket_key("fix(API-208): wallet"), "API-208")
        self.assertIsNone(github_api.ticket_key("chore: no ticket here"))

    def test_categorize_pr(self):
        self.assertEqual(github_api.categorize_pr({"state": "merged"}), "merged")
        self.assertEqual(github_api.categorize_pr(
            {"state": "open", "_status": {"reviewDecision": "CHANGES_REQUESTED"}}), "changes")
        self.assertEqual(github_api.categorize_pr(
            {"state": "open", "_status": {"reviewDecision": None}}), "review")
        self.assertEqual(github_api.categorize_pr(
            {"state": "open", "_status": None}), "review")
        self.assertIsNone(github_api.categorize_pr({"state": "closed"}))

    def test_review_glyph(self):
        self.assertEqual(github_api.review_glyph({"reviewDecision": "APPROVED", "isDraft": False}), "✓ approved")
        self.assertEqual(github_api.review_glyph({"reviewDecision": "CHANGES_REQUESTED", "isDraft": False}), "⏳ changes")
        self.assertEqual(github_api.review_glyph({"reviewDecision": "", "isDraft": False}), "● review")
        self.assertEqual(github_api.review_glyph({"reviewDecision": "", "isDraft": True}), "📝 draft")
        self.assertEqual(github_api.review_glyph(None), "")

    def test_ci_glyph(self):
        self.assertEqual(github_api.ci_glyph({"statusCheckRollup": []}), "")
        self.assertEqual(github_api.ci_glyph({"statusCheckRollup": [{"conclusion": "SUCCESS"}]}), "🟢 CI")
        self.assertEqual(github_api.ci_glyph({"statusCheckRollup": [{"conclusion": "FAILURE"}]}), "🔴 CI")
        self.assertEqual(github_api.ci_glyph({"statusCheckRollup": [{"status": "IN_PROGRESS"}]}), "🟡 CI")
        self.assertEqual(github_api.ci_glyph(None), "")

    def test_matches_repos(self):
        pr = {"repository": {"nameWithOwner": "acme/widgets"}}
        self.assertTrue(github_api.matches_repos(pr, []))
        self.assertTrue(github_api.matches_repos(pr, ["acme/widgets"]))
        self.assertTrue(github_api.matches_repos(pr, ["acme"]))
        self.assertFalse(github_api.matches_repos(pr, ["other/repo"]))


if __name__ == "__main__":
    unittest.main()
