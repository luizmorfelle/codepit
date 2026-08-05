"""GitHub contribution calendar (commits, PRs, issues, reviews — everything GitHub counts
as a "contribution") via `gh api graphql`. Same aggregate that powers the profile heatmap,
including private contributions the account has access to. Shared by the board's Heatmap
card and the pet's mood/streak calculation — both only need "count per day"."""
import json
import subprocess
from datetime import datetime, timedelta, timezone

QUERY = """
query($from: DateTime!, $to: DateTime!) {
  viewer {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def parse_calendar(raw):
    """Flatten the GraphQL response into [{date, count}], oldest first. Pure."""
    collection = (((raw or {}).get("data") or {}).get("viewer") or {}) \
        .get("contributionsCollection") or {}
    weeks = (collection.get("contributionCalendar") or {}).get("weeks") or []
    out = []
    for week in weeks:
        for day in week.get("contributionDays", []):
            out.append({"date": day["date"], "count": day["contributionCount"]})
    return out


def fetch_calendar(weeks=12):
    """[{date, count}] for the last `weeks`*7 days, oldest first.
    Raises RuntimeError with a clear message on gh failure."""
    to = datetime.now(timezone.utc)
    frm = to - timedelta(weeks=weeks)
    args = ["gh", "api", "graphql", "-f", f"query={QUERY}",
            "-F", f"from={frm.strftime('%Y-%m-%dT00:00:00Z')}",
            "-F", f"to={to.strftime('%Y-%m-%dT23:59:59Z')}"]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        raise RuntimeError("gh api timed out after 30s")
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "gh failed")
    return parse_calendar(json.loads(out.stdout or "null") or {})
