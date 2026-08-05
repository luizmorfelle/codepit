"""Tickets from an MCP server (JSON-RPC over streamable HTTP) — my open tickets.

Talks the MCP protocol directly (no SDK): initialize → notifications/initialized →
tools/call(search_tickets), responses arriving as SSE (event: message / data: {...}).
The server endpoint and key come from the environment (MCP_URL / MCP_KEY);
nothing host-specific is baked in."""
import json
import os
import re
import urllib.error
import urllib.request

DEFAULT_PROJECTS = ()  # empty = show every project
PROTOCOL_VERSION = "2025-06-18"
DONE_STATUS = "Done"

# Trackers tend to return PascalCase statuses; map them to the labels the board
# already knows (order and color live in widgets/board.py).
STATUS_LABELS = {
    "Todo": "To Do",
    "InAnalysis": "In Analysis",
    "InDevelopment": "In Development",
    "InProgress": "In Progress",
    "InReview": "Review",
    "OpenPR": "Pull Request",
    "Done": "Done",
}


def _config():
    url = os.environ.get("MCP_URL", "").strip()
    key = os.environ.get("MCP_KEY", "").strip()
    assignee = os.environ.get("MCP_ASSIGNEE_ID", "").strip()
    if not url:
        raise RuntimeError("set MCP_URL (the MCP server endpoint) in .env")
    if not key:
        raise RuntimeError("set MCP_KEY in .env")
    if not assignee.isdigit():
        raise RuntimeError("set MCP_ASSIGNEE_ID (numeric id) in .env")
    raw = os.environ.get("MCP_PROJECTS", "").strip()
    projects = {p.strip().upper() for p in raw.split(",") if p.strip()} or set(DEFAULT_PROJECTS)
    return url, key, int(assignee), projects


def friendly_status(name):
    """Friendly label for a tracker status. Pure."""
    if name in STATUS_LABELS:
        return STATUS_LABELS[name]
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name or "")
    return spaced or "?"


def parse_items(items, projects):
    """search_tickets items → the board's contract. Filters by project, drops Done. Pure."""
    out = []
    for it in items:
        proj = (it.get("projectKey") or "").upper()
        status = it.get("statusName") or ""
        if projects and proj not in projects:
            continue
        if status == DONE_STATUS:
            continue
        out.append({
            "key": it.get("issueKey", "?"),
            "status": friendly_status(status),
            "summary": it.get("title", ""),
            "project": proj,
            "url": "",  # ponytail: no per-ticket URL in the MCP payload; fill it if yours has one
        })
    return out


def _parse_sse(body):
    """Extract and concatenate the `data:` payloads of an SSE response → JSON dict. Pure."""
    chunks = [ln[5:].lstrip() for ln in body.splitlines() if ln.startswith("data:")]
    if not chunks:
        raise RuntimeError("MCP response has no SSE body")
    return json.loads("".join(chunks))


def _post(url, key, payload, session_id=None):
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=30)


def _mcp_search_tickets(url, key, assignee_id):
    """MCP handshake + tools/call(search_tickets); returns the raw items list."""
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                       "clientInfo": {"name": "codepit", "version": "1.0"}}}
    with _post(url, key, init) as resp:
        session_id = resp.headers.get("Mcp-Session-Id")
        _parse_sse(resp.read().decode())  # validates the initialize response
    try:
        with _post(url, key, {"jsonrpc": "2.0", "method": "notifications/initialized"},
                   session_id) as resp:
            resp.read()
    except urllib.error.HTTPError:
        pass  # the notify is best-effort; some servers answer 4xx and carry on
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "search_tickets",
                       "arguments": {"assigneeId": assignee_id, "perPage": 200}}}
    with _post(url, key, call, session_id) as resp:
        msg = _parse_sse(resp.read().decode())
    if "error" in msg:
        err = msg["error"]
        raise RuntimeError(f"MCP: {err.get('message', err)}")
    content = (msg.get("result") or {}).get("content") or []
    text = next((c.get("text") for c in content if c.get("type") == "text"), None)
    if not text:
        raise RuntimeError("search_tickets returned no content")
    return json.loads(text).get("items", [])


def fetch_issues():
    """My open tickets on the MCP server. Raises RuntimeError with a clear message on failure."""
    url, key, assignee_id, projects = _config()
    try:
        items = _mcp_search_tickets(url, key, assignee_id)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("401 — invalid or expired MCP_KEY")
        raise RuntimeError(f"HTTP {exc.code} — {exc.reason}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network: {exc.reason}") from exc
    return parse_items(items, projects)
