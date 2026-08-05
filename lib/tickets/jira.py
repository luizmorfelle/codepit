"""Jira Cloud as a ticket source (REST API v3, Basic auth email:api_token).

Uses the current /rest/api/3/search/jql endpoint (the classic /search was deprecated).
Site URL + projects are non-secret (config.json); email + token are secrets (.env)."""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_PATH = "/rest/api/3/search/jql"
FIELDS = "summary,status,project"


def build_jql(projects):
    """JQL for my open issues, newest first, optionally scoped to projects. Pure."""
    jql = "assignee = currentUser() AND statusCategory != Done"
    if projects:
        joined = ", ".join(f'"{p}"' for p in projects)
        jql += f" AND project in ({joined})"
    return jql + " ORDER BY updated DESC"


def parse_issue(raw, site=""):
    """A Jira issue → the board's ticket contract. Pure. `site` builds the browse URL."""
    f = raw.get("fields") or {}
    key = raw.get("key", "?")
    return {
        "key": key,
        "status": (f.get("status") or {}).get("name", "?"),
        "summary": f.get("summary", ""),
        "project": (f.get("project") or {}).get("key", ""),
        "url": f"{site}/browse/{key}" if site else "",
    }


def auth_header(email, token):
    """Basic auth header value for email:api_token. Pure."""
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


def fetch(cfg):
    cfg = cfg or {}
    site = (cfg.get("site") or os.environ.get("JIRA_SITE", "")).strip().rstrip("/")
    email = os.environ.get("JIRA_EMAIL", "").strip()
    token = os.environ.get("JIRA_TOKEN", "").strip()
    if not (site and email and token):
        raise RuntimeError("set JIRA_SITE (or tickets.site) + JIRA_EMAIL + JIRA_TOKEN in .env")
    query = urllib.parse.urlencode({
        "jql": build_jql(cfg.get("projects") or []),
        "fields": FIELDS,
        "maxResults": 100,
    })
    req = urllib.request.Request(f"{site}{API_PATH}?{query}", headers={
        "Authorization": auth_header(email, token),
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("401 — invalid JIRA_EMAIL/JIRA_TOKEN")
        raise RuntimeError(f"HTTP {exc.code} — {exc.reason}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network: {exc.reason}") from exc
    return [parse_issue(it, site) for it in data.get("issues", [])]
