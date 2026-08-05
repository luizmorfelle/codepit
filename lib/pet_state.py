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
