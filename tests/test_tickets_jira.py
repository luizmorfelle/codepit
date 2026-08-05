import base64
import unittest
from lib.tickets import jira


class TestTicketsJira(unittest.TestCase):
    def test_build_jql_no_projects(self):
        self.assertEqual(
            jira.build_jql([]),
            "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC")

    def test_build_jql_with_projects(self):
        jql = jira.build_jql(["ABC", "DEF"])
        self.assertIn('project in ("ABC", "DEF")', jql)
        self.assertTrue(jql.startswith("assignee = currentUser()"))

    def test_parse_issue(self):
        raw = {"key": "ABC-12", "fields": {
            "summary": "fix login", "status": {"name": "In Progress"},
            "project": {"key": "ABC", "name": "Alpha"}}}
        self.assertEqual(jira.parse_issue(raw, "https://x.atlassian.net"), {
            "key": "ABC-12", "status": "In Progress", "summary": "fix login", "project": "ABC",
            "url": "https://x.atlassian.net/browse/ABC-12"})

    def test_parse_issue_missing_fields(self):
        self.assertEqual(jira.parse_issue({"key": "X-1"}),
                         {"key": "X-1", "status": "?", "summary": "", "project": "", "url": ""})

    def test_auth_header(self):
        h = jira.auth_header("me@x.com", "tok")
        self.assertEqual(h, "Basic " + base64.b64encode(b"me@x.com:tok").decode())


if __name__ == "__main__":
    unittest.main()
