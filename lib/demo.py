"""Fake data for a self-contained demo — no network, no secrets, no real data.

Lets anyone run the dashboard immediately and makes it safe to screenshot without
leaking real tickets/PRs. Enable with a config that has {"demo": true} (see
config.demo.json). All values below are invented."""
from datetime import datetime, timedelta, timezone


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
