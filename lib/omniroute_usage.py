"""OmniRoute provider usage — reads from local SQLite quota_snapshots."""
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


def get_latest_quota_snapshots() -> dict[str, dict[str, Any]]:
    """Get latest quota snapshot per provider/connection/window_key."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT qs.* FROM quota_snapshots qs
            INNER JOIN (
                SELECT provider, connection_id, window_key, MAX(created_at) as max_created
                FROM quota_snapshots
                GROUP BY provider, connection_id, window_key
            ) latest ON qs.provider = latest.provider
                AND qs.connection_id = latest.connection_id
                AND qs.window_key = latest.window_key
                AND qs.created_at = latest.max_created
        """).fetchall()
        # Organize by provider -> connection_id -> window_key
        result = {}
        for r in rows:
            d = dict(r)
            provider = d["provider"]
            conn_id = d["connection_id"]
            if provider not in result:
                result[provider] = {}
            if conn_id not in result[provider]:
                result[provider][conn_id] = {}
            result[provider][conn_id][d["window_key"]] = d
        return result
    finally:
        conn.close()


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
    quota_snapshots = get_latest_quota_snapshots()
    result = {"connections": [], "fetched_at": datetime.now(timezone.utc).isoformat()}

    for conn in connections:
        provider = conn["provider"]
        conn_id = conn["id"]
        snapshots = quota_snapshots.get(provider, {}).get(conn_id, {})

        usage_data = {
            "provider": provider,
            "name": conn.get("name") or provider,
            "email": conn.get("email") or "",
            "windows": {}
        }

        # Add quota data for each window (5h, 7d, etc.)
        for window_key, snap in snapshots.items():
            usage_data["windows"][window_key] = {
                "remaining_pct": snap.get("remaining_percentage"),
                "is_exhausted": bool(snap.get("is_exhausted")),
                "next_reset_at": snap.get("next_reset_at"),
            }

        result["connections"].append(usage_data)

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