"""Fake data for a self-contained demo — no network, no secrets, no real data.

Lets anyone run the dashboard immediately and makes it safe to screenshot without
leaking real tickets/PRs. Enable with a config that has {"demo": true} (see
config.demo.json). All values below are invented."""
from datetime import date, datetime, timedelta, timezone


def issues():
    """Fake tickets in the board's contract, across a spread of statuses."""
    return [
        {"key": "APP-142", "status": "To Do", "summary": "Dark mode toggle in settings", "project": "APP", "url": ""},
        {"key": "APP-138", "status": "To Do", "summary": "Empty-state illustrations for the inbox", "project": "APP", "url": ""},
        {"key": "WEB-91", "status": "In Progress", "summary": "Server-side pagination on the orders table", "project": "WEB", "url": ""},
        {"key": "API-57", "status": "In Progress", "summary": "Rate-limit the public search endpoint", "project": "API", "url": ""},
        {"key": "WEB-88", "status": "Review", "summary": "Refactor the checkout form validation", "project": "WEB", "url": ""},
        {"key": "API-53", "status": "Review", "summary": "Cache the currency conversion table", "project": "API", "url": ""},
        {"key": "OPS-20", "status": "Backlog", "summary": "Migrate CI to the new runners", "project": "OPS", "url": ""},
    ]


def prs():
    """Fake pull requests in the normalized PR contract."""
    return [
        {"number": 214, "title": "feat(APP-142): dark mode toggle", "url": "",
         "_repo": "web-client", "_role": "author", "_category": "review",
         "_key": "APP-142", "_review": "● review", "_ci": "🟢 CI"},
        {"number": 209, "title": "fix(API-57): rate limiter off-by-one", "url": "",
         "_repo": "api-server", "_role": "author", "_category": "changes",
         "_key": "API-57", "_review": "⏳ changes", "_ci": "🔴 CI"},
        {"number": 205, "title": "chore: bump deps", "url": "",
         "_repo": "api-server", "_role": "reviewer", "_category": "review",
         "_key": None, "_review": "✓ approved", "_ci": "🟢 CI"},
        {"number": 198, "title": "feat(WEB-88): checkout validation", "url": "",
         "_repo": "web-client", "_role": "author", "_category": "merged",
         "_key": "WEB-88", "_review": "", "_ci": ""},
    ]


def usage():
    """Fake Claude usage windows (invented percentages)."""
    now = datetime.now(timezone.utc)

    def win(pct, hours):
        return {"pct": float(pct), "resets_at": (now + timedelta(hours=hours)).isoformat()}

    return {"five_hour": win(42, 3), "seven_day": win(27, 96),
            "sonnet": win(15, 96), "plan": "pro"}


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
