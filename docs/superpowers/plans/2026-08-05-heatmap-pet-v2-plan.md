# Heatmap Labels + Walking Pet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Heatmap card readable (weekday/month labels) and turn the static Pet widget into one that walks side to side beside the Clock, blinking periodically.

**Architecture:** `heatmap_grid()` starts carrying each cell's real date (not just its count) so `board.py`'s render code can derive weekday/month labels from it. `lib/config.py`'s `build_layout()` nests Clock and Pet into a 50/50 side-by-side pair when both are enabled. `widgets/pet.py` gains three new pure functions (frame lookup, left/right mirroring, one walking step) driven by plain loop-local state in `run()` — mirroring how `board.py` already keeps its own UI-only state (`spin`, `scroll`, `sel`) outside the network-backed `Store`.

**Tech Stack:** Python 3 standard library only (`curses`, `datetime`), `unittest`.

## Global Constraints

- Python 3.8+, Linux only, zero pip dependencies — matches the rest of codepit.
- No comments in Portuguese; English only in code (Portuguese only appears in
  user-facing weekday abbreviations, which are content, not comments).
- No changes to `pet_state.mood()`, `pet_state.streak_from_calendar()`,
  `heatmap_github.fetch_calendar()`/`parse_calendar()`, or either widget's `_worker()` —
  this plan is presentation-only.
- Tests: plain `unittest`, no frameworks. Pure functions get unit tests; curses draw
  loops are verified by manual `tmux` smoke test, matching the existing project
  convention (see `tests/test_board.py`, `tests/test_clock.py` — only the pure helpers
  extracted from those widget files are tested, never the `run()`/`_draw()` loops
  themselves).

## Implementation note (read before Task 4)

The approved spec described the pet's new `x`/`facing`/`blink` fields as living on
`pet.py`'s `Store`. Task 4 below puts them as plain local variables in `run()` instead —
`board.py`'s own `Store` only ever holds fields the background worker thread writes
(`issues`, `prs`, `usage`, `heatmap`, `*_error`); its purely-UI state (`spin`, `scroll`,
`sel`, `row_sel`, …) lives as loop-local variables in `run()`, never in `Store`. Putting
`x`/`facing`/`blink` in `pet.py`'s `Store` — which the worker thread never touches —
would be the only field on that class not written by the worker, and would force every
read of it through a lock that serves no purpose there. Local variables are simpler, need
no lock, and match the codebase's own established split. This is a pure
implementation-detail refinement of the spec's stated intent (ephemeral, resets on
launch) — it does not change any observable behavior.

---

### Task 1: `heatmap_grid()` date-tuple cells + weekday/month label functions

**Files:**
- Modify: `widgets/board.py`
- Modify: `tests/test_board.py`

**Interfaces:**
- Produces: `board.heatmap_grid(calendar, weeks=HEATMAP_WEEKS)` — same shape as today
  (`weeks` columns x 7 rows), but each cell is now `(date: str, count: int|None)`,
  except when `calendar` is empty, where every cell stays plain `None` (no anchor date
  exists to compute anything from).
- Produces: `board.WEEKDAY_LABELS` — list of 7 strings (`""` or a 3-letter Portuguese
  abbreviation), indexed Sun=0..Sat=6.
- Produces: `board.heatmap_month_labels(grid) -> {week_index: "Mon"}`, pure.
- Produces: `board.HEATMAP_COL0 = 6` (module constant: x-offset where the grid itself
  starts, after the weekday-label column).

- [ ] **Step 1: Write the failing tests**

In `tests/test_board.py`, replace the three existing heatmap-grid tests:

```python
    def test_heatmap_grid_shape(self):
        grid = board.heatmap_grid([{"date": "2026-07-27", "count": 3}], weeks=2)
        self.assertEqual(len(grid), 2)
        self.assertTrue(all(len(col) == 7 for col in grid))
```

stays unchanged (shape doesn't change). Replace this one:

```python
    def test_heatmap_grid_places_count_on_right_weekday(self):
        # 2026-07-27 is a Monday -> row index 1 (Sun=0..Sat=6) of the last (only) column
        grid = board.heatmap_grid([{"date": "2026-07-27", "count": 3}], weeks=1)
        self.assertEqual(grid[0][1], 3)
        self.assertIsNone(grid[0][0])
```

with:

```python
    def test_heatmap_grid_places_count_on_right_weekday(self):
        # 2026-07-27 is a Monday -> row index 1 (Sun=0..Sat=6) of the last (only) column
        grid = board.heatmap_grid([{"date": "2026-07-27", "count": 3}], weeks=1)
        self.assertEqual(grid[0][1], ("2026-07-27", 3))
        self.assertEqual(grid[0][0], ("2026-07-26", None))
```

`test_heatmap_grid_empty_calendar` stays unchanged (empty calendar still returns bare
`None` cells). Add these two new tests after it:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_board -v`
Expected: FAIL — `test_heatmap_grid_places_count_on_right_weekday` fails (old shape
still returns bare ints), `test_heatmap_grid_dates_always_present_when_calendar_nonempty`
and the two `heatmap_month_labels` tests fail with `AttributeError`.

- [ ] **Step 3: Write the implementation**

In `widgets/board.py`, change `HEATMAP_WEEKS = 12` to also add the new column-offset
constant right after it:

```python
REFRESH = 90
HEATMAP_WEEKS = 12
HEATMAP_COL0 = 6  # x where the grid starts, after the weekday-label column
TICK_MS = 120
```

Change `heatmap_grid()` from:

```python
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

to:

```python
def heatmap_grid(calendar, weeks=HEATMAP_WEEKS):
    """Group a flat [{date, count}] list into `weeks` columns of 7 rows (Sun..Sat, oldest
    week first). "Today" is inferred as the most recent date present in `calendar` (so
    this is pure — no wall-clock dependency, fully testable with a fixed fixture). Each
    cell is a (date, count) tuple: date is the real calendar date for that grid position
    (always present), count is None where no entry exists for that date — except when
    `calendar` is empty, where there is no date to anchor "today" to at all and every
    cell is bare None. Uses each entry's own weekday, so it's correct no matter how many
    extra padding days the source included."""
    if not calendar:
        return [[None] * 7 for _ in range(weeks)]
    by_date = {d["date"]: d["count"] for d in calendar}
    today = date.fromisoformat(max(by_date))
    days_since_sunday = (today.weekday() + 1) % 7  # Mon=0..Sun=6 -> Sun=0..Sat=6
    week_end = today + timedelta(days=6 - days_since_sunday)  # this week's Saturday
    grid = []
    for w in range(weeks):
        col_end = week_end - timedelta(days=7 * (weeks - 1 - w))
        col = []
        for d in range(7):
            day = col_end - timedelta(days=6 - d)
            col.append((day.isoformat(), by_date.get(day.isoformat())))
        grid.append(col)
    return grid
```

Right after `heatmap_grid()`, add the label constants and function:

```python
WEEKDAY_LABELS = ["", "Seg", "", "Qua", "", "Sex", ""]  # Sun=0..Sat=6; Portuguese, 3-letter
MONTH_ABBR = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
              "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def heatmap_month_labels(grid):
    """{week_index: 'Mon'} for each column whose Sunday date starts a new month relative
    to the previous labeled column (column 0 is always labeled if it has a date). Pure."""
    labels = {}
    prev_month = None
    for w, col in enumerate(grid):
        cell = col[0]  # Sunday
        if not cell:
            continue
        date_str, _count = cell
        month = date_str[5:7]
        if month != prev_month:
            labels[w] = MONTH_ABBR[int(month) - 1]
            prev_month = month
    return labels
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_board -v`
Expected: PASS (all tests, including the new/updated ones)

- [ ] **Step 5: Commit**

```bash
cd ~/Personal/codepit
git add widgets/board.py tests/test_board.py
git commit -m "heatmap_grid() cells carry their date; add weekday/month label helpers"
```

---

### Task 2: Wire weekday/month labels into the Heatmap card's render

**Files:**
- Modify: `widgets/board.py`

**Interfaces:**
- Consumes: `heatmap_grid()`, `heatmap_month_labels()`, `WEEKDAY_LABELS`,
  `HEATMAP_COL0`, `heatmap_color()` (all from Task 1).
- Produces: the Heatmap card visibly shows weekday letters (Mon/Wed/Fri rows) and month
  abbreviations above the columns where a new month starts.

No new pure logic here — this is drawing-code wiring, same coverage boundary as the rest
of `run()`. Verified by manual smoke test.

- [ ] **Step 1: Update the Heatmap card's drawing block**

In `widgets/board.py`, change:

```python
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
```

to:

```python
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
                total = sum(cell[1] for col in grid for cell in col if cell and cell[1])
                for w, label in heatmap_month_labels(grid).items():
                    putin(row, HEATMAP_COL0 + w * 3, label, text("dim"))
                row += 1
                for d, wd_label in enumerate(WEEKDAY_LABELS):
                    if wd_label:
                        putin(row + d, 2, wd_label, text("dim"))
                for w, col in enumerate(grid):
                    for d, cell in enumerate(col):
                        count = cell[1] if cell else None
                        putin(row + d, HEATMAP_COL0 + w * 3, "██", text(heatmap_color(count)))
                row += 7
            box(box_top, row, "Heatmap", "green", total)
            row += 1
```

- [ ] **Step 2: Manual smoke test — demo mode, labels visible, no crash**

```bash
cd ~/Personal/codepit
tmux kill-session -t heatmaplabels 2>/dev/null
tmux new-session -d -s heatmaplabels -x 100 -y 45 \
  "CODEPIT_CONFIG=config.demo.json python3 widgets/board.py"
sleep 1.5
tmux capture-pane -t heatmaplabels -p
tmux kill-session -t heatmaplabels
```

Expected: no traceback; the Heatmap card shows `Seg`/`Qua`/`Sex` down the left edge on
their respective rows, and 1-3 month abbreviations (e.g. `Mai`, `Jun`, `Jul`, `Ago`,
depending on today's date) above the grid, with the `██` columns shifted right to make
room.

- [ ] **Step 3: Run the full test suite (regression check)**

Run: `cd ~/Personal/codepit && python3 -m unittest discover -s tests -t . -v 2>&1 | tail -5`
Expected: `OK`, all tests passing.

- [ ] **Step 4: Commit**

```bash
cd ~/Personal/codepit
git add widgets/board.py
git commit -m "Show weekday and month labels on the Heatmap card"
```

---

### Task 3: Clock and Pet side by side in the layout

**Files:**
- Modify: `lib/config.py`
- Modify: `tests/test_config.py`

**Interfaces:**
- Produces: `config.build_layout(cfg, root)` — when both `clock` and `pet` panels are
  enabled, they render as a nested 50/50 side-by-side pane pair; either alone still
  takes the full row width as before; existing behavior for every other combination is
  unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py` (inside `TestConfig`, after `test_build_layout_pet_toggle`):

```python
    def test_build_layout_clock_and_pet_side_by_side(self):
        both = config.build_layout({"panels": ["clock", "pet"]}, "/x")
        self.assertIn("Clock", both)
        self.assertIn("Pet", both)
        self.assertIn('split_direction="vertical" size="20%"', both)

    def test_build_layout_pet_alone_full_width(self):
        pet_only = config.build_layout({"panels": ["pet"]}, "/x")
        self.assertIn("Pet", pet_only)
        self.assertNotIn("Clock", pet_only)
        self.assertNotIn('split_direction="vertical" size="20%"', pet_only)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_config -v`
Expected: FAIL — `test_build_layout_clock_and_pet_side_by_side` fails (no nested
vertical-split marker in today's stacked layout).

- [ ] **Step 3: Write the implementation**

In `lib/config.py`, change `build_layout()` from:

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
    if board_enabled(cfg):
        board = _pane("Board", f"{src}python3 {root}/widgets/board.py", size='"30%"')
        left = f'pane split_direction="horizontal" size="70%" {{\n{left_body}\n}}'
        content = f'pane split_direction="vertical" {{\n{left}\n{board}\n}}'
    else:
        content = f'pane split_direction="horizontal" {{\n{left_body}\n}}'

    return (f'layout {{\n    tab name="Dashboard" focus=true {{\n'
            f'        pane split_direction="horizontal" {{\n'
            f'{content}\n{shortcuts}\n'
            f'        }}\n    }}\n}}\n')
```

to:

```python
def build_layout(cfg, root):
    """Generate the Zellij layout (KDL) honoring which panels are enabled. Pure.

    Structure: a full-width content region on top and a single-line Shortcuts bar
    at the very bottom. The content is left column (clock+pet row, then one shell) +
    the board. Clock and pet sit side by side (50/50) when both are enabled; either
    alone takes the full row width; the row is absent if neither is enabled."""
    src = f'source {root}/.env 2>/dev/null; exec '
    shell = ('pane focus=true command="bash" {\n'
             '    args "-lc" "cd $HOME; claude; exec bash -i"\n'
             '}')
    shortcuts = _pane("Shortcuts", f"exec python3 {root}/widgets/cheatsheet.py", size="1")

    show_clock = panel_enabled(cfg, "clock")
    show_pet = panel_enabled(cfg, "pet")
    if show_clock and show_pet:
        clock = _pane("Clock", f"{src}python3 {root}/widgets/clock.py", size='"50%"')
        pet = _pane("Pet", f"{src}python3 {root}/widgets/pet.py", size='"50%"')
        top_row = [f'pane split_direction="vertical" size="20%" {{\n{clock}\n{pet}\n}}']
    elif show_clock:
        top_row = [_pane("Clock", f"{src}python3 {root}/widgets/clock.py", size='"20%"')]
    elif show_pet:
        top_row = [_pane("Pet", f"{src}python3 {root}/widgets/pet.py", size='"20%"')]
    else:
        top_row = []

    left_children = top_row + [shell]
    left_body = "\n".join(left_children)
    if board_enabled(cfg):
        board = _pane("Board", f"{src}python3 {root}/widgets/board.py", size='"30%"')
        left = f'pane split_direction="horizontal" size="70%" {{\n{left_body}\n}}'
        content = f'pane split_direction="vertical" {{\n{left}\n{board}\n}}'
    else:
        content = f'pane split_direction="horizontal" {{\n{left_body}\n}}'

    return (f'layout {{\n    tab name="Dashboard" focus=true {{\n'
            f'        pane split_direction="horizontal" {{\n'
            f'{content}\n{shortcuts}\n'
            f'        }}\n    }}\n}}\n')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_config -v`
Expected: PASS (all tests, including the 2 new ones; the 4 pre-existing
`test_build_layout_*` tests pass unmodified — trace through each combination in the new
code by hand if you want to confirm before running: `["clock","tickets"]` and
`["tickets"]` for `test_build_layout_clock_toggle`, `["pet"]` and `["clock"]` for
`test_build_layout_pet_toggle`, `["clock"]` for `test_build_layout_no_board`, and the 3
panel lists for `test_build_layout_shortcuts_bar_always_present` — none of them enable
both `clock` and `pet` together, so none hit the new nested-split branch).

- [ ] **Step 5: Commit**

```bash
cd ~/Personal/codepit
git add lib/config.py tests/test_config.py
git commit -m "Lay Clock and Pet out side by side when both are enabled"
```

---

### Task 4: Pet walks and blinks

**Files:**
- Modify: `widgets/pet.py`
- Create: `tests/test_pet.py`

**Interfaces:**
- Produces: `pet.frame_for(mood, blink) -> list[str]`, pure.
- Produces: `pet.mirror_frame(frame) -> list[str]`, pure.
- Produces: `pet.step_x(x, facing, maxx) -> (x, facing)`, pure.
- Produces: `pet.FRAME_WIDTH` (module constant, width of the pet's ASCII frame).
- Consumes: nothing new from other modules — this task only touches `widgets/pet.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pet.py`:

```python
import unittest
from widgets import pet


class TestPet(unittest.TestCase):
    def test_frame_for_no_blink_returns_base_mood(self):
        self.assertEqual(pet.frame_for("happy", False), pet.FRAMES["happy"])

    def test_frame_for_blink_returns_blink_variant(self):
        self.assertEqual(pet.frame_for("happy", True), pet.FRAMES["happy_blink"])

    def test_frame_for_unknown_mood_has_no_blink_variant_and_falls_back(self):
        self.assertEqual(pet.frame_for("unknown", True), pet.FRAMES["unknown"])

    def test_mirror_frame_swaps_parens(self):
        self.assertEqual(pet.mirror_frame(["( ^‿^ )"]), [") ^‿^ ("])

    def test_step_x_walks_in_facing_direction(self):
        self.assertEqual(pet.step_x(10, 1, 100), (11, 1))
        self.assertEqual(pet.step_x(10, -1, 100), (9, -1))

    def test_step_x_bounces_at_right_edge(self):
        maxx = 20
        x, facing = pet.step_x(maxx - pet.FRAME_WIDTH, 1, maxx)
        self.assertEqual(facing, -1)
        self.assertLessEqual(x + pet.FRAME_WIDTH, maxx)

    def test_step_x_bounces_at_left_edge(self):
        self.assertEqual(pet.step_x(0, -1, 100), (0, 1))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_pet -v`
Expected: FAIL with `AttributeError: module 'widgets.pet' has no attribute 'frame_for'`

- [ ] **Step 3: Write the implementation**

Replace the entire contents of `widgets/pet.py` with:

```python
#!/usr/bin/env python3
"""Terminal pet — ASCII companion whose mood reflects today's dev activity (commits +
Claude usage), and who walks back and forth across its pane with a periodic blink.
Standalone curses widget with its own Zellij pane (same shape as clock.py), but fetches
over the network like board.py, so it runs its own small background worker thread
instead of computing everything inline."""
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
TICK_MS = 150
BLINK_EVERY = 20  # ticks (~3s at TICK_MS=150)

FRAMES = {
    "happy":          [" ∩___∩ ", "( ^‿^ )", " ‾‾‾‾‾ "],
    "happy_blink":    [" ∩___∩ ", "( -‿- )", " ‾‾‾‾‾ "],
    "thinking":       [" ∩___∩ ", "( ·_· )", " ‾‾‾‾‾ "],
    "thinking_blink": [" ∩___∩ ", "( -_- )", " ‾‾‾‾‾ "],
    "hungry":         [" ∩___∩ ", "( ;_; )", " ‾‾‾‾‾ "],
    "hungry_blink":   [" ∩___∩ ", "( >_< )", " ‾‾‾‾‾ "],
    "unknown":        [" ∩___∩ ", "( ?_? )", " ‾‾‾‾‾ "],
}
MOOD_COLOR = {"happy": "green", "thinking": "cyan", "hungry": "orange", "unknown": "dim"}
MIRROR = str.maketrans("()", ")(")
FRAME_WIDTH = max(len(line) for line in FRAMES["happy"])


def frame_for(mood, blink):
    """The FRAMES entry for this mood, swapping in the blink variant when blink is True
    and one exists. Pure."""
    key = f"{mood}_blink" if blink else mood
    return FRAMES.get(key, FRAMES.get(mood, FRAMES["unknown"]))


def mirror_frame(frame):
    """The frame with its left/right parens swapped, to hint the pet facing the other
    way — no separate left-facing art needed. Pure."""
    return [line.translate(MIRROR) for line in frame]


def step_x(x, facing, maxx):
    """Next (x, facing) after one walking step, bouncing off the pane edges so the
    frame (FRAME_WIDTH wide) always stays fully visible. Pure."""
    x += facing
    if x < 0:
        x, facing = 0, 1
    elif x + FRAME_WIDTH > maxx:
        x, facing = max(0, maxx - FRAME_WIDTH), -1
    return x, facing


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
            calendar = heatmap_github.fetch_calendar(weeks=12)
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


def _draw(stdscr, pairs, store, x, facing, blink):
    stdscr.erase()
    maxy, maxx = stdscr.getmaxyx()
    with store.lock:
        name, mood, streak, error = store.name, store.mood, store.streak, store.error

    frame = frame_for(mood, blink)
    if facing == -1:
        frame = mirror_frame(frame)
    attr = curses.color_pair(pairs[MOOD_COLOR.get(mood, "dim")]) | curses.A_BOLD

    label_rows = [(f"{name} · streak {streak}", curses.color_pair(pairs["dim"]))]
    if error:
        label_rows.append((f"⚠ {error}", curses.color_pair(pairs["red"])))

    top = max(0, (maxy - len(frame) - len(label_rows)) // 2)
    for i, line in enumerate(frame):
        y = top + i
        if 0 <= y < maxy:
            try:
                stdscr.addnstr(y, x, line, max(0, maxx - x), attr)
            except curses.error:
                pass
    for i, (s, row_attr) in enumerate(label_rows):
        y = top + len(frame) + i
        if 0 <= y < maxy:
            lx = max(0, (maxx - len(s)) // 2)
            try:
                stdscr.addnstr(y, lx, s, max(0, maxx - lx - 1), row_attr)
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
    x, facing, blink = None, 1, False
    tick = 0
    while True:
        maxx = stdscr.getmaxyx()[1]
        if x is None:
            x = max(0, (maxx - FRAME_WIDTH) // 2)
        _draw(stdscr, pairs, store, x, facing, blink)
        if stdscr.getch() == ord("q"):
            break
        tick += 1
        if tick % BLINK_EVERY == 0:
            blink = not blink
        x, facing = step_x(x, facing, maxx)
        if time.monotonic() - last >= REFRESH:
            start_refresh(store, cfg)
            last = time.monotonic()


def main():
    curses.wrapper(run)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Personal/codepit && python3 -m unittest tests.test_pet -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Manual smoke test — demo mode, pet walks and blinks, no crash**

```bash
cd ~/Personal/codepit
tmux kill-session -t petwalk 2>/dev/null
tmux new-session -d -s petwalk -x 60 -y 12 \
  "CODEPIT_CONFIG=config.demo.json python3 widgets/pet.py"
sleep 1
tmux capture-pane -t petwalk -p > /tmp/petwalk1.txt
sleep 2
tmux capture-pane -t petwalk -p > /tmp/petwalk2.txt
diff /tmp/petwalk1.txt /tmp/petwalk2.txt
tmux kill-session -t petwalk
rm /tmp/petwalk1.txt /tmp/petwalk2.txt
```

Expected: no traceback in either capture; `diff` shows the frame's horizontal position
changed between the two captures (the pet walked) — if `diff` prints nothing, the pet
didn't move and that's a real bug to investigate before reporting done, not something to
paper over.

- [ ] **Step 6: Run the full test suite (regression check)**

Run: `cd ~/Personal/codepit && python3 -m unittest discover -s tests -t . -v 2>&1 | tail -5`
Expected: `OK`, all tests passing.

- [ ] **Step 7: Commit**

```bash
cd ~/Personal/codepit
git add widgets/pet.py tests/test_pet.py
git commit -m "Pet walks side to side and blinks periodically"
```

---

### Task 5: Full regression + combined smoke test

**Files:** none (verification only).

**Interfaces:** none.

- [ ] **Step 1: Full test suite**

Run: `cd ~/Personal/codepit && python3 -m unittest discover -s tests -t . -v 2>&1 | tail -10`
Expected: `OK`. Count should be 96 (baseline before this plan) + 4 new/changed heatmap
tests in Task 1 (2 replaced in place, 2 added) + 2 new config tests (Task 3) + 7 new
pet tests (Task 4) = 96 + 2 + 2 + 7 = 107. Report the actual number rather than forcing
it to match if it differs — this estimate is for your own sanity-check, not a hard gate.

- [ ] **Step 2: Combined manual smoke test — full demo layout**

```bash
cd ~/Personal/codepit
export PATH="$HOME/.local/bin:$PATH"
tmux kill-session -t fulldemo2 2>/dev/null
tmux new-session -d -s fulldemo2 -x 160 -y 50 \
  "CODEPIT_CONFIG=config.demo.json zellij --layout codepit"
sleep 3
tmux capture-pane -t fulldemo2 -p > /tmp/fulldemo2_a.txt
sleep 2
tmux capture-pane -t fulldemo2 -p > /tmp/fulldemo2_b.txt
cat /tmp/fulldemo2_a.txt
echo "--- diff (should show the pet having moved) ---"
diff /tmp/fulldemo2_a.txt /tmp/fulldemo2_b.txt
tmux kill-session -t fulldemo2
rm /tmp/fulldemo2_a.txt /tmp/fulldemo2_b.txt
```

If `zellij --layout codepit` fails or the layout looks stale (Clock and Pet not side by
side), regenerate it first: `printf "all\ngithub\n\ngithub\nboth\n\n" | python3 setup.py`,
then retry.

Expected: no crash; Clock and Pet render side by side (each roughly half the row's
width); the Heatmap card shows weekday/month labels; the diff between the two captures
shows the pet's position changed. Paste the first capture and the diff output into your
verification notes as evidence — this is the same pattern that caught a stale-layout
issue during the previous plan's final task, so don't skip straight to "looks fine."

- [ ] **Step 3: Commit**

Nothing to commit if both checks pass cleanly (this task is verification-only). If
Step 2 required regenerating the layout, that only touches
`~/.config/zellij/layouts/codepit.kdl` (outside the repo) and possibly `config.json`
(gitignored) — neither should be committed.

---

## Self-Review

**Spec coverage:**
- Heatmap weekday labels (3-letter, Mon/Wed/Fri only, avoiding Portuguese's
  single-letter collisions) → Task 1 (`WEEKDAY_LABELS`) + Task 2 (wiring). ✓
- Heatmap month labels (abbreviation above the first week of each new month) → Task 1
  (`heatmap_month_labels`) + Task 2 (wiring). ✓
- `heatmap_grid()` always carrying a real date per cell (the fix found during the
  spec's own self-review) → Task 1. ✓
- Pet beside Clock, 50/50, either alone still full-width → Task 3. ✓
- Pet walks horizontally, bounces at pane edges → Task 4 (`step_x`). ✓
- Pet blink layered on top of existing mood, independent cadence from the 90s data
  refresh → Task 4 (`frame_for`, `BLINK_EVERY`, unchanged `REFRESH`). ✓
- No 4th "sad" mood, no vertical/bouncing-both-axes movement, no mood/streak logic
  changes → correctly absent from every task. ✓
- Config.json ticket-source fix (`github` -> `mcp`) — already done directly in the
  session before this plan was written (see spec's Goal section); nothing to do here. ✓

**Placeholder scan:** no "TBD"/"TODO"/vague steps — every step has complete code.

**Type consistency check:**
- `heatmap_grid()`'s new `(date, count)` cell shape is consumed identically in Task 2's
  render code (`cell[1]`) and Task 1's own new tests. `heatmap_month_labels()` also
  expects that same shape (`col[0]` unpacked as `date_str, _count`) — consistent.
- `heatmap_color(count)` keeps taking a plain `count`, never a cell tuple — verified
  Task 2's wiring unwraps before calling it (`heatmap_color(count)` where `count` was
  already extracted from `cell`).
- `pet.frame_for`/`pet.mirror_frame`/`pet.step_x` signatures in Task 4's implementation
  match exactly what Task 4's own tests call and what `_draw()`/`run()` call internally
  (`frame_for(mood, blink)`, `mirror_frame(frame)`, `step_x(x, facing, maxx)`) —
  consistent throughout the single file that owns all of them.
- `FRAME_WIDTH` is computed once from `FRAMES["happy"]` and reused identically in
  `step_x()` (bounce math) and `run()` (initial centering) — no duplicated literal `7`.
