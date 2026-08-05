# Git heatmap + terminal pet — design

Date: 2026-08-05
Status: approved

## Goal

Add two new codepit panels:

1. **Heatmap** — a GitHub-contributions-style grid, as a new card in the existing `board.py`.
2. **Pet** — an ASCII "tamagotchi" whose mood reflects today's dev activity, as a new
   standalone widget pane (own process, like `clock.py`).

A future, separate spec will add a panel to customize the pet (name, skin). This design
only needs to leave room for that — it does not implement it.

## File map

```
lib/
  heatmap_github.py   # gh api graphql -> contribution calendar (shared by board + pet)
  pet_state.py        # read/write pet_state.json, mood rule, streak logic
widgets/
  pet.py              # curses standalone widget, own Zellij pane
board.py              # +1 "Heatmap" card in the existing stack
config.py             # PANELS += heatmap, pet; build_layout adds a Pet pane next to Clock
setup.py              # panel list mentions heatmap, pet (no per-source question — GitHub only)
demo.py               # +heatmap(), +pet_state() fakes, so demo/screenshot stays 100% mocked
.gitignore            # +pet_state.json (per-user, same treatment as config.json)
```

`heatmap_github.py` is shared: both the board card and the pet's mood calculation need
"how many commits today," so there is exactly one place that knows how to ask GitHub.

## Git heatmap

**Data source**: `gh api graphql`, querying `viewer.contributionsCollection(from, to).contributionCalendar`
— the same aggregate that powers the GitHub profile heatmap (includes private
contributions the account has access to). Chosen over the REST `events` API because REST
only returns ~90 days of *public* events; GraphQL returns per-day counts pre-aggregated
and includes private activity.

```python
# lib/heatmap_github.py
def fetch_calendar(weeks=12):
    """[{date, count}] for the last `weeks`*7 days, oldest first.
    Raises RuntimeError with a clear message on gh failure."""
```

Implementation follows the existing `github_api.py` pattern: `subprocess.run(["gh", "api",
"graphql", ...], capture_output=True)` + `json.loads`.

**Rendering**: new card in `board.py`, same `box()` helper as the other cards. Grid is 12
columns (weeks) x 7 rows (Sun-Sat), each cell a colored `██` block. Five intensity levels
(0 commits = dim, then 4 increasing shades of green) — added as five new named entries in
`theme.COLORS` (e.g. `heat0`..`heat4`, xterm-256 indexes like `236, 22, 28, 35, 41`), not
a separate list: `board.py`'s `_init_pairs()` already iterates every key in
`theme.COLORS` to build curses pairs, so new names there are picked up with no extra
plumbing in `board.py`, the same way `blue`/`green`/etc. already are. Box title shows the
total commit count for the period, matching how "By Status"/"Tickets" show a count today.

**Config**: `"heatmap"` added to `config.PANELS` and to the `board_enabled` tuple
(`claude`/`tickets`/`prs`/`heatmap`) so it toggles like the other board cards. No
`tickets`/`prs`-style "source" sub-question in `setup.py` — heatmap only has one source
(GitHub), so it only appears in the panel on/off list, like `clock`/`claude` do today.

**Refresh**: fetched inside `board.py`'s existing threaded `_worker()`, alongside
tickets/prs/claude usage — no new refresh mechanism.

## Terminal pet

**State**: `pet_state.json` at the repo root — same treatment as `config.json` (per-user,
gitignored, not the `.env` secrets file).

```python
# lib/pet_state.py
def load():
    """{"name": "Bit", "created_at": "<iso-date>", "streak": 0, "last_active_date": None}
    Returns defaults if the file doesn't exist yet (first run)."""

def touch(streak, active_date):
    """Persists an updated streak + last_active_date."""
```

`name` defaults to `"Bit"`. No naming prompt in this round — `name` is the exact field a
future customization panel would edit; this design just makes sure it already exists and
is persisted.

**Mood rule**: `widgets/pet.py` runs its own threaded worker (same lock/thread shape as
`board.py`'s), calling `heatmap_github.fetch_calendar(weeks=2)` and
`claude_usage.fetch_usage()`. Two weeks (not one) so "yesterday" is always in the
returned range even when today is the first day of a new calendar week (a `weeks=1`
request would return only the current Sun-Sat week, missing Saturday's count on a
Sunday). Today's and yesterday's counts are picked out of the returned `[{date, count}]`
by matching `date` against the two calendar dates.

| commits today | Claude 5h usage | mood |
|---|---|---|
| > 0 | any | happy |
| 0 | > 0% | thinking |
| 0 | 0% | hungry |

If yesterday's commits were also 0 (streak broken), an additional "sad" tag overlays the
above.

Streak increments by 1 when `commits_today > 0` and `last_active_date != today` (so it
only counts once per day); it resets to 0 if more than one day passed with no commit.

**Rendering**: one static ASCII frame per mood, centered in the pane the way `clock.py`
centers its rows — no multi-frame animation in this round.
`# ponytail: static frame per mood, add a 2-frame idle blink if it feels dead — needs a
periodic swap timer, skipped for v1 scope.`

**Config/layout**: `"pet"` added to `config.PANELS`. `build_layout()` in `config.py` adds
a "Pet" pane to the left column next to Clock, the same conditional-inclusion pattern
`left_children` already uses for the clock pane.

## Errors

Same pattern as existing cards: on `gh` failure, the heatmap card shows `⚠ <message>`
instead of the grid (like `usage_error`/`error` today). `pet.py` follows the identical
rule — no attempt to cache or guess a mood from stale data (nothing else in codepit does
that either): on fetch failure it shows a distinct "?" placeholder frame plus a small
inline `⚠ <message>` line, and never crashes the pane.

## Demo mode

`demo.heatmap()` returns a fixed (non-random) 12x7 grid so screenshots stay reproducible.
`demo.pet_state()` returns a fixed `{"name": "Bit", "streak": 5, "mood": "happy"}`. In
demo mode neither the heatmap card nor `pet.py` calls `gh` or `claude_usage` — same rule
`board.py`'s `demo` branch already follows for the other cards.

## Testing

Plain `unittest`, same style as the existing suite:

- `tests/test_heatmap_github.py` — count-to-color-level mapping; parsing a sample GraphQL
  response into `[{date, count}]`.
- `tests/test_pet_state.py` — mood table (commits/usage -> expected mood); streak logic
  (increments once/day, resets after a skipped day).
- The heatmap card's layout function and `pet.py`'s render function are pure and tested
  directly, the same way `board.py`'s other layout helpers and `clock.py` are today — the
  curses event loop itself is not (matches existing coverage boundary).

## Out of scope

- Pet customization panel (name/skin editing UI) — future spec. This design only ensures
  `pet_state.json` already has a `name` field for it to edit.
- Multi-frame pet animation — noted as a `ponytail:` shortcut above, not built now.
- Full-year (53-week) heatmap — the board column is narrow; 12 weeks was chosen to fit
  without a tiny font or horizontal scroll.
