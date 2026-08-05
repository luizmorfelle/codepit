"""Claude plan usage — reads ~/.claude/.credentials.json and Anthropic's usage endpoint."""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime

CREDENTIALS = os.path.expanduser("~/.claude/.credentials.json")
CACHE = "/tmp/dev-dashboard-claude-usage.json"
CACHE_TTL = 300  # 5 min — the endpoint is undocumented and rate-limited
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


def read_credentials():
    """Read token and plan from the Claude CLI credentials file (re-read on every fetch)."""
    try:
        with open(CREDENTIALS) as f:
            oauth = json.load(f).get("claudeAiOauth", {})
    except FileNotFoundError:
        raise RuntimeError("credentials not found — open Claude")
    token = oauth.get("accessToken", "")
    if not token:
        raise RuntimeError("no accessToken in ~/.claude/.credentials.json")
    return {"token": token, "plan": oauth.get("subscriptionType") or ""}


def parse_usage(raw):
    """Normalize the endpoint response. Pure."""
    def window(key):
        w = raw.get(key)
        if isinstance(w, dict) and w.get("utilization") is not None:
            return {"pct": float(w["utilization"]), "resets_at": w.get("resets_at", "")}
        return None
    return {
        "five_hour": window("five_hour"),
        "seven_day": window("seven_day"),
        "sonnet": window("seven_day_sonnet"),
    }


def usage_bar(pct, width):
    """Block bar (█ filled / ░ empty). Pure."""
    width = max(1, width)
    filled = max(0, min(width, int(round(pct / 100 * width))))
    return "█" * filled + "░" * (width - filled)


def usage_color(pct):
    """Color for a utilization band. Pure."""
    if pct >= 95:
        return "red"
    if pct >= 80:
        return "orange"
    if pct >= 60:
        return "yellow"
    return "green"


def human_reset(iso, now):
    """Time until reset: 'Xd' / 'XhYYm' / 'Ym' / 'now'. Pure (now is passed in, tz-aware)."""
    try:
        dt = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return ""
    if dt.tzinfo and now.tzinfo is None:
        now = now.replace(tzinfo=dt.tzinfo)
    secs = int((dt - now).total_seconds())
    if secs <= 0:
        return "now"
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d{hours}h" if hours else f"{days}d"
    if hours:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m"


def _http_usage(token):
    req = urllib.request.Request(USAGE_URL, headers={
        "Authorization": "Bearer " + token,
        "anthropic-beta": "oauth-2025-04-20",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("token expired — open Claude")
        raise RuntimeError(f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network: {exc.reason}")


def fetch_usage():
    """Current usage, cached for 5 min. Includes 'plan'. Raises RuntimeError on failure."""
    now = time.time()
    try:
        if now - os.stat(CACHE).st_mtime < CACHE_TTL:
            with open(CACHE) as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    creds = read_credentials()
    data = parse_usage(_http_usage(creds["token"]))
    data["plan"] = creds["plan"]
    try:
        with open(CACHE, "w") as f:
            json.dump(data, f)
    except OSError:
        pass
    return data
