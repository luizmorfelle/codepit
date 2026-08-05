#!/usr/bin/env python3
"""Unified right-hand pane (curses): Claude usage + tickets by status + pull requests."""
import curses
import os
import sys
import threading
import time
import webbrowser
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from lib import config  # noqa: E402
from lib import tickets  # noqa: E402
from lib import prs as prs_source  # noqa: E402
from lib import claude_usage  # noqa: E402
from lib import theme  # noqa: E402

REFRESH = 90
HEATMAP_WEEKS = 12
TICK_MS = 120
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
STATUS_ORDER = ["To Do", "In Analysis", "In Development", "In Progress",
                "Review", "Pull Request", "Done"]
DEFAULT_ON = {"to do", "in development", "in progress"}
STATUS_COLOR = {
    "to do": "blue", "in progress": "yellow", "in development": "yellow",
    "in analysis": "cyan", "review": "purple", "pull request": "orange", "done": "green",
}
PR_CATS = [("review", "awaiting review"), ("changes", "changes"), ("merged", "merged")]
PR_DEFAULT = {"review", "changes"}
ROLE_GLYPH = {"author": "✎", "reviewer": "👁"}
WHEEL_UP = curses.BUTTON4_PRESSED
WHEEL_DOWN = getattr(curses, "BUTTON5_PRESSED", 0)  # some ncurses builds lack button 5
# Act on the PRESSED half of a click only. With mouseinterval(0) ncurses emits just
# PRESSED/RELEASED (no synthesized CLICKED), so a click fires exactly once — otherwise
# press+release would toggle a chip twice (mark then unmark).
CLICK = curses.BUTTON1_PRESSED


def distinct_statuses(issues):
    present = []
    for it in issues:
        if it["status"] not in present:
            present.append(it["status"])
    order_lc = [s.lower() for s in STATUS_ORDER]

    def sort_key(s):
        sl = s.lower()
        rank = order_lc.index(sl) if sl in order_lc else len(order_lc)
        return (rank, sl)

    return sorted(present, key=sort_key)


def default_active(statuses):
    return {s for s in statuses if s.lower() in DEFAULT_ON}


def apply_filter(issues, active):
    return [it for it in issues if it["status"] in active]


def chip_layout(statuses, active, x0=0, y=1, gap=1):
    chips = []
    x = x0
    for s in statuses:
        label = f" {s} "
        chips.append({"label": label, "status": s, "x0": x, "x1": x + len(label) - 1,
                      "y": y, "active": s in active})
        x += len(label) + gap
    return chips


def hit_test(chips, x, y):
    """Status of the ticket chip at (x, y), or None. Pure."""
    for c in chips:
        if c["y"] == y and c["x0"] <= x <= c["x1"]:
            return c["status"]
    return None


def button_hit(rect, x, y):
    """True if (x, y) is inside the (x0, x1, y) button rect. Pure."""
    x0, x1, by = rect
    return y == by and x0 <= x <= x1


def clamp_scroll(offset, total, viewport):
    return max(0, min(offset, max(0, total - viewport)))


def status_color(name):
    return STATUS_COLOR.get(name.lower(), "dim")


def status_distribution(issues):
    """[{status, count, pct}] over the open issues, in STATUS_ORDER. Pure."""
    total = len(issues)
    if not total:
        return []
    counts = {}
    for it in issues:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    return [{"status": s, "count": counts[s], "pct": round(counts[s] * 100 / total)}
            for s in distinct_statuses(issues)]


def role_glyph(role):
    return ROLE_GLYPH.get(role, "")


def pr_counts(prs):
    counts = {}
    for pr in prs:
        c = pr.get("_category")
        if c:
            counts[c] = counts.get(c, 0) + 1
    return counts


def filter_prs(prs, active_cats):
    """PRs whose category is active. Pure."""
    return [pr for pr in prs if pr.get("_category") in active_cats]


def pr_chip_layout(counts, active_cats, x0=1, y=0, gap=1):
    """PR category chips. Pure."""
    chips = []
    x = x0
    for cat, label in PR_CATS:
        text = f" {label} {counts.get(cat, 0)} "
        chips.append({"label": text, "cat": cat, "x0": x, "x1": x + len(text) - 1,
                      "y": y, "active": cat in active_cats})
        x += len(text) + gap
    return chips


def pr_hit_test(chips, x, y):
    """Category of the PR chip at (x, y), or None. Pure."""
    for c in chips:
        if c["y"] == y and c["x0"] <= x <= c["x1"]:
            return c["cat"]
    return None


def review_color(glyph):
    if "approved" in glyph:
        return "green"
    if "changes" in glyph:
        return "red"
    if "draft" in glyph:
        return "dim"
    return "blue"


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


def start_refresh(store, cfg):
    with store.lock:
        if store.loading:
            return
        store.loading = True
    threading.Thread(target=_worker, args=(store, cfg), daemon=True).start()


def _init_pairs():
    curses.start_color()
    curses.use_default_colors()
    pairs = {}
    pid = 1
    for name, idx in theme.COLORS.items():
        curses.init_pair(pid, idx, -1)
        text_pair = pid
        pid += 1
        curses.init_pair(pid, theme.COLORS["bg"], idx)
        badge_pair = pid
        pid += 1
        pairs[name] = (text_pair, badge_pair)
    return pairs


def run(stdscr):
    curses.curs_set(0)
    try:
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        curses.mouseinterval(0)  # no synthesized CLICKED → one PRESSED per click
    except curses.error:
        pass
    pairs = _init_pairs()
    stdscr.timeout(TICK_MS)

    cfg = config.load()
    show_claude = config.panel_enabled(cfg, "claude")
    show_tickets = config.panel_enabled(cfg, "tickets")
    show_prs = config.panel_enabled(cfg, "prs")

    store = Store()
    start_refresh(store, cfg)
    active = set()
    initialized = False
    sel = 0
    scroll = 0
    row_sel = 0
    spin = 0
    last_auto = time.monotonic()
    pr_active = set(PR_DEFAULT)
    button_rect = (0, 0, -1)
    chip_row = 0
    pr_chip_row = 0

    def text(name):
        return curses.color_pair(pairs[name][0])

    def badge_attr(name):
        return curses.color_pair(pairs[name][1]) | curses.A_BOLD

    while True:
        with store.lock:
            issues = list(store.issues)
            prs = list(store.prs)
            usage = store.usage
            usage_error = store.usage_error
            error = store.error
            loading = store.loading
            updated = store.last_updated

        statuses = distinct_statuses(issues)
        if not initialized and statuses:
            active = default_active(statuses)
            initialized = True
        sel = min(sel, max(0, len(statuses) - 1))
        open_keys = {it["key"] for it in issues}
        shown = []  # filled by the tickets card; referenced by the Enter handler

        stdscr.erase()
        maxy, maxx = stdscr.getmaxyx()

        def put(y, x, s, attr=0):
            if 0 <= y < maxy and 0 <= x < maxx:
                try:
                    stdscr.addnstr(y, x, s, max(0, maxx - x - 1), attr)
                except curses.error:
                    pass

        # Boxes span cols 0..maxx-2 (a 1-col right margin dodges the curses
        # "can't write the last column" error). W is the box's right border col.
        W = maxx - 1

        def putin(y, x, s, attr=0):
            """put() for content inside a box: never writes onto the right border."""
            if 0 <= y < maxy and 1 <= x < W - 1:
                try:
                    stdscr.addnstr(y, x, s, max(0, W - 1 - x), attr)
                except curses.error:
                    pass

        def box(top, bottom, label, color, count=None):
            """Rounded box (╭╮╰╯) with a titled top rule and right-aligned count. Draw
            AFTER the content (content lives at rows top+1..bottom-1, cols 1..W-2)."""
            prefix = f"╭─ {label} "
            top_line = prefix + "─" * max(0, W - len(prefix) - 1) + "╮"
            put(top, 0, top_line, text(color) | curses.A_BOLD)
            if count is not None:
                cs = f" {count} "
                put(top, max(1, W - len(cs) - 1), cs, text("dim"))
            for y in range(top + 1, bottom):
                put(y, 0, "│", text(color))
                put(y, W - 1, "│", text(color))
            put(bottom, 0, "╰" + "─" * max(0, W - 2) + "╯", text(color))

        # top status line
        if loading:
            status_line = f"{SPINNER[spin % len(SPINNER)]} updating…"
        elif updated:
            status_line = f"↻ updated {updated.strftime('%H:%M:%S')}"
        else:
            status_line = "↻ —"
        put(0, 1, status_line, text("dim"))
        btn = " R  refresh "
        bx = max(1, maxx - len(btn) - 2)
        put(0, bx, btn, badge_attr("blue"))
        button_rect = (bx, bx + len(btn) - 1, 0)
        row = 1

        # CLAUDE USAGE
        if show_claude:
            plan = (usage or {}).get("plan", "")
            box_top = row
            row += 1
            if usage_error:
                putin(row, 2, f"⚠ {usage_error}", text("red"))
                row += 1
            elif usage:
                any_win = False
                for label, key in (("5h", "five_hour"), ("7d", "seven_day"), ("Sonnet", "sonnet")):
                    win = usage.get(key)
                    if not win:
                        continue
                    any_win = True
                    pct = win["pct"]
                    putin(row, 2, f"{label:<6}", text("dim"))
                    putin(row, 8, claude_usage.usage_bar(pct, 12), text(claude_usage.usage_color(pct)))
                    reset = claude_usage.human_reset(win["resets_at"], datetime.now(timezone.utc))
                    putin(row, 21, f"{int(pct)}% {reset}", text("text"))
                    row += 1
                if not any_win:
                    putin(row, 2, "no usage data", text("dim"))
                    row += 1
            else:
                putin(row, 2, "usage unavailable", text("dim"))
                row += 1
            box(box_top, row, "Claude Usage" + (f" · {plan}" if plan else ""), "cyan")
            row += 1

        # TICKETS: a "By Status" box then a "Tickets" list box (with a row cursor)
        if show_tickets:
            bs_top = row
            row += 1
            dist = status_distribution(issues)
            if not dist:
                putin(row, 2, "no open tickets", text("dim"))
                row += 1
            for d in dist:
                putin(row, 2, f"{d['status'][:12]:<12}", text("dim"))
                putin(row, 15, claude_usage.usage_bar(d["pct"], 10), text(status_color(d["status"])))
                putin(row, 26, f"{d['pct']}% ({d['count']})", text("text"))
                row += 1
            box(bs_top, row, "By Status", "green", len(issues))
            row += 1

            shown = apply_filter(issues, active)
            list_start = row + 4  # box top + chips + divider before the first row
            items = max(1, ((maxy - list_start) // 2) // 2)
            row_sel = max(0, min(row_sel, len(shown) - 1)) if shown else 0
            if row_sel < scroll:                       # keep the cursor in view
                scroll = row_sel
            elif items and row_sel >= scroll + items:
                scroll = row_sel - items + 1
            scroll = clamp_scroll(scroll, len(shown), items)

            tk_top = row
            row += 1
            chip_row = row
            chips = chip_layout(statuses, active, x0=1, y=row)
            for i, c in enumerate(chips):
                attr = badge_attr(status_color(c["status"])) if c["active"] else text("dim")
                if i == sel:
                    attr |= curses.A_UNDERLINE | curses.A_BOLD
                putin(c["y"], c["x0"], c["label"], attr)
            row += 1
            putin(row, 2, "─" * max(0, W - 4), text("dim"))  # chips ↔ list divider
            row += 1
            for idx in range(scroll, min(scroll + items, len(shown))):
                it = shown[idx]
                selected = idx == row_sel
                sc = status_color(it["status"])
                putin(row, 2, "▌", text(sc))
                key_attr = text("text") | curses.A_BOLD | (curses.A_REVERSE if selected else 0)
                putin(row, 4, it["key"], key_attr)
                putin(row, 4 + len(it["key"]) + 2, it["status"], text(sc))
                putin(row + 1, 4, it["summary"], text("text" if selected else "dim"))
                row += 2
            box(tk_top, row, "Tickets", "blue", len(shown))
            row += 1

        # PULL REQUESTS (author OR reviewer)
        if show_prs:
            counts = pr_counts(prs)
            pr_shown = filter_prs(prs, pr_active)
            pr_top = row
            row += 1
            pr_chip_row = row
            pr_chips = pr_chip_layout(counts, pr_active, x0=1, y=row)
            for c in pr_chips:
                color = {"merged": "green", "changes": "red", "review": "blue"}.get(c["cat"], "blue")
                attr = badge_attr(color) if c["active"] else text("dim")
                putin(c["y"], c["x0"], c["label"], attr)
            row += 1
            putin(row, 2, "─" * max(0, W - 4), text("dim"))  # chips ↔ list divider
            row += 1
            for pr in pr_shown:
                cat_color = {"merged": "green", "changes": "red", "review": "blue"}.get(pr["_category"], "blue")
                putin(row, 2, "▌", text(cat_color))
                label = f"{role_glyph(pr.get('_role'))} {pr['_repo']} #{pr['number']}"
                putin(row, 4, label, text("text") | curses.A_BOLD)
                x = 4 + len(label) + 2
                putin(row, x, pr["_category"], text(cat_color))
                x += len(pr["_category"]) + 1
                if pr.get("_review"):
                    putin(row, x, pr["_review"], text(review_color(pr["_review"])))
                    x += len(pr["_review"]) + 1
                if pr.get("_ci"):
                    putin(row, x, pr["_ci"], text("text"))
                    x += len(pr["_ci"]) + 1
                if pr.get("_key") in open_keys:
                    putin(row, x, "·open", text("cyan"))
                putin(row + 1, 4, pr["title"], text("dim"))
                row += 2
            box(pr_top, row, "Pull Requests", "purple", len(pr_shown))
            row += 1

        if error:
            putin(row, 2, f"⚠ {error}", text("red"))
            row += 1

        stdscr.refresh()

        ch = stdscr.getch()
        if loading:
            spin += 1
        if time.monotonic() - last_auto >= REFRESH:
            start_refresh(store, cfg)
            last_auto = time.monotonic()
        if ch == -1:
            continue
        if ch == ord("q"):
            break
        elif ch in (ord("R"), ord("r")):
            start_refresh(store, cfg)
            last_auto = time.monotonic()
        elif ch == curses.KEY_LEFT and statuses:
            sel = (sel - 1) % len(statuses)
        elif ch == curses.KEY_RIGHT and statuses:
            sel = (sel + 1) % len(statuses)
        elif ch == ord(" ") and statuses:
            active ^= {statuses[sel]}
        elif ch in (curses.KEY_ENTER, 10, 13):
            if shown and shown[row_sel].get("url"):
                webbrowser.open(shown[row_sel]["url"])
        elif ch == ord("a"):
            active = set(statuses)
        elif ch == ord("n"):
            active = set()
        elif ch in (curses.KEY_DOWN, ord("j")):
            row_sel = min(row_sel + 1, max(0, len(shown) - 1))
        elif ch in (curses.KEY_UP, ord("k")):
            row_sel = max(0, row_sel - 1)
        elif ch in (ord("1"), ord("2"), ord("3")):
            pr_active ^= {PR_CATS[ch - ord("1")][0]}
        elif ch == curses.KEY_MOUSE:
            try:
                _id, mx, my, _z, bstate = curses.getmouse()
            except curses.error:
                continue
            if bstate & WHEEL_UP:
                row_sel = max(0, row_sel - 1)
            elif WHEEL_DOWN and bstate & WHEEL_DOWN:
                row_sel = min(row_sel + 1, max(0, len(shown) - 1))
            elif not bstate & CLICK:
                continue  # ignore the release half of a click (would double-toggle)
            elif button_hit(button_rect, mx, my):
                start_refresh(store, cfg)
                last_auto = time.monotonic()
            else:
                ticket_hit = hit_test(chip_layout(statuses, active, x0=1, y=chip_row), mx, my)
                pr_hit = pr_hit_test(
                    pr_chip_layout(pr_counts(prs), pr_active, x0=1, y=pr_chip_row), mx, my)
                if ticket_hit:
                    active ^= {ticket_hit}
                elif pr_hit:
                    pr_active ^= {pr_hit}


def main():
    curses.wrapper(run)


if __name__ == "__main__":
    main()
