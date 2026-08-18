"""OmniRoute provider usage — reads from local SQLite and calls provider usage APIs."""
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, ".omniroute", "runtime", "node_modules"))

DB_PATH = os.path.expanduser("~/.omniroute/storage.sqlite")
CACHE_PATH = "/tmp/codepit-omniroute-usage.json"
CACHE_TTL = 300  # 5 min


def get_active_connections() -> list[dict[str, Any]]:
    """Fetch active provider connections from OmniRoute SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT id, provider, name, email, access_token, api_key, provider_specific_data, project_id
            FROM provider_connections
            WHERE is_active = 1
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


USAGE_FETCHER_PROVIDERS = {
    "github", "antigravity", "agy", "claude", "codex", "cursor", "kiro", "amazon-q",
    "kimi-coding", "kimi-coding-apikey", "qoder", "glm", "glm-cn", "zai", "glmt",
    "opencode-go", "ollama-cloud", "minimax", "minimax-cn", "crof", "bailian-coding-plan",
    "nanogpt", "deepseek", "opencode", "opencode-zen", "xiaomi-mimo", "xai", "xai-oauth",
    "xao", "vertex", "vertex-partner", "codebuddy-cn", "openrouter", "promptql", "pql",
    "hyperagent", "ha", "firecrawl", "adobe-firefly", "firefly",
}


def fetch_usage_for_connection(conn_data: dict[str, Any]) -> dict[str, Any] | None:
    """Fetch usage for a single connection using OmniRoute's usage module."""
    provider = conn_data["provider"]
    if provider not in USAGE_FETCHER_PROVIDERS:
        return {"provider": provider, "error": f"No usage fetcher for {provider}"}

    return {"provider": provider, "connection_id": conn_data["id"], "needs_http": True}


def fetch_usage_via_gateway() -> dict[str, Any]:
    """Fetch usage by calling the OmniRoute gateway API."""
    import urllib.error
    import urllib.request

    url = "http://localhost:20128/api/usage"
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer omniroute",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {"error": "auth_required"}
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"network: {e.reason}"}


def fetch_usage():
    """Main fetch function — returns usage data for all active connections."""
    # Check cache first
    try:
        if time.time() - os.stat(CACHE_PATH).st_mtime < CACHE_TTL:
            with open(CACHE_PATH) as f:
                return json.load(f)
    except (OSError, ValueError):
        pass

    connections = get_active_connections()
    result = {"connections": [], "fetched_at": datetime.now(timezone.utc).isoformat()}

    for conn in connections:
        usage = fetch_usage_for_connection(conn)
        if usage:
            usage["name"] = conn.get("name") or conn["provider"]
            usage["email"] = conn.get("email") or ""
            result["connections"].append(usage)

    gateway_usage = fetch_usage_via_gateway()
    if "error" not in gateway_usage:
        result["gateway"] = gateway_usage

    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(result, f)
    except OSError:
        pass

    return result


def usage_bar(pct: float, width: int = 10) -> str:
    """Block bar (█ filled / ░ empty). Pure."""
    width = max(1, width)
    filled = max(0, min(width, int(round(pct / 100 * width))))
    return "█" * filled + "░" * (width - filled)


def usage_color(pct: float) -> str:
    """Color for a utilization band. Pure."""
    if pct >= 95:
        return "red"
    if pct >= 80:
        return "orange"
    if pct >= 60:
        return "yellow"
    return "green"


def human_reset(iso: str | None, now: datetime) -> str:
    """Time until reset: 'Xd' / 'XhYYm' / 'Ym' / 'now'. Pure."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
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