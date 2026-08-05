"""GitHub — PRs where I am author OR reviewer, categorized (merged/changes/review) + CI status."""
import json
import re
import subprocess

GH_FIELDS = "number,title,repository,author,url,state"
# max 60 PRs per list (author / reviewer) — beyond that it truncates silently
SEARCH_AUTHOR = ["gh", "search", "prs", "--author=@me", "--limit", "60", "--json", GH_FIELDS]
SEARCH_REVIEWER = ["gh", "search", "prs", "--review-requested=@me", "--state=open",
                   "--limit", "60", "--json", GH_FIELDS]
KEY_RE = re.compile(r"\b[A-Z]{2,}-\d+\b")  # any ticket key like ABC-123


def matches_repos(pr, repos):
    """True if the PR's repo is in `repos` (owner or owner/repo), or repos is empty. Pure."""
    if not repos:
        return True
    full = (pr.get("repository") or {}).get("nameWithOwner", "")
    owner = full.split("/")[0] if "/" in full else ""
    return full in repos or owner in repos


def _gh_json(args):
    out = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "gh failed")
    return json.loads(out.stdout or "null")


def ticket_key(title):
    """Ticket key found in a PR title (e.g. 'ABC-428'), or None. Pure."""
    m = KEY_RE.search(title or "")
    return m.group(0) if m else None


def categorize_pr(pr):
    """'merged' | 'changes' | 'review' | None (closed without merge). Pure."""
    state = (pr.get("state") or "").lower()
    if state == "merged":
        return "merged"
    if state != "open":
        return None
    status = pr.get("_status") or {}
    if (status.get("reviewDecision") or "").upper() == "CHANGES_REQUESTED":
        return "changes"
    return "review"


def fetch_prs(role="both", repos=None):
    """PRs where I am author OR reviewer (deduped by repo+number). reviewDecision only for open ones.
    `role`: 'author' | 'reviewer' | 'both'. `repos`: limit to owner/owner-repo (empty = all).
    Every PR carries _role, _status, _category, _key. Closed-without-merge is dropped."""
    repos = repos or []
    authored = (_gh_json(SEARCH_AUTHOR) or []) if role in ("author", "both") else []
    for pr in authored:
        pr["_role"] = "author"
    reviewing = (_gh_json(SEARCH_REVIEWER) or []) if role in ("reviewer", "both") else []
    for pr in reviewing:
        pr["_role"] = "reviewer"
    seen = set()
    out = []
    for pr in authored + reviewing:
        if not matches_repos(pr, repos):
            continue
        key = (pr["repository"]["nameWithOwner"], pr["number"])
        if key in seen:
            continue
        seen.add(key)
        pr["_status"] = None
        if (pr.get("state") or "").lower() == "open":
            try:
                pr["_status"] = _gh_json([
                    "gh", "pr", "view", str(pr["number"]), "--repo", key[0],
                    "--json", "reviewDecision,isDraft,statusCheckRollup,state"])
            except Exception:
                pr["_status"] = None
        pr["_category"] = categorize_pr(pr)
        pr["_key"] = ticket_key(pr["title"])
        if pr["_category"]:
            out.append(pr)
    return out


def review_glyph(status):
    if status is None:
        return ""
    if status.get("isDraft"):
        return "📝 draft"
    decision = (status.get("reviewDecision") or "").upper()
    if decision == "APPROVED":
        return "✓ approved"
    if decision == "CHANGES_REQUESTED":
        return "⏳ changes"
    return "● review"


def ci_glyph(status):
    if not status:
        return ""
    rollup = status.get("statusCheckRollup") or []
    if not rollup:
        return ""
    states = [(c.get("conclusion") or c.get("status") or c.get("state") or "").upper()
              for c in rollup]
    if any(s in ("FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED") for s in states):
        return "🔴 CI"
    if any(s in ("PENDING", "IN_PROGRESS", "QUEUED", "EXPECTED", "WAITING") for s in states):
        return "🟡 CI"
    return "🟢 CI"
