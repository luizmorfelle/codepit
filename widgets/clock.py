#!/usr/bin/env python3
"""Block-font clock (clock-tui's BricksFont), auto-scaled — curses render (no scrolling)."""
import curses
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from lib import theme  # noqa: E402
from lib import holidays_br  # noqa: E402
from lib import agenda  # noqa: E402

# BricksFont (clock-tui): every glyph is 5 rows; each row is an RLE list of run
# lengths alternating OFF/ON and starting with OFF (off, on, off, on, ...).
BRICKS = {
    "0": [[0, 6], [0, 2, 2, 2], [0, 2, 2, 2], [0, 2, 2, 2], [0, 6]],
    "1": [[0, 4], [2, 2], [2, 2], [2, 2], [0, 6]],
    "2": [[0, 6], [4, 2], [0, 6], [0, 2], [0, 6]],
    "3": [[0, 6], [4, 2], [0, 6], [4, 2], [0, 6]],
    "4": [[0, 2, 2, 2], [0, 2, 2, 2], [0, 6], [4, 2], [4, 2]],
    "5": [[0, 6], [0, 2], [0, 6], [4, 2], [0, 6]],
    "6": [[0, 6], [0, 2], [0, 6], [0, 2, 2, 2], [0, 6]],
    "7": [[0, 6], [4, 2], [4, 2], [4, 2], [4, 2]],
    "8": [[0, 6], [0, 2, 2, 2], [0, 6], [0, 2, 2, 2], [0, 6]],
    "9": [[0, 6], [0, 2, 2, 2], [0, 6], [4, 2], [0, 6]],
    ":": [[], [2, 2], [], [2, 2], []],
}

# Hardcoded names instead of strftime: %A/%B follow the shell locale, and the
# dashboard should read the same in English on any machine.
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def _decode_row(runs):
    """Decode one RLE row (starts OFF) into a string of █/space. Pure."""
    out = ""
    on = False
    for n in runs:
        out += ("█" if on else " ") * n
        on = not on
    return out


def glyph(char):
    """The 5 equal-width rows of the character in block font. Pure."""
    rows = [_decode_row(r) for r in BRICKS.get(char, [[]] * 5)]
    width = max((len(r) for r in rows), default=0)
    return [r.ljust(width) for r in rows]


def big_time(hhmm, size=1):
    """Render 'HH:MM' as 5*size rows, scaled by `size`. Pure."""
    glyphs = []
    for ch in hhmm:
        base = glyph(ch)
        scaled = []
        for row in base:
            wide = "".join(c * size for c in row)
            scaled.extend([wide] * size)
        glyphs.append(scaled)
    gap = "  "
    height = 5 * size
    return [gap.join(g[r] for g in glyphs) for r in range(height)]


def format_date(d):
    """Long-form date, locale-independent. Pure."""
    return f"{WEEKDAYS[d.weekday()]}, {MONTHS[d.month - 1]} {d.day}, {d.year}"


def _init_pairs():
    curses.start_color()
    curses.use_default_colors()
    pairs = {}
    pid = 1
    for name in ("cyan", "dim", "red", "orange"):
        idx = theme.COLORS[name]
        curses.init_pair(pid, idx, -1)
        text_pair = pid
        pid += 1
        curses.init_pair(pid, theme.COLORS["bg"], idx)
        badge_pair = pid
        pid += 1
        pairs[name] = (text_pair, badge_pair)
    return pairs


def _draw(stdscr, pairs):
    stdscr.erase()
    maxy, maxx = stdscr.getmaxyx()
    now = datetime.now()
    hhmm = now.strftime("%H:%M")
    base_w = len(big_time(hhmm, 1)[0])
    size = max(1, min((maxx - 2) // max(1, base_w), (maxy - 3) // 5))

    rows = []
    for line in big_time(hhmm, size):
        rows.append((line, curses.color_pair(pairs["cyan"][0]) | curses.A_BOLD))
    rows.append((format_date(now.date()), curses.color_pair(pairs["dim"][0])))
    rows.append((f"◷ {agenda.next_event_text(now)}", curses.color_pair(pairs["cyan"][0])))
    hol = holidays_br.holiday_for(now.date())
    if hol:
        name, kind = hol
        tag = "Holiday" if kind == "holiday" else "Optional holiday"
        color = "red" if kind == "holiday" else "orange"
        rows.append((f" {tag} — {name} ", curses.color_pair(pairs[color][1]) | curses.A_BOLD))

    top = max(0, (maxy - len(rows)) // 2)
    for i, (s, attr) in enumerate(rows):
        y = top + i
        if 0 <= y < maxy:
            x = max(0, (maxx - len(s)) // 2)
            try:
                stdscr.addnstr(y, x, s, max(0, maxx - x - 1), attr)
            except curses.error:
                pass
    stdscr.refresh()


def run(stdscr):
    curses.curs_set(0)
    pairs = _init_pairs()
    stdscr.timeout(1000)
    while True:
        _draw(stdscr, pairs)
        if stdscr.getch() == ord("q"):
            break


def main():
    curses.wrapper(run)


if __name__ == "__main__":
    main()
