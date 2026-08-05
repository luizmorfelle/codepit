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
