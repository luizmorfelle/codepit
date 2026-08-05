import unittest
from lib import heatmap_github


class TestHeatmapGithub(unittest.TestCase):
    def test_parse_calendar_flattens_weeks(self):
        raw = {"data": {"viewer": {"contributionsCollection": {"contributionCalendar": {
            "weeks": [
                {"contributionDays": [
                    {"date": "2026-07-01", "contributionCount": 2},
                    {"date": "2026-07-02", "contributionCount": 0},
                ]},
                {"contributionDays": [
                    {"date": "2026-07-03", "contributionCount": 5},
                ]},
            ]
        }}}}}
        self.assertEqual(heatmap_github.parse_calendar(raw), [
            {"date": "2026-07-01", "count": 2},
            {"date": "2026-07-02", "count": 0},
            {"date": "2026-07-03", "count": 5},
        ])

    def test_parse_calendar_empty_on_malformed(self):
        self.assertEqual(heatmap_github.parse_calendar({}), [])
        self.assertEqual(heatmap_github.parse_calendar({"data": None}), [])


if __name__ == "__main__":
    unittest.main()
