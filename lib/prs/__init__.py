"""Pluggable PR/MR source. Each backend exposes fetch(cfg) -> normalized PR dicts.

Normalized PR: {number, title, url, _repo, _role, _category, _key, _review, _ci}
  _role     "author" | "reviewer"
  _category "review" | "changes" | "merged"
  _review   glyph string for review state (may be "")
  _ci        glyph string for CI state (may be "")"""


def fetch(cfg):
    """PRs where I'm author or reviewer, from the configured host. Raises RuntimeError on failure."""
    source = (cfg or {}).get("source", "github")
    if source == "github":
        from lib.prs import github
        return github.fetch(cfg)
    raise RuntimeError(f"PR host '{source}' is not implemented yet")
