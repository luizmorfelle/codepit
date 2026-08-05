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
