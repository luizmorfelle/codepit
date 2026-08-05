# Git Heatmap + Terminal Pet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub-contributions heatmap card to codepit's board, and a standalone ASCII "pet" widget whose mood reflects today's dev activity.

**Architecture:** Two new `lib/` data modules (`heatmap_github.py`, `pet_state.py`) hold all fetching and pure logic; `widgets/board.py` gets one new card (Heatmap) using the existing Store/worker/curses pattern; `widgets/pet.py` is a new standalone widget mirroring `clock.py`'s curses shape combined with `board.py`'s background-worker shape. `demo.py` gets matching fakes so demo mode and screenshots stay 100% mocked.

**Tech Stack:** Python 3 standard library only (`curses`, `subprocess`, `json`, `threading`, `datetime`), `gh` CLI for GitHub data, `unittest` for tests.

## Global Constraints

- Python 3.8+, Linux only, zero pip dependencies (stdlib only) — matches the rest of codepit.
- GitHub-backed panels shell out to `gh api ...` via `subprocess`, same as `lib/github_api.py` — no `urllib` + token juggling for GitHub.
- Every new per-user file (`pet_state.json`) is gitignored, same treatment as `config.json`.
- Demo mode (`config.demo.json`, `demo: true`) must never call `gh` or read Claude credentials — matches the existing rule in `widgets/board.py`'s `_worker()`.
- No comments in Portuguese; English only, matching the existing codebase.
- Tests: plain `unittest`, no frameworks, no mocking of `subprocess`/`gh` calls (the existing suite doesn't mock `gh` either — only pure helper functions are tested; `fetch_calendar()` itself is not unit tested, same as `fetch_prs()`/`fetch_issues()` today).

## Design deviation from the approved spec (read this first)

The approved spec (`docs/superpowers/specs/2026-08-05-heatmap-pet-design.md`) described the pet's streak as **persisted state** in `pet_state.json`, incremented via a `touch()` call. While writing this plan, that turned out to have a real bug: `commits_today` is provisional (it starts every day at 0, before you've committed yet), so a `touch()` call early in the morning would zero out an otherwise-live streak just because you haven't committed *yet* today.

The fix, applied in Task 6 below: **streak is not stored at all.** It's computed fresh on every refresh from the same `heatmap_github.fetch_calendar()` data the mood already uses — `streak_from_calendar(calendar, today)` walks backward from the most recent day that has *fully elapsed* (skipping today if today's count is still 0) counting consecutive non-zero days. This is simpler (no persisted counter, no day-rollover bookkeeping, no idempotency concerns) and correct in the morning-before-your-first-commit case the stored version got wrong. `pet_state.json` now only holds `name` + `created_at` — exactly what the deferred customization panel needs to edit later, per the spec's stated goal.

---

### Task 1: `lib/heatmap_github.py` — fetch + parse the GitHub contribution calendar

**Files:**
- Create: `lib/heatmap_github.py`
- Test: `tests/test_heatmap_github.py`

**Interfaces:**
- Produces: `heatmap_github.fetch_calendar(weeks=12) -> [{"date": "YYYY-MM-DD", "count": int}]`, oldest first. Raises `RuntimeError` on `gh` failure.
- Produces: `heatmap_github.parse_calendar(raw: dict) -> [{"date": str, "count": int}]`, pure, used by `fetch_calendar` and directly testable.

- [ ] **Step 1: Write the failing test**

Create `tests/test_heatmap_github.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_heatmap_github -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.heatmap_github'`

- [ ] **Step 3: Write the implementation**

Create `lib/heatmap_github.py`:

```python
"""GitHub contribution calendar (commits, PRs, issues, reviews — everything GitHub counts
as a "contribution") via `gh api graphql`. Same aggregate that powers the profile heatmap,
including private contributions the account has access to. Shared by the board's Heatmap
card and the pet's mood/streak calculation — both only need "count per day"."""
import json
import subprocess
from datetime import datetime, timedelta, timezone

QUERY = """
query($from: DateTime!, $to: DateTime!) {
  viewer {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def parse_calendar(raw):
    """Flatten the GraphQL response into [{date, count}], oldest first. Pure."""
    collection = (((raw or {}).get("data") or {}).get("viewer") or {}) \
        .get("contributionsCollection") or {}
    weeks = (collection.get("contributionCalendar") or {}).get("weeks") or []
    out = []
    for week in weeks:
        for day in week.get("contributionDays", []):
            out.append({"date": day["date"], "count": day["contributionCount"]})
    return out


def fetch_calendar(weeks=12):
    """[{date, count}] for the last `weeks`*7 days, oldest first.
    Raises RuntimeError with a clear message on gh failure."""
    to = datetime.now(timezone.utc)
    frm = to - timedelta(weeks=weeks)
    args = ["gh", "api", "graphql", "-f", f"query={QUERY}",
            "-F", f"from={frm.strftime('%Y-%m-%dT00:00:00Z')}",
            "-F", f"to={to.strftime('%Y-%m-%dT23:59:59Z')}"]
    out = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "gh failed")
    return parse_calendar(json.loads(out.stdout or "null") or {})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_heatmap_github -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Personal/codepit
git add lib/heatmap_github.py tests/test_heatmap_github.py
git commit -m "Add lib/heatmap_github.py: fetch + parse the GitHub contribution calendar"
```

---

### Task 2: `lib/demo.py` — fake heatmap data

**Files:**
- Modify: `lib/demo.py`
- Modify: `tests/test_demo.py`

**Interfaces:**
- Consumes: nothing new (pure, self-contained; uses `datetime.date`).
- Produces: `demo.heatmap() -> [{"date": str, "count": int}]`, 84 entries, same shape as `heatmap_github.fetch_calendar()`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_demo.py` (inside `TestDemo`, after `test_usage_shape`):

```python
    def test_heatmap_shape(self):
        cal = demo.heatmap()
        self.assertEqual(len(cal), 84)
        for d in cal:
            self.assertEqual(set(d), {"date", "count"})
            self.assertIsInstance(d["count"], int)
            self.assertGreaterEqual(d["count"], 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_demo -v`
Expected: FAIL with `AttributeError: module 'lib.demo' has no attribute 'heatmap'`

- [ ] **Step 3: Write the implementation**

In `lib/demo.py`, change the import line:

```python
from datetime import datetime, timedelta, timezone
```

to:

```python
from datetime import date, datetime, timedelta, timezone
```

Then add this function at the end of the file, after `usage()`:

```python
def heatmap():
    """Fake 12-week (84-day) contribution calendar, deterministic (no randomness) so the
    demo/screenshot always looks the same relative to 'today'. A repeating weekly shape,
    a couple of quiet weeks, and one busy week — invented but plausible-looking."""
    today = date.today()
    week_shape = [0, 2, 3, 0, 4, 1, 0]  # Sun..Sat, a "typical" week
    quiet_weeks = {2, 3, 8}
    busy_week = 10
    out = []
    for offset in range(83, -1, -1):
        day = today - timedelta(days=offset)
        week_idx = (83 - offset) // 7
        weekday = (day.weekday() + 1) % 7  # Mon=0..Sun=6 -> Sun=0..Sat=6
        if week_idx in quiet_weeks:
            count = 0
        elif week_idx == busy_week:
            count = week_shape[weekday] + 4
        else:
            count = week_shape[weekday]
        out.append({"date": day.isoformat(), "count": count})
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_demo -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Personal/codepit
git add lib/demo.py tests/test_demo.py
git commit -m "Add demo.heatmap() fake contribution calendar"
```

---

### Task 3: `widgets/board.py` — heatmap grid + color pure functions

**Files:**
- Modify: `widgets/board.py`
- Modify: `tests/test_board.py`

**Interfaces:**
- Consumes: nothing new yet (this task only adds pure functions; wiring into the Store/worker/curses loop is Task 4).
- Produces: `board.heatmap_color(count) -> "heat0".."heat4"`, pure.
- Produces: `board.heatmap_grid(calendar, weeks=board.HEATMAP_WEEKS) -> list[list[int|None]]`, `weeks` columns x 7 rows (Sun..Sat), pure.
- Produces: `board.HEATMAP_WEEKS = 12` (module constant).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_board.py` (inside `TestBoard`, after `test_pr_hit_test`):

```python
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
        self.assertEqual(grid[0][1], 3)
        self.assertIsNone(grid[0][0])

    def test_heatmap_grid_empty_calendar(self):
        self.assertEqual(board.heatmap_grid([], weeks=3), [[None] * 7 for _ in range(3)])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_board -v`
Expected: FAIL with `AttributeError: module 'widgets.board' has no attribute 'heatmap_color'`

- [ ] **Step 3: Write the implementation**

In `widgets/board.py`, change the datetime import line:

```python
from datetime import datetime, timezone
```

to:

```python
from datetime import date, datetime, timedelta, timezone
```

Add `HEATMAP_WEEKS = 12` right after the `REFRESH = 90` line, so the top constants block reads:

```python
REFRESH = 90
HEATMAP_WEEKS = 12
TICK_MS = 120
```

Add these two pure functions right after `review_color` (right before `class Store:`):

```python
HEATMAP_LEVELS = [(0, "heat0"), (2, "heat1"), (4, "heat2"), (7, "heat3")]


def heatmap_color(count):
    """'heat0'..'heat4' by commit-count thresholds (0 / 1-2 / 3-4 / 5-7 / 8+). Pure."""
    count = count or 0
    for threshold, name in HEATMAP_LEVELS:
        if count <= threshold:
            return name
    return "heat4"


def heatmap_grid(calendar, weeks=HEATMAP_WEEKS):
    """Group a flat [{date, count}] list into `weeks` columns of 7 rows (Sun..Sat, oldest
    week first). "Today" is inferred as the most recent date present in `calendar` (so
    this is pure — no wall-clock dependency, fully testable with a fixed fixture). A cell
    is None where no entry exists for that date. Uses each entry's own weekday, so it's
    correct no matter how many extra padding days the source included."""
    if not calendar:
        return [[None] * 7 for _ in range(weeks)]
    by_date = {d["date"]: d["count"] for d in calendar}
    today = date.fromisoformat(max(by_date))
    days_since_sunday = (today.weekday() + 1) % 7  # Mon=0..Sun=6 -> Sun=0..Sat=6
    week_end = today + timedelta(days=6 - days_since_sunday)  # this week's Saturday
    grid = []
    for w in range(weeks):
        col_end = week_end - timedelta(days=7 * (weeks - 1 - w))
        col = [by_date.get((col_end - timedelta(days=6 - d)).isoformat()) for d in range(7)]
        grid.append(col)
    return grid
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_board -v`
Expected: PASS (all tests, including the 4 new ones)

- [ ] **Step 5: Commit**

```bash
cd ~/Personal/codepit
git add widgets/board.py tests/test_board.py
git commit -m "Add heatmap_grid()/heatmap_color() pure functions to board.py"
```

---

### Task 4: Wire the Heatmap card into `board.py`'s Store/worker/curses loop

**Files:**
- Modify: `widgets/board.py`
- Modify: `lib/theme.py`

**Interfaces:**
- Consumes: `heatmap_github.fetch_calendar(weeks)`, `demo.heatmap()`, `board.heatmap_grid()`, `board.heatmap_color()` (all from Tasks 1-3).
- Produces: a "Heatmap" card visible in the board pane when `config.panel_enabled(cfg, "heatmap")`.

This task has no new pure logic to unit-test (it's wiring + curses drawing, same coverage boundary as the rest of `run()`/`_worker()`), so verification is a manual smoke test instead of a new automated test — same as how the existing Claude Usage/Tickets/PRs cards are verified.

- [ ] **Step 1: Add the five heatmap colors to the theme**

In `lib/theme.py`, change the `COLORS` dict from:

```python
COLORS = {
    "blue": 111,
    "green": 150,
    "yellow": 179,
    "red": 210,
    "purple": 141,
    "cyan": 117,
    "orange": 215,
    "text": 189,
    "dim": 60,
    "bg": 235,
}
```

to:

```python
COLORS = {
    "blue": 111,
    "green": 150,
    "yellow": 179,
    "red": 210,
    "purple": 141,
    "cyan": 117,
    "orange": 215,
    "text": 189,
    "dim": 60,
    "bg": 235,
    "heat0": 237,
    "heat1": 22,
    "heat2": 28,
    "heat3": 34,
    "heat4": 40,
}
```

No other change needed in `theme.py` — `board.py`'s `_init_pairs()` already iterates every key in `theme.COLORS`, so `text("heat0")`..`text("heat4")` become usable automatically.

- [ ] **Step 2: Add the `heatmap_github` import**

In `widgets/board.py`, change:

```python
from lib import config  # noqa: E402
from lib import tickets  # noqa: E402
from lib import prs as prs_source  # noqa: E402
from lib import claude_usage  # noqa: E402
from lib import theme  # noqa: E402
```

to:

```python
from lib import config  # noqa: E402
from lib import heatmap_github  # noqa: E402
from lib import tickets  # noqa: E402
from lib import prs as prs_source  # noqa: E402
from lib import claude_usage  # noqa: E402
from lib import theme  # noqa: E402
```

- [ ] **Step 3: Add heatmap fields to `Store`**

Change:

```python
class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.issues = []
        self.prs = []
        self.usage = None
        self.usage_error = None
        self.error = None
        self.last_updated = None
        self.loading = False
```

to:

```python
class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.issues = []
        self.prs = []
        self.usage = None
        self.usage_error = None
        self.heatmap = []
        self.heatmap_error = None
        self.error = None
        self.last_updated = None
        self.loading = False
```

- [ ] **Step 4: Fetch the heatmap in `_worker()`**

Change:

```python
def _worker(store, cfg):
    issues, prs, err = [], [], None
    usage, usage_err = None, None
    try:
        if cfg.get("demo"):
            from lib import demo
            issues = demo.issues() if config.panel_enabled(cfg, "tickets") else []
            prs = demo.prs() if config.panel_enabled(cfg, "prs") else []
            usage = demo.usage() if config.panel_enabled(cfg, "claude") else None
        else:
            if config.panel_enabled(cfg, "tickets"):
                try:
                    issues = tickets.fetch_issues(cfg.get("tickets"))
                except Exception as exc:
                    err = str(exc)
            if config.panel_enabled(cfg, "prs"):
                try:
                    prs = prs_source.fetch(cfg.get("prs"))
                except Exception as exc:
                    err = err or str(exc)
            if config.panel_enabled(cfg, "claude"):
                try:
                    usage = claude_usage.fetch_usage()
                except Exception as exc:
                    usage_err = str(exc)
    finally:
        with store.lock:
            store.issues = issues
            store.prs = prs
            store.usage = usage
            store.usage_error = usage_err
            store.error = err
            store.last_updated = datetime.now()
            store.loading = False
```

to:

```python
def _worker(store, cfg):
    issues, prs, err = [], [], None
    usage, usage_err = None, None
    heatmap, heatmap_err = [], None
    try:
        if cfg.get("demo"):
            from lib import demo
            issues = demo.issues() if config.panel_enabled(cfg, "tickets") else []
            prs = demo.prs() if config.panel_enabled(cfg, "prs") else []
            usage = demo.usage() if config.panel_enabled(cfg, "claude") else None
            heatmap = demo.heatmap() if config.panel_enabled(cfg, "heatmap") else []
        else:
            if config.panel_enabled(cfg, "tickets"):
                try:
                    issues = tickets.fetch_issues(cfg.get("tickets"))
                except Exception as exc:
                    err = str(exc)
            if config.panel_enabled(cfg, "prs"):
                try:
                    prs = prs_source.fetch(cfg.get("prs"))
                except Exception as exc:
                    err = err or str(exc)
            if config.panel_enabled(cfg, "claude"):
                try:
                    usage = claude_usage.fetch_usage()
                except Exception as exc:
                    usage_err = str(exc)
            if config.panel_enabled(cfg, "heatmap"):
                try:
                    heatmap = heatmap_github.fetch_calendar(weeks=HEATMAP_WEEKS)
                except Exception as exc:
                    heatmap_err = str(exc)
    finally:
        with store.lock:
            store.issues = issues
            store.prs = prs
            store.usage = usage
            store.usage_error = usage_err
            store.heatmap = heatmap
            store.heatmap_error = heatmap_err
            store.error = err
            store.last_updated = datetime.now()
            store.loading = False
```

- [ ] **Step 5: Add `show_heatmap` and read the store fields in `run()`**

Change:

```python
    cfg = config.load()
    show_claude = config.panel_enabled(cfg, "claude")
    show_tickets = config.panel_enabled(cfg, "tickets")
    show_prs = config.panel_enabled(cfg, "prs")
```

to:

```python
    cfg = config.load()
    show_claude = config.panel_enabled(cfg, "claude")
    show_tickets = config.panel_enabled(cfg, "tickets")
    show_prs = config.panel_enabled(cfg, "prs")
    show_heatmap = config.panel_enabled(cfg, "heatmap")
```

Change:

```python
        with store.lock:
            issues = list(store.issues)
            prs = list(store.prs)
            usage = store.usage
            usage_error = store.usage_error
            error = store.error
            loading = store.loading
            updated = store.last_updated
```

to:

```python
        with store.lock:
            issues = list(store.issues)
            prs = list(store.prs)
            usage = store.usage
            usage_error = store.usage_error
            heatmap = list(store.heatmap)
            heatmap_error = store.heatmap_error
            error = store.error
            loading = store.loading
            updated = store.last_updated
```

- [ ] **Step 6: Draw the Heatmap card**

Change:

```python
            box(box_top, row, "Claude Usage" + (f" · {plan}" if plan else ""), "cyan")
            row += 1

        # TICKETS: a "By Status" box then a "Tickets" list box (with a row cursor)
        if show_tickets:
```

to:

```python
            box(box_top, row, "Claude Usage" + (f" · {plan}" if plan else ""), "cyan")
            row += 1

        # GIT HEATMAP
        if show_heatmap:
            box_top = row
            row += 1
            total = None
            if heatmap_error:
                putin(row, 2, f"⚠ {heatmap_error}", text("red"))
                row += 1
            else:
                grid = heatmap_grid(heatmap, weeks=HEATMAP_WEEKS)
                total = sum(c for col in grid for c in col if c)
                for w, col in enumerate(grid):
                    for d, count in enumerate(col):
                        putin(row + d, 2 + w * 3, "██", text(heatmap_color(count)))
                row += 7
            box(box_top, row, "Heatmap", "green", total)
            row += 1

        # TICKETS: a "By Status" box then a "Tickets" list box (with a row cursor)
        if show_tickets:
```

- [ ] **Step 7: Manual smoke test — demo mode, no crash, card visible**

The card isn't behind a panel toggle in `config.demo.json` yet (that's Task 5), so temporarily point at a config with `heatmap` on to check the rendering:

```bash
cd ~/Personal/codepit
python3 -c "
import json
cfg = json.load(open('config.demo.json'))
cfg['panels'] = ['clock', 'claude', 'tickets', 'prs', 'heatmap']
json.dump(cfg, open('/tmp/codepit-heatmap-check.json', 'w'))
"
tmux kill-session -t heatmapcheck 2>/dev/null
tmux new-session -d -s heatmapcheck -x 100 -y 45 \
  "CODEPIT_CONFIG=/tmp/codepit-heatmap-check.json python3 widgets/board.py"
sleep 1.5
tmux capture-pane -t heatmapcheck -p
tmux kill-session -t heatmapcheck
rm /tmp/codepit-heatmap-check.json
```

Expected: no traceback; a box titled `Heatmap` with a count in the top-right, followed by 12 columns x 7 rows of `██` blocks, appears above "By Status".

- [ ] **Step 8: Run the full test suite (regression check)**

Run: `cd ~/Personal/codepit && python3 -m unittest discover -s tests -t . -v 2>&1 | tail -5`
Expected: `OK`, all tests still passing.

- [ ] **Step 9: Commit**

```bash
cd ~/Personal/codepit
git add widgets/board.py lib/theme.py
git commit -m "Wire the Heatmap card into board.py's Store/worker/curses loop"
```

---

### Task 5: Turn on the `heatmap` panel toggle

**Files:**
- Modify: `lib/config.py`
- Modify: `setup.py`
- Modify: `tests/test_config.py`

**Interfaces:**
- Consumes: `config.PANELS`, `config.board_enabled()` (existing).
- Produces: `"heatmap"` is now a real, toggleable panel name end-to-end (setup prompt -> config.json -> board.py card).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py` (inside `TestConfig`, after `test_panel_and_board_enabled`):

```python
    def test_heatmap_is_a_board_card(self):
        self.assertTrue(config.board_enabled({"panels": ["heatmap"]}))
        self.assertTrue(config.panel_enabled({"panels": ["heatmap"]}, "heatmap"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_config -v`
Expected: FAIL — `board_enabled({"panels": ["heatmap"]})` is `False` (heatmap isn't in the tuple yet).

- [ ] **Step 3: Write the implementation**

In `lib/config.py`, change:

```python
PANELS = ["clock", "claude", "tickets", "prs"]
```

to:

```python
PANELS = ["clock", "claude", "tickets", "prs", "heatmap"]
```

Change:

```python
def board_enabled(cfg):
    """The board pane exists if any of its cards (claude/tickets/prs) is on."""
    return any(panel_enabled(cfg, p) for p in ("claude", "tickets", "prs"))
```

to:

```python
def board_enabled(cfg):
    """The board pane exists if any of its cards (claude/tickets/prs/heatmap) is on."""
    return any(panel_enabled(cfg, p) for p in ("claude", "tickets", "prs", "heatmap"))
```

In `setup.py`, change:

```python
def ask_panels():
    print("Available panels: clock, claude, tickets, prs")
```

to:

```python
def ask_panels():
    print("Available panels: clock, claude, tickets, prs, heatmap")
```

Also add `"heatmap"` to `config.demo.json` so the demo/screenshot flow shows it. Change the file's contents from:

```json
{
  "demo": true,
  "panels": ["clock", "claude", "tickets", "prs"]
}
```

to:

```json
{
  "demo": true,
  "panels": ["clock", "claude", "tickets", "prs", "heatmap"]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_config -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run the full suite + a demo smoke test through the real `config.demo.json`**

```bash
cd ~/Personal/codepit
python3 -m unittest discover -s tests -t . -v 2>&1 | tail -5
tmux kill-session -t heatmapcheck2 2>/dev/null
tmux new-session -d -s heatmapcheck2 -x 100 -y 45 \
  "CODEPIT_CONFIG=config.demo.json python3 widgets/board.py"
sleep 1.5
tmux capture-pane -t heatmapcheck2 -p
tmux kill-session -t heatmapcheck2
```

Expected: `OK` on the test suite; the Heatmap card visible in the capture, same as Task 4's check but now via the real demo config (no more temp file needed).

- [ ] **Step 6: Commit**

```bash
cd ~/Personal/codepit
git add lib/config.py setup.py config.demo.json tests/test_config.py
git commit -m "Turn on the heatmap panel toggle end-to-end"
```

---

### Task 6: `lib/pet_state.py` — identity, mood, streak

**Files:**
- Create: `lib/pet_state.py`
- Test: `tests/test_pet_state.py`

**Interfaces:**
- Produces: `pet_state.load(path=None) -> {"name": str, "created_at": str}`. Creates the file with today's date on first call.
- Produces: `pet_state.save(state, path=None)`.
- Produces: `pet_state.mood(commits_today: int, claude_pct_5h: float) -> "happy"|"thinking"|"hungry"`, pure.
- Produces: `pet_state.streak_from_calendar(calendar: list, today: str) -> int`, pure. `calendar` is the same `[{date, count}]` shape `heatmap_github.fetch_calendar()` returns; `today` is an ISO date string.

- [ ] **Step 1: Write the failing test**

Create `tests/test_pet_state.py`:

```python
import json
import os
import tempfile
import unittest
from lib import pet_state


class TestPetState(unittest.TestCase):
    def test_load_defaults_on_missing_file(self):
        path = tempfile.mktemp(suffix=".json")
        try:
            state = pet_state.load(path)
            self.assertEqual(state["name"], "Bit")
            self.assertTrue(state["created_at"])
            self.assertTrue(os.path.exists(path))  # persisted for next time
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_load_reads_existing_state(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"name": "Rex", "created_at": "2026-01-01"}, f)
            path = f.name
        try:
            state = pet_state.load(path)
            self.assertEqual(state["name"], "Rex")
            self.assertEqual(state["created_at"], "2026-01-01")
        finally:
            os.unlink(path)

    def test_mood_happy_when_committed_today(self):
        self.assertEqual(pet_state.mood(commits_today=2, claude_pct_5h=0), "happy")

    def test_mood_thinking_when_no_commit_but_claude_used(self):
        self.assertEqual(pet_state.mood(commits_today=0, claude_pct_5h=15), "thinking")

    def test_mood_hungry_when_no_activity(self):
        self.assertEqual(pet_state.mood(commits_today=0, claude_pct_5h=0), "hungry")

    def test_streak_counts_consecutive_days_ending_today(self):
        calendar = [
            {"date": "2026-07-28", "count": 1},
            {"date": "2026-07-29", "count": 2},
            {"date": "2026-07-30", "count": 1},
        ]
        self.assertEqual(pet_state.streak_from_calendar(calendar, "2026-07-30"), 3)

    def test_streak_ignores_todays_zero_and_uses_yesterday(self):
        calendar = [
            {"date": "2026-07-29", "count": 1},
            {"date": "2026-07-30", "count": 0},  # today, no commit yet
        ]
        self.assertEqual(pet_state.streak_from_calendar(calendar, "2026-07-30"), 1)

    def test_streak_zero_when_yesterday_also_empty(self):
        calendar = [
            {"date": "2026-07-29", "count": 0},
            {"date": "2026-07-30", "count": 0},
        ]
        self.assertEqual(pet_state.streak_from_calendar(calendar, "2026-07-30"), 0)

    def test_streak_missing_dates_treated_as_zero(self):
        self.assertEqual(pet_state.streak_from_calendar([], "2026-07-30"), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_pet_state -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.pet_state'`

- [ ] **Step 3: Write the implementation**

Create `lib/pet_state.py`:

```python
"""Local pet identity: name + creation date. Persisted at pet_state.json (repo root),
gitignored — same treatment as config.json (per-user, never committed). Mood and streak
are NOT stored here: they're derived fresh every refresh from live activity data (see
mood() and streak_from_calendar() below), because "today" is always still in progress —
a stored streak counter would get zeroed by a morning check before you've committed yet."""
import json
import os
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "pet_state.json")

DEFAULTS = {"name": "Bit", "created_at": None}


def load(path=None):
    """{"name", "created_at"}. Creates the file with today's date on first run.
    Never raises."""
    path = path or STATE_PATH
    state = dict(DEFAULTS)
    try:
        with open(path) as f:
            state.update(json.load(f))
    except (OSError, ValueError):
        state["created_at"] = date.today().isoformat()
        save(state, path)
    return state


def save(state, path=None):
    with open(path or STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def mood(commits_today, claude_pct_5h):
    """'happy' | 'thinking' | 'hungry', from today's dev activity. Pure."""
    if commits_today > 0:
        return "happy"
    if claude_pct_5h > 0:
        return "thinking"
    return "hungry"


def streak_from_calendar(calendar, today):
    """Consecutive days with >=1 commit, walking back from `today` (or the last fully-
    elapsed day if today has no commits yet, since today's count is still provisional and
    must not zero out an otherwise-live streak). `calendar` is [{date, count}]; `today` is
    an ISO date string. Pure."""
    by_date = {d["date"]: d["count"] for d in calendar}
    day = date.fromisoformat(today)
    if by_date.get(today, 0) == 0:
        day -= timedelta(days=1)
    streak = 0
    while by_date.get(day.isoformat(), 0) > 0:
        streak += 1
        day -= timedelta(days=1)
    return streak
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_pet_state -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Personal/codepit
git add lib/pet_state.py tests/test_pet_state.py
git commit -m "Add lib/pet_state.py: identity persistence + pure mood/streak logic"
```

---

### Task 7: `lib/demo.py` — fake pet data

**Files:**
- Modify: `lib/demo.py`
- Modify: `tests/test_demo.py`

**Interfaces:**
- Produces: `demo.pet() -> {"name": str, "mood": "happy"|"thinking"|"hungry", "streak": int}`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_demo.py` (inside `TestDemo`, after `test_heatmap_shape`):

```python
    def test_pet_shape(self):
        p = demo.pet()
        self.assertEqual(set(p), {"name", "mood", "streak"})
        self.assertIn(p["mood"], ("happy", "thinking", "hungry"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_demo -v`
Expected: FAIL with `AttributeError: module 'lib.demo' has no attribute 'pet'`

- [ ] **Step 3: Write the implementation**

Add to `lib/demo.py`, at the end of the file, after `heatmap()`:

```python
def pet():
    """Fake pet display data — no randomness, same every time."""
    return {"name": "Bit", "mood": "happy", "streak": 5}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_demo -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Personal/codepit
git add lib/demo.py tests/test_demo.py
git commit -m "Add demo.pet() fake pet display data"
```

---

### Task 8: `widgets/pet.py` — the standalone pet widget

**Files:**
- Create: `widgets/pet.py`

**Interfaces:**
- Consumes: `pet_state.load()`, `pet_state.mood()`, `pet_state.streak_from_calendar()`, `heatmap_github.fetch_calendar()`, `claude_usage.fetch_usage()`, `demo.pet()`, `config.load()`, `theme.COLORS`.
- Produces: a runnable widget (`python3 widgets/pet.py`), same invocation shape as `widgets/clock.py`.

No new pure logic lives in this file (mood/streak are already tested in `lib/pet_state.py`); verification here is a manual smoke test, matching the coverage boundary the rest of the curses widgets already use.

- [ ] **Step 1: Write the implementation**

Create `widgets/pet.py`:

```python
#!/usr/bin/env python3
"""Terminal pet — ASCII companion whose mood reflects today's dev activity (commits +
Claude usage). Standalone curses widget with its own Zellij pane (same shape as
clock.py), but fetches over the network like board.py, so it runs its own small
background worker thread instead of computing everything inline."""
import curses
import os
import sys
import threading
import time
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from lib import claude_usage  # noqa: E402
from lib import config  # noqa: E402
from lib import heatmap_github  # noqa: E402
from lib import pet_state  # noqa: E402
from lib import theme  # noqa: E402

REFRESH = 90
TICK_MS = 1000

FRAMES = {
    "happy":    [" ∩___∩ ", "( ^‿^ )", " ‾‾‾‾‾ "],
    "thinking": [" ∩___∩ ", "( ·_· )", " ‾‾‾‾‾ "],
    "hungry":   [" ∩___∩ ", "( ;_; )", " ‾‾‾‾‾ "],
    "unknown":  [" ∩___∩ ", "( ?_? )", " ‾‾‾‾‾ "],
}
MOOD_COLOR = {"happy": "green", "thinking": "cyan", "hungry": "orange", "unknown": "dim"}


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.name = pet_state.load()["name"]
        self.mood = "unknown"
        self.streak = 0
        self.error = None


def _worker(store, cfg):
    mood, streak, err = "unknown", 0, None
    try:
        if cfg.get("demo"):
            from lib import demo
            fake = demo.pet()
            mood, streak = fake["mood"], fake["streak"]
        else:
            calendar = heatmap_github.fetch_calendar(weeks=2)
            today = date.today().isoformat()
            commits_today = next((d["count"] for d in calendar if d["date"] == today), 0)
            usage = {}
            try:
                usage = claude_usage.fetch_usage()
            except Exception:
                pass
            claude_pct = (usage.get("five_hour") or {}).get("pct", 0) or 0
            mood = pet_state.mood(commits_today, claude_pct)
            streak = pet_state.streak_from_calendar(calendar, today)
    except Exception as exc:
        err = str(exc)
    with store.lock:
        store.mood = mood
        store.streak = streak
        store.error = err


def start_refresh(store, cfg):
    threading.Thread(target=_worker, args=(store, cfg), daemon=True).start()


def _init_pairs():
    curses.start_color()
    curses.use_default_colors()
    pairs = {}
    pid = 1
    for name in ("green", "cyan", "orange", "dim", "red"):
        idx = theme.COLORS[name]
        curses.init_pair(pid, idx, -1)
        pairs[name] = pid
        pid += 1
    return pairs


def _draw(stdscr, pairs, store):
    stdscr.erase()
    maxy, maxx = stdscr.getmaxyx()
    with store.lock:
        name, mood, streak, error = store.name, store.mood, store.streak, store.error

    frame = FRAMES.get(mood, FRAMES["unknown"])
    attr = curses.color_pair(pairs[MOOD_COLOR.get(mood, "dim")]) | curses.A_BOLD

    rows = [(line, attr) for line in frame]
    rows.append((f"{name} · streak {streak}", curses.color_pair(pairs["dim"])))
    if error:
        rows.append((f"⚠ {error}", curses.color_pair(pairs["red"])))

    top = max(0, (maxy - len(rows)) // 2)
    for i, (s, row_attr) in enumerate(rows):
        y = top + i
        if 0 <= y < maxy:
            x = max(0, (maxx - len(s)) // 2)
            try:
                stdscr.addnstr(y, x, s, max(0, maxx - x - 1), row_attr)
            except curses.error:
                pass
    stdscr.refresh()


def run(stdscr):
    curses.curs_set(0)
    pairs = _init_pairs()
    stdscr.timeout(TICK_MS)
    cfg = config.load()
    store = Store()
    start_refresh(store, cfg)
    last = time.monotonic()
    while True:
        _draw(stdscr, pairs, store)
        if stdscr.getch() == ord("q"):
            break
        if time.monotonic() - last >= REFRESH:
            start_refresh(store, cfg)
            last = time.monotonic()


def main():
    curses.wrapper(run)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manual smoke test — demo mode, no crash, pet visible**

```bash
cd ~/Personal/codepit
tmux kill-session -t petcheck 2>/dev/null
tmux new-session -d -s petcheck -x 40 -y 12 \
  "CODEPIT_CONFIG=config.demo.json python3 widgets/pet.py"
sleep 1.5
tmux capture-pane -t petcheck -p
tmux kill-session -t petcheck
```

Expected: no traceback; a small ASCII face is centered, with `Bit · streak 5` underneath (the demo values from `demo.pet()`).

- [ ] **Step 3: Manual smoke test — real mode doesn't crash even without network**

This exercises the non-demo path's error handling (Step 1's `except Exception as exc: err = str(exc)` in `_worker`):

```bash
cd ~/Personal/codepit
tmux kill-session -t petcheck2 2>/dev/null
tmux new-session -d -s petcheck2 -x 40 -y 12 "python3 widgets/pet.py"
sleep 1.5
tmux capture-pane -t petcheck2 -p
tmux kill-session -t petcheck2
```

Expected: no traceback; the `unknown` "( ?_? )" frame while the first fetch is in flight, settling into a real mood (or a `⚠ <message>` line) once the worker thread finishes — never a crash regardless of network/`gh` state.

- [ ] **Step 4: Commit**

```bash
cd ~/Personal/codepit
git add widgets/pet.py
git commit -m "Add widgets/pet.py: standalone ASCII pet widget"
```

---

### Task 9: Turn on the `pet` panel toggle + layout + gitignore

**Files:**
- Modify: `lib/config.py`
- Modify: `setup.py`
- Modify: `.gitignore`
- Modify: `tests/test_config.py`

**Interfaces:**
- Consumes: `config.build_layout()`, `config._pane()` (existing).
- Produces: `"pet"` is a real, toggleable panel name end-to-end; enabling it puts a "Pet" pane next to "Clock" in the generated Zellij layout.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py` (inside `TestConfig`, after `test_heatmap_is_a_board_card`):

```python
    def test_build_layout_pet_toggle(self):
        with_pet = config.build_layout({"panels": ["pet"]}, "/x")
        self.assertIn("Pet", with_pet)
        no_pet = config.build_layout({"panels": ["clock"]}, "/x")
        self.assertNotIn("Pet", no_pet)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_config -v`
Expected: FAIL — `"Pet"` not in the generated layout string.

- [ ] **Step 3: Write the implementation**

In `lib/config.py`, change:

```python
PANELS = ["clock", "claude", "tickets", "prs", "heatmap"]
```

to:

```python
PANELS = ["clock", "claude", "tickets", "prs", "heatmap", "pet"]
```

Change `build_layout()` from:

```python
def build_layout(cfg, root):
    """Generate the Zellij layout (KDL) honoring which panels are enabled. Pure.

    Structure: a full-width content region on top and a single-line Shortcuts bar
    at the very bottom. The content is left column (clock + one shell) + the board."""
    src = f'source {root}/.env 2>/dev/null; exec '
    clock = _pane("Clock", f"{src}python3 {root}/widgets/clock.py", size='"20%"')
    shell = ('pane focus=true command="bash" {\n'
             '    args "-lc" "cd $HOME; claude; exec bash -i"\n'
             '}')
    shortcuts = _pane("Shortcuts", f"exec python3 {root}/widgets/cheatsheet.py", size="1")

    left_children = ([clock] if panel_enabled(cfg, "clock") else []) + [shell]
    left_body = "\n".join(left_children)
```

to:

```python
def build_layout(cfg, root):
    """Generate the Zellij layout (KDL) honoring which panels are enabled. Pure.

    Structure: a full-width content region on top and a single-line Shortcuts bar
    at the very bottom. The content is left column (clock + pet + one shell) + the
    board."""
    src = f'source {root}/.env 2>/dev/null; exec '
    clock = _pane("Clock", f"{src}python3 {root}/widgets/clock.py", size='"20%"')
    pet = _pane("Pet", f"{src}python3 {root}/widgets/pet.py", size='"20%"')
    shell = ('pane focus=true command="bash" {\n'
             '    args "-lc" "cd $HOME; claude; exec bash -i"\n'
             '}')
    shortcuts = _pane("Shortcuts", f"exec python3 {root}/widgets/cheatsheet.py", size="1")

    left_children = (
        ([clock] if panel_enabled(cfg, "clock") else [])
        + ([pet] if panel_enabled(cfg, "pet") else [])
        + [shell]
    )
    left_body = "\n".join(left_children)
```

(the rest of `build_layout` — the `if board_enabled(cfg):` block onward — is unchanged)

In `setup.py`, change:

```python
def ask_panels():
    print("Available panels: clock, claude, tickets, prs, heatmap")
```

to:

```python
def ask_panels():
    print("Available panels: clock, claude, tickets, prs, heatmap, pet")
```

In `.gitignore`, change:

```
# Secrets — never commit
.env

# Per-user config (written by setup.py)
config.json

# Python
__pycache__/
*.pyc
```

to:

```
# Secrets — never commit
.env

# Per-user config (written by setup.py)
config.json

# Per-user pet identity (written on first run of widgets/pet.py)
pet_state.json

# Python
__pycache__/
*.pyc
```

Also add `"pet"` to `config.demo.json`. Change:

```json
{
  "demo": true,
  "panels": ["clock", "claude", "tickets", "prs", "heatmap"]
}
```

to:

```json
{
  "demo": true,
  "panels": ["clock", "claude", "tickets", "prs", "heatmap", "pet"]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_config -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Personal/codepit
git add lib/config.py setup.py .gitignore config.demo.json tests/test_config.py
git commit -m "Turn on the pet panel toggle end-to-end"
```

---

### Task 10: README + full-suite regression + combined smoke test

**Files:**
- Modify: `README.md`

**Interfaces:** none (documentation + verification only).

- [ ] **Step 1: Update the Panels list in README.md**

Change:

```markdown
## Panels (toggle any of them at setup)

- **clock** — big block-font clock, date, and the Brazilian national holiday of the day.
- **claude** — your 5h / 7d / per-model Claude usage bars, read from the local Claude Code credentials.
- **tickets** — your open tickets, filterable by status with clickable chips and scroll.
- **prs** — open PRs where you're author *or* reviewer, with review/CI status badges.
```

to:

```markdown
## Panels (toggle any of them at setup)

- **clock** — big block-font clock, date, and the Brazilian national holiday of the day.
- **claude** — your 5h / 7d / per-model Claude usage bars, read from the local Claude Code credentials.
- **tickets** — your open tickets, filterable by status with clickable chips and scroll.
- **prs** — open PRs where you're author *or* reviewer, with review/CI status badges.
- **heatmap** — a GitHub-contributions-style grid of your last 12 weeks of commits.
- **pet** — an ASCII companion whose mood reflects today's commits + Claude usage.

`heatmap` and `pet` always use GitHub (via `gh`) — there's no source to pick for them,
unlike `tickets`/`prs` below.
```

- [ ] **Step 2: Run the full test suite**

Run: `cd ~/Personal/codepit && python3 -m unittest discover -s tests -t . -v 2>&1 | tail -10`
Expected: `OK`, all tests passing (should be 76 existing + 2 heatmap_github + 1 demo.heatmap + 4 board heatmap + 1 config heatmap + 8 pet_state + 1 demo.pet + 1 config pet = 94 tests).

- [ ] **Step 3: Combined manual smoke test — full demo layout, both new panels together**

```bash
cd ~/Personal/codepit
export PATH="$HOME/.local/bin:$PATH"
tmux kill-session -t fulldemo 2>/dev/null
tmux new-session -d -s fulldemo -x 160 -y 50 \
  "CODEPIT_CONFIG=config.demo.json zellij --layout codepit"
sleep 3
tmux capture-pane -t fulldemo -p
tmux kill-session -t fulldemo
```

Expected: no crash; the Clock, Pet, Board (with Heatmap/Claude Usage/Tickets/Pull Requests cards), and Shortcuts panes all render. If `zellij --layout codepit` fails because the layout file wasn't regenerated for this repo checkout, run `python3 setup.py` first (answer `all` at the panels prompt) to regenerate `~/.config/zellij/layouts/codepit.kdl`, then retry.

- [ ] **Step 4: Regenerate the screenshot (optional but recommended, since the layout changed)**

The existing `screenshot.png` in the README predates these two panels. If you want it to reflect the new layout, follow the same `vhs` process used for the original screenshot: run `CODEPIT_CONFIG=config.demo.json cpit` (or the `board.py` demo command) in a `vhs` tape with `Screenshot`, save over `screenshot.png` at the repo root. This step has no pass/fail — it's a visual refresh, do it if you want the README image current.

- [ ] **Step 5: Commit**

```bash
cd ~/Personal/codepit
git add README.md
git commit -m "Document the heatmap and pet panels in README"
```

---

## Self-Review

**Spec coverage:**
- Heatmap data source (GraphQL via `gh`) → Task 1. ✓
- Heatmap as a board card, 12-week grid, 5-color scale, count in title → Tasks 3-4. ✓
- Heatmap panel toggle (no source sub-question) → Task 5. ✓
- Pet state persistence (`pet_state.json`, gitignored, `name` field for future customization) → Task 6, `.gitignore` in Task 9. ✓
- Pet mood rule (commits/Claude usage table) → Task 6. ✓
- Pet streak → Task 6 (redesigned as computed, not stored — see the deviation note above the task list). ✓
- Pet as standalone pane next to Clock → Task 8 (widget) + Task 9 (layout). ✓
- Pet static single-frame-per-mood rendering, `ponytail:` note for the deferred idle-blink animation → Task 8 (the "no multi-frame animation" choice is implicit in `FRAMES` being one frame per mood; a `ponytail:` comment noting the deferred animation was in the spec's prose, not code — not re-added as a code comment since there's no animation-adjacent code to anchor it to yet). Flagging this as a minor spec-vs-plan gap: **not fixed inline** since it's a no-op (there's nothing to comment on until someone builds the animation), but worth knowing if a future reader expects to find the `ponytail:` marker literally in `pet.py`.
- Error handling (heatmap card shows `⚠`, pet shows `unknown` + `⚠`, no crash) → Tasks 4 and 8. ✓
- Demo mode never touches `gh`/Claude credentials → Tasks 2, 4, 7, 8 (demo branches use `demo.heatmap()`/`demo.pet()` exclusively). ✓
- Tests: `test_heatmap_github.py`, `test_pet_state.py`, `test_board.py` additions, `test_config.py` additions, `test_demo.py` additions → Tasks 1, 2, 3, 5, 6, 7, 9. ✓
- Out of scope (customization panel, multi-frame animation, full-year heatmap) → correctly not built in any task. ✓

**Placeholder scan:** no "TBD"/"TODO"/"add error handling" style placeholders — every step has complete, runnable code.

**Type consistency check:**
- `heatmap_github.fetch_calendar()` / `parse_calendar()` return shape `[{"date": str, "count": int}]` — used identically in `board.heatmap_grid()` (Task 3), `demo.heatmap()` (Task 2), and `pet.py`'s worker (Task 8). Consistent throughout.
- `pet_state.mood(commits_today, claude_pct_5h)` signature matches its two call sites: the test in Task 6 and `widgets/pet.py`'s `_worker()` in Task 8 (`pet_state.mood(commits_today, claude_pct)`). Consistent.
- `pet_state.streak_from_calendar(calendar, today)` signature matches Task 6's tests and Task 8's `_worker()` call (`pet_state.streak_from_calendar(calendar, today)`). Consistent.
- `demo.pet()` shape `{"name", "mood", "streak"}` matches exactly what Task 8's `_worker()` demo branch unpacks (`fake["mood"]`, `fake["streak"]`) — `fake["name"]` is intentionally unused there since `Store.__init__` already sets `self.name` from `pet_state.load()["name"]` once at startup, not from the demo fake, so the pet's name stays consistent whether or not demo mode is on. Consistent, not a bug.
- `board.heatmap_color()`/`heatmap_grid()` color names (`"heat0"`..`"heat4"`) match the keys added to `theme.COLORS` in Task 4 exactly. Consistent.
