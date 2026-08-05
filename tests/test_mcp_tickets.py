import unittest
from lib import mcp_tickets

ITEMS = [
    {"issueKey": "APP-425", "title": "Dark mode", "statusName": "InProgress",
     "projectKey": "APP"},
    {"issueKey": "APP-450", "title": "Onboarding tour", "statusName": "Done",
     "projectKey": "APP"},
    {"issueKey": "WEB-341", "title": "Orders table filter", "statusName": "Todo",
     "projectKey": "WEB"},
    {"issueKey": "OPS-9", "title": "out of scope", "statusName": "Todo",
     "projectKey": "OPS"},
]


class TestMcpTickets(unittest.TestCase):
    def test_friendly_status_maps_known_ones(self):
        self.assertEqual(mcp_tickets.friendly_status("Todo"), "To Do")
        self.assertEqual(mcp_tickets.friendly_status("InProgress"), "In Progress")
        self.assertEqual(mcp_tickets.friendly_status("OpenPR"), "Pull Request")
        self.assertEqual(mcp_tickets.friendly_status("InReview"), "Review")

    def test_friendly_status_splits_unknown_camelcase(self):
        self.assertEqual(mcp_tickets.friendly_status("OnHold"), "On Hold")

    def test_friendly_status_empty(self):
        self.assertEqual(mcp_tickets.friendly_status(""), "?")

    def test_parse_items_filters_done_and_project(self):
        out = mcp_tickets.parse_items(ITEMS, {"APP", "WEB"})
        keys = [it["key"] for it in out]
        self.assertEqual(keys, ["APP-425", "WEB-341"])  # no Done, no OPS

    def test_parse_items_board_contract(self):
        out = mcp_tickets.parse_items(ITEMS, {"APP", "WEB"})
        self.assertEqual(out[0], {"key": "APP-425", "status": "In Progress",
                                  "summary": "Dark mode", "project": "APP", "url": ""})

    def test_parse_items_empty(self):
        self.assertEqual(mcp_tickets.parse_items([], {"APP"}), [])

    def test_parse_sse_extracts_data(self):
        body = 'event: message\ndata: {"result": {"ok": 1}, "id": 2}\n\n'
        self.assertEqual(mcp_tickets._parse_sse(body), {"result": {"ok": 1}, "id": 2})

    def test_parse_sse_without_body(self):
        with self.assertRaises(RuntimeError):
            mcp_tickets._parse_sse("event: ping\n\n")


if __name__ == "__main__":
    unittest.main()
