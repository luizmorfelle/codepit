"""GitHub PRs as a PR source — normalizes github_api output to the neutral contract."""
from lib import github_api


def normalize(pr):
    """A github_api PR → the neutral PR contract. Pure."""
    category = pr.get("_category")
    return {
        "number": pr["number"],
        "title": pr["title"],
        "url": pr.get("url", ""),
        "_repo": (pr.get("repository") or {}).get("name", "?"),
        "_role": pr.get("_role", ""),
        "_category": category,
        "_key": pr.get("_key"),
        "_review": github_api.review_glyph(pr.get("_status")) if category != "merged" else "",
        "_ci": github_api.ci_glyph(pr.get("_status")),
    }


def fetch(cfg):
    prs = github_api.fetch_prs(role=(cfg or {}).get("role", "both"),
                               repos=(cfg or {}).get("repos") or [])
    return [normalize(pr) for pr in prs]
