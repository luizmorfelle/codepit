#!/usr/bin/env python3
"""Bottom bar: single-line shortcut cheatsheet spanning the full width."""
import curses
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from lib import theme  # noqa: E402
from lib import cheatsheet  # noqa: E402


def _init_pairs():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, theme.COLORS["dim"], -1)
    return {"dim": 1}


def _draw(stdscr, pairs):
    stdscr.erase()
    maxy, maxx = stdscr.getmaxyx()
    if maxy > 0:
        try:
            stdscr.addnstr(0, 1, cheatsheet.one_line(), max(0, maxx - 2),
                           curses.color_pair(pairs["dim"]))
        except curses.error:
            pass
    stdscr.refresh()


def run(stdscr):
    curses.curs_set(0)
    pairs = _init_pairs()
    stdscr.timeout(1000)
    while True:
        _draw(stdscr, pairs)
        ch = stdscr.getch()
        if ch == ord("q"):
            break


def main():
    curses.wrapper(run)


if __name__ == "__main__":
    main()
