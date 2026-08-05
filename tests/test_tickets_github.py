import unittest
from lib.tickets import github


class TestTicketsGithub(unittest.TestCase):
    def test_to_issue(self):
        raw = {"number": 42, "title": "fix map", "repository": {"name": "widgets"},
               "state": "open", "url": "https://github.com/acme/widgets/issues/42"}
        self.assertEqual(github.to_issue(raw), {
            "key": "widgets#42", "status": "Open", "summary": "fix map", "project": "widgets",
            "url": "https://github.com/acme/widgets/issues/42"})

    def test_matches_repos(self):
        raw = {"repository": {"name": "widgets", "nameWithOwner": "acme/widgets"}}
        self.assertTrue(github.matches_repos(raw, []))                 # empty = all
        self.assertTrue(github.matches_repos(raw, ["acme/widgets"]))   # exact
        self.assertTrue(github.matches_repos(raw, ["acme"]))           # owner
        self.assertFalse(github.matches_repos(raw, ["someoneelse/repo"]))


if __name__ == "__main__":
    unittest.main()
