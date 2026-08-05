# Heatmap labels + walking pet — design

Date: 2026-08-05
Status: approved

## Goal

Follow-up polish on the heatmap + pet panels shipped in the previous spec/plan
(`2026-08-05-heatmap-pet-design.md`), based on real usage feedback:

1. **Heatmap** — the grid has no orientation (no day/month labels), making it hard to
   read at a glance. Add weekday and month labels, GitHub-style.
2. **Pet** — currently a static centered frame below the Clock. Move it to a pane beside
   the Clock, and give it actual movement (walks left/right, turns at the pane edges)
   plus a periodic idle animation (blink) layered on top of its existing mood.

Also fixed as part of this same session, no design needed (pure config, not a code
change): `config.json`'s `tickets.source` was `"github"` (0 real results — the user's
tickets live in SunDesk, not GitHub Issues) and is now `"mcp"`.

## 1. Heatmap labels

**Problem:** `heatmap_grid()` already computes each cell against its real calendar date
internally, but discards the date and returns only `count` per cell — the render code in
`board.py` has no date to label with.

**Fix:** change `heatmap_grid()`'s cell value from a bare `count` (or `None`) to an
always-present `(date, count)` tuple, where `date` is the real ISO date computed for
that grid position (every position has a real calendar date, regardless of whether the
input `calendar` had an entry for it) and `count` is `None` only when that date has no
entry in the input (same "missing" meaning as today's bare `None`). Carrying the date on
every cell — not just ones with data — matters because month labels need to read "this
column's Sunday date," and a Sunday with zero commits must not lose its date just
because its count is unknown. `heatmap_color()` still takes a plain `count` (`None` or
0+); every existing test that checks a cell's count needs a one-line unwrap
(`cell[1]` instead of `cell`).

One degenerate case keeps today's bare-`None` behavior: a fully empty `calendar` input
has no date to anchor "today" to at all (that's what the existing `if not calendar:`
early return handles), so cells stay plain `None` — not a `(date, count)` tuple — only
in that one case. Every non-empty calendar produces real dates on every cell.

**Render (in `board.py`'s drawing block):**
- A weekday-abbreviation column at the left of the grid, one row per weekday, but only
  the Mon/Wed/Fri rows carry a label — the other rows are blank. This is GitHub's own
  convention (labeling every row is too noisy at this cell size). The label itself is a
  3-letter Portuguese abbreviation (`Seg`, `Qua`, `Sex`), not a single letter: Portuguese
  weekday names collide on their first letter (Segunda/Sexta/Sábado all start with `S`;
  Quarta/Quinta both start with `Q`), so a single-letter column would be ambiguous. The
  column needs ~3 chars of width, not 2.
- A month-name row above the grid: for each column (week) whose Sunday date is the
  first week of a new month within the visible 12-week window, print a short month
  abbreviation (`Jan`, `Fev`, ...) starting at that column. At most 3-4 month labels
  will appear in a 12-week window.
- Both labels shift the grid's drawing origin right/down by a fixed offset (4 cols for
  the weekday column — 3 for the label plus 1 gap — and 1 row for the month row) — the
  box height/width calc in `run()` needs the `+1` row accounted for.

**No changes** to `heatmap_color()`, `HEATMAP_WEEKS`, `lib/heatmap_github.py`, or
`lib/demo.py`'s `heatmap()` (demo data already carries real dates per cell, so it works
unchanged once `heatmap_grid()`'s cell shape changes).

## 2. Pet layout: beside the Clock

**Current:** `build_layout()`'s left column is `[clock?] + [pet?] + [shell]` stacked
vertically (`split_direction="horizontal"`, top-to-bottom).

**New:** when both `clock` and `pet` panels are enabled, they become a nested
`split_direction="vertical"` (side-by-side) pane pair, 50/50, sitting above the shell
in the same vertical stack the shell already occupies. If only one of the two is
enabled, it takes the full width alone (no empty half-pane) — same on/off independence
`panel_enabled()` already guarantees for every other panel.

```
left column (top to bottom):
  [ Clock (50%) | Pet (50%) ]   <- new nested vertical split, only when both are on
  [        Shell             ]
```

If only `pet` is on (no `clock`): pet alone occupies that row, full width. If only
`clock` is on: unchanged from today (clock alone, full width). This mirrors the
existing `left_children` list-building pattern in `build_layout()` — no special-casing
beyond building a `[clock, pet]` pair conditionally instead of a flat list entry.

## 3. Pet: walking + idle animation

**New ephemeral state** (in `pet.py`'s `Store`, NOT persisted to `pet_state.json` —
resets to center on every launch, like a real pet waking up in the same spot):

```python
self.x = None        # set to center on first draw, once maxx is known
self.facing = 1       # 1 = walking right, -1 = walking left
self.blink = False    # alternates on a slower cadence than position
```

**Animation tick:** `pet.py`'s curses loop timeout (`stdscr.timeout(...)`) drops from
the current `TICK_MS = 1000` to `150` — matching `board.py`'s own `TICK_MS = 120`
(close enough; 150 keeps the walk visibly smooth without redrawing more than needed).
This is purely the *redraw/input-poll* cadence — the existing 90s `REFRESH` data-fetch
timer is untouched and independent, exactly as it is in `board.py` today (fast redraw
tick, slow data refresh, already-proven split).

Each tick (when not still on the very first load):
- `x += facing`; if `x` would put the frame past either pane edge, flip `facing` and
  clamp `x` back onto the last valid column — the same "bounce" moment.
- A separate slower counter (every ~20 ticks, ~3s at 150ms) toggles `blink`.

**Rendering:** the 3 existing mood frames (`happy`/`thinking`/`hungry`) each gain a
second, blink variant (eyes closed) — 3 new small ASCII arts, not 3 new moods. When
`facing == -1`, the frame's two side characters swap (e.g. `(` <-> `)`) via a plain
string trick (`str.translate` with a `(`↔`)` mapping) so the face visibly turns around
— no new art needed for "facing left" vs "facing right", just a character mirror on
the two parenthesis-like glyphs already in each frame.

**Positioning:** instead of `clock.py`-style vertical+horizontal centering, only the
row is centered (mood text + name/streak line stay stacked beneath, centered
independently); the frame's horizontal position is `self.x` (clamped to stay fully
inside the pane), not `(maxx - len(s)) // 2`.

**Unaffected:** mood computation (`pet_state.mood`), streak computation
(`pet_state.streak_from_calendar`), the `_worker()` fetch thread, demo mode, and error
handling are all untouched — this section only changes what `_draw()` does with an
already-known mood, plus two small new ephemeral fields on `Store` that `_draw()` reads
under the same lock pattern already in place for `mood`/`streak`/`error`.

## Testing

- `heatmap_grid()`'s shape change (`count` -> `(date, count)`) needs its 3 existing
  shape/content tests in `tests/test_board.py` (`test_heatmap_grid_shape`,
  `test_heatmap_grid_places_count_on_right_weekday`, `test_heatmap_grid_empty_calendar`)
  updated to unwrap the tuple; add one new test asserting the date returned for a known
  cell matches the fixture's input date. `test_heatmap_color_thresholds` is untouched —
  it tests `heatmap_color()`, whose signature doesn't change.
- The weekday-letter and month-label placement (which columns/rows get a label) is pure
  computation, worth its own small pure helper function + tests (e.g.
  `heatmap_month_labels(grid)` or similar) rather than being buried inline in the curses
  draw block, the way `heatmap_color`/`heatmap_grid` already are.
- Pet's walking/blink/facing logic is curses-loop state (position increments, bounce,
  frame mirroring) — same untested-widget-file boundary as the rest of `pet.py` and
  `board.py`'s draw loops. Verified via manual `tmux` smoke test (watch a few ticks,
  confirm the frame moves and turns around at an edge) rather than a unit test, matching
  existing project convention.

## Out of scope

- Vertical movement / bouncing in two axes (explicitly rejected in favor of horizontal
  walking, per the design conversation).
- Any change to the mood/streak *logic* — this is presentation-only.
- A 4th "sad" mood (already decided against in the previous spec's final-review
  follow-up: the streak number already communicates a broken streak).
