"""GitHub Issues as a ticket source (via the `gh` CLI)."""
import json
import subprocess

FIELDS = "number,title,repository,state,url"
# GitHub issues have no workflow status like Jira or an MCP tracker; the board's "By Status"
# collapses to a single "Open" bucket.
# ponytail: single status; map from a `status:*` label or Projects v2 field if you need columns.
STATUS = "Open"


def to_issue(raw):
    """A `gh search issues` item → the board's ticket contract. Pure."""
    repo = (raw.get("repository") or {}).get("name", "?")
    return {
        "key": f"{repo}#{raw.get('number', '?')}",
        "status": STATUS,
        "summary": raw.get("title", ""),
        "project": repo,
        "url": raw.get("url", ""),
    }


def matches_repos(raw, repos):
    """True if the issue's repo is in `repos` (owner or owner/repo), or repos is empty. Pure."""
    if not repos:
        return True
    repo = raw.get("repository") or {}
    full = repo.get("nameWithOwner") or repo.get("name") or ""
    owner = full.split("/")[0] if "/" in full else ""
    return full in repos or owner in repos


def fetch(cfg):
    args = ["gh", "search", "issues", "--assignee=@me", "--state=open",
            "--limit", "100", "--json", FIELDS]
    out = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "gh failed")
    repos = (cfg or {}).get("repos") or []
    items = json.loads(out.stdout or "null") or []
    return [to_issue(it) for it in items if matches_repos(it, repos)]
