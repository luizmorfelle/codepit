import unittest
from widgets import board

ISSUES = [
    {"key": "APP-411", "status": "In Development", "category": "indeterminate", "summary": "x"},
    {"key": "WEB-183", "status": "Review", "category": "indeterminate", "summary": "y"},
    {"key": "API-1", "status": "To Do", "category": "new", "summary": "z"},
]


class TestBoard(unittest.TestCase):
    def test_distinct_statuses_is_ordered(self):
        self.assertEqual(board.distinct_statuses(ISSUES), ["To Do", "In Development", "Review"])

    def test_default_active(self):
        self.assertEqual(board.default_active(["To Do", "In Development", "Review"]),
                         {"To Do", "In Development"})

    def test_apply_filter(self):
        self.assertEqual([i["key"] for i in board.apply_filter(ISSUES, {"To Do"})], ["API-1"])

    def test_chip_layout(self):
        chips = board.chip_layout(["To Do", "Review"], {"To Do"}, x0=0, y=1)
        self.assertEqual(chips[0]["label"], " To Do ")
        self.assertTrue(chips[0]["active"])
        self.assertGreater(chips[1]["x0"], chips[0]["x1"])

    def test_clamp_scroll(self):
        self.assertEqual(board.clamp_scroll(0, 10, 5), 0)
        self.assertEqual(board.clamp_scroll(99, 10, 5), 5)
        self.assertEqual(board.clamp_scroll(-3, 10, 5), 0)
        self.assertEqual(board.clamp_scroll(2, 3, 5), 0)

    def test_status_color(self):
        self.assertEqual(board.status_color("In Development"), "yellow")
        self.assertEqual(board.status_color("Review"), "purple")
        self.assertEqual(board.status_color("Anything Else"), "dim")

    def test_review_color(self):
        self.assertEqual(board.review_color("✓ approved"), "green")
        self.assertEqual(board.review_color("⏳ changes"), "red")
        self.assertEqual(board.review_color("● review"), "blue")
        self.assertEqual(board.review_color("📝 draft"), "dim")

    def test_status_distribution_includes_done_and_orders(self):
        issues = [
            {"status": "To Do"}, {"status": "To Do"},
            {"status": "In Development"},
            {"status": "Done"},
        ]
        dist = board.status_distribution(issues)
        self.assertEqual([d["status"] for d in dist], ["To Do", "In Development", "Done"])
        self.assertEqual([d["count"] for d in dist], [2, 1, 1])
        self.assertEqual([d["pct"] for d in dist], [50, 25, 25])

    def test_status_distribution_empty(self):
        self.assertEqual(board.status_distribution([]), [])

    def test_pr_counts_and_filter(self):
        prs = [
            {"_category": "merged", "_key": "APP-1"},
            {"_category": "review", "_key": "APP-2"},
            {"_category": "review", "_key": None},
        ]
        self.assertEqual(board.pr_counts(prs), {"merged": 1, "review": 2})
        only_review = board.filter_prs(prs, {"review"})
        self.assertEqual(len(only_review), 2)
        review_changes = board.filter_prs(prs, {"review", "changes"})
        self.assertTrue(all(p["_category"] in {"review", "changes"} for p in review_changes))
        self.assertEqual(len(review_changes), 2)

    def test_pr_default_excludes_merged(self):
        self.assertEqual(board.PR_DEFAULT, {"review", "changes"})

    def test_pr_chip_layout(self):
        chips = board.pr_chip_layout({"review": 4, "changes": 2, "merged": 9},
                                     {"review", "changes"}, x0=1, y=5)
        self.assertEqual([c["cat"] for c in chips], ["review", "changes", "merged"])
        self.assertTrue(chips[0]["active"])      # review (default on)
        self.assertFalse(chips[2]["active"])     # merged (default off)

    def test_role_glyph(self):
        self.assertEqual(board.role_glyph("reviewer"), "👁")
        self.assertEqual(board.role_glyph("author"), "✎")

    def test_hit_test(self):
        chips = board.chip_layout(["To Do", "Review"], set(), x0=1, y=5)
        # a x inside the first chip's span, on its row → its status
        self.assertEqual(board.hit_test(chips, chips[0]["x0"], 5), "To Do")
        self.assertEqual(board.hit_test(chips, chips[1]["x1"], 5), "Review")
        self.assertIsNone(board.hit_test(chips, chips[0]["x0"], 6))   # wrong row
        self.assertIsNone(board.hit_test(chips, 999, 5))              # past the chips

    def test_button_hit(self):
        self.assertTrue(board.button_hit((10, 20, 0), 15, 0))
        self.assertFalse(board.button_hit((10, 20, 0), 15, 1))       # wrong row
        self.assertFalse(board.button_hit((10, 20, 0), 21, 0))       # past the button

    def test_pr_hit_test(self):
        chips = board.pr_chip_layout({"review": 1, "changes": 0, "merged": 0},
                                     {"review"}, x0=1, y=3)
        self.assertEqual(board.pr_hit_test(chips, chips[0]["x0"], 3), "review")
        self.assertIsNone(board.pr_hit_test(chips, chips[0]["x0"], 4))

    def test_heatmap_color_thresholds(self):
        self.assertEqual(board.heatmap_color(0), "heat0")
        self.assertEqual(board.heatmap_color(None), "heat0")
        self.assertEqual(board.heatmap_color(1), "heat1")
        self.assertEqual(board.heatmap_color(2), "heat1")
        self.assertEqual(board.heatmap_color(3), "heat2")
        self.assertEqual(board.heatmap_color(4), "heat2")
        self.assertEqual(board.heatmap_color(5), "heat3")
        self.assertEqual(board.heatmap_color(7), "heat3")
        self.assertEqual(board.heatmap_color(8), "heat4")
        self.assertEqual(board.heatmap_color(100), "heat4")

    def test_heatmap_grid_shape(self):
        grid = board.heatmap_grid([{"date": "2026-07-27", "count": 3}], weeks=2)
        self.assertEqual(len(grid), 2)
        self.assertTrue(all(len(col) == 7 for col in grid))

    def test_heatmap_grid_places_count_on_right_weekday(self):
        # 2026-07-27 is a Monday -> row index 1 (Sun=0..Sat=6) of the last (only) column
        grid = board.heatmap_grid([{"date": "2026-07-27", "count": 3}], weeks=1)
        self.assertEqual(grid[0][1], ("2026-07-27", 3))
        self.assertEqual(grid[0][0], ("2026-07-26", None))

    def test_heatmap_grid_empty_calendar(self):
        self.assertEqual(board.heatmap_grid([], weeks=3), [[None] * 7 for _ in range(3)])

    def test_heatmap_grid_dates_always_present_when_calendar_nonempty(self):
        grid = board.heatmap_grid([{"date": "2026-07-27", "count": 3}], weeks=1)
        for cell in grid[0]:
            self.assertIsNotNone(cell)
            date_str, _count = cell
            self.assertRegex(date_str, r"^\d{4}-\d{2}-\d{2}$")

    def test_heatmap_month_labels_marks_month_changes(self):
        grid = [
            [("2026-06-28", 0)] + [None] * 6,   # Sunday in June
            [("2026-07-05", 1)] + [None] * 6,   # Sunday in July (new month)
            [("2026-07-12", 2)] + [None] * 6,   # Sunday still in July
        ]
        self.assertEqual(board.heatmap_month_labels(grid), {0: "Jun", 1: "Jul"})

    def test_heatmap_month_labels_empty_grid(self):
        self.assertEqual(board.heatmap_month_labels([[None] * 7]), {})


if __name__ == "__main__":
    unittest.main()
